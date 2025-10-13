#!/usr/bin/env python3
"""
Batch render IPython notebooks to PDF using otter-pensieve.
Supports parallel processing and resumable execution.
"""

import argparse
import asyncio
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from tqdm.asyncio import tqdm
except ImportError:
    print("Installing tqdm for progress tracking...")
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "tqdm"])
    from tqdm.asyncio import tqdm


class NotebookProcessor:
    """Process notebooks in parallel with async/await."""

    def __init__(
        self,
        base_dir: Path,
        working_dir: Path,
        max_parallel: int = 10,
        verbose: bool = False,
        json_only: bool = False,
    ):
        self.base_dir = base_dir
        self.working_dir = working_dir
        self.max_parallel = max_parallel
        self.json_only = json_only
        self.output_dir = base_dir / "_rendered"

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
        )
        self.logger = logging.getLogger(__name__)

        # Statistics
        self.processed = 0
        self.failed = 0
        self.skipped = 0
        self.lock = asyncio.Lock()

    @staticmethod
    def sanitize_email(email: str) -> str:
        """Sanitize email for use in filename."""
        return email.replace("@", "_").replace(".", "_")

    def get_output_paths(
        self, notebook_path: Path
    ) -> Optional[Tuple[Path, Path, str, str]]:
        """
        Get output paths for a notebook.
        Returns: (pdf_path, json_path, user_email, notebook_name) or None if should skip
        """
        # Get relative path from base directory
        try:
            rel_path = notebook_path.relative_to(self.base_dir)
        except ValueError:
            # If not relative to base_dir, use the path as-is
            rel_path = notebook_path

        # Extract user email (first directory component)
        parts = rel_path.parts
        user_email = parts[0] if len(parts) > 0 else "unknown"

        # Skip if it's the rendered directory
        if "_rendered" in user_email:
            return None

        # Get notebook name without extension
        notebook_name = notebook_path.stem

        # Sanitize email for filename
        sanitized_email = self.sanitize_email(user_email)

        # Define output paths
        output_pdf = self.output_dir / f"{sanitized_email}_{notebook_name}.pdf"
        output_json = self.output_dir / f"{sanitized_email}_{notebook_name}.json"

        return output_pdf, output_json, user_email, notebook_name

    def should_skip(self, output_pdf: Path, output_json: Path) -> bool:
        """Check if notebook should be skipped (already processed)."""
        if self.json_only:
            # In JSON-only mode, only check if JSON exists
            return output_json.exists()
        else:
            # In full mode, check both PDF and JSON
            return output_pdf.exists() and output_json.exists()

    async def process_notebook(
        self, notebook_path: Path, semaphore: asyncio.Semaphore
    ) -> Tuple[bool, str]:
        """
        Process a single notebook.
        Returns: (success, status_message)
        """
        async with semaphore:
            result = self.get_output_paths(notebook_path)

            # Skip if not valid
            if result is None:
                return True, "skipped_rendered_dir"

            output_pdf, output_json, user_email, notebook_name = result

            # Check if already processed (resumable)
            if self.should_skip(output_pdf, output_json):
                async with self.lock:
                    self.skipped += 1
                self.logger.debug(f"Skipped: {user_email} / {notebook_name}")
                return True, "skipped"

            self.logger.info(f"Processing: {user_email} / {notebook_name}")

            # Run the otter-pensieve command
            # Use generate_json.py if json_only mode is enabled
            if self.json_only:
                # Use absolute path for generate_json.py
                generate_json_path = self.working_dir / "generate_json.py"
                cmd = [
                    "python3",
                    str(generate_json_path),
                    str(notebook_path),
                    "-o",
                    str(output_json),
                ]
            else:
                cmd = [
                    "poetry",
                    "run",
                    "python",
                    "otter_pensieve_local.py",
                    str(notebook_path),
                    "-o",
                    str(output_pdf),
                    "-m",
                    str(output_json),
                ]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=self.working_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    async with self.lock:
                        self.processed += 1
                    self.logger.info(f"✓ Success: {user_email} / {notebook_name}")
                    return True, "success"
                else:
                    async with self.lock:
                        self.failed += 1
                    error_msg = stderr.decode("utf-8", errors="ignore").strip()
                    self.logger.error(
                        f"✗ Failed: {user_email} / {notebook_name}\n"
                        f"  Error: {error_msg[:200]}"
                    )
                    return False, "failed"

            except Exception as e:
                async with self.lock:
                    self.failed += 1
                self.logger.error(
                    f"✗ Exception: {user_email} / {notebook_name}: {str(e)}"
                )
                return False, "exception"

    async def process_all(self, notebooks: List[Path]):
        """Process all notebooks with progress bar."""
        semaphore = asyncio.Semaphore(self.max_parallel)

        # Create tasks for all notebooks
        tasks = [self.process_notebook(notebook, semaphore) for notebook in notebooks]

        # Process with progress bar
        results = []
        for coro in tqdm.as_completed(
            tasks, total=len(tasks), desc="Processing notebooks"
        ):
            result = await coro
            results.append(result)

        return results

    def print_summary(self, total: int):
        """Print final summary."""
        print("\n" + "=" * 60)
        print("Rendering complete!")
        print(f"✓ Successfully processed: {self.processed} notebooks")
        print(f"⊙ Skipped (already exists): {self.skipped} notebooks")
        if self.failed > 0:
            print(f"✗ Failed: {self.failed} notebooks")
        print(f"Total: {total} notebooks")
        print("=" * 60)


def find_notebooks(base_dir: Path) -> List[Path]:
    """Find all .ipynb files in the base directory."""
    notebooks = list(base_dir.rglob("*.ipynb"))
    # Filter out notebooks in _rendered directory
    notebooks = [nb for nb in notebooks if "_rendered" not in nb.parts]
    return notebooks


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


def generate_csv(output_dir: Path, csv_path: Path):
    """
    Generate a CSV file with all student answers.

    Format: user_email, Q1_answer, Q2_answer, Q3_answer, ...
    """
    print("\n" + "=" * 60)
    print("Generating CSV file...")

    # Find all JSON files in the output directory
    json_files = list(output_dir.glob("*.json"))

    if not json_files:
        print("No JSON files found. Skipping CSV generation.")
        return

    # Collect data from all JSON files
    student_data = {}  # {email: {question_index: answer_text}}
    max_questions = 0

    for json_file in json_files:
        try:
            with open(json_file, "r") as f:
                metadata = json.load(f)

            # Extract student email from filename
            # Format: {sanitized_email}_{notebook_name}.json
            filename = json_file.stem
            # Remove notebook name suffix to get sanitized email
            parts = filename.rsplit("_", 1)
            if len(parts) >= 1:
                sanitized_email = parts[0]
                # Restore email format (this is approximate)
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

        except Exception as e:
            print(f"Warning: Failed to process {json_file.name}: {e}")
            continue

    if not student_data:
        print("No valid data found. Skipping CSV generation.")
        return

    # Write CSV file
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        # Create header
        headers = ["User Email"] + [f"Question {i + 1}" for i in range(max_questions)]
        writer = csv.writer(csvfile)
        writer.writerow(headers)

        # Write data rows
        for email in sorted(student_data.keys()):
            row = [email]
            for i in range(max_questions):
                answer = student_data[email].get(i, "")
                row.append(answer)
            writer.writerow(row)

    print(f"✓ CSV file created: {csv_path}")
    print(f"  Students: {len(student_data)}")
    print(f"  Questions: {max_questions}")
    print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(
        description="Batch render IPython notebooks to PDF using otter-pensieve"
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("/Users/qria/Downloads/HW 1 submissions"),
        help="Base directory containing all submissions",
    )
    parser.add_argument(
        "--working-dir",
        type=Path,
        default=Path("/Users/qria/otter-pensieve"),
        help="Working directory for otter-pensieve",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=10,
        help="Maximum number of parallel jobs (default: 10)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Generate CSV file with all answers (e.g., answers.csv)",
    )
    parser.add_argument(
        "--csv-only",
        action="store_true",
        help="Only generate CSV from existing JSON files (skip PDF rendering)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only generate JSON metadata (skip PDF rendering - much faster!)",
    )

    args = parser.parse_args()

    # Validate directories
    if not args.base_dir.exists():
        print(f"Error: Base directory does not exist: {args.base_dir}")
        sys.exit(1)

    if not args.working_dir.exists():
        print(f"Error: Working directory does not exist: {args.working_dir}")
        sys.exit(1)

    # Handle CSV-only mode (skip PDF rendering)
    if args.csv_only:
        if not args.csv:
            print("Error: --csv-only requires --csv to be specified")
            sys.exit(1)

        output_dir = args.base_dir / "_rendered"
        if not output_dir.exists():
            print(f"Error: Output directory does not exist: {output_dir}")
            print("Run without --csv-only first to generate JSON files")
            sys.exit(1)

        print(f"Generating CSV from existing JSON files in: {output_dir}")
        generate_csv(output_dir, args.csv)
        return

    # Find all notebooks
    print(f"Searching for notebooks in: {args.base_dir}")
    notebooks = find_notebooks(args.base_dir)

    if not notebooks:
        print("No notebooks found!")
        sys.exit(0)

    print(f"Found {len(notebooks)} notebooks")
    print(f"Parallel jobs: {args.jobs}")
    print("-" * 60)

    # Process notebooks
    processor = NotebookProcessor(
        base_dir=args.base_dir,
        working_dir=args.working_dir,
        max_parallel=args.jobs,
        verbose=args.verbose,
        json_only=args.json_only,
    )

    # Print mode
    if args.json_only:
        print("Mode: JSON-only (PDF rendering skipped - fast!)")
    else:
        print("Mode: Full (PDF + JSON rendering)")

    await processor.process_all(notebooks)

    # Print summary
    processor.print_summary(len(notebooks))

    # Generate CSV if requested
    if args.csv:
        generate_csv(processor.output_dir, args.csv)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
        sys.exit(130)
