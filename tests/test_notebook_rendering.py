import os
import unittest

import nbformat


from tests.helpers import TESTS_DIR, load_submission_ipynb
from otter_pensieve.notebook_parsing import parse_notebook
from otter_pensieve.notebook_rendering import render_notebook
from otter_pensieve.notebook_slicing import slice_notebook


class TestNotebookRendering(unittest.TestCase):
    def test_notebook_rendering(self):
        notebook = load_submission_ipynb()
        parsed_notebook = parse_notebook(notebook)
        notebook_slice = slice_notebook(notebook, parsed_notebook.questions[0])
        nbformat.validate(notebook_slice)
        notebook_slice_pdf = render_notebook(notebook_slice)
        with open(os.path.join(TESTS_DIR, "submission.pdf"), "wb") as output_file:
            _ = output_file.write(notebook_slice_pdf)
