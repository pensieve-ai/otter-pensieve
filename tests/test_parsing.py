import os
from typing import cast
import unittest

import nbformat
from otter.utils import NBFORMAT_VERSION
from otter_pensieve.parsing import parse_notebook


tests_dir = os.path.dirname(__file__)


class TestParsing(unittest.TestCase):
    def test_submission_ipynb(self):
        with open(os.path.join(tests_dir, "submission.ipynb")) as notebook_file:
            notebook = cast(
                nbformat.NotebookNode,
                nbformat.read(notebook_file, as_version=NBFORMAT_VERSION),
            )
        parsed_notebook = parse_notebook(notebook)
        self.assertEqual(len(parsed_notebook.questions), 2)
        self.assertEqual(parsed_notebook.questions[0].begin.cell_index, 4)
        self.assertEqual(parsed_notebook.questions[0].begin.line_index, 0)
        self.assertEqual(parsed_notebook.questions[0].end.cell_index, 6)
        self.assertEqual(parsed_notebook.questions[0].end.line_index, 1)
        self.assertEqual(parsed_notebook.questions[1].begin.cell_index, 6)
        self.assertEqual(parsed_notebook.questions[1].begin.line_index, 2)
        self.assertEqual(parsed_notebook.questions[1].end.cell_index, 8)
        self.assertEqual(parsed_notebook.questions[1].end.line_index, 1)
