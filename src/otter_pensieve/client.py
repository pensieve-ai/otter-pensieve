from pydantic import BaseModel, TypeAdapter
import requests

from otter_pensieve.answer_extraction import ExtractedAnswer


class _PostSubmissionResponseBody(BaseModel):
    submission_id: str


class Client:
    _hostname: str
    _token: str

    def __init__(self, hostname: str, token: str):
        self._hostname = hostname
        self._token = token

    def post_submission(self, submission_pdf: bytes) -> str:
        """
        Upload a PDF as a submission and return the created submission's id.
        """
        response = requests.post(
            self._make_api_url(
                "v1/programming-assignment/associated-paper-assignment/submissions"
            ),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/octet-stream",
            },
            data=submission_pdf,
        )
        response.raise_for_status()
        return _PostSubmissionResponseBody.model_validate_json(
            response.content
        ).submission_id

    def post_submission_page_matching(
        self, submission_id: str, page_indices: list[list[int]]
    ) -> None:
        """
        Update the page matching of a submission created by `post_submission`.
        """
        response = requests.post(
            self._make_api_url(
                "v1/programming-assignment/associated-paper-assignment/submission-page-matchings"
            ),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            json={"submission_id": submission_id, "page_indices": page_indices},
        )
        response.raise_for_status()

    def post_submission_answers(
        self, submission_id: str, answers: list[ExtractedAnswer]
    ) -> None:
        """
        Update the page matching of a submission created by `post_submission`.
        """
        response = requests.post(
            self._make_api_url(
                "v1/programming-assignment/associated-paper-assignment/submission-answers"
            ),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            json={
                "submission_id": submission_id,
                "answers": TypeAdapter(list[ExtractedAnswer]).dump_python(answers),
            },
        )
        response.raise_for_status()

    def _make_api_url(self, endpoint_name: str) -> str:
        return f"https://{self._hostname}/api/b2s/{endpoint_name}"
