#!/usr/bin/env python3
"""
Generate CSV from existing JSON metadata files.
This script can be run independently without re-rendering PDFs.
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict


def extract_text_from_answer(question_data: Dict[str, Any]) -> str:
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

    # Join all parts with newlines
    return "\n".join(text_parts).strip()


def generate_csv(json_dir: Path, output_csv: Path, verbose: bool = False):
    """
    Generate a CSV file with all student answers from JSON files.

    Args:
        json_dir: Directory containing JSON metadata files
        output_csv: Path to save the CSV file
        verbose: Print progress information
    """
    if verbose:
        print(f"Searching for JSON files in: {json_dir}")

    # Find all JSON files in the directory
    json_files = list(json_dir.glob("*.json"))

    if not json_files:
        print(f"Error: No JSON files found in {json_dir}")
        sys.exit(1)

    if verbose:
        print(f"Found {len(json_files)} JSON files")

    # Collect data from all JSON files
    student_data = {}  # {email: {question_index: answer_text}}
    max_questions = 0
    failed_files = []

    for json_file in json_files:
        try:
            with open(json_file, "r") as f:
                metadata = json.load(f)

            # Extract student email from filename
            # Format: {sanitized_email}_{notebook_name}.json
            filename = json_file.stem

            # Remove notebook name suffix to get sanitized email
            # Handle cases like "student_email_Exercise_1" -> "student_email"
            parts = filename.rsplit("_", 1)
            if len(parts) >= 1:
                sanitized_email = parts[0]
                # Try to restore email format
                # First underscore becomes @, subsequent ones become .
                email = sanitized_email.replace("_", "@", 1).replace("_", ".")
            else:
                email = filename

            # Extract answers from questions
            questions = metadata.get("questions", [])
            max_questions = max(max_questions, len(questions))

            if email not in student_data:
                student_data[email] = {}

            for i, question in enumerate(questions):
                answer_text = extract_text_from_answer(question)
                student_data[email][i] = answer_text

            if verbose:
                print(f"  ✓ Processed: {email} ({len(questions)} questions)")

        except Exception as e:
            failed_files.append((json_file.name, str(e)))
            if verbose:
                print(f"  ✗ Failed: {json_file.name}: {e}")
            continue

    if not student_data:
        print("Error: No valid data found in JSON files")
        sys.exit(1)

    # Write CSV file
    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        # Create header
        headers = ["User Email"] + [f"Question {i + 1}" for i in range(max_questions)]
        writer = csv.writer(csvfile)
        writer.writerow(headers)

        # Write data rows (sorted by email)
        for email in sorted(student_data.keys()):
            row = [email]
            for i in range(max_questions):
                answer = student_data[email].get(i, "")
                row.append(answer)
            writer.writerow(row)

    # Print summary
    print("\n" + "=" * 60)
    print("CSV Generation Complete!")
    print(f"✓ CSV file created: {output_csv}")
    print(f"  Students: {len(student_data)}")
    print(f"  Questions: {max_questions}")
    if failed_files:
        print(f"  Failed files: {len(failed_files)}")
        if verbose:
            for filename, error in failed_files:
                print(f"    - {filename}: {error}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Generate CSV from existing JSON metadata files (no PDF rendering required)"
    )
    parser.add_argument(
        "json_dir",
        type=Path,
        help="Directory containing JSON metadata files (e.g., ./_rendered)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output CSV file path (e.g., answers.csv)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print progress information"
    )

    args = parser.parse_args()

    # Validate directory
    if not args.json_dir.exists():
        print(f"Error: Directory does not exist: {args.json_dir}")
        sys.exit(1)

    if not args.json_dir.is_dir():
        print(f"Error: Not a directory: {args.json_dir}")
        sys.exit(1)

    # Generate CSV
    try:
        generate_csv(args.json_dir, args.output, args.verbose)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
