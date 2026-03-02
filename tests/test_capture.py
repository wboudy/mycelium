"""
Tests for Capture stage (stage 1/7, §6.1.1).

Acceptance Criteria:
- AC-1: URL input → RawSourcePayload with text, media_type, source_kind="url".
- AC-2: PDF path → RawSourcePayload with source_kind="pdf".
- AC-3: Unsupported source → ERR_UNSUPPORTED_SOURCE.
- AC-4: Network/IO failure → ERR_CAPTURE_FAILED with stage="capture".
- AC-5: Cache entries in Draft Scope only (not Canonical Scope).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mycelium.stages.capture import (
    ERR_CAPTURE_FAILED,
    ERR_SSRF_BLOCKED,
    ERR_UNSUPPORTED_SOURCE,
    STAGE_NAME,
    RawSourcePayload,
    SourceInput,
    SourceKind,
    _MAX_RESPONSE_BYTES,
    _validate_url,
    capture,
)


# ---------------------------------------------------------------------------
# AC-1: URL source → correct payload
# ---------------------------------------------------------------------------

class TestCaptureUrl:
    """AC-1: URL input produces RawSourcePayload with source_kind='url'."""

    def test_url_success(self):
        """Mocked URL fetch returns valid payload."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html>Hello</html>"
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("mycelium.stages.capture._is_private_ip", return_value=False):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                payload, env = capture(SourceInput(url="https://example.com"))

        assert payload is not None
        assert payload.source_kind == "url"
        assert payload.text is not None
        assert len(payload.text) > 0
        assert payload.media_type == "text/html"
        assert payload.source_ref == "https://example.com"
        assert env.ok is True

    def test_url_envelope_has_data(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"content"
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("mycelium.stages.capture._is_private_ip", return_value=False):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                payload, env = capture(SourceInput(url="https://example.com"))

        d = env.to_dict()
        assert d["ok"] is True
        assert d["command"] == STAGE_NAME
        assert d["data"]["source_kind"] == "url"
        assert d["data"]["has_text"] is True


# ---------------------------------------------------------------------------
# AC-2: PDF path → correct payload
# ---------------------------------------------------------------------------

class TestCapturePdf:
    """AC-2: PDF path produces RawSourcePayload with source_kind='pdf'."""

    def test_pdf_success(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 fake pdf content")
            f.flush()
            pdf_path = f.name

        try:
            payload, env = capture(SourceInput(pdf_path=pdf_path))
            assert payload is not None
            assert payload.source_kind == "pdf"
            assert payload.raw_bytes is not None
            assert payload.media_type == "application/pdf"
            assert env.ok is True
        finally:
            Path(pdf_path).unlink()

    def test_pdf_not_found(self):
        payload, env = capture(SourceInput(pdf_path="/nonexistent/file.pdf"))
        assert payload is None
        assert env.ok is False
        assert len(env.errors) >= 1
        assert env.errors[0].code == ERR_CAPTURE_FAILED
        assert env.errors[0].stage == STAGE_NAME


# ---------------------------------------------------------------------------
# AC-3: Unsupported source → ERR_UNSUPPORTED_SOURCE
# ---------------------------------------------------------------------------

class TestUnsupportedSource:
    """AC-3: unsupported source type returns structured error."""

    def test_no_input(self):
        """Empty SourceInput → error."""
        payload, env = capture(SourceInput())
        assert payload is None
        assert env.ok is False
        assert env.errors[0].code == ERR_UNSUPPORTED_SOURCE

    def test_unsupported_kind_in_error(self):
        """SourceInput with no recognized fields → ERR_UNSUPPORTED_SOURCE."""
        payload, env = capture(SourceInput())
        assert env.errors[0].stage == STAGE_NAME


# ---------------------------------------------------------------------------
# AC-4: Network/IO failure → ERR_CAPTURE_FAILED with stage="capture"
# ---------------------------------------------------------------------------

class TestCaptureFailure:
    """AC-4: failures return ERR_CAPTURE_FAILED with stage='capture'."""

    def test_url_network_error(self):
        with patch("mycelium.stages.capture._is_private_ip", return_value=False):
            with patch(
                "urllib.request.urlopen",
                side_effect=ConnectionError("Network down"),
            ):
                payload, env = capture(SourceInput(url="https://unreachable.example.com"))

        assert payload is None
        assert env.ok is False
        assert env.errors[0].code == ERR_CAPTURE_FAILED
        assert env.errors[0].stage == STAGE_NAME
        assert env.errors[0].retryable is True

    def test_url_timeout(self):
        with patch("mycelium.stages.capture._is_private_ip", return_value=False):
            with patch(
                "urllib.request.urlopen",
                side_effect=TimeoutError("Timed out"),
            ):
                payload, env = capture(SourceInput(url="https://slow.example.com"))

        assert payload is None
        assert env.ok is False
        assert env.errors[0].code == ERR_CAPTURE_FAILED
        assert env.errors[0].stage == STAGE_NAME

    def test_empty_text_bundle(self):
        payload, env = capture(SourceInput(text_bundle="   "))
        assert payload is None
        assert env.ok is False
        assert env.errors[0].code == ERR_CAPTURE_FAILED


# ---------------------------------------------------------------------------
# AC-5: Draft Scope only (no canonical writes)
# ---------------------------------------------------------------------------

class TestDraftScopeOnly:
    """AC-5: capture does not write to Canonical Scope."""

    def test_text_bundle_no_filesystem_writes(self):
        """text_bundle capture produces payload without filesystem side effects."""
        payload, env = capture(SourceInput(text_bundle="Some interesting claim about AI."))
        assert payload is not None
        assert payload.source_kind == "text_bundle"
        assert payload.text == "Some interesting claim about AI."
        assert env.ok is True
        # No filesystem paths modified — this is a pure in-memory transform


# ---------------------------------------------------------------------------
# SourceInput and SourceKind
# ---------------------------------------------------------------------------

class TestSourceInput:

    def test_url_kind(self):
        si = SourceInput(url="https://example.com")
        assert si.source_kind == SourceKind.URL

    def test_pdf_kind(self):
        si = SourceInput(pdf_path="/tmp/test.pdf")
        assert si.source_kind == SourceKind.PDF

    def test_text_bundle_kind(self):
        si = SourceInput(text_bundle="hello")
        assert si.source_kind == SourceKind.TEXT_BUNDLE

    def test_empty_kind(self):
        si = SourceInput()
        assert si.source_kind is None


class TestRawSourcePayload:

    def test_to_dict_text(self):
        p = RawSourcePayload(text="hello", media_type="text/plain", source_ref="ref", source_kind="url")
        d = p.to_dict()
        assert d["has_text"] is True
        assert d["text_length"] == 5
        assert d["source_kind"] == "url"

    def test_to_dict_bytes(self):
        p = RawSourcePayload(raw_bytes=b"pdf", media_type="application/pdf", source_ref="ref", source_kind="pdf")
        d = p.to_dict()
        assert d["has_bytes"] is True
        assert d["bytes_length"] == 3


class TestSourceKindEnum:

    def test_all_kinds(self):
        expected = {"url", "pdf", "doi", "arxiv", "highlights", "book", "text_bundle"}
        actual = {sk.value for sk in SourceKind}
        assert actual == expected


# ---------------------------------------------------------------------------
# SSRF Protection (bd-21p)
# ---------------------------------------------------------------------------

class TestSSRFProtection:
    """SSRF protection: scheme allowlist, host blocklist, size cap."""

    def test_blocks_file_scheme(self):
        err = _validate_url("file:///etc/passwd")
        assert err is not None
        assert err.code == ERR_SSRF_BLOCKED
        assert "file" in err.message

    def test_blocks_ftp_scheme(self):
        err = _validate_url("ftp://evil.com/data")
        assert err is not None
        assert err.code == ERR_SSRF_BLOCKED

    def test_blocks_gopher_scheme(self):
        err = _validate_url("gopher://evil.com")
        assert err is not None
        assert err.code == ERR_SSRF_BLOCKED

    def test_allows_https(self):
        with patch("mycelium.stages.capture._is_private_ip", return_value=False):
            err = _validate_url("https://example.com/page")
        assert err is None

    def test_allows_http(self):
        with patch("mycelium.stages.capture._is_private_ip", return_value=False):
            err = _validate_url("http://example.com/page")
        assert err is None

    def test_blocks_localhost(self):
        err = _validate_url("http://127.0.0.1/admin")
        assert err is not None
        assert err.code == ERR_SSRF_BLOCKED
        assert "private" in err.message.lower()

    def test_blocks_private_10_network(self):
        err = _validate_url("http://10.0.0.1/internal")
        assert err is not None
        assert err.code == ERR_SSRF_BLOCKED

    def test_blocks_metadata_endpoint(self):
        err = _validate_url("http://169.254.169.254/latest/meta-data/")
        assert err is not None
        assert err.code == ERR_SSRF_BLOCKED

    def test_blocks_no_hostname(self):
        err = _validate_url("http://")
        assert err is not None
        assert err.code == ERR_SSRF_BLOCKED

    def test_capture_url_blocks_ssrf(self):
        """Integration: capture() rejects SSRF URLs."""
        payload, env = capture(SourceInput(url="file:///etc/shadow"))
        assert payload is None
        assert env.ok is False
        assert env.errors[0].code == ERR_SSRF_BLOCKED

    def test_capture_url_blocks_private_ip(self):
        payload, env = capture(SourceInput(url="http://127.0.0.1:8080/secret"))
        assert payload is None
        assert env.ok is False
        assert env.errors[0].code == ERR_SSRF_BLOCKED

    def test_size_cap_enforced(self):
        """Response exceeding size cap is rejected."""
        oversized_data = b"X" * (_MAX_RESPONSE_BYTES + 1)
        mock_resp = MagicMock()
        mock_resp.read.return_value = oversized_data
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("mycelium.stages.capture._is_private_ip", return_value=False):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                payload, env = capture(SourceInput(url="https://example.com/huge"))

        assert payload is None
        assert env.ok is False
        assert env.errors[0].code == ERR_CAPTURE_FAILED
        assert "size cap" in env.errors[0].message.lower()
