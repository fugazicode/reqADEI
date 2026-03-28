import io
from typing import Optional
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter, errors


def apply_watermark(pdf_bytes: bytes, text: str = "PREVIEW") -> bytes:
    """
    Overlay a tiled, rotated watermark text on every page of the input PDF.
    Returns the watermarked PDF as bytes. If input is not a valid PDF, returns original bytes.
    """
    # Create watermark overlay PDF in memory
    page_width, page_height = 595, 842  # A4 in points
    overlay = FPDF(unit="pt", format=[page_width, page_height])
    overlay.add_page()
    overlay.set_text_color(180, 180, 180)
    overlay.set_font("helvetica", size=36)

    # Tile the watermark text at 45°
    for x in range(0, page_width, 160):
        for y in range(0, page_height, 120):
            with overlay.rotation(45, x + 60, y + 30):
                overlay.text(x + 10, y + 60, text)

    buf = io.BytesIO()
    overlay.output(buf)
    buf.seek(0)

    try:
        watermark_reader = PdfReader(buf)
        watermark_page = watermark_reader.pages[0]
        src_reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        for page in src_reader.pages:
            page.merge_page(watermark_page)
            writer.add_page(page)
        out_buf = io.BytesIO()
        writer.write(out_buf)
        return out_buf.getvalue()
    except errors.PdfReadError:
        return pdf_bytes
    except Exception:
        return pdf_bytes
