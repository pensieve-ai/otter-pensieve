import asyncio
import concurrent.futures
import inspect
import io
import os
import subprocess
import sys
import tempfile
from typing import Any, Callable, cast

import nbconvert
import nbformat
from otter.export.exporters.base_exporter import TEMPLATE_DIR
from pypdf import PdfReader
from typing_extensions import override

MAX_RENDER_ATTEMPTS = 3


class BlankRenderError(Exception):
    pass


def _has_known_run_playwright_signature() -> bool:
    run_playwright = cast(
        Callable[..., object], getattr(nbconvert.WebPDFExporter, "run_playwright")
    )
    return list(inspect.signature(run_playwright).parameters) == ["self", "html"]


class LoadWaitingWebPDFExporter(nbconvert.WebPDFExporter):
    """
    `WebPDFExporter` that waits for the page's `load` event before printing.

    nbconvert only waits for `networkidle`, which fires 500ms after the last
    request finishes rather than after the document is parsed. Otter's template
    has a large `<head>` of blocking CDN scripts in front of the body, so when
    the main thread stalls (e.g. CPU starvation in the autograder container),
    Chromium prints the document before it reaches `<body>` and produces a
    blank page.
    """

    @override
    def run_playwright(self, html: str) -> bytes:
        if not _has_known_run_playwright_signature():
            return cast(bytes, super().run_playwright(html))

        # Copied from nbconvert 7.17.2 `WebPDFExporter.run_playwright`, plus the
        # `wait_for_load_state("load")` after `goto`.
        async def main(temp_file_name: str) -> bytes:
            try:
                from playwright.async_api import async_playwright
            except ModuleNotFoundError as e:
                msg = (
                    "Playwright is not installed to support Web PDF conversion. "
                    "Please install `nbconvert[webpdf]` to enable."
                )
                raise RuntimeError(msg) from e

            if self.allow_chromium_download:
                cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
                _ = subprocess.check_call(cmd)

            playwright = await async_playwright().start()
            chromium = playwright.chromium

            args = list(cast(list[str], getattr(self, "browser_args", [])))
            if self.disable_sandbox:
                args.append("--no-sandbox")

            try:
                browser = await chromium.launch(
                    handle_sigint=False,
                    handle_sigterm=False,
                    handle_sighup=False,
                    args=args,
                )
            except Exception as e:
                msg = (
                    "No suitable chromium executable found on the system. "
                    "Please use '--allow-chromium-download' to allow downloading one,"
                    "or install it using `playwright install chromium`."
                )
                await playwright.stop()
                raise RuntimeError(msg) from e

            page = await browser.new_page()
            await page.emulate_media(media="print")
            await page.wait_for_timeout(100)
            _ = await page.goto(f"file://{temp_file_name}", wait_until="networkidle")
            await page.wait_for_load_state("load")
            await page.wait_for_timeout(getattr(self, "page_render_timeout", 100))

            pdf_params: dict[str, Any] = {"print_background": True}
            if not self.paginate:
                # Floating point precision errors cause the printed
                # PDF from spilling over a new page by a pixel fraction.
                dimensions = cast(
                    dict[str, int],
                    await page.evaluate("""() => {
                        const rect = document.body.getBoundingClientRect();
                        return {
                        width: Math.ceil(rect.width) + 1,
                        height: Math.ceil(rect.height) + 1,
                        }
                    }"""),
                )
                # 200 inches is the maximum size for Adobe Acrobat Reader.
                pdf_params["width"] = min(dimensions["width"], 200 * 72)
                pdf_params["height"] = min(dimensions["height"], 200 * 72)
            pdf_data = await page.pdf(**pdf_params)

            await browser.close()
            await playwright.stop()
            return pdf_data

        # Chromium can't open a file another process holds open on Windows, so
        # close the temporary file before rendering and delete it afterwards.
        temp_file = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
        with temp_file:
            _ = temp_file.write(html.encode("utf-8"))
        try:
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, main(temp_file.name)).result()
        finally:
            os.unlink(temp_file.name)


def is_blank_pdf(pdf: bytes) -> bool:
    """
    Whether no page of the PDF draws anything: every page has an empty (or
    whitespace-only) content stream and no annotations.
    """
    for page in PdfReader(io.BytesIO(pdf)).pages:
        if "/Annots" in page:
            return False
        contents = page.get_contents()
        if contents is not None and contents.get_data().strip():
            return False
    return True


def _render_notebook_once(notebook: nbformat.NotebookNode) -> bytes:
    nbconvert.TemplateExporter.extra_template_basedirs = [str(TEMPLATE_DIR)]
    orig_template_name = nbconvert.TemplateExporter.template_name
    nbconvert.TemplateExporter.template_name = "via_html"
    try:
        exporter = LoadWaitingWebPDFExporter()
        pdf, _ = nbconvert.export(exporter, notebook)
    finally:
        nbconvert.TemplateExporter.template_name = orig_template_name
    return cast(bytes, pdf)


def render_notebook(notebook: nbformat.NotebookNode) -> bytes:
    """
    Render the notebook to PDF, retrying blank renders. Raises
    `BlankRenderError` if every attempt is blank.
    """
    for attempt in range(1, MAX_RENDER_ATTEMPTS + 1):
        pdf = _render_notebook_once(notebook)
        if not is_blank_pdf(pdf):
            return pdf
        print(f"Rendered PDF is blank (attempt {attempt}/{MAX_RENDER_ATTEMPTS}).")
    raise BlankRenderError(
        f"Rendered PDF was blank after {MAX_RENDER_ATTEMPTS} attempts."
    )
