import io

from pypdf import PdfReader, PdfWriter


def merge_pdfs(pdfs: list[bytes]) -> bytes:
    writer = PdfWriter()
    for pdf in pdfs:
        stream = io.BytesIO(pdf)
        reader = PdfReader(stream)
        for page in reader.pages:
            _ = writer.add_page(page)
    stream = io.BytesIO()
    _ = writer.write(stream)
    return stream.getvalue()
