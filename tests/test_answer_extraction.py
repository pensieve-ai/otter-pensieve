import unittest

from otter_pensieve.answer_extraction import extract_answer
from otter_pensieve.notebook_parsing import parse_notebook
from otter_pensieve.notebook_slicing import slice_notebook
from tests.helpers import load_submission_ipynb


class TestAnswerExtraction(unittest.TestCase):
    def test_answer_extraction(self):
        notebook = load_submission_ipynb()
        parsed_notebook = parse_notebook(notebook)
        notebook_slice = slice_notebook(notebook, parsed_notebook.questions[0])
        answer_parts = extract_answer(notebook_slice)
        self.assertEqual(len(answer_parts), 1)
        self.assertEqual(answer_parts[0].content_type, "text")
        self.assertEqual(
            answer_parts[0].content.strip(),
            """
 _Type your answer here, replacing this text._
""".strip(),
        )
