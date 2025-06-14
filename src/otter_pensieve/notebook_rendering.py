from typing import cast
import nbformat

from otter.export.exporters.base_exporter import TEMPLATE_DIR


def render_notebook(notebook: nbformat.NotebookNode) -> bytes:
    import nbconvert

    nbconvert.TemplateExporter.extra_template_basedirs = [str(TEMPLATE_DIR)]
    orig_template_name = nbconvert.TemplateExporter.template_name
    nbconvert.TemplateExporter.template_name = "via_latex_xecjk"
    try:
        exporter = cast(nbconvert.PDFExporter, nbconvert.PDFExporter())
        pdf, _ = nbconvert.export(exporter, notebook)
    finally:
        nbconvert.TemplateExporter.template_name = orig_template_name
    return cast(bytes, pdf)
