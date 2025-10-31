#!/bin/bash

# Configuration - UPDATE THESE VALUES
BASE_DIR="/Users/qria/Downloads/Midterm1Submissions"
CLAZZ_ID="columbia_ieore4100_fa25"  # e.g., data100_su25
ASSIGNMENT_ID="944a4f15-2a3f-40f2-af87-083a72de430d"  #Midterm 1
# API key (default provided, change if needed)
API_KEY="sk_live_Zl3ZEISWxdi-seojWJ8L0BlVcvOsGFuJ"

# Number of parallel jobs
JOBS=5

# Number of first questions to skip (0 = don't skip any)
SKIP_FIRST_QUESTIONS=2

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting batch submission to Pensieve API...${NC}"
echo "Base directory: $BASE_DIR"
echo "Class ID: $CLAZZ_ID"
echo "Assignment ID: $ASSIGNMENT_ID"
echo "Parallel jobs: $JOBS"
echo "Skip first questions: $SKIP_FIRST_QUESTIONS"
echo "----------------------------------------"

# Check if required parameters are set
if [ "$CLAZZ_ID" == "your_class_id" ] || [ "$ASSIGNMENT_ID" == "your_assignment_id" ]; then
    echo -e "${RED}Error: Please update CLAZZ_ID and ASSIGNMENT_ID in submit_yi.sh${NC}"
    exit 1
fi

# Run the submission script
poetry run python submit_yi.py \
    --base-dir "$BASE_DIR" \
    --api-key "$API_KEY" \
    --clazz-id "$CLAZZ_ID" \
    --assignment-id "$ASSIGNMENT_ID" \
    --jobs $JOBS \
    --skip-first-questions $SKIP_FIRST_QUESTIONS

echo ""
echo -e "${GREEN}Done!${NC}"
echo "Check error.txt for any submission errors."

