#!/usr/bin/env python3
"""
Generate JSON metadata from notebooks WITHOUT rendering PDFs.
This is much faster than full PDF rendering - use this when you only need the metadata/answers.
"""

import argparse
import copy
import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union, cast

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired

import nbformat


# Type definitions
class NotebookCellOutputNode(TypedDict, total=False):
    data: Dict[str, Union[str, List[str]]]
    text: Union[str, List[str]]
    traceback: Union[str, List[str]]


class NotebookCellNode(TypedDict):
    cell_type: Literal["markdown", "code", "raw"]
    metadata: NotRequired[dict[str, object]]
    source: Union[str, list[str]]
    outputs: NotRequired[list[NotebookCellOutputNode]]


# Data structures
@dataclass
class ParsedQuestionPosition:
    cell_index: int
    line_index: int


@dataclass
class ParsedQuestion:
    begin: ParsedQuestionPosition
    end: ParsedQuestionPosition


@dataclass
class ParsedNotebook:
    questions: List[ParsedQuestion]


# Patterns for parsing
_BEGIN_QUESTION_PATTERN = re.compile(r"<!--\s*BEGIN QUESTION\s*-->")
_END_QUESTION_PATTERN = re.compile(r"<!--\s*END QUESTION\s*-->")
_QUESTION_HEADER_PATTERN = re.compile(r"^#+\s*(Q|Question)\s*\d+", re.MULTILINE)


# Helper functions
def get_cell_source_as_list(cell: NotebookCellNode) -> List[str]:
    """Convert cell source to list of strings."""
    source = cell["source"]
    if isinstance(source, str):
        return source.splitlines(keepends=True)
    else:
        return source


def get_cell_source_as_str(cell: NotebookCellNode) -> str:
    """Convert cell source to single string."""
    return "".join(get_cell_source_as_list(cell))


# Notebook parsing
def parse_notebook(notebook: nbformat.NotebookNode) -> ParsedNotebook:
    """Parse notebook to find questions."""
    questions = []
    current_question: Optional[ParsedQuestion] = None

    # Detect format
    has_html_format = False
    has_header_format = False

    for cell in cast(List[NotebookCellNode], notebook["cells"]):
        if cell["cell_type"] == "markdown":
            source = get_cell_source_as_str(cell)
            if re.search(_BEGIN_QUESTION_PATTERN, source):
                has_html_format = True
                break
            if re.search(_QUESTION_HEADER_PATTERN, source):
                has_header_format = True

    # Parse based on detected format
    if has_html_format:
        for cell_index, cell in enumerate(
            cast(List[NotebookCellNode], notebook["cells"])
        ):
            if cell["cell_type"] == "markdown":
                source = get_cell_source_as_list(cell)
                if current_question is not None:
                    current_question.end.cell_index = cell_index
                    current_question.end.line_index = 0
                for line_index, line in enumerate(source):
                    if current_question is None:
                        if re.search(_BEGIN_QUESTION_PATTERN, line):
                            current_question = ParsedQuestion(
                                begin=ParsedQuestionPosition(cell_index, line_index),
                                end=ParsedQuestionPosition(cell_index, line_index + 1),
                            )
                    else:
                        current_question.end.line_index = line_index + 1
                        if re.search(_END_QUESTION_PATTERN, line):
                            questions.append(current_question)
                            current_question = None

        if current_question is not None:
            questions.append(current_question)

    elif has_header_format:
        question_headers = []

        for cell_index, cell in enumerate(
            cast(List[NotebookCellNode], notebook["cells"])
        ):
            if cell["cell_type"] == "markdown":
                source = get_cell_source_as_list(cell)
                for line_index, line in enumerate(source):
                    if re.match(_QUESTION_HEADER_PATTERN, line):
                        question_headers.append((cell_index, line_index))

        for i, (cell_index, line_index) in enumerate(question_headers):
            begin = ParsedQuestionPosition(cell_index, line_index)

            if i < len(question_headers) - 1:
                next_cell, next_line = question_headers[i + 1]
                end = ParsedQuestionPosition(next_cell, next_line)
            else:
                end = ParsedQuestionPosition(
                    len(notebook["cells"]) - 1,
                    len(get_cell_source_as_list(notebook["cells"][-1])),
                )

            questions.append(ParsedQuestion(begin=begin, end=end))

    return ParsedNotebook(questions)


# Notebook slicing
def slice_notebook(
    notebook: nbformat.NotebookNode, question: ParsedQuestion
) -> nbformat.NotebookNode:
    """Extract a slice of the notebook containing a single question."""
    retval = nbformat.v4.new_notebook()
    retval_cells = cast(List[NotebookCellNode], retval["cells"])
    notebook_cells = cast(List[NotebookCellNode], notebook["cells"])
    begin_cell_index = question.begin.cell_index
    end_cell_index = min(question.end.cell_index + 1, len(notebook_cells))

    for cell_index in range(begin_cell_index, end_cell_index):
        cell = notebook_cells[cell_index]
        cell_source = get_cell_source_as_list(cell)
        begin_line_index = (
            question.begin.line_index if cell_index == begin_cell_index else 0
        )
        end_line_index = (
            question.end.line_index
            if cell_index == question.end.cell_index
            else len(cell_source)
        )
        retval_cells.append(
            {
                **copy.deepcopy(cell),
                "source": "".join(cell_source[begin_line_index:end_line_index]),
            }
        )

    return cast(nbformat.NotebookNode, nbformat.from_dict(retval))


# Cell formatting
def format_cells_as_answer_parts(
    notebook_slice: nbformat.NotebookNode,
) -> List[Dict[str, Any]]:
    """Format all cells from a notebook slice in the answer format."""
    formatted_cells = []
    all_cells = cast(List[NotebookCellNode], notebook_slice["cells"])

    for cell in all_cells:
        if not get_cell_source_as_str(cell).strip():
            continue

        cell_parts = []
        writer = io.StringIO()
        cell_source = get_cell_source_as_str(cell).splitlines()

        if cell["cell_type"] == "code":
            writer.write("`In:`\n\n```python\n")
        elif cell["cell_type"] == "markdown":
            writer.write("`Markdown:`\n\n")

        for line in cell_source:
            writer.write(line)
            writer.write("\n")

        if cell["cell_type"] == "code":
            writer.write("```")

        cell_parts.append({"content_type": "text", "content": writer.getvalue()})

        # Add cell outputs for code cells
        if (
            cell["cell_type"] == "code"
            and (cell_outputs := cell.get("outputs")) is not None
        ):
            for cell_output in cell_outputs:
                if (output_data := cell_output.get("data")) is not None:
                    if (png_data := output_data.get("image/png")) is not None:
                        if isinstance(png_data, list):
                            png_data_str = "".join(png_data)
                        else:
                            png_data_str = png_data
                        cell_parts.append(
                            {"content_type": "png", "content": png_data_str}
                        )
                    elif (text_data := output_data.get("text/plain")) is not None:
                        writer = io.StringIO()
                        writer.write("`Out:`\n\n```text\n")
                        if isinstance(text_data, str):
                            writer.write(text_data)
                            ends_with_newline = text_data.endswith("\n")
                        else:
                            for line in text_data:
                                writer.write(line)
                            ends_with_newline = text_data[-1].endswith("\n")
                        if not ends_with_newline:
                            writer.write("\n")
                        writer.write("```")
                        cell_parts.append(
                            {"content_type": "text", "content": writer.getvalue()}
                        )

                if (output_text := cell_output.get("text")) is not None:
                    writer = io.StringIO()
                    writer.write("`Out:`\n\n```text\n")
                    if isinstance(output_text, str):
                        writer.write(output_text)
                        ends_with_newline = output_text.endswith("\n")
                    else:
                        for line in output_text:
                            writer.write(line)
                        ends_with_newline = output_text[-1].endswith("\n")
                    if not ends_with_newline:
                        writer.write("\n")
                    writer.write("```")
                    cell_parts.append(
                        {"content_type": "text", "content": writer.getvalue()}
                    )

                if (output_traceback := cell_output.get("traceback")) is not None:
                    writer = io.StringIO()
                    writer.write("`Out:`\n\n```text\n")
                    if isinstance(output_traceback, str):
                        writer.write(output_traceback)
                        ends_with_newline = output_traceback.endswith("\n")
                    else:
                        for line in output_traceback:
                            writer.write(line)
                            writer.write("\n")
                        ends_with_newline = True
                    if not ends_with_newline:
                        writer.write("\n")
                    writer.write("```")
                    cell_parts.append(
                        {"content_type": "text", "content": writer.getvalue()}
                    )

        formatted_cells.append(
            {
                "cell_type": cell["cell_type"],
                "metadata": cell.get("metadata", {}),
                "parts": cell_parts,
            }
        )

    return formatted_cells


# Main processing function
def process_notebook_to_json(
    notebook_path: str,
    output_json_path: str,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Process a notebook to create JSON metadata WITHOUT rendering PDFs.
    This is much faster than full processing since it skips PDF rendering.

    Args:
        notebook_path: Path to the Jupyter notebook
        output_json_path: Path to save metadata JSON
        verbose: Print progress information

    Returns:
        Dictionary with processing results
    """
    if verbose:
        print(f"Processing notebook: {notebook_path}")

    # Load notebook
    with open(notebook_path) as f:
        notebook = nbformat.read(f, as_version=4)

    # Parse questions
    parsed_notebook = parse_notebook(notebook)
    if verbose:
        print(f"Found {len(parsed_notebook.questions)} questions")

    # Process each question
    question_formatted_cells = []

    for i, question in enumerate(parsed_notebook.questions):
        if verbose:
            print(f"  Processing question {i + 1}...")

        # Slice notebook for this question
        notebook_slice = slice_notebook(notebook, question)

        # Format cells for this question
        formatted_cells = format_cells_as_answer_parts(notebook_slice)
        question_formatted_cells.append(formatted_cells)

    # Create metadata (without PDF-related fields)
    metadata = {
        "notebook_path": str(Path(notebook_path).absolute()),
        "num_questions": len(parsed_notebook.questions),
        "questions": [
            {
                "index": i,
                "begin": {
                    "cell_index": q.begin.cell_index,
                    "line_index": q.begin.line_index,
                },
                "end": {"cell_index": q.end.cell_index, "line_index": q.end.line_index},
                "formatted_cells": question_formatted_cells[i],
            }
            for i, q in enumerate(parsed_notebook.questions)
        ],
    }

    # Save metadata
    with open(output_json_path, "w") as f:
        json.dump(metadata, f, indent=2)
    if verbose:
        print(f"Saved metadata to: {output_json_path}")

    return {
        "questions": parsed_notebook.questions,
        "formatted_cells": question_formatted_cells,
        "metadata_path": output_json_path,
    }


# CLI interface
def main():
    parser = argparse.ArgumentParser(
        description="Extract notebook metadata to JSON WITHOUT rendering PDFs (fast!)"
    )
    parser.add_argument("notebook_path", help="Path to the Jupyter notebook to process")
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Path to save the metadata JSON",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print progress information"
    )

    args = parser.parse_args()

    # Process notebook
    try:
        result = process_notebook_to_json(
            args.notebook_path,
            output_json_path=args.output,
            verbose=args.verbose,
        )

        print(f"\n✓ Successfully processed notebook!")
        print(f"  Metadata saved to: {result['metadata_path']}")
        print(f"  Found {len(result['questions'])} questions")
        print(f"  (PDF rendering skipped - much faster!)")

    except Exception as e:
        print(f"Error processing notebook: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
