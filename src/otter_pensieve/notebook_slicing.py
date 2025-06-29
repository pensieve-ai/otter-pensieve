import copy
from typing import cast

import nbformat

from otter_pensieve.notebook_parsing import (
    NotebookCellNode,
    ParsedQuestion,
    get_cell_source_as_list,
)


def slice_notebook(notebook: nbformat.NotebookNode, question: ParsedQuestion):
    retval = nbformat.v4.new_notebook()
    retval_cells = cast(list[NotebookCellNode], retval["cells"])
    notebook_cells = cast(list[NotebookCellNode], notebook["cells"])
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
            else len(notebook_cells[cell_index]["source"])
        )
        retval_cells.append(
            {
                **copy.deepcopy(cell),
                "source": "".join(cell_source[begin_line_index:end_line_index]),
            }
        )
    return cast(nbformat.NotebookNode, nbformat.from_dict(retval))
