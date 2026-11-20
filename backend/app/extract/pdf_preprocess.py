"""PDF 300-DPI rasterization and image contrast preprocessing for Gemini extraction.

Optional dependencies (`Pillow`, `pypdfium2`, `fitz`/PyMuPDF) are imported lazily
so offline environments and minimal installs degrade gracefully without crashing.
"""
from __future__ import annotations

import io
from pathlib import Path


def preprocess_image_bytes(raw_bytes: bytes, enhance_contrast: bool = True) -> bytes:
    """Auto-orient, normalize mode, and optionally autocontrast image bytes to PNG.

    Returns ``raw_bytes`` unchanged if ``Pillow`` is not installed or the input
    bytes cannot be decoded as an image.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return raw_bytes

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                img = img.convert("L" if img.mode == "LA" else "RGB")
            if enhance_contrast:
                img = ImageOps.autocontrast(img, cutoff=1)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except Exception:
        return raw_bytes


def render_pdf_to_png_pages(
    pdf_path: Path,
    dpi: int = 300,
    max_pages: int = 10,
    enhance_contrast: bool = True,
    fallback_empty: bool = True,
) -> list[bytes]:
    """Render up to ``max_pages`` of ``pdf_path`` at ``dpi`` into preprocessed PNGs.

    Uses ``pypdfium2`` or ``fitz`` (PyMuPDF) when installed. If neither renderer
    is available, returns ``[]`` when ``fallback_empty=True`` or raises
    ``RuntimeError("PDF renderer not installed")`` otherwise.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError:
        pdfium = None

    if pdfium is not None:
        try:
            doc = pdfium.PdfDocument(str(pdf_path))
            try:
                scale = dpi / 72.0
                pages: list[bytes] = []
                for idx in range(min(len(doc), max_pages)):
                    page = doc[idx]
                    try:
                        bitmap = page.render(scale=scale)
                        pil_img = bitmap.to_pil()
                        buf = io.BytesIO()
                        pil_img.save(buf, format="PNG")
                        pages.append(
                            preprocess_image_bytes(
                                buf.getvalue(), enhance_contrast=enhance_contrast
                            )
                        )
                    finally:
                        if hasattr(page, "close"):
                            page.close()
                return pages
            finally:
                if hasattr(doc, "close"):
                    doc.close()
        except Exception:
            if fallback_empty:
                return []
            raise

    try:
        import fitz
    except ImportError:
        fitz = None

    if fitz is not None:
        try:
            doc = fitz.open(str(pdf_path))
            try:
                zoom = dpi / 72.0
                matrix = fitz.Matrix(zoom, zoom)
                pages = []
                for idx in range(min(len(doc), max_pages)):
                    pix = doc[idx].get_pixmap(matrix=matrix)
                    png_bytes = pix.tobytes("png")
                    pages.append(
                        preprocess_image_bytes(
                            png_bytes, enhance_contrast=enhance_contrast
                        )
                    )
                return pages
            finally:
                if hasattr(doc, "close"):
                    doc.close()
        except Exception:
            if fallback_empty:
                return []
            raise

    if fallback_empty:
        return []
    raise RuntimeError("PDF renderer not installed")


def prepare_document_parts(
    file_path: Path,
    mime_type: str,
    dpi: int = 300,
) -> list[tuple[bytes, str]]:
    """Prepare ``(bytes, mime_type)`` parts for live Gemini multimodal requests."""
    if mime_type.startswith("image/"):
        return [(preprocess_image_bytes(file_path.read_bytes()), "image/png")]
    if mime_type == "application/pdf":
        pages = render_pdf_to_png_pages(file_path, dpi=dpi, fallback_empty=True)
        if pages:
            return [(page_bytes, "image/png") for page_bytes in pages]
        return [(file_path.read_bytes(), "application/pdf")]
    return [(file_path.read_bytes(), mime_type)]
