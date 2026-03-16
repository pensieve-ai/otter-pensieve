#!/bin/bash

# Configuration
# Each BASE_DIR entry must have a corresponding ASSIGNMENT_ID at the same index.
BASE_DIRS=(
    "/Users/qria/Downloads/midterm"
)

ASSIGNMENT_IDS=(
    "c9c7e444-50e9-422a-a8f3-fdb6e395ddf3" # Midterm
)

CLAZZ_ID="columbia_ieore3404_sp26"

# API key (default provided, change if needed)
API_KEY="sk_live_Zl3ZEISWxdi-seojWJ8L0BlVcvOsGFuJ"

# Number of parallel jobs
JOBS=5

# Number of first questions to skip (0 = don't skip any)
SKIP_FIRST_QUESTIONS=2

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Validate arrays have same length
if [ ${#BASE_DIRS[@]} -ne ${#ASSIGNMENT_IDS[@]} ]; then
    echo -e "${RED}Error: BASE_DIRS and ASSIGNMENT_IDS must have the same number of entries${NC}"
    echo "  BASE_DIRS has ${#BASE_DIRS[@]} entries, ASSIGNMENT_IDS has ${#ASSIGNMENT_IDS[@]} entries"
    exit 1
fi

for i in "${!BASE_DIRS[@]}"; do
    BASE_DIR="${BASE_DIRS[$i]}"
    ASSIGNMENT_ID="${ASSIGNMENT_IDS[$i]}"

    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Submitting: $BASE_DIR${NC}"
    echo "Class ID: $CLAZZ_ID"
    echo "Assignment ID: $ASSIGNMENT_ID"
    echo "Parallel jobs: $JOBS"
    echo "Skip first questions: $SKIP_FIRST_QUESTIONS"
    echo "Question structure: Auto-detect from submissions"
    echo -e "${YELLOW}========================================${NC}"

    poetry run python submit_yi.py \
        --base-dir "$BASE_DIR" \
        --api-key "$API_KEY" \
        --clazz-id "$CLAZZ_ID" \
        --assignment-id "$ASSIGNMENT_ID" \
        --jobs $JOBS \
        --skip-first-questions $SKIP_FIRST_QUESTIONS

    echo ""
    echo -e "${GREEN}Done with $BASE_DIR${NC}"
    echo "Check error.txt for any submission errors."
    echo "----------------------------------------"
done

echo ""
echo -e "${GREEN}All batches complete!${NC}"
