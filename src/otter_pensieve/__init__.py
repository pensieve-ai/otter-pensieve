import copy
import io
import os
from abc import ABC
from typing import TYPE_CHECKING, Union, cast
from urllib.parse import urlparse

import nbformat
from otter.utils import NBFORMAT_VERSION
from pypdf import PdfReader
import requests
from otter.assign import Assignment
from otter.run import AutograderConfig
from otter.test_files import GradingResults
from typing_extensions import override

from otter_pensieve.answer_extraction import extract_answer
from otter_pensieve.client import Client
from otter_pensieve.notebook_parsing import parse_notebook
from otter_pensieve.notebook_rendering import render_notebook
from otter_pensieve.notebook_slicing import slice_notebook
from otter_pensieve.pdf_merging import merge_pdfs

if TYPE_CHECKING:

    class AbstractOtterPlugin(ABC):
        submission_path: str

        def __init__(
            self,
            submission_path: str,
            submission_metadata: dict[str, object],
            plugin_config: dict[str, object],
        ): ...

        def during_assign(self, assignment: Assignment) -> None: ...

        def during_generate(
            self, otter_config: dict[str, object], assignment: Assignment
        ) -> None: ...

        def before_grading(self, config: AutograderConfig) -> None: ...

        def after_grading(self, results: GradingResults) -> None: ...

else:
    from otter.plugins import AbstractOtterPlugin


class PensieveOtterPlugin(AbstractOtterPlugin):
    _autograder_config: Union[AutograderConfig, None]

    def __init__(
        self,
        submission_path: str,
        submission_metadata: dict[str, object],
        plugin_config: dict[str, object],
    ):
        super().__init__(submission_path, submission_metadata, plugin_config)
        self._autograder_config = None

    @override
    def before_grading(self, config: AutograderConfig) -> None:
        print(
            r"""
 _____  ______ _   _  _____ _____ ______ _    _ ______ 
|  __ \|  ____| \ | |/ ____|_   _|  ____| |  | |  ____|
| |__) | |__  |  \| | (___   | | | |__  | |  | | |__   
|  ___/|  __| | . ` |\___ \  | | |  __| | |  | |  __|  
| |    | |____| |\  |____) |_| |_| |____ \ \/ /| |____ 
|_|    |______|_| \_|_____/|_____|______| \__/ |______|
                                                 v1.5.0
""",
            end="\n\n",
        )
        submission_url = os.getenv("SUBMISSION_URL")
        if submission_url is None:
            print("SUBMISSION_URL is None. Returning...")
            return
        pensieve_hostname = urlparse(submission_url).hostname
        if pensieve_hostname is None:
            print("Failed to parse hostname from SUBMISSION_URL. Returning...")
            return
        pensieve_token = os.getenv("PENSIEVE_TOKEN")
        if pensieve_token is None:
            print("PENSIEVE_TOKEN is None. Returning...")
            return
        pensieve = Client(pensieve_hostname, pensieve_token)
        submission_files = os.listdir("./")
        submission_ipynb = None
        for submission_file in submission_files:
            if os.path.splitext(submission_file)[1] == ".ipynb":
                submission_ipynb = submission_file
                break
        if submission_ipynb is None:
            print("Failed to find submission ipynb. Returning...")
            return
        with open(submission_ipynb) as submission_reader:
            notebook = cast(
                nbformat.NotebookNode,
                nbformat.read(submission_reader, as_version=NBFORMAT_VERSION),
            )
        notebook = copy.deepcopy(notebook)
        parsed_notebook = parse_notebook(notebook)
        notebook_slices = [
            slice_notebook(notebook, question) for question in parsed_notebook.questions
        ]
        notebook_slice_pdfs = [
            render_notebook(notebook_slice) for notebook_slice in notebook_slices
        ]
        notebook_pdf = merge_pdfs(notebook_slice_pdfs)
        try:
            submission_id = pensieve.post_submission(notebook_pdf)
            print("Successfully submitted submission PDF to Pensieve!", end="\n\n")
        except requests.HTTPError as e:
            print("Failed to upload submission to Pensieve.")
            print(f"Response code: {e.response.status_code}")
            print(f"Response content: {e.response.text}")
            return
        page_indices = list[list[int]]()
        next_page_index = 0
        for notebook_slice_pdf in notebook_slice_pdfs:
            slice_page_indices = list[int]()
            for _ in range(len(PdfReader(io.BytesIO(notebook_slice_pdf)).pages)):
                slice_page_indices.append(next_page_index)
                next_page_index += 1
            page_indices.append(slice_page_indices)
        try:
            pensieve.post_submission_page_matching(submission_id, page_indices)
            print("Successfully matches questions with pages on Pensieve!", end="\n\n")
        except requests.HTTPError as e:
            print("Failed to match questions with pages on Pensieve.")
            print(f"Response code: {e.response.status_code}")
            print(f"Response content: {e.response.text}")
        answers = [extract_answer(notebook_slice) for notebook_slice in notebook_slices]
        try:
            pensieve.post_submission_answers(submission_id, answers)
            print("Successfully uploaded answers to Pensieve!", end="\n\n")
        except requests.HTTPError as e:
            print("Failed to match upload answers to Pensieve.")
            print("Answers will be processed with the regular pipeline.")
            print(f"Response code: {e.response.status_code}")
            print(f"Response content: {e.response.text}")
