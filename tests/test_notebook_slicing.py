import logging
from typing import cast
import unittest

import nbformat

from otter_pensieve.notebook_parsing import NotebookCellNode, parse_notebook
from otter_pensieve.notebook_slicing import slice_notebook
from tests.helpers import load_submission_ipynb


class TestNotebookSlicing(unittest.TestCase):
    def test_submission_ipynb(self):
        notebook = load_submission_ipynb()
        parsed_notebook = parse_notebook(notebook)
        notebook_slices = [
            slice_notebook(notebook, question) for question in parsed_notebook.questions
        ]
        for notebook_slice in notebook_slices:
            errors = False
            try:
                nbformat.validate(notebook_slice)
            except nbformat.ValidationError as e:
                logging.warning(e)
                errors = True
            self.assertFalse(errors)
        cells = [
            cast(list[NotebookCellNode], notebook_slice["cells"])
            for notebook_slice in notebook_slices
        ]
        self.assertEqual(len(cells[0]), 3)
        self.assertEqual(len(cells[0][0]["source"]), 5)
        self.assertEqual(len(cells[0][1]["source"]), 1)
        self.assertEqual(len(cells[0][2]["source"]), 1)
        self.assertEqual(len(cells[1]), 3)
        self.assertEqual(len(cells[1][0]["source"]), 5)
        self.assertEqual(len(cells[1][1]["source"]), 1)
        self.assertEqual(len(cells[1][2]["source"]), 1)
