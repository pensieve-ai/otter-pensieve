#!/usr/bin/env python3
"""
Submit rendered notebooks to Pensieve API.
Reads PDFs and metadata from _rendered directory and submits them.
"""

import argparse
import asyncio
import base64
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
    from tqdm.asyncio import tqdm
except ImportError:
    print("Installing required packages...")
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "tqdm"])
    import requests
    from tqdm.asyncio import tqdm


class SubmissionClient:
    """Client for submitting to Pensieve API."""

    def __init__(
        self,
        api_key: str,
        clazz_id: str,
        assignment_id: str,
        base_url: str = "https://api.pensieve.co/api/b2s/v1/external-client",
        max_parallel: int = 5,
        verbose: bool = False,
        skip_questions: int = 0,
        expected_question_ids: Optional[List[str]] = None,
    ):
        self.api_key = api_key
        self.clazz_id = clazz_id
        self.assignment_id = assignment_id
        self.base_url = base_url
        self.max_parallel = max_parallel
        self.skip_questions = skip_questions
        self.expected_question_ids = expected_question_ids

        # Setup logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
        )
        self.logger = logging.getLogger(__name__)

        # Setup error logging
        self.error_log_path = Path("error.txt")
        self.error_log = open(self.error_log_path, "w")

        # Statistics
        self.submitted = 0
        self.failed = 0
        self.lock = asyncio.Lock()

    def __del__(self):
        """Close error log file."""
        if hasattr(self, "error_log"):
            self.error_log.close()

    @staticmethod
    def desanitize_email(sanitized: str) -> str:
        """Convert sanitized email back to normal email format.

        Heuristic: Replace first underscore with @, then remaining underscores with dots.
        This may not be perfect for all edge cases.
        """
        # Find the first underscore and replace with @
        parts = sanitized.split("_", 1)
        if len(parts) == 2:
            # Replace remaining underscores with dots
            return f"{parts[0]}@{parts[1].replace('_', '.')}"
        return sanitized

    @staticmethod
    def parse_question_identifier(question_data: Dict[str, Any]) -> Optional[str]:
        """Parse question identifier from formatted cells.

        Looks for patterns like:
        - ## Question 0.a [1 Point]
        - ## Q1. [8 points]
        - # Q2

        Returns the identifier (e.g., "0.a", "1", "2") or None if not found.
        """
        formatted_cells = question_data.get("formatted_cells", [])

        # Look at the first markdown cell
        for cell in formatted_cells:
            if cell.get("cell_type") == "markdown":
                for part in cell.get("parts", []):
                    if part.get("content_type") == "text":
                        content = part.get("content", "")

                        # Pattern 1: ## Question X.Y [points] or ## Question X [points]
                        match = re.search(
                            r"^`Markdown:`\s*\n+#+\s*Question\s+([\d.]+[a-z]?)",
                            content,
                            re.MULTILINE | re.IGNORECASE
                        )
                        if match:
                            return match.group(1).strip()

                        # Pattern 2: ## QX. [points] or ## QX [points]
                        match = re.search(
                            r"^`Markdown:`\s*\n+#+\s*Q\s*([\d.]+[a-z]?)",
                            content,
                            re.MULTILINE | re.IGNORECASE
                        )
                        if match:
                            return match.group(1).strip().rstrip('.')

                        # Pattern 3: # QX or ## QX (without [points])
                        match = re.search(
                            r"^`Markdown:`\s*\n+#+\s*Q(?:uestion)?\s*([\d.]+[a-z]?)",
                            content,
                            re.MULTILINE | re.IGNORECASE
                        )
                        if match:
                            return match.group(1).strip().rstrip('.')

                        # Pattern 4: just # Questions
                        match = re.search(
                            r"^`Markdown:`\s*\n+#+\s*Questions\s*",
                            content,
                            re.MULTILINE | re.IGNORECASE
                        )
                        if match:
                            return "Questions"

                # Only check first markdown cell
                break

        return None

    def normalize_questions_structure(
        self,
        metadata: Dict[str, Any],
        expected_question_ids: Optional[List[str]] = None
    ) -> Tuple[List[List[int]], List[Dict[str, Any]]]:
        """Normalize question structure by filling in missing questions.

        Args:
            metadata: The metadata dict containing questions
            expected_question_ids: Optional list of expected question IDs (e.g., ["0.a", "0.b", "1", "2"])
                                  If None, will infer from existing questions

        Returns:
            Tuple of (page_indices, answers) with gaps filled with empty data
        """
        questions = metadata.get("questions", [])
        page_indices = metadata.get("page_indices", [])

        # Parse question identifiers from existing questions
        parsed_questions = []
        for i, question in enumerate(questions):
            qid = self.parse_question_identifier(question)
            parsed_questions.append({
                "id": qid,
                "original_index": i,
                "page_indices": page_indices[i] if i < len(page_indices) else [],
                "formatted_cells": question.get("formatted_cells", [])
            })

        # If no expected IDs provided, use what we have
        if expected_question_ids is None:
            # Just return the data as-is if we can't determine structure
            self.logger.debug("No expected question structure provided, using existing questions")
            return page_indices, self.extract_answers_from_metadata(metadata)

        # Build normalized structure
        normalized_page_indices = []
        normalized_answers = []

        # Create a map of parsed questions by ID
        question_map = {pq["id"]: pq for pq in parsed_questions if pq["id"] is not None}

        for expected_id in expected_question_ids:
            if expected_id in question_map:
                # Question exists
                q = question_map[expected_id]
                normalized_page_indices.append(q["page_indices"])

                # Extract answer parts from formatted cells
                parts = []
                for cell in q["formatted_cells"]:
                    cell_parts = cell.get("parts", [])
                    parts.extend(cell_parts)
                normalized_answers.append({"parts": parts})
            else:
                # Question missing - insert empty data
                self.logger.warning(f"Question {expected_id} missing, inserting empty data")
                normalized_page_indices.append([])
                normalized_answers.append({"parts": [{"content_type": "text", "content": ""}]})

        return normalized_page_indices, normalized_answers

    def log_error(self, message: str):
        """Log error to error.txt file."""
        self.error_log.write(message + "\n")
        self.error_log.flush()

    def create_submission(self, student_email: str, pdf_path: Path) -> Optional[str]:
        """Create a submission and return submission_id."""
        try:
            # Read and encode PDF
            with open(pdf_path, "rb") as f:
                pdf_file_base64 = base64.b64encode(f.read()).decode("utf-8")

            # Prepare request
            url = f"{self.base_url}/create-submission"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            data = {
                "clazz_id": self.clazz_id,
                "assignment_id": self.assignment_id,
                "student_email": student_email,
                "pdf_file_base64": pdf_file_base64,
                "pdf_file_name": pdf_path.name,
                "add_to_roster": True,
            }

            # Make request
            response = requests.post(url, json=data, headers=headers, timeout=60)
            response.raise_for_status()

            result = response.json()
            if result.get("success"):
                return result.get("submission_id")
            else:
                error_msg = f"Failed to create submission for {student_email}: {result}"
                self.logger.error(error_msg)
                self.log_error(error_msg)
                return None

        except Exception as e:
            error_msg = f"Exception creating submission for {student_email}: {str(e)}"
            self.logger.error(error_msg)
            self.log_error(error_msg)
            return None

    def submit_page_matchings(
        self,
        submission_id: str,
        page_indices: List[List[int]],
        student_email: str,
    ) -> bool:
        """Submit page matchings for a submission."""
        try:
            url = f"{self.base_url}/create-submission/page-matchings"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            data = {
                "clazz_id": self.clazz_id,
                "assignment_id": self.assignment_id,
                "submission_id": submission_id,
                "page_indices": page_indices,
            }

            response = requests.post(url, json=data, headers=headers, timeout=30)
            response.raise_for_status()

            return True

        except Exception as e:
            error_msg = (
                f"Exception submitting page matchings for {student_email}: {str(e)}"
            )
            self.logger.error(error_msg)
            self.log_error(error_msg)
            return False

    def submit_answers(
        self,
        submission_id: str,
        answers: List[Dict[str, Any]],
        student_email: str,
    ) -> bool:
        """Submit answers for a submission."""
        try:
            url = f"{self.base_url}/create-submission/answers"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            data = {
                "clazz_id": self.clazz_id,
                "assignment_id": self.assignment_id,
                "submission_id": submission_id,
                "answers": answers,
            }

            response = requests.post(url, json=data, headers=headers, timeout=30)
            response.raise_for_status()

            return True

        except Exception as e:
            error_msg = f"Exception submitting answers for {student_email}: {str(e)}"
            self.logger.error(error_msg)
            self.log_error(error_msg)
            return False

    def extract_answers_from_metadata(
        self, metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract answers from metadata in the format expected by the API."""
        answers = []

        for question in metadata.get("questions", []):
            # Get formatted cells for this question
            formatted_cells = question.get("formatted_cells", [])

            # Collect all parts from all cells
            parts = []
            for cell in formatted_cells:
                cell_parts = cell.get("parts", [])
                parts.extend(cell_parts)

            # Create answer object
            answers.append({"parts": parts})

        return answers

    async def submit_one(
        self,
        pdf_path: Path,
        json_path: Path,
        semaphore: asyncio.Semaphore,
    ) -> Tuple[bool, str]:
        """Submit one notebook (PDF + metadata)."""
        async with semaphore:
            # Extract student email from filename
            # Format: {sanitized_email}_{notebook_name}.pdf
            filename = pdf_path.stem
            parts = filename.rsplit("_", 1)
            if len(parts) != 2:
                error_msg = f"Cannot parse filename: {filename}"
                self.logger.error(error_msg)
                self.log_error(error_msg)
                return False, "parse_error"

            sanitized_email = parts[0]
            student_email = self.desanitize_email(sanitized_email)
            notebook_name = parts[1]

            self.logger.info(f"Submitting: {student_email} / {notebook_name}")

            # Read metadata
            try:
                with open(json_path, "r") as f:
                    metadata = json.load(f)
            except Exception as e:
                error_msg = f"Failed to read metadata for {student_email}: {str(e)}"
                self.logger.error(error_msg)
                self.log_error(error_msg)
                return False, "metadata_error"

            # Step 1: Create submission (synchronous, run in executor)
            loop = asyncio.get_event_loop()
            submission_id = await loop.run_in_executor(
                None, self.create_submission, student_email, pdf_path
            )

            if not submission_id:
                async with self.lock:
                    self.failed += 1
                return False, "create_failed"

            self.logger.debug(f"Created submission {submission_id} for {student_email}")

            # Step 2: Normalize question structure (handle missing questions)
            if self.expected_question_ids:
                page_indices, answers = self.normalize_questions_structure(
                    metadata, self.expected_question_ids
                )
            else:
                page_indices = metadata.get("page_indices", [])
                answers = self.extract_answers_from_metadata(metadata)

            # Skip first N questions if requested
            if self.skip_questions > 0 and len(page_indices) > self.skip_questions:
                page_indices = page_indices[self.skip_questions:]
                answers = answers[self.skip_questions:]

            # Step 3: Submit page matchings
            success = await loop.run_in_executor(
                None,
                self.submit_page_matchings,
                submission_id,
                page_indices,
                student_email,
            )

            if not success:
                async with self.lock:
                    self.failed += 1
                return False, "page_matchings_failed"

            # Step 4: Submit answers
            success = await loop.run_in_executor(
                None, self.submit_answers, submission_id, answers, student_email
            )

            if not success:
                async with self.lock:
                    self.failed += 1
                return False, "answers_failed"

            # Success!
            async with self.lock:
                self.submitted += 1
            self.logger.info(
                f"✓ Successfully submitted: {student_email} / {notebook_name}"
            )
            return True, "success"

    async def submit_all(self, submissions: List[Tuple[Path, Path]]):
        """Submit all PDFs and metadata."""
        semaphore = asyncio.Semaphore(self.max_parallel)

        # Create tasks for all submissions
        tasks = [
            self.submit_one(pdf_path, json_path, semaphore)
            for pdf_path, json_path in submissions
        ]

        # Process with progress bar
        results = []
        for coro in tqdm.as_completed(
            tasks, total=len(tasks), desc="Submitting to Pensieve"
        ):
            result = await coro
            results.append(result)

        return results

    def print_summary(self, total: int):
        """Print final summary."""
        print("\n" + "=" * 60)
        print("Submission complete!")
        print(f"✓ Successfully submitted: {self.submitted} notebooks")
        if self.failed > 0:
            print(f"✗ Failed: {self.failed} notebooks")
            print("   Check error.txt for details")
        print(f"Total: {total} notebooks")
        print("=" * 60)


def find_submissions(rendered_dir: Path) -> List[Tuple[Path, Path]]:
    """Find all PDF and corresponding JSON files in rendered directory."""
    submissions = []

    # Find all PDF files
    pdf_files = list(rendered_dir.glob("*.pdf"))

    for pdf_path in pdf_files:
        # Find corresponding JSON file
        json_path = pdf_path.with_suffix(".json")

        if json_path.exists():
            submissions.append((pdf_path, json_path))
        else:
            print(f"Warning: No metadata file found for {pdf_path.name}")

    return submissions


def infer_question_structure(submissions: List[Tuple[Path, Path]]) -> List[str]:
    """Infer the complete question structure by analyzing all submissions.

    Collects all question identifiers from all submissions and determines
    the most complete set of questions.

    Args:
        submissions: List of (pdf_path, json_path) tuples

    Returns:
        Sorted list of question identifiers
    """
    print("\nInferring question structure from submissions...")

    all_question_ids = {}  # {question_id: count}

    for pdf_path, json_path in submissions:
        try:
            with open(json_path, "r") as f:
                metadata = json.load(f)

            questions = metadata.get("questions", [])
            for question in questions:
                qid = SubmissionClient.parse_question_identifier(question)
                if qid:
                    all_question_ids[qid] = all_question_ids.get(qid, 0) + 1
        except Exception as e:
            print(f"Warning: Failed to parse {json_path.name}: {e}")
            continue

    if not all_question_ids:
        print("Warning: Could not infer question structure from any submissions")
        return []

    # Sort question IDs naturally
    # Handle formats like: 0.a, 0.b, 1, 2, 3.a, 3.b, etc.
    def sort_key(qid: str) -> tuple:
        """Create a sort key for natural sorting of question IDs."""
        # Split on dot to handle "1.a" style IDs
        parts = qid.split('.')
        result = []
        for part in parts:
            # Try to convert to int, otherwise keep as string
            try:
                result.append((0, int(part)))
            except ValueError:
                result.append((1, part))
        return tuple(result)

    sorted_ids = sorted(all_question_ids.keys(), key=sort_key)

    print(f"✓ Detected {len(sorted_ids)} unique questions: {', '.join(sorted_ids)}")
    print(f"  Question frequency across {len(submissions)} submissions:")
    for qid in sorted_ids:
        count = all_question_ids[qid]
        percentage = (count / len(submissions)) * 100
        indicator = "⚠️" if percentage < 80 else "✓"
        print(f"    {indicator} {qid}: {count}/{len(submissions)} ({percentage:.0f}%)")

    return sorted_ids


async def main():
    parser = argparse.ArgumentParser(
        description="Submit rendered notebooks to Pensieve API"
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("/Users/qria/Downloads/HW 1 submissions"),
        help="Base directory containing _rendered subdirectory",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="sk_live_Zl3ZEISWxdi-seojWJ8L0BlVcvOsGFuJ",
        help="API key for authentication",
    )
    parser.add_argument(
        "--clazz-id",
        type=str,
        required=True,
        help="Class ID (e.g., data100_su25)",
    )
    parser.add_argument(
        "--assignment-id",
        type=str,
        required=True,
        help="Assignment ID (get from URL)",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=5,
        help="Maximum number of parallel submissions (default: 5)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--skip-first-questions",
        type=int,
        default=0,
        help="Number of first questions to skip (default: 0)",
    )
    parser.add_argument(
        "--expected-questions",
        type=str,
        help='Optional: Override expected question IDs (comma-separated, e.g., "0.a,0.b,1,2,3"). '
             'By default, the structure is automatically inferred from all submissions.',
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Disable automatic question normalization (submit questions as-is)",
    )

    args = parser.parse_args()

    # Find rendered directory
    rendered_dir = args.base_dir / "_rendered"
    if not rendered_dir.exists():
        print(f"Error: Rendered directory does not exist: {rendered_dir}")
        print("Please run yi.sh first to generate PDFs.")
        sys.exit(1)

    # Find all submissions
    print(f"Searching for submissions in: {rendered_dir}")
    submissions = find_submissions(rendered_dir)

    if not submissions:
        print("No submissions found!")
        sys.exit(0)

    print(f"Found {len(submissions)} submissions")
    print(f"Parallel jobs: {args.jobs}")
    print(f"Class ID: {args.clazz_id}")
    print(f"Assignment ID: {args.assignment_id}")

    # Determine expected question structure
    expected_question_ids = None
    if args.no_normalize:
        print("Question normalization: DISABLED")
    elif args.expected_questions:
        # Manual override provided
        expected_question_ids = [q.strip() for q in args.expected_questions.split(",")]
        print(f"Expected questions (manual): {', '.join(expected_question_ids)}")
    else:
        # Automatically infer from submissions
        expected_question_ids = infer_question_structure(submissions)
        if expected_question_ids:
            print("Question normalization: ENABLED (auto-detected)")
        else:
            print("Question normalization: DISABLED (could not infer structure)")

    print("-" * 60)

    # Create client and submit
    client = SubmissionClient(
        api_key=args.api_key,
        clazz_id=args.clazz_id,
        assignment_id=args.assignment_id,
        max_parallel=args.jobs,
        verbose=args.verbose,
        skip_questions=args.skip_first_questions,
        expected_question_ids=expected_question_ids,
    )

    await client.submit_all(submissions)

    # Print summary
    client.print_summary(len(submissions))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
        sys.exit(130)
