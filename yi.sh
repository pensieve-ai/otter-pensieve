#!/bin/bash

# Base directory containing all submissions
BASE_DIR="/Users/qria/Downloads/test-labs/columbia Yi/Sample Submissions"

# Working directory for otter-pensieve
WORKING_DIR="/Users/qria/otter-pensieve"

# Counter for processed files
processed=0
failed=0

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Starting batch rendering of IPython notebooks..."
echo "Base directory: $BASE_DIR"
echo "----------------------------------------"

# Find all .ipynb files matching the pattern
find "$BASE_DIR" -type f -name "*.ipynb" -path "*/Sample Submissions/*/*/*.ipynb" | while read -r notebook_path; do
    # Extract the assignment name and user name from the path
    # Path format: .../Sample Submissions/{assignmentName}/{userName}/{assignmentName}.ipynb

    # Get the relative path from Sample Submissions
    rel_path="${notebook_path#$BASE_DIR/}"

    # Extract assignment name (first directory after Sample Submissions)
    assignment_name=$(echo "$rel_path" | cut -d'/' -f1)

    # Extract user name (second directory)
    user_name=$(echo "$rel_path" | cut -d'/' -f2)

    # Skip if it's already a rendered directory
    if [[ "$assignment_name" == *"_rendered" ]]; then
        continue
    fi

    # Create output directory if it doesn't exist
    output_dir="$BASE_DIR/${assignment_name}_rendered"
    mkdir -p "$output_dir"

    # Define output paths
    output_pdf="$output_dir/${user_name}.pdf"
    output_json="$output_dir/${user_name}.json"

    echo -e "${YELLOW}Processing:${NC} $assignment_name / $user_name"
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

# Final summary
echo ""
echo "Rendering complete!"
echo -e "${GREEN}Successfully processed: $processed notebooks${NC}"
if [ $failed -gt 0 ]; then
    echo -e "${RED}Failed: $failed notebooks${NC}"
fi