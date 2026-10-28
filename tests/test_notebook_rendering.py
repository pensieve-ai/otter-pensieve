import io
import os
import unittest
from typing import cast
from unittest import mock

import nbconvert
import nbformat
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, ContentStream, NameObject


from tests.helpers import TESTS_DIR, load_submission_ipynb
from otter_pensieve.notebook_parsing import parse_notebook
from otter_pensieve.notebook_rendering import (
    MAX_RENDER_ATTEMPTS,
    BlankRenderError,
    LoadWaitingWebPDFExporter,
    is_blank_pdf,
    render_notebook,
)
from otter_pensieve.notebook_slicing import slice_notebook
from otter.export.exporters.base_exporter import TEMPLATE_DIR


def make_pdf(contents: list[bytes], annotated: bool = False) -> bytes:
    writer = PdfWriter()
    for content in contents:
        page = writer.add_blank_page(612, 792)
        stream = ContentStream(None, writer)
        stream.set_data(content)
        page.replace_contents(stream)
        if annotated:
            page[NameObject("/Annots")] = ArrayObject()
    output = io.BytesIO()
    _ = writer.write(output)
    return output.getvalue()


def load_first_slice() -> nbformat.NotebookNode:
    notebook = load_submission_ipynb()
    parsed_notebook = parse_notebook(notebook)
    return slice_notebook(notebook, parsed_notebook.questions[0])


class TestNotebookRendering(unittest.TestCase):
    def test_notebook_rendering(self):
        notebook_slice = load_first_slice()
        nbformat.validate(notebook_slice)
        notebook_slice_pdf = render_notebook(notebook_slice)
        self.assertFalse(is_blank_pdf(notebook_slice_pdf))
        with open(os.path.join(TESTS_DIR, "submission.pdf"), "wb") as output_file:
            _ = output_file.write(notebook_slice_pdf)

    def test_rendering_waits_for_load_when_main_thread_stalls(self):
        # Stall the main thread inside <head> after the blocking CDN scripts
        # have loaded, as CPU starvation does. Printing at `networkidle` alone
        # yields a blank page here.
        nbconvert.TemplateExporter.extra_template_basedirs = [str(TEMPLATE_DIR)]
        exporter = nbconvert.HTMLExporter(template_name="via_html")
        html, _ = nbconvert.export(exporter, load_first_slice())
        html = cast(str, html).replace(
            "</head>",
            "<script>var t = Date.now(); while (Date.now() - t < 1500) {}</script>"
            + "</head>",
            1,
        )
        pdf = LoadWaitingWebPDFExporter().run_playwright(html)
        self.assertFalse(is_blank_pdf(pdf))


class TestIsBlankPdf(unittest.TestCase):
    def test_page_without_contents_is_blank(self):
        writer = PdfWriter()
        _ = writer.add_blank_page(612, 792)
        output = io.BytesIO()
        _ = writer.write(output)
        self.assertTrue(is_blank_pdf(output.getvalue()))

    def test_empty_and_whitespace_contents_are_blank(self):
        self.assertTrue(is_blank_pdf(make_pdf([b"", b" \n\t"])))

    def test_page_that_draws_is_not_blank(self):
        self.assertFalse(is_blank_pdf(make_pdf([b"", b"0 0 10 10 re f"])))

    def test_page_with_annotations_is_not_blank(self):
        self.assertFalse(is_blank_pdf(make_pdf([b""], annotated=True)))


class TestRenderRetry(unittest.TestCase):
    blank_pdf = make_pdf([b""])
    drawn_pdf = make_pdf([b"0 0 10 10 re f"])

    def test_retries_blank_render(self):
        with mock.patch(
            "otter_pensieve.notebook_rendering._render_notebook_once",
            side_effect=[self.blank_pdf, self.drawn_pdf],
        ) as render_once:
            pdf = render_notebook(nbformat.v4.new_notebook())
        self.assertEqual(pdf, self.drawn_pdf)
        self.assertEqual(render_once.call_count, 2)

    def test_raises_when_every_render_is_blank(self):
        with mock.patch(
            "otter_pensieve.notebook_rendering._render_notebook_once",
            return_value=self.blank_pdf,
        ) as render_once:
            with self.assertRaises(BlankRenderError):
                _ = render_notebook(nbformat.v4.new_notebook())
        self.assertEqual(render_once.call_count, MAX_RENDER_ATTEMPTS)
