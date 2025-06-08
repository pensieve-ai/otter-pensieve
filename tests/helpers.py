import os
from typing import cast

import nbformat
from otter.utils import NBFORMAT_VERSION


TESTS_DIR = os.path.dirname(__file__)


def load_submission_ipynb() -> nbformat.NotebookNode:
    with open(os.path.join(TESTS_DIR, "submission.ipynb")) as notebook_file:
        return cast(
            nbformat.NotebookNode,
            nbformat.read(notebook_file, as_version=NBFORMAT_VERSION),
        )
