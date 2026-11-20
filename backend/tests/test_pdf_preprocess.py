"""Unit tests for PDF 300-DPI & contrast preprocessing and Gemini wiring."""
from __future__ import annotations

import builtins
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app import config
from app.extract import gemini_extract, pdf_preprocess


def _block_imports(monkeypatch, blocked: set[str]) -> None:
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        top = name.split(".")[0]
        if top in blocked:
            raise ImportError(f"Blocked import for test: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


def _sample_invoice_payload() -> dict:
    return {
        "vendor": {"name": "Sunbeam Electricals Pvt Ltd", "tax_id": None},
        "invoice": {
            "number": "INV-MP-01",
            "date": "2026-11-15",
            "currency": "INR",
            "po_reference": "PO-1006",
            "payment_terms": "Net 30",
        },
        "lines": [
            {
                "item": "LED Panel 18W",
                "quantity": 10.0,
                "unit_price": 420.0,
                "tax_pct": 18.0,
                "line_total": 4956.0,
            }
        ],
        "totals": {"subtotal": 4200.0, "tax": 756.0, "grand_total": 4956.0},
    }


def test_preprocess_image_bytes_passthrough_without_pil(monkeypatch):
    _block_imports(monkeypatch, {"PIL"})
    raw = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
    assert pdf_preprocess.preprocess_image_bytes(raw) == raw


def test_preprocess_image_bytes_exif_and_autocontrast_with_mock_pil(monkeypatch):
    calls: list[tuple] = []

    class FakeImageObj:
        def __init__(self, mode="RGBA"):
            self.mode = mode

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def convert(self, target_mode):
            calls.append(("convert", target_mode))
            return FakeImageObj(mode=target_mode)

        def save(self, buf, format="PNG"):
            calls.append(("save", format, self.mode))
            buf.write(b"\x89PNG\r\n\x1a\nprocessed")

    fake_image_mod = SimpleNamespace(open=lambda buf: FakeImageObj(mode="RGBA"))
    fake_ops_mod = SimpleNamespace(
        exif_transpose=lambda img: (calls.append(("exif_transpose",)), img)[1],
        autocontrast=lambda img, cutoff=0: (calls.append(("autocontrast", cutoff)), img)[1],
    )
    fake_pil = ModuleType("PIL")
    fake_pil.Image = fake_image_mod
    fake_pil.ImageOps = fake_ops_mod
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_image_mod)
    monkeypatch.setitem(sys.modules, "PIL.ImageOps", fake_ops_mod)

    out_contrast = pdf_preprocess.preprocess_image_bytes(b"raw-img", enhance_contrast=True)
    assert out_contrast == b"\x89PNG\r\n\x1a\nprocessed"
    assert ("exif_transpose",) in calls
    assert ("convert", "RGB") in calls
    assert ("autocontrast", 1) in calls
    assert ("save", "PNG", "RGB") in calls

    calls.clear()
    out_no_contrast = pdf_preprocess.preprocess_image_bytes(b"raw-img", enhance_contrast=False)
    assert out_no_contrast == b"\x89PNG\r\n\x1a\nprocessed"
    assert ("autocontrast", 1) not in calls


def test_preprocess_image_bytes_corrupt_bytes_graceful_fallback(monkeypatch):
    def _boom(_buf):
        raise OSError("cannot identify image file")

    fake_image_mod = SimpleNamespace(open=_boom)
    fake_ops_mod = SimpleNamespace()
    fake_pil = ModuleType("PIL")
    fake_pil.Image = fake_image_mod
    fake_pil.ImageOps = fake_ops_mod
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_image_mod)
    monkeypatch.setitem(sys.modules, "PIL.ImageOps", fake_ops_mod)

    corrupt = b"not-an-image-at-all"
    assert pdf_preprocess.preprocess_image_bytes(corrupt) == corrupt


def test_render_pdf_fallback_when_no_renderer_installed(monkeypatch, tmp_path):
    _block_imports(monkeypatch, {"pypdfium2", "fitz"})
    pdf_path = tmp_path / "doc.pdf"
    pdf_bytes = b"%PDF-1.4\n%sample"
    pdf_path.write_bytes(pdf_bytes)

    assert pdf_preprocess.render_pdf_to_png_pages(pdf_path, fallback_empty=True) == []
    with pytest.raises(RuntimeError, match="PDF renderer not installed"):
        pdf_preprocess.render_pdf_to_png_pages(pdf_path, fallback_empty=False)

    parts = pdf_preprocess.prepare_document_parts(pdf_path, "application/pdf")
    assert parts == [(pdf_bytes, "application/pdf")]


def test_prepare_document_parts_multipage_pdf_and_image(monkeypatch, tmp_path):
    pdf_path = tmp_path / "multipage.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(
        pdf_preprocess,
        "render_pdf_to_png_pages",
        lambda path, dpi=300, fallback_empty=True: [b"png-page-1", b"png-page-2"],
    )
    parts = pdf_preprocess.prepare_document_parts(pdf_path, "application/pdf", dpi=300)
    assert parts == [(b"png-page-1", "image/png"), (b"png-page-2", "image/png")]

    img_path = tmp_path / "scan.jpg"
    img_path.write_bytes(b"raw-jpg")
    monkeypatch.setattr(
        pdf_preprocess,
        "preprocess_image_bytes",
        lambda raw, enhance_contrast=True: b"clean-png",
    )
    img_parts = pdf_preprocess.prepare_document_parts(img_path, "image/jpeg")
    assert img_parts == [(b"clean-png", "image/png")]


def test_gemini_extract_integration_uses_multipage_parts(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_extract, "has_live_ai_credentials", lambda: True)

    pdf_path = tmp_path / "two_page.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(
        gemini_extract,
        "prepare_document_parts",
        lambda path, mime_type, dpi=300: [
            (b"page-1-png", "image/png"),
            (b"page-2-png", "image/png"),
        ],
    )

    recorded: dict = {}

    def fake_generate(
        file_bytes,
        mime_type,
        schema,
        model_name,
        retry_feedback=None,
        temperature=0.0,
        parts=None,
    ):
        recorded["file_bytes"] = file_bytes
        recorded["mime_type"] = mime_type
        recorded["parts"] = parts
        recorded["model_name"] = model_name
        return _sample_invoice_payload()

    monkeypatch.setattr(gemini_extract, "_generate_with_model", fake_generate)

    res = gemini_extract.extract_document(pdf_path, "invoices")
    assert res["mode"] == "gemini_live"
    assert res["needs_review"] is False
    assert recorded["parts"] == [(b"page-1-png", "image/png"), (b"page-2-png", "image/png")]
    assert res["records"][0]["invoice_number"] == "INV-MP-01"
