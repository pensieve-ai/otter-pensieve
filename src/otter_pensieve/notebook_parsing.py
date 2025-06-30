from dataclasses import dataclass
import re
from typing import Literal, Union, cast
from typing_extensions import NotRequired, TypedDict
import nbformat


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
    questions: list[ParsedQuestion]


class NotebookCellOutputNode(TypedDict):
    data: NotRequired[dict[str, Union[str, list[str]]]]
    text: NotRequired[Union[str, list[str]]]
    traceback: NotRequired[Union[str, list[str]]]


class NotebookCellNode(TypedDict):
    cell_type: Literal["markdown", "code", "raw"]
    metadata: NotRequired[dict[str, object]]
    source: Union[str, list[str]]
    outputs: NotRequired[list[NotebookCellOutputNode]]


_BEGIN_QUESTION_PATTERN = re.compile(r"<!--\s*BEGIN QUESTION\s*-->")
_END_QUESTION_PATTERN = re.compile(r"<!--\s*END QUESTION\s*-->")


def parse_notebook(notebook: nbformat.NotebookNode) -> ParsedNotebook:
    questions = list[ParsedQuestion]()
    current_question: Union[ParsedQuestion, None] = None
    for cell_index, cell in enumerate(cast(list[NotebookCellNode], notebook["cells"])):
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
        current_question = None
    return ParsedNotebook(questions)


def get_cell_source_as_list(cell: NotebookCellNode) -> list[str]:
    source = cell["source"]
    if isinstance(source, str):
        return source.splitlines(keepends=True)
    else:
        return source


def get_cell_source_as_str(cell: NotebookCellNode) -> str:
    return "".join(get_cell_source_as_list(cell))
