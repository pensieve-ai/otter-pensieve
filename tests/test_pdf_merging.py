import io
import os
import unittest

from pypdf import PdfReader

from otter_pensieve.notebook_parsing import parse_notebook
from otter_pensieve.notebook_rendering import render_notebook
from otter_pensieve.notebook_slicing import slice_notebook
from otter_pensieve.pdf_merging import merge_pdfs
from tests.helpers import TESTS_DIR, load_submission_ipynb


class TestPdfMerging(unittest.TestCase):
    def test_pdf_merging(self):
        notebook = load_submission_ipynb()
        parsed_notebook = parse_notebook(notebook)
        notebook_slices = [
            slice_notebook(notebook, question) for question in parsed_notebook.questions
        ]
        notebook_slice_pdfs = [
            render_notebook(notebook_slice) for notebook_slice in notebook_slices
        ]
        notebook_pdf = merge_pdfs(notebook_slice_pdfs)
        with open(os.path.join(TESTS_DIR, "submission.pdf"), "wb") as writer:
            _ = writer.write(notebook_pdf)
        with PdfReader(io.BytesIO(notebook_pdf)) as notebook_pdf_reader:
            total_notebook_slice_pdf_page_count = 0
            for notebook_slice_pdf in notebook_slice_pdfs:
                with PdfReader(
                    io.BytesIO(notebook_slice_pdf)
                ) as notebook_slice_pdf_reader:
                    total_notebook_slice_pdf_page_count += len(
                        notebook_slice_pdf_reader.pages
                    )
            self.assertEqual(
                total_notebook_slice_pdf_page_count, len(notebook_pdf_reader.pages)
            )
