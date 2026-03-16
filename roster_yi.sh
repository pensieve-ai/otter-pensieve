#!/bin/bash

BASE_DIR="/Users/qria/Downloads/HW1-1"

OUTPUT_CSV="$BASE_DIR/_rendered/roster.csv"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "Generating roster CSV from parsed JSON files..."
echo "Base directory: $BASE_DIR/_rendered"
echo "Output: $OUTPUT_CSV"
echo "----------------------------------------"

python3 - "$BASE_DIR/_rendered" "$OUTPUT_CSV" <<'PYTHON'
import sys
import json
import csv
from pathlib import Path

def extract_answer(question_data):
    """Extract the Out: value from the first code cell of a question."""
    import re
    for cell in question_data.get("formatted_cells", []):
        for part in cell.get("parts", []):
            content = part.get("content", "")
            if content.startswith("`Out:`"):
                m = re.search(r"```\w*\n(.*?)\n```", content, re.DOTALL)
                if m:
                    val = m.group(1).strip()
                    # strip surrounding quotes: 'foo' or "foo"
                    if len(val) >= 2 and val[0] in ("'", '"') and val[-1] == val[0]:
                        val = val[1:-1]
                    return val
    return ""

output_dir = Path(sys.argv[1])
csv_path = Path(sys.argv[2])

json_files = list(output_dir.glob("*.json"))

if not json_files:
    print("No JSON files found.")
    sys.exit(0)

rows = []

for json_file in json_files:
    try:
        with open(json_file, "r") as f:
            metadata = json.load(f)

        filename = json_file.stem
        sanitized_email = filename.rsplit("_", 1)[0]
        email = sanitized_email.replace("_", "@", 1).replace("_", ".")

        questions = metadata.get("questions", [])
        name = extract_answer(questions[0]) if len(questions) > 0 else ""
        sid = extract_answer(questions[1]) if len(questions) > 1 else ""

        rows.append((name, sid, email))
    except Exception as e:
        print(f"Warning: Failed to process {json_file.name}: {e}")
        continue

if not rows:
    print("No valid data found.")
    sys.exit(0)

rows.sort(key=lambda r: r[2])

with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Name", "SID", "Email"])
    writer.writerows(rows)

print(f"✓ Roster CSV created: {csv_path}")
print(f"  Students: {len(rows)}")
PYTHON

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Done!${NC}"
else
    echo -e "${RED}Failed to generate roster.${NC}"
fi
