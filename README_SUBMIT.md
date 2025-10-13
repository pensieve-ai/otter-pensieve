# Submission Workflow

This document explains how to use the batch submission workflow to submit rendered notebooks to the Pensieve API.

## Workflow Overview

1. **Render notebooks** → Creates PDFs and metadata from Jupyter notebooks
2. **Submit to Pensieve** → Uploads PDFs with page matchings and answers

## Step 1: Render Notebooks

Use `yi.sh` to batch render all notebooks:

```bash
./yi.sh
```

This will:

- Process all `.ipynb` files in the base directory
- Create PDFs and metadata JSON files in the `_rendered` subdirectory
- Files are named: `{email}_{notebook_name}.pdf` and `{email}_{notebook_name}.json`
- Skip already processed files (resumable)

### Configuration (yi.sh)

Edit these variables in `yi.sh`:

- `BASE_DIR`: Directory containing student submissions
- `WORKING_DIR`: otter-pensieve working directory

## Step 2: Submit to Pensieve

After rendering, submit to the Pensieve API:

```bash
./submit_yi.sh
```

### Configuration (submit_yi.sh)

**Required:** Edit these variables in `submit_yi.sh`:

- `CLAZZ_ID`: Your class ID (e.g., `data100_su25`)
- `ASSIGNMENT_ID`: Assignment ID from Pensieve URL (`/my-assignments/{assignment_id}`)
- `BASE_DIR`: Same directory as in yi.sh
- `API_KEY`: API key for authentication (default provided)
- `JOBS`: Number of parallel submissions (default: 5)

### What Gets Submitted

For each notebook, the script submits:

1. **PDF file** - The rendered PDF
2. **Page matchings** - Page indices for each question
3. **Answers** - Extracted cell content, code, and outputs

All data is read from the metadata JSON files created in Step 1.

## Error Handling

- All submission errors are logged to `error.txt`
- The script continues processing even if some submissions fail
- Check `error.txt` after completion to see any issues

## Direct Python Usage

You can also call the Python scripts directly:

### Rendering

```bash
poetry run python yi.py \
    --base-dir "/path/to/submissions" \
    --working-dir "/path/to/otter-pensieve" \
    --jobs 10 \
    --verbose
```

### Submission

```bash
poetry run python submit_yi.py \
    --base-dir "/path/to/submissions" \
    --clazz-id "data100_su25" \
    --assignment-id "439f814c-4ab5-47ad-94a2-14dde836e4b1" \
    --api-key "sk_live_..." \
    --jobs 5 \
    --verbose
```

## API Endpoints

The submission script uses these Pensieve API endpoints:

1. `POST /create-submission` - Create submission with PDF
2. `POST /create-submission/page-matchings` - Set page indices
3. `POST /create-submission/answers` - Set extracted answers

## Notes

- Student emails are extracted from the directory structure
- Email format conversion: `user_email_com` → `user@email.com`
- The script processes all notebooks in the `_rendered` directory
- Failed submissions are logged but don't stop the process
