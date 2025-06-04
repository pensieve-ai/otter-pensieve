from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from typing_extensions import override
from otter.test_files import GradingResults

if TYPE_CHECKING:

    class AbstractOtterPlugin(ABC):
        def __init__(
            self,
            submission_path: str,
            submission_metadata: dict[str, object],
            plugin_config: dict[str, object],
        ): ...

        @abstractmethod
        def after_grading(self, results: GradingResults) -> None: ...

else:
    from otter.plugins import AbstractOtterPlugin


class PensieveOtterPlugin(AbstractOtterPlugin):
    def __init__(
        self,
        submission_path: str,
        submission_metadata: dict[str, object],
        plugin_config: dict[str, object],
    ):
        super().__init__(submission_path, submission_metadata, plugin_config)

    @override
    def after_grading(self, results: GradingResults):
        print(
            r"""
 _____  ______ _   _  _____ _____ ______ _    _ ______ 
|  __ \|  ____| \ | |/ ____|_   _|  ____| |  | |  ____|
| |__) | |__  |  \| | (___   | | | |__  | |  | | |__   
|  ___/|  __| | . ` |\___ \  | | |  __| | |  | |  __|  
| |    | |____| |\  |____) |_| |_| |____ \ \/ /| |____ 
|_|    |______|_| \_|_____/|_____|______| \__/ |______|
"""
        )
