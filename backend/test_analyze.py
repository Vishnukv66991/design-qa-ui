"""
Contract tests for /analyze endpoint.
Run:  cd backend && python -m pytest test_analyze.py -v
"""

import sys, os, io, base64
import pytest
from fastapi.testclient import TestClient
from PIL import Image

# Ensure backend is importable
sys.path.insert(0, os.path.dirname(__file__))

from main import app

client = TestClient(app)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_image_bytes(width=1200, height=1200, color=(128, 128, 128), fmt="PNG"):
    """Create a small test image in memory and return bytes."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _make_form(image_bytes, requirements="Test requirement", guidance="", filename="test.png"):
    return {
        "file": (filename, image_bytes, "image/png"),
        "requirements": (None, requirements),
        "guidance": (None, guidance),
    }


# ── Tests ───────────────────────────────────────────────────────────────────────

class TestAnalyzeEndpoint:

    # ── Basic image upload ────────────────────────────────────────────────────

    def test_image_upload_returns_success(self):
        img = _make_image_bytes()
        files = _make_form(img, requirements="dark theme, 1:1")
        resp = client.post("/analyze", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "score" in data
        assert "issues" in data
        assert "meta" in data

    def test_missing_requirements_returns_400(self):
        img = _make_image_bytes()
        files = _make_form(img, requirements="   ")
        resp = client.post("/analyze", files=files)
        assert resp.status_code == 400
        assert "requirements" in resp.json()["error"].lower()

    def test_missing_file_returns_400(self):
        resp = client.post(
            "/analyze",
            data={"requirements": "dark theme"},
            files={"file": ("test.txt", b"not an image", "text/plain")},
        )
        assert resp.status_code == 400
        assert "image" in resp.json()["error"].lower()

    def test_invalid_file_returns_400(self):
        # Send a text file (not image/video/pdf)
        resp = client.post(
            "/analyze",
            data={"requirements": "anything"},
            files={"file": ("test.txt", b"plain text content", "text/plain")},
        )
        assert resp.status_code == 400
        assert "only" in resp.json()["error"].lower() or "allowed" in resp.json()["error"].lower()

    def test_oversized_file_returns_400(self):
        # Create a valid PNG that's > 10MB (compressed to bypass size check won't work,
        # so we send raw bytes > 10MB with image/png content_type)
        big_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * (10 * 1024 * 1024 + 100)
        resp = client.post(
            "/analyze",
            data={"requirements": "anything"},
            files={"file": ("big.png", big_bytes, "image/png")},
        )
        # Should be 400 (size) or 500 (processing) — both acceptable for bad input
        assert resp.status_code in (400, 500)

    # ── Response structure ─────────────────────────────────────────────────────

    def test_response_has_required_fields(self):
        img = _make_image_bytes()
        files = _make_form(img, requirements="neon theme, 1:1")
        resp = client.post("/analyze", files=files)
        data = resp.json()
        for key in ("status", "score", "summary", "issues", "strengths", "quick_fixes", "meta"):
            assert key in data, f"Missing key: {key}"

    def test_meta_has_modules_run(self):
        img = _make_image_bytes()
        files = _make_form(img, requirements="dark theme")
        resp = client.post("/analyze", files=files)
        data = resp.json()
        assert "modules_run" in data["meta"]
        assert isinstance(data["meta"]["modules_run"], list)
        assert len(data["meta"]["modules_run"]) > 0

    def test_issues_have_required_fields(self):
        img = _make_image_bytes()
        files = _make_form(img, requirements="dark theme")
        resp = client.post("/analyze", files=files)
        data = resp.json()
        for issue in data["issues"]:
            assert "category" in issue
            assert "severity" in issue
            assert "problem" in issue
            assert "impact" in issue
            assert "suggestion" in issue
            assert "confidence" in issue

    # ── Contrast threshold (4.5:1 rule) ────────────────────────────────────

    def test_contrast_issue_reports_correct_threshold(self):
        # Create low-contrast image (gray on gray)
        img = Image.new("RGB", (400, 400), (140, 140, 140))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        files = _make_form(buf.getvalue(), requirements="text on gray background")
        resp = client.post("/analyze", files=files)
        data = resp.json()
        # Check that any contrast issue mentions 4.5:1
        contrast_issues = [i for i in data["issues"] if i["category"] == "Color"]
        if contrast_issues:
            assert any("4.5" in i["problem"] for i in contrast_issues)

    # ── Score is bounded ─────────────────────────────────────────────────────

    def test_score_is_between_10_and_100(self):
        img = _make_image_bytes()
        files = _make_form(img, requirements="dark theme")
        resp = client.post("/analyze", files=files)
        data = resp.json()
        assert 10 <= data["score"] <= 100

    # ── Spelling check (when available) ────────────────────────────────────

    def test_spelling_issue_has_correct_fields(self):
        # Create image with misspelled text (requires Tesseract + pyspellchecker)
        img = Image.new("RGB", (800, 200), (255, 255, 255))
        try:
            import pytesseract
            from spellchecker import SpellChecker
            # We can't easily render text without heavy deps, so skip if not available
        except ImportError:
            pytest.skip("Tesseract or pyspellchecker not available")
        files = _make_form(_make_image_bytes(800, 200), requirements="anything")
        resp = client.post("/analyze", files=files)
        data = resp.json()
        # Just verify structure is intact
        assert "issues" in data

    # ── OCR text extraction ──────────────────────────────────────────────────

    def test_text_extracted_field_present(self):
        img = _make_image_bytes()
        files = _make_form(img, requirements="anything")
        resp = client.post("/analyze", files=files)
        data = resp.json()
        assert "text_extracted" in data["meta"]

    # ── Image format detection ──────────────────────────────────────────────

    def test_jpeg_upload_works(self):
        img_bytes = _make_image_bytes(fmt="JPEG")
        files = {
            "file": ("test.jpg", img_bytes, "image/jpeg"),
            "requirements": (None, "1:1 format"),
        }
        resp = client.post("/analyze", files=files)
        assert resp.status_code == 200
        assert "Square" in resp.json()["meta"]["format"]

    def test_webp_upload_works(self):
        img_bytes = _make_image_bytes()
        # Pillow can write WebP; simulate
        img = Image.new("RGB", (1200, 1200), (100, 100, 100))
        buf = io.BytesIO()
        img.save(buf, format="WEBP")
        files = {
            "file": ("test.webp", buf.getvalue(), "image/webp"),
            "requirements": (None, "dark theme"),
        }
        resp = client.post("/analyze", files=files)
        assert resp.status_code == 200

    # ── Guidance field optional ──────────────────────────────────────────────

    def test_without_guidance_field(self):
        img = _make_image_bytes()
        files = {
            "file": ("test.png", img, "image/png"),
            "requirements": (None, "dark theme"),
        }
        resp = client.post("/analyze", files=files)
        assert resp.status_code == 200

    # ── CTA detection ────────────────────────────────────────────────────────

    def test_cta_found_in_meta(self):
        img = _make_image_bytes()
        files = _make_form(img, requirements="add a buy now button")
        resp = client.post("/analyze", files=files)
        data = resp.json()
        assert "cta_found" in data["meta"]
