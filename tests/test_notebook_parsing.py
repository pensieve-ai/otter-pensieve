import unittest

from otter_pensieve.notebook_parsing import parse_notebook
from tests.helpers import load_submission_ipynb


class TestNotebookParsing(unittest.TestCase):
    def test_submission_ipynb(self):
        notebook = load_submission_ipynb()
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
