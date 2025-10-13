# Fast Processing Modes - No PDF Rendering Required

## TL;DR

**Want to grade student notebooks quickly?** Use JSON-only mode - it's **10-20x faster**!

```bash
# Generate JSON + CSV for all students (FAST!)
python3 yi.py --json-only --csv answers.csv

# Then open answers.csv in Excel/Google Sheets to review all answers
```

## New Features

### 1. JSON-Only Mode (⚡ 10-20x Faster)

Generate all the metadata and answers **WITHOUT** rendering PDFs:

```bash
# Batch process all notebooks (JSON only)
python3 yi.py --json-only

# Single notebook
python3 generate_json.py notebook.ipynb -o output.json
```

**Why is this faster?**

- PDF rendering takes ~5-10 seconds per notebook
- JSON extraction takes ~0.5-1 second per notebook
- For 100 notebooks: **8-17 minutes** instead of **83-167 minutes**!

### 2. CSV Export

Get all student answers in one spreadsheet:

```bash
# Generate CSV from existing JSON files
python3 generate_csv.py /path/to/_rendered -o answers.csv

# Or combine with JSON-only mode
python3 yi.py --json-only --csv answers.csv
```

CSV format:

```
User Email          | Question 1    | Question 2    | Question 3
student1@email.com  | answer text   | answer text   | answer text
student2@email.com  | answer text   | answer text   | answer text
```

## Available Scripts

| Script | Purpose | Speed |
|--------|---------|-------|
| `yi.py` | Batch process notebooks | Various modes |
| `yi.py --json-only` | Batch JSON only (no PDFs) | ⚡ Fast! |
| `yi.py --csv-only` | Generate CSV from existing JSON | ⚡⚡ Instant! |
| `generate_json.py` | Single notebook JSON (no PDF) | ⚡ Fast! |
| `generate_csv.py` | Standalone CSV generator | ⚡⚡ Instant! |
| `generate_csv.sh` | Bash wrapper for CSV | ⚡⚡ Instant! |

## Processing Modes Comparison

| Mode | Command | Output | Speed per notebook |
|------|---------|--------|-------------------|
| **Full** | `python3 yi.py` | PDF + JSON | ~5-10 seconds |
| **JSON-only** | `python3 yi.py --json-only` | JSON only | ~0.5-1 second ⚡ |
| **CSV-only** | `python3 yi.py --csv-only --csv out.csv` | CSV from existing | ~instant ⚡⚡ |
| **JSON+CSV** | `python3 yi.py --json-only --csv out.csv` | JSON + CSV | ~0.5-1 second ⚡ |

## Use Cases

### Use Case 1: Quick Grading

**Goal:** Review all student answers quickly

```bash
python3 yi.py --json-only --csv answers.csv
# Open answers.csv in Excel/Google Sheets
```

✅ Fast, easy to grade, no PDFs needed

### Use Case 2: Formal Submission

**Goal:** Need PDFs for archival

```bash
python3 yi.py --csv answers.csv
```

✅ Get PDFs, JSON, and CSV all at once

### Use Case 3: Re-generate CSV

**Goal:** Already have JSON, need new CSV

```bash
python3 generate_csv.py /path/to/_rendered -o new_answers.csv
```

✅ Instant, no re-processing

### Use Case 4: Single Notebook

**Goal:** Quick test/check one notebook

```bash
python3 generate_json.py notebook.ipynb -o output.json
```

✅ Fast, simple, no dependencies

## Examples

### Process 100 student notebooks (JSON-only + CSV)

```bash
python3 yi.py \
  --base-dir "/path/to/submissions" \
  --json-only \
  --csv answers.csv \
  --jobs 20
```

**Time:** ~1-2 minutes for 100 notebooks
**Output:** 100 JSON files + 1 CSV file

### Process 100 student notebooks (Full PDF+JSON+CSV)

```bash
python3 yi.py \
  --base-dir "/path/to/submissions" \
  --csv answers.csv \
  --jobs 20
```

**Time:** ~10-20 minutes for 100 notebooks
**Output:** 100 PDFs + 100 JSON files + 1 CSV file

## Tips

1. **Start with JSON-only mode** to quickly check if everything works
2. **Use CSV export** for easy grading in spreadsheets
3. **Only generate PDFs** if you actually need them
4. **Increase --jobs** for faster parallel processing (default: 10)
5. **Scripts are resumable** - if interrupted, re-run and it will skip already-processed files

## See Also

- `CSV_USAGE.md` - Detailed documentation on CSV export and all modes
- `README.md` - Main project documentation
- `yi.py --help` - Full command-line options

## Questions?

**Q: Do I need PDFs?**
A: Only if you're submitting to a system that requires them. For grading, CSV is often enough!

**Q: Can I generate PDFs later?**
A: No - you need to re-process the notebooks. So decide upfront if you need PDFs.

**Q: What's in the JSON files?**
A: All notebook content: questions, code, outputs, markdown - everything except the formatted PDF.

**Q: Can I customize the CSV format?**
A: Yes! Edit `generate_csv.py` or `yi.py`'s `generate_csv()` function.
