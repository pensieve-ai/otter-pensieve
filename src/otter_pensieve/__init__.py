import logging
import os
from abc import ABC
from typing import TYPE_CHECKING, Union
from urllib.parse import urlparse

import requests
from otter.assign import Assignment
from otter.run import AutograderConfig
from otter.test_files import GradingResults
from pydantic import BaseModel
from typing_extensions import override

from otter_pensieve.client import Client

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
            logger.warning("SUBMISSION_URL is None. Returning...")
            return
        pensieve_hostname = urlparse(submission_url).hostname
        if pensieve_hostname is None:
            logger.warning("Failed to parse hostname from SUBMISSION_URL. Returning...")
            return
        pensieve_token = os.getenv("PENSIEVE_TOKEN")
        if pensieve_token is None:
            logger.warning("PENSIEVE_TOKEN is None. Returning...")
            return
        pensieve = Client(pensieve_hostname, pensieve_token)
        submission_pdf_path = os.path.splitext(self.submission_path)[0] + ".pdf"
        try:
            with open(submission_pdf_path, "rb") as f:
                submission_pdf_bytes = f.read()
        except BaseException:
            logger.warning("Failed to read Submission PDF. Returning...")
            return
        try:
            _ = pensieve.post_submission(submission_pdf_bytes)
        except requests.HTTPError as e:
            logger.error("Failed to upload submission to Pensieve.")
            logger.error(f"Response code: {e.response.status_code}")
            logger.error(f"Response content: {e.response.text}")
            return
        print("Successfully submitted submission PDF to Pensieve!", end="\n\n")
