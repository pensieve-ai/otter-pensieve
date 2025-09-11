#!/usr/bin/env python3
"""
Self-contained script with equivalent functionality to otter-pensieve library.
Processes otter-formatted Jupyter notebooks to:
1. Parse questions marked with BEGIN/END QUESTION comments
2. Slice notebooks by question
3. Render to PDF
4. Extract answers from tagged cells
5. Submit to Pensieve server with metadata
"""

import argparse
import base64
import copy
import io
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union, cast

import nbconvert
import nbformat
import requests
from nbconvert import WebPDFExporter
from pydantic import BaseModel, TypeAdapter
from pypdf import PdfReader, PdfWriter
from strip_ansi import strip_ansi


# Type definitions
class NotebookCellOutputNode(TypedDict, total=False):
    data: Dict[str, Union[str, List[str]]]
    text: Union[str, List[str]]
    traceback: Union[str, List[str]]


class NotebookCellNode(TypedDict, total=False):
    cell_type: Literal["markdown", "code", "raw"]
    metadata: Dict[str, Any]
    source: Union[str, List[str]]
    outputs: List[NotebookCellOutputNode]


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


ExtractedAnswerContentType = Literal["text", "png"]


class ExtractedAnswerPart(BaseModel):
    content_type: ExtractedAnswerContentType
    content: str


class ExtractedAnswer(BaseModel):
    parts: List[ExtractedAnswerPart]


# Patterns for parsing
_BEGIN_QUESTION_PATTERN = re.compile(r"<!--\s*BEGIN QUESTION\s*-->")
_END_QUESTION_PATTERN = re.compile(r"<!--\s*END QUESTION\s*-->")


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
    """Parse notebook to find questions marked with BEGIN/END QUESTION comments."""
    questions = []
    current_question: Optional[ParsedQuestion] = None

    for cell_index, cell in enumerate(cast(List[NotebookCellNode], notebook["cells"])):
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


# Notebook rendering
def render_notebook(notebook: nbformat.NotebookNode) -> bytes:
    """Render notebook to PDF using nbconvert with otter templates."""
    try:
        # Try to use otter templates if available
        from otter.export.exporters.base_exporter import TEMPLATE_DIR

        nbconvert.TemplateExporter.extra_template_basedirs = [str(TEMPLATE_DIR)]
        orig_template_name = nbconvert.TemplateExporter.template_name
        nbconvert.TemplateExporter.template_name = "via_html"
    except ImportError:
        # Fallback to default templates
        orig_template_name = None

    try:
        exporter = WebPDFExporter()
        pdf, _ = exporter.from_notebook_node(notebook)
        return pdf
    finally:
        if orig_template_name is not None:
            nbconvert.TemplateExporter.template_name = orig_template_name


# PDF merging
def merge_pdfs(pdfs: List[bytes]) -> bytes:
    """Merge multiple PDFs into a single PDF."""
    writer = PdfWriter()
    for pdf in pdfs:
        stream = io.BytesIO(pdf)
        reader = PdfReader(stream)
        for page in reader.pages:
            writer.add_page(page)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


# Answer extraction
def _is_otter_answer_cell(cell: NotebookCellNode) -> bool:
    """Check if cell is marked as an otter answer cell."""
    cell_metadata = cell.get("metadata", {})
    cell_tags = cell_metadata.get("tags", [])
    return "otter_answer_cell" in cell_tags


def extract_answer(notebook: nbformat.NotebookNode) -> ExtractedAnswer:
    """Extract answers from cells marked with otter_answer_cell tag."""
    all_cells = cast(List[NotebookCellNode], notebook["cells"])
    answer_cells = [cell for cell in all_cells if _is_otter_answer_cell(cell)]
    retval_parts = []

    for cell in answer_cells:
        # Add cell source
        writer = io.StringIO()
        cell_source = get_cell_source_as_str(cell).splitlines()
        if cell["cell_type"] == "code":
            writer.write("`In:`\n\n```python\n")
        for line in cell_source:
            writer.write(line)
            writer.write("\n")
        if cell["cell_type"] == "code":
            writer.write("```")
        retval_parts.append(
            ExtractedAnswerPart(content_type="text", content=writer.getvalue())
        )

        # Add cell outputs
        if (cell_outputs := cell.get("outputs")) is not None:
            for cell_output in cell_outputs:
                writer = io.StringIO()
                if (output_data := cell_output.get("data")) is not None:
                    if (png_data := output_data.get("image/png")) is not None:
                        retval_parts.append(
                            ExtractedAnswerPart(content_type="png", content=png_data)
                        )
                    elif (text_data := output_data.get("text/plain")) is not None:
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
                        retval_parts.append(
                            ExtractedAnswerPart(
                                content_type="text", content=writer.getvalue()
                            )
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
                    retval_parts.append(
                        ExtractedAnswerPart(
                            content_type="text", content=writer.getvalue()
                        )
                    )

                if (output_traceback := cell_output.get("traceback")) is not None:
                    writer = io.StringIO()
                    writer.write("`Out:`\n\n```text\n")
                    if isinstance(output_traceback, str):
                        writer.write(strip_ansi(output_traceback))
                        ends_with_newline = output_traceback.endswith("\n")
                    else:
                        for line in output_traceback:
                            writer.write(strip_ansi(line))
                            writer.write("\n")
                        ends_with_newline = True
                    if not ends_with_newline:
                        writer.write("\n")
                    writer.write("```")
                    retval_parts.append(
                        ExtractedAnswerPart(
                            content_type="text", content=writer.getvalue()
                        )
                    )

    return ExtractedAnswer(parts=retval_parts)


# Client for submission
class PensieveClient:
    """Client for submitting to Pensieve server."""

    def __init__(self, hostname: str, token: str):
        self._hostname = hostname
        self._token = token

    def post_submission(self, submission_pdf: bytes) -> str:
        """Upload a PDF as a submission and return the created submission's id."""
        response = requests.post(
            self._make_api_url(
                "v1/programming-assignment/associated-paper-assignment/submissions"
            ),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/octet-stream",
            },
            data=submission_pdf,
        )
        response.raise_for_status()
        return response.json()["submission_id"]

    def post_submission_page_matching(
        self, submission_id: str, page_indices: List[List[int]]
    ) -> None:
        """Update the page matching of a submission."""
        response = requests.post(
            self._make_api_url(
                "v1/programming-assignment/associated-paper-assignment/submission-page-matchings"
            ),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            json={"submission_id": submission_id, "page_indices": page_indices},
        )
        response.raise_for_status()

    def post_submission_answers(
        self, submission_id: str, answers: List[ExtractedAnswer]
    ) -> None:
        """Update the answers of a submission."""
        response = requests.post(
            self._make_api_url(
                "v1/programming-assignment/associated-paper-assignment/submission-answers"
            ),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            json={
                "submission_id": submission_id,
                "answers": TypeAdapter(List[ExtractedAnswer]).dump_python(answers),
            },
        )
        response.raise_for_status()

    def _make_api_url(self, endpoint_name: str) -> str:
        return f"https://{self._hostname}/api/b2s/{endpoint_name}"


# Main processing function
def process_notebook(
    notebook_path: str,
    output_pdf_path: Optional[str] = None,
    hostname: Optional[str] = None,
    token: Optional[str] = None,
    submit: bool = False,
) -> Dict[str, Any]:
    """
    Process an otter-formatted Jupyter notebook.

    Args:
        notebook_path: Path to the Jupyter notebook
        output_pdf_path: Optional path to save the PDF
        hostname: Pensieve server hostname (required if submit=True)
        token: Authentication token (required if submit=True)
        submit: Whether to submit to Pensieve server

    Returns:
        Dictionary with processing results including:
        - pdf: The rendered PDF as bytes
        - questions: List of parsed questions
        - page_indices: Page matching metadata
        - answers: Extracted answers
        - submission_id: ID if submitted to server
    """
    # Load notebook
    with open(notebook_path) as f:
        notebook = nbformat.read(f, as_version=4)

    # Parse questions
    parsed_notebook = parse_notebook(notebook)

    # Process each question
    notebook_slices = []
    answers = []

    for question in parsed_notebook.questions:
        # Slice notebook for this question
        notebook_slice = slice_notebook(notebook, question)
        notebook_slices.append(notebook_slice)

        # Extract answer
        answer = extract_answer(notebook_slice)
        answers.append(answer)

    # Render PDFs
    slice_pdfs = []
    page_indices = []
    current_page = 0

    for notebook_slice in notebook_slices:
        # Render this slice to PDF
        slice_pdf = render_notebook(notebook_slice)
        slice_pdfs.append(slice_pdf)

        # Track page indices
        reader = PdfReader(io.BytesIO(slice_pdf))
        num_pages = len(reader.pages)
        page_indices.append(list(range(current_page, current_page + num_pages)))
        current_page += num_pages

    # Merge PDFs
    final_pdf = merge_pdfs(slice_pdfs)

    # Save PDF if requested
    if output_pdf_path:
        with open(output_pdf_path, "wb") as f:
            f.write(final_pdf)

    result = {
        "pdf": final_pdf,
        "questions": parsed_notebook.questions,
        "page_indices": page_indices,
        "answers": answers,
    }

    # Submit to server if requested
    if submit:
        if not hostname or not token:
            raise ValueError("hostname and token required for submission")

        client = PensieveClient(hostname, token)
        submission_id = client.post_submission(final_pdf)
        client.post_submission_page_matching(submission_id, page_indices)
        client.post_submission_answers(submission_id, answers)
        result["submission_id"] = submission_id

    return result


# CLI interface
def main():
    parser = argparse.ArgumentParser(
        description="Process otter-formatted Jupyter notebooks"
    )
    parser.add_argument("notebook_path", help="Path to the Jupyter notebook to process")
    parser.add_argument("-o", "--output", help="Path to save the output PDF")
    parser.add_argument(
        "--submit", action="store_true", help="Submit to Pensieve server"
    )
    parser.add_argument(
        "--hostname", help="Pensieve server hostname (required if --submit)"
    )
    parser.add_argument("--token", help="Authentication token (required if --submit)")
    parser.add_argument(
        "--metadata",
        help="Save metadata (questions, page indices, answers) to JSON file",
    )

    args = parser.parse_args()

    # Process notebook
    result = process_notebook(
        args.notebook_path,
        output_pdf_path=args.output,
        hostname=args.hostname,
        token=args.token,
        submit=args.submit,
    )

    # Save metadata if requested
    if args.metadata:
        metadata = {
            "questions": [
                {
                    "begin": {
                        "cell_index": q.begin.cell_index,
                        "line_index": q.begin.line_index,
                    },
                    "end": {
                        "cell_index": q.end.cell_index,
                        "line_index": q.end.line_index,
                    },
                }
                for q in result["questions"]
            ],
            "page_indices": result["page_indices"],
            "answers": [
                {
                    "parts": [
                        {
                            "content_type": part.content_type,
                            "content": part.content
                            if part.content_type == "text"
                            else "base64_png_data",
                        }
                        for part in answer.parts
                    ]
                }
                for answer in result["answers"]
            ],
        }

        if "submission_id" in result:
            metadata["submission_id"] = result["submission_id"]

        with open(args.metadata, "w") as f:
            json.dump(metadata, f, indent=2)

    # Print summary
    print(f"Processed notebook: {args.notebook_path}")
    print(f"Found {len(result['questions'])} questions")
    if args.output:
        print(f"Saved PDF to: {args.output}")
    if args.submit:
        print(f"Submitted with ID: {result['submission_id']}")


if __name__ == "__main__":
    main()
