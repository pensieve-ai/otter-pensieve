# CSV Export & JSON-Only Features

## Overview

The batch processing scripts now support:

1. **Exporting all student answers to CSV** for easy review and grading
2. **Generating JSON metadata WITHOUT rendering PDFs** (much faster!)

**Important**: You can generate both CSV and JSON files **without re-rendering PDFs**!

## CSV Format

The generated CSV file has the following structure:

```
User Email, Question 1, Question 2, Question 3, ...
student1@example.com, "answer text...", "answer text...", "answer text..."
student2@example.com, "answer text...", "answer text...", "answer text..."
```

- **Column 1**: Student email address
- **Columns 2+**: Answer content for each question (includes code, outputs, and markdown cells)

## Quick Start - Skip PDF Rendering

### Generate JSON Only (Fast!)

If you just need the metadata/answers WITHOUT PDFs:

```bash
# Option 1: Standalone script for single notebook
python3 generate_json.py notebook.ipynb -o output.json

# Option 2: Batch process all notebooks (JSON only, no PDFs!)
python3 yi.py --json-only

# Option 3: JSON-only + CSV in one command
python3 yi.py --json-only --csv answers.csv
```

⚡ **JSON-only mode is 10-20x faster** because it skips expensive PDF rendering!

### Generate CSV from Existing JSON

If you've already generated JSON files and want to create/update the CSV:

```bash
# Option 1: Standalone Python script (recommended)
python3 generate_csv.py /path/to/_rendered -o answers.csv

# Option 2: Standalone bash script
bash generate_csv.sh

# Option 3: Using yi.py with --csv-only flag
python3 yi.py --csv answers.csv --csv-only
```

These commands **do NOT re-render anything** - they only read existing JSON files!

## Usage

### Standalone JSON Generator (Fast - No PDF!)

**`generate_json.py`** - Generates JSON metadata from notebooks WITHOUT rendering PDFs.

```bash
# Single notebook
python3 generate_json.py notebook.ipynb -o output.json

# With verbose output
python3 generate_json.py notebook.ipynb -o output.json -v
```

**Arguments:**

- `notebook_path` (required): Path to the Jupyter notebook
- `-o, --output` (required): Output JSON file path
- `-v, --verbose`: Print progress information

**Speed comparison:**

- Full PDF+JSON: ~5-10 seconds per notebook
- JSON-only: ~0.5-1 second per notebook (10-20x faster!)

### Standalone CSV Generator (Recommended for CSV-only)

**`generate_csv.py`** - Generates CSV from existing JSON files without re-rendering PDFs.

```bash
# Basic usage
python3 generate_csv.py /path/to/_rendered -o answers.csv

# With verbose output
python3 generate_csv.py /path/to/_rendered -o answers.csv -v
```

**Arguments:**

- `json_dir` (required): Directory containing JSON metadata files
- `-o, --output` (required): Output CSV file path
- `-v, --verbose`: Print progress information

**Or use the bash wrapper:**

```bash
# Uses default paths
bash generate_csv.sh

# Custom paths
bash generate_csv.sh /path/to/_rendered /path/to/answers.csv
```

### Python Script (yi.py)

```bash
# Full mode: Generate PDFs + JSON + CSV
python3 yi.py --csv answers.csv

# JSON-only mode: Fast! No PDF rendering
python3 yi.py --json-only

# JSON-only + CSV in one go (recommended!)
python3 yi.py --json-only --csv answers.csv

# CSV-only: Generate CSV from existing JSON (no rendering)
python3 yi.py --csv answers.csv --csv-only

# Full command with all options
python3 yi.py \
  --base-dir "/path/to/submissions" \
  --working-dir "/path/to/otter-pensieve" \
  --jobs 10 \
  --json-only \
  --csv "/path/to/output/answers.csv"
```

**Arguments:**

- `--csv PATH`: Path where the CSV file should be saved (e.g., `answers.csv`)
- `--json-only`: Only generate JSON metadata (skip PDF rendering - 10-20x faster!)
- `--csv-only`: Only generate CSV from existing JSON files (skip all rendering)
- `--base-dir`: Directory containing student submissions (default: `/Users/qria/Downloads/HW 1 submissions`)
- `--working-dir`: otter-pensieve working directory (default: `/Users/qria/otter-pensieve`)
- `-j, --jobs`: Number of parallel jobs (default: 10)
- `-v, --verbose`: Enable verbose logging

**Mode comparison:**

- Full mode: PDF + JSON (~5-10s per notebook)
- JSON-only mode: JSON only (~0.5-1s per notebook) ⚡
- CSV-only mode: CSV from existing JSON (~instant)

### Bash Script (yi.sh)

The bash script automatically generates a CSV file by default. You can configure it by editing the script:

```bash
# Edit yi.sh and modify this line:
OUTPUT_CSV="$BASE_DIR/_rendered/answers.csv"

# To disable CSV generation, set it to empty:
OUTPUT_CSV=""
```

Then run:

```bash
bash yi.sh
```

## Answer Content

Each answer cell contains:

- **Markdown cells**: The raw markdown content
- **Code cells**: Both the code (`In:`) and output (`Out:`)
- **PNG images**: Marked as `[PNG image]`
- **Errors/Tracebacks**: Error messages and stack traces

## Example

If you have submissions from 3 students with 2 questions each, the CSV will look like:

```csv
User Email,Question 1,Question 2
alice@columbia.edu,"`In:`

```python
x = 5 + 3
print(x)
```

`Out:`

```text
8
```","`Markdown:`

The answer is 42."
bob@columbia.edu,"...",
"..."
charlie@columbia.edu,"...","..."
```

## Recommended Workflows

### Workflow 1: Fast grading with CSV (No PDFs needed)

```bash
# Step 1: Generate JSON only (fast!)
python3 yi.py --json-only --csv answers.csv

# Step 2: Review answers in CSV
# Open answers.csv in Excel/Google Sheets

# Optional: Regenerate CSV later if needed
python3 generate_csv.py /path/to/_rendered -o new_answers.csv
```

⚡ **This is 10-20x faster** than full PDF rendering!

### Workflow 2: Need PDFs for formal submission

```bash
# Step 1: Generate everything at once
python3 yi.py --csv answers.csv

# Step 2: Review answers in CSV
# Step 3: PDFs are available in _rendered/ directory
```

### Workflow 3: Already have PDFs, just need CSV

```bash
# Generate CSV from existing JSON files (instant)
python3 generate_csv.py /path/to/_rendered -o answers.csv
```

## Notes

- The CSV generation runs **after** all notebooks have been processed
- Existing JSON files in the `_rendered` directory are used as the source
- Student emails are extracted from the filename format: `{email}_{notebook_name}.json`
- Empty answers are represented as empty strings in the CSV
- Multi-line answers are properly escaped in CSV format
- JSON-only mode is much faster because PDF rendering is the slowest part (~90% of processing time)
