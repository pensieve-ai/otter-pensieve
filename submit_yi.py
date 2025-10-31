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
    ):
        self.api_key = api_key
        self.clazz_id = clazz_id
        self.assignment_id = assignment_id
        self.base_url = base_url
        self.max_parallel = max_parallel
        self.skip_questions = skip_questions

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

            # Step 2: Submit page matchings
            page_indices = metadata.get("page_indices", [])
            # Skip first N questions if requested
            if self.skip_questions > 0 and len(page_indices) > self.skip_questions:
                page_indices = page_indices[self.skip_questions:]
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

            # Step 3: Submit answers
            answers = self.extract_answers_from_metadata(metadata)
            # Skip first N questions if requested
            if self.skip_questions > 0 and len(answers) > self.skip_questions:
                answers = answers[self.skip_questions:]
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
            print(f"   Check error.txt for details")
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
    print("-" * 60)

    # Create client and submit
    client = SubmissionClient(
        api_key=args.api_key,
        clazz_id=args.clazz_id,
        assignment_id=args.assignment_id,
        max_parallel=args.jobs,
        verbose=args.verbose,
        skip_questions=args.skip_first_questions,
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
