import logging
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Union
from urllib.parse import urlparse

from otter.run import AutograderConfig
import requests
from otter.assign import Assignment
from otter.test_files import GradingResults
from pydantic import BaseModel
from typing_extensions import override

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


logger = logging.getLogger(__file__)


class PensieveOtterPluginConfig(BaseModel):
    use_submission_pdf: bool = False


class PensieveOtterPlugin(AbstractOtterPlugin):
    _autograder_config: Union[AutograderConfig, None]

    def __init__(
        self,
        submission_path: str,
        submission_metadata: dict[str, object],
        plugin_config: dict[str, object],
    ):
        super().__init__(submission_path, submission_metadata, plugin_config)
        _ = PensieveOtterPluginConfig.model_validate(plugin_config)
        self._autograder_config = None

    @override
    def during_generate(
        self, otter_config: dict[str, object], assignment: Assignment
    ) -> None:
        otter_config["pdf"] = True

    @override
    def before_grading(self, config: AutograderConfig) -> None:
        self._autograder_config = config

    @override
    def after_grading(self, results: GradingResults) -> None:
        print(
            r"""
 _____  ______ _   _  _____ _____ ______ _    _ ______ 
|  __ \|  ____| \ | |/ ____|_   _|  ____| |  | |  ____|
| |__) | |__  |  \| | (___   | | | |__  | |  | | |__   
|  ___/|  __| | . ` |\___ \  | | |  __| | |  | |  __|  
| |    | |____| |\  |____) |_| |_| |____ \ \/ /| |____ 
|_|    |______|_| \_|_____/|_____|______| \__/ |______|
""",
            end="\n\n",
        )
        if self._autograder_config is not None:
            print(repr(self._autograder_config))
        submission_url = os.getenv("SUBMISSION_URL")
        if submission_url is None:
            logger.warning("SUBMISSION_URL was None. Returning...")
            return
        pensieve_hostname = urlparse(submission_url).hostname
        pensieve_token_encoded = os.getenv("PENSIEVE_TOKEN")
        if pensieve_token_encoded is None:
            logger.warning("PENSIEVE_TOKEN was None. Returning...")
            return
        submission_pdf_path = os.path.splitext(self.submission_path)[0] + ".pdf"
        try:
            with open(submission_pdf_path, "rb") as f:
                submission_pdf_bytes = f.read()
        except BaseException:
            logger.warning("Failed to read Submission PDF. Returning...")
            return
        post_submission_response = requests.post(
            f"https://{pensieve_hostname}/api/b2s/v1/programming-assignment/associated-paper-assignment/submissions",
            headers={
                "Authorization": f"Bearer {pensieve_token_encoded}",
                "Content-Type": "application/octet-stream",
            },
            data=submission_pdf_bytes,
        )
        if not post_submission_response.ok:
            logger.error("Failed to upload submission to Pensieve.")
            logger.error(f"Response code: {post_submission_response.status_code}")
            logger.error(f"Response content: {post_submission_response.text}")
        print("Successfully submitted submission PDF to Pensieve!", end="\n\n")
