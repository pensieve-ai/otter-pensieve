import io
from dataclasses import dataclass
from typing import Literal, Union, cast

import nbformat
from pydantic import BaseModel
from strip_ansi import strip_ansi

from otter_pensieve.notebook_parsing import NotebookCellNode, get_cell_source_as_str

ExtractedAnswerContentType = Literal["text", "png"]


class ExtractedAnswerPart(BaseModel):
    content_type: ExtractedAnswerContentType
    content: str


class ExtractedAnswer(BaseModel):
    parts: list[ExtractedAnswerPart]


def extract_answer(notebook: nbformat.NotebookNode) -> ExtractedAnswer:
    all_cells = cast(list[NotebookCellNode], notebook["cells"])
    answer_cells = [cell for cell in all_cells if _is_otter_answer_cell(cell)]
    retval_parts = list[ExtractedAnswerPart]()
    for cell in answer_cells:
        with io.StringIO() as writer:
            cell_source = get_cell_source_as_str(cell).splitlines()
            if cell["cell_type"] == "code":
                _ = writer.write("`In:`\n\n```python\n")
            for line in cell_source:
                _ = writer.write(line)
                _ = writer.write("\n")
            if cell["cell_type"] == "code":
                _ = writer.write("```")
            retval_parts.append(
                ExtractedAnswerPart(content_type="text", content=writer.getvalue())
            )
        if (cell_outputs := cell.get("outputs")) is not None:
            for cell_output in cell_outputs:
                with io.StringIO() as writer:
                    if (output_data := cell_output.get("data")) is not None:
                        if (
                            png_data := cast(
                                Union[str, None], output_data.get("image/png")
                            )
                        ) is not None:
                            retval_parts.append(
                                ExtractedAnswerPart(
                                    content_type="png", content=png_data
                                )
                            )
                        elif (text_data := output_data.get("text/plain")) is not None:
                            with io.StringIO() as writer:
                                _ = writer.write("`Out:`\n\n```text\n")
                                if isinstance(text_data, str):
                                    _ = writer.write(text_data)
                                    ends_with_newline = text_data.endswith("\n")
                                else:
                                    for line in text_data:
                                        _ = writer.write(line)
                                    ends_with_newline = text_data[-1].endswith("\n")
                                if not ends_with_newline:
                                    _ = writer.write("\n")
                                _ = writer.write("```")
                                retval_parts.append(
                                    ExtractedAnswerPart(
                                        content_type="text", content=writer.getvalue()
                                    )
                                )
                    if (output_text := cell_output.get("text")) is not None:
                        _ = writer.write("`Out:`\n\n```text\n")
                        if isinstance(output_text, str):
                            _ = writer.write(output_text)
                            ends_with_newline = output_text.endswith("\n")
                        else:
                            for line in output_text:
                                _ = writer.write(line)
                            ends_with_newline = output_text[-1].endswith("\n")
                        if not ends_with_newline:
                            _ = writer.write("\n")
                        _ = writer.write("```")
                        retval_parts.append(
                            ExtractedAnswerPart(
                                content_type="text", content=writer.getvalue()
                            )
                        )
                    if (output_traceback := cell_output.get("traceback")) is not None:
                        _ = writer.write("`Out:`\n\n```text\n")
                        if isinstance(output_traceback, str):
                            _ = writer.write(strip_ansi(output_traceback))
                            ends_with_newline = output_traceback.endswith("\n")
                        else:
                            for line in output_traceback:
                                _ = writer.write(strip_ansi(line))
                                _ = writer.write("\n")
                            ends_with_newline = True
                        if not ends_with_newline:
                            _ = writer.write("\n")
                        _ = writer.write("```")
                        retval_parts.append(
                            ExtractedAnswerPart(
                                content_type="text", content=writer.getvalue()
                            )
                        )
    return ExtractedAnswer(parts=retval_parts)


def _is_otter_answer_cell(cell: NotebookCellNode) -> bool:
    cell_metadata = cell.get("metadata")
    if cell_metadata is not None:
        cell_tags = cast(Union[list[str], None], cell_metadata.get("tags"))
        if cell_tags is not None and "otter_answer_cell" in cell_tags:
            return True
    return False
