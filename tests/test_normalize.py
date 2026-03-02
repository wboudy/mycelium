"""
Tests for Normalize stage (stage 2/7, §6.1.1).

Acceptance Criteria:
- AC-1: URL source → canonicalized normalized_locator.
- AC-2: Pure function — identical inputs → byte-identical outputs.
- AC-3: Malformed input → ERR_NORMALIZATION_FAILED with stage="normalize".
- AC-4: extracted_metadata includes source_kind and source_ref.
"""

from __future__ import annotations

import pytest

from mycelium.stages.capture import RawSourcePayload
from mycelium.stages.normalize import (
    ERR_NORMALIZATION_FAILED,
    STAGE_NAME,
    NormalizedSource,
    normalize,
    _normalize_url_locator,
    _normalize_text,
)


# ---------------------------------------------------------------------------
# AC-1: URL → canonicalized normalized_locator
# ---------------------------------------------------------------------------

class TestUrlNormalization:
    """AC-1: URL source produces deterministic normalized_locator."""

    def test_url_source_produces_locator(self):
        payload = RawSourcePayload(
            text="Hello world",
            media_type="text/html",
            source_ref="https://Example.COM/page/",
            source_kind="url",
        )
        result, env = normalize(payload)
        assert result is not None
        assert env.ok is True
        assert result.normalized_locator == "https://example.com/page"

    def test_url_strips_fragment(self):
        loc = _normalize_url_locator("https://example.com/page#section")
        assert "#" not in loc

    def test_url_lowercases_host(self):
        loc = _normalize_url_locator("HTTPS://EXAMPLE.COM/Path")
        assert loc.startswith("https://example.com")

    def test_url_sorts_query_params(self):
        loc = _normalize_url_locator("https://example.com?b=2&a=1")
        assert "a=1&b=2" in loc

    def test_url_removes_trailing_slash(self):
        loc = _normalize_url_locator("https://example.com/page/")
        assert loc.endswith("/page")

    def test_url_root_keeps_slash(self):
        loc = _normalize_url_locator("https://example.com/")
        assert loc.endswith("/")

    def test_url_removes_default_https_port(self):
        loc = _normalize_url_locator("https://example.com:443/page")
        assert ":443" not in loc

    def test_url_removes_default_http_port(self):
        loc = _normalize_url_locator("http://example.com:80/page")
        assert ":80" not in loc


# ---------------------------------------------------------------------------
# AC-2: Pure function (determinism)
# ---------------------------------------------------------------------------

class TestDeterminism:
    """AC-2: Identical inputs → byte-identical outputs."""

    def test_same_payload_same_result(self):
        payload = RawSourcePayload(
            text="Deterministic content",
            media_type="text/plain",
            source_ref="https://example.com",
            source_kind="url",
        )
        r1, _ = normalize(payload)
        r2, _ = normalize(payload)
        assert r1 is not None and r2 is not None
        assert r1.normalized_text == r2.normalized_text
        assert r1.normalized_locator == r2.normalized_locator
        assert r1.source_kind == r2.source_kind
        assert r1.source_ref == r2.source_ref

    def test_repeated_normalize_identical(self):
        payload = RawSourcePayload(
            text="Some\r\ncontent\r\nhere",
            media_type="text/plain",
            source_ref="test",
            source_kind="text_bundle",
        )
        results = [normalize(payload)[0] for _ in range(5)]
        texts = [r.normalized_text for r in results if r]
        assert len(set(texts)) == 1


# ---------------------------------------------------------------------------
# AC-3: Malformed input → ERR_NORMALIZATION_FAILED
# ---------------------------------------------------------------------------

class TestMalformedInput:
    """AC-3: bad input returns ERR_NORMALIZATION_FAILED with stage='normalize'."""

    def test_no_text_no_bytes(self):
        payload = RawSourcePayload(
            media_type="text/plain",
            source_ref="test",
            source_kind="url",
        )
        result, env = normalize(payload)
        assert result is None
        assert env.ok is False
        assert len(env.errors) >= 1
        assert env.errors[0].code == ERR_NORMALIZATION_FAILED
        assert env.errors[0].stage == STAGE_NAME


# ---------------------------------------------------------------------------
# AC-4: extracted_metadata includes source_kind and source_ref
# ---------------------------------------------------------------------------

class TestExtractedMetadata:
    """AC-4: extracted_metadata passes through source_kind and source_ref."""

    def test_metadata_includes_source_kind(self):
        payload = RawSourcePayload(
            text="content",
            media_type="text/plain",
            source_ref="https://example.com",
            source_kind="url",
        )
        result, _ = normalize(payload)
        assert result is not None
        assert result.extracted_metadata["source_kind"] == "url"
        assert result.extracted_metadata["source_ref"] == "https://example.com"

    def test_metadata_includes_media_type(self):
        payload = RawSourcePayload(
            text="content",
            media_type="application/pdf",
            source_ref="/tmp/test.pdf",
            source_kind="pdf",
        )
        result, _ = normalize(payload)
        assert result.extracted_metadata["media_type"] == "application/pdf"


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

class TestTextNormalization:

    def test_strips_whitespace(self):
        assert _normalize_text("  hello  ") == "hello"

    def test_normalizes_crlf(self):
        assert _normalize_text("a\r\nb") == "a\nb"

    def test_collapses_blank_lines(self):
        result = _normalize_text("a\n\n\n\nb")
        assert result == "a\n\nb"

    def test_bytes_fallback(self):
        """When text is None, decodes raw_bytes."""
        payload = RawSourcePayload(
            raw_bytes=b"Hello bytes",
            media_type="text/plain",
            source_ref="test",
            source_kind="text_bundle",
        )
        result, env = normalize(payload)
        assert result is not None
        assert result.normalized_text == "Hello bytes"
        assert env.ok is True


# ---------------------------------------------------------------------------
# NormalizedSource to_dict
# ---------------------------------------------------------------------------

class TestNormalizedSourceDict:

    def test_to_dict(self):
        ns = NormalizedSource(
            normalized_text="hello",
            normalized_locator="https://example.com",
            source_kind="url",
            source_ref="https://example.com",
        )
        d = ns.to_dict()
        assert d["normalized_text_length"] == 5
        assert d["normalized_locator"] == "https://example.com"
        assert d["source_kind"] == "url"
