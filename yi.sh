#!/bin/bash

# Base directories containing submissions
BASE_DIRS=(
    "/Users/qria/Downloads/midterm"
)

# Working directory for otter-pensieve
WORKING_DIR="/Users/qria/otter-pensieve"

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

total_processed=0
total_failed=0

for BASE_DIR in "${BASE_DIRS[@]}"; do
    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Processing: $BASE_DIR${NC}"
    echo -e "${YELLOW}========================================${NC}"

    # Output CSV file (set to empty string to disable CSV generation)
    OUTPUT_CSV="$BASE_DIR/_rendered/answers.csv"

    processed=0
    failed=0

    # Find all .ipynb files matching the pattern
    find "$BASE_DIR" -type f -name "*.ipynb" -not -path "*/.ipynb_checkpoints/*" | while read -r notebook_path; do
        # Get the relative path from base directory
        rel_path="${notebook_path#$BASE_DIR/}"

        # Extract user email (first directory)
        user_email=$(echo "$rel_path" | cut -d'/' -f1)

        # Extract notebook filename (e.g., "Exercise 1.ipynb")
        notebook_filename=$(basename "$notebook_path")
        notebook_name="${notebook_filename%.ipynb}"

        # Skip if it's already a rendered directory
        if [[ "$user_email" == *"_rendered" ]]; then
            continue
        fi

        # Create output directory if it doesn't exist
        output_dir="$BASE_DIR/_rendered"
        mkdir -p "$output_dir"

        # Sanitize email for filename (replace @ and . with _)
        sanitized_email=$(echo "$user_email" | sed 's/@/_/g' | sed 's/\./_/g')

        # Define output paths
        output_pdf="$output_dir/${sanitized_email}_${notebook_name}.pdf"
        output_json="$output_dir/${sanitized_email}_${notebook_name}.json"

        echo -e "${YELLOW}Processing:${NC} $user_email / $notebook_name"
        echo "  Input:  $notebook_path"
        echo "  Output: $output_pdf"
        echo "         $output_json"

        # Change to working directory and run the command
        cd "$WORKING_DIR" || exit 1

        # Run the poetry command
        echo "  Command: poetry run python otter_pensieve_local.py \"$notebook_path\" -o \"$output_pdf\" -m \"$output_json\""
        if poetry run python otter_pensieve_local.py "$notebook_path" -o "$output_pdf" -m "$output_json" 2>/dev/null; then
            echo -e "${GREEN}  ✓ Successfully rendered${NC}"
            ((processed++))
        else
            echo -e "${RED}  ✗ Failed to render${NC}"
            ((failed++))
        fi

        echo "----------------------------------------"
    done

    echo ""
    echo -e "Rendering complete for ${YELLOW}$BASE_DIR${NC}"
    echo -e "${GREEN}Successfully processed: $processed notebooks${NC}"
    if [ $failed -gt 0 ]; then
        echo -e "${RED}Failed: $failed notebooks${NC}"
    fi

    ((total_processed += processed))
    ((total_failed += failed))

    # Generate CSV if OUTPUT_CSV is set
    if [ -n "$OUTPUT_CSV" ]; then
        echo ""
        echo "Generating CSV file..."
        cd "$WORKING_DIR" || exit 1

        python3 - "$BASE_DIR/_rendered" "$OUTPUT_CSV" <<'PYTHON'
import sys
import json
import csv
from pathlib import Path

def extract_text_from_answer(question_data):
    """Extract text content from a question's formatted cells."""
    formatted_cells = question_data.get("formatted_cells", [])

    # Collect all text content from all parts
    text_parts = []
    for cell in formatted_cells:
        for part in cell.get("parts", []):
            if part.get("content_type") == "text":
                text_parts.append(part.get("content", ""))
            elif part.get("content_type") == "png":
                text_parts.append("[PNG image]")

    return "\n".join(text_parts).strip()

output_dir = Path(sys.argv[1])
csv_path = Path(sys.argv[2])

# Find all JSON files
json_files = list(output_dir.glob("*.json"))

if not json_files:
    print("No JSON files found.")
    sys.exit(0)

# Collect data
student_data = {}
max_questions = 0

for json_file in json_files:
    try:
        with open(json_file, "r") as f:
            metadata = json.load(f)

        # Extract email from filename
        filename = json_file.stem
        parts = filename.rsplit("_", 1)
        if len(parts) >= 1:
            sanitized_email = parts[0]
            email = sanitized_email.replace("_", "@", 1).replace("_", ".")
        else:
            email = filename

        # Extract answers
        questions = metadata.get("questions", [])
        max_questions = max(max_questions, len(questions))

        if email not in student_data:
            student_data[email] = {}

        for i, question in enumerate(questions):
            answer_text = extract_text_from_answer(question)
            student_data[email][i] = answer_text

    except Exception as e:
        print(f"Warning: Failed to process {json_file.name}: {e}")
        continue

if not student_data:
    print("No valid data found.")
    sys.exit(0)

# Write CSV
with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
    headers = ["User Email"] + [f"Question {i+1}" for i in range(max_questions)]
    writer = csv.writer(csvfile)
    writer.writerow(headers)

    for email in sorted(student_data.keys()):
        row = [email]
        for i in range(max_questions):
            answer = student_data[email].get(i, "")
            row.append(answer)
        writer.writerow(row)

print(f"✓ CSV file created: {csv_path}")
print(f"  Students: {len(student_data)}")
print(f"  Questions: {max_questions}")
PYTHON
    fi
done

echo ""
echo "========================================"
echo "All batches complete!"
echo -e "${GREEN}Total processed: $total_processed notebooks${NC}"
if [ $total_failed -gt 0 ]; then
    echo -e "${RED}Total failed: $total_failed notebooks${NC}"
fi
