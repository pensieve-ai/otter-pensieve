# Otter Pensieve Local - Standalone Script

A simplified standalone Python script for processing otter-formatted Jupyter notebooks locally. This script extracts questions, renders PDFs, and creates metadata without any server submission functionality.

## Features

- Parse otter-formatted Jupyter notebooks
- Extract questions marked with `<!-- BEGIN QUESTION -->` and `<!-- END QUESTION -->`
- Slice notebooks by question
- Render notebooks to PDF
- Extract answers from cells tagged with `otter_answer_cell`
- Create comprehensive metadata.json with all processing information

## Requirements

```bash
pip install nbformat nbconvert pypdf pydantic strip-ansi
```

Optional (for better PDF rendering with otter templates):

```bash
pip install otter-grader
```

## Quick Start

```bash
# Basic usage - creates notebook.pdf and notebook_metadata.json
python otter_pensieve_local.py notebook.ipynb

# With custom output paths
python otter_pensieve_local.py notebook.ipynb -o output.pdf -m metadata.json

# With verbose output
python otter_pensieve_local.py notebook.ipynb -v
```

## Example Usage

```python
import otter_pensieve_local as opl

# Process a notebook
result = opl.process_notebook(
    notebook_path="Exercise 2.ipynb",
    output_pdf_path="exercise2.pdf",           # Optional, defaults to Exercise 2.pdf
    output_metadata_path="exercise2_meta.json", # Optional, defaults to Exercise 2_metadata.json
    verbose=True                               # Optional, prints progress
)

# Result contains:
# - result['pdf']: PDF bytes
# - result['pdf_path']: Path where PDF was saved
# - result['metadata_path']: Path where metadata was saved
# - result['questions']: List of parsed questions
# - result['page_indices']: Page matching for each question
# - result['answers']: Extracted answers
```

## Metadata Format

The generated metadata.json contains:

```json
{
  "notebook_path": "/absolute/path/to/notebook.ipynb",
  "pdf_path": "/absolute/path/to/output.pdf",
  "num_questions": 3,
  "questions": [
    {
      "index": 0,
      "begin": {"cell_index": 4, "line_index": 0},
      "end": {"cell_index": 6, "line_index": 1}
    }
  ],
  "page_indices": [[0, 1], [2], [3, 4]],
  "answers": [
    {
      "question_index": 0,
      "num_parts": 1,
      "parts": [
        {
          "content_type": "text",
          "content": "Answer content here..."
        }
      ]
    }
  ]
}
```

## Notebook Format

The script automatically detects and supports two question formats:

### Format 1: HTML Comments (Original Otter Format)

Questions marked with HTML comments:

```markdown
<!-- BEGIN QUESTION -->
## Question 1
Your question content here...
<!-- END QUESTION -->
```

### Format 2: Markdown Headers

Questions marked with headers using any number of `#` followed by Q and digits:

```markdown
# Q1

Your first question content here...

## Q2

Your second question content here...

### Q3 [Optional Points]

Questions can have any heading level and additional text after the number
```

### Answer Cells

For both formats, answer cells must be tagged with `otter_answer_cell`:

- In Jupyter: Add tag "otter_answer_cell" to the cell
- The cell metadata should contain: `{"tags": ["otter_answer_cell"]}`

## Examples

See `example_local.py` for complete working examples including:

- Basic processing
- Custom output paths
- Batch processing multiple notebooks
- Direct API usage

## Direct API Usage

You can also use individual functions:

```python
import nbformat
import otter_pensieve_local as opl

# Load notebook
with open("notebook.ipynb") as f:
    notebook = nbformat.read(f, as_version=4)

# Parse questions
parsed = opl.parse_notebook(notebook)

# Process each question
for question in parsed.questions:
    # Slice notebook
    slice_nb = opl.slice_notebook(notebook, question)

    # Render to PDF
    pdf_bytes = opl.render_notebook(slice_nb)

    # Extract answer
    answer = opl.extract_answer(slice_nb)
```

## Troubleshooting

1. **"No module named 'nbformat'"**: Install requirements with `pip install -r requirements.txt`

2. **PDF rendering issues**:
   - Make sure you have `pyppeteer` chromium installed: `pyppeteer-install`
   - Or install otter-grader for better templates: `pip install otter-grader`

3. **No questions found**: Check that your notebook has proper `<!-- BEGIN QUESTION -->` and `<!-- END QUESTION -->` markers

## License

Same as otter-pensieve library - MIT License
