#!/bin/bash

# Standalone CSV generator for existing JSON files
# This script does NOT re-render PDFs - it only reads existing JSON metadata

# Default paths
BASE_DIR="/Users/qria/Downloads/HW 1 submissions"
JSON_DIR="$BASE_DIR/_rendered"
OUTPUT_CSV="$JSON_DIR/answers.csv"

# Override with command line arguments if provided
if [ $# -ge 1 ]; then
    JSON_DIR="$1"
fi

if [ $# -ge 2 ]; then
    OUTPUT_CSV="$2"
fi

# Check if JSON directory exists
if [ ! -d "$JSON_DIR" ]; then
    echo "Error: JSON directory does not exist: $JSON_DIR"
    echo ""
    echo "Usage: $0 [json_directory] [output_csv]"
    echo "  json_directory: Directory containing .json files (default: $BASE_DIR/_rendered)"
    echo "  output_csv: Path for output CSV file (default: answers.csv in json_directory)"
    exit 1
fi

echo "Generating CSV from existing JSON files..."
echo "JSON directory: $JSON_DIR"
echo "Output CSV: $OUTPUT_CSV"
echo ""

# Run the Python CSV generator
python3 generate_csv.py "$JSON_DIR" -o "$OUTPUT_CSV" -v

exit $?

