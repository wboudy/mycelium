"""
Capture stage — stage 1/7 of the ingestion pipeline (§6.1.1).

Input:  Source input (url / pdf_path / id / text_bundle)
Output: RawSourcePayload { bytes|text, media_type, source_ref, source_kind }
Errors: ERR_CAPTURE_FAILED, ERR_UNSUPPORTED_SOURCE

Spec reference: mycelium_refactor_plan_apr_round5.md §6.1.1
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mycelium.models import ErrorObject, OutputEnvelope, error_envelope, make_envelope

STAGE_NAME = "capture"


# ---------------------------------------------------------------------------
# Source kinds (§4.2.2)
# ---------------------------------------------------------------------------

class SourceKind(enum.Enum):
    URL = "url"
    PDF = "pdf"
    DOI = "doi"
    ARXIV = "arxiv"
    HIGHLIGHTS = "highlights"
    BOOK = "book"
    TEXT_BUNDLE = "text_bundle"


# MVP1 supported kinds
_SUPPORTED_KINDS = {SourceKind.URL, SourceKind.PDF, SourceKind.TEXT_BUNDLE}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SourceInput:
    """Input to the capture stage.

    Exactly one of url, pdf_path, or text_bundle must be provided.
    """

    url: str | None = None
    pdf_path: str | None = None
    text_bundle: str | None = None
    source_id: str | None = None

    @property
    def source_kind(self) -> SourceKind | None:
        if self.url is not None:
            return SourceKind.URL
        if self.pdf_path is not None:
            return SourceKind.PDF
        if self.text_bundle is not None:
            return SourceKind.TEXT_BUNDLE
        return None


@dataclass
class RawSourcePayload:
    """Output of the capture stage.

    Contains either text or raw bytes from the source, along with metadata.
    """

    text: str | None = None
    raw_bytes: bytes | None = None
    media_type: str = "text/plain"
    source_ref: str = ""
    source_kind: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "media_type": self.media_type,
            "source_ref": self.source_ref,
            "source_kind": self.source_kind,
        }
        if self.text is not None:
            d["text_length"] = len(self.text)
            d["has_text"] = True
        if self.raw_bytes is not None:
            d["bytes_length"] = len(self.raw_bytes)
            d["has_bytes"] = True
        return d


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

ERR_CAPTURE_FAILED = "ERR_CAPTURE_FAILED"
ERR_UNSUPPORTED_SOURCE = "ERR_UNSUPPORTED_SOURCE"


# ---------------------------------------------------------------------------
# Capture implementations
# ---------------------------------------------------------------------------

def _capture_url(source_input: SourceInput) -> RawSourcePayload | ErrorObject:
    """Capture content from a URL."""
    url = source_input.url
    assert url is not None

    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "text/html")
            raw = resp.read()
            # Determine encoding
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].split(";")[0].strip()
            text = raw.decode(charset, errors="replace")
            media_type = content_type.split(";")[0].strip()

        return RawSourcePayload(
            text=text,
            raw_bytes=raw,
            media_type=media_type,
            source_ref=url,
            source_kind=SourceKind.URL.value,
        )
    except Exception as e:
        return ErrorObject(
            code=ERR_CAPTURE_FAILED,
            message=f"Failed to capture URL: {e}",
            retryable=True,
            stage=STAGE_NAME,
            details={"url": url},
        )


def _capture_pdf(source_input: SourceInput) -> RawSourcePayload | ErrorObject:
    """Capture content from a local PDF file."""
    pdf_path = source_input.pdf_path
    assert pdf_path is not None

    path = Path(pdf_path)
    if not path.exists():
        return ErrorObject(
            code=ERR_CAPTURE_FAILED,
            message=f"PDF file not found: {pdf_path}",
            retryable=False,
            stage=STAGE_NAME,
            details={"pdf_path": pdf_path},
        )

    try:
        raw = path.read_bytes()
        return RawSourcePayload(
            raw_bytes=raw,
            media_type="application/pdf",
            source_ref=str(path.resolve()),
            source_kind=SourceKind.PDF.value,
        )
    except Exception as e:
        return ErrorObject(
            code=ERR_CAPTURE_FAILED,
            message=f"Failed to read PDF: {e}",
            retryable=False,
            stage=STAGE_NAME,
            details={"pdf_path": pdf_path},
        )


def _capture_text_bundle(source_input: SourceInput) -> RawSourcePayload | ErrorObject:
    """Capture content from a direct text bundle."""
    text = source_input.text_bundle
    assert text is not None

    if not text.strip():
        return ErrorObject(
            code=ERR_CAPTURE_FAILED,
            message="Text bundle is empty",
            retryable=False,
            stage=STAGE_NAME,
        )

    return RawSourcePayload(
        text=text,
        media_type="text/plain",
        source_ref=source_input.source_id or "text_bundle",
        source_kind=SourceKind.TEXT_BUNDLE.value,
    )


# ---------------------------------------------------------------------------
# Main capture function
# ---------------------------------------------------------------------------

def capture(source_input: SourceInput) -> tuple[RawSourcePayload | None, OutputEnvelope]:
    """Execute the capture stage.

    Args:
        source_input: The source to capture.

    Returns:
        Tuple of (payload_or_none, envelope).
        On success, payload is a RawSourcePayload and envelope.ok is True.
        On failure, payload is None and envelope contains the error.
    """
    kind = source_input.source_kind

    if kind is None:
        return None, error_envelope(
            STAGE_NAME,
            ERR_UNSUPPORTED_SOURCE,
            "No source input provided (url, pdf_path, or text_bundle required)",
            stage=STAGE_NAME,
        )

    if kind not in _SUPPORTED_KINDS:
        return None, error_envelope(
            STAGE_NAME,
            ERR_UNSUPPORTED_SOURCE,
            f"Source kind '{kind.value}' is not supported in MVP1",
            stage=STAGE_NAME,
            details={"source_kind": kind.value},
        )

    # Dispatch to handler
    handlers = {
        SourceKind.URL: _capture_url,
        SourceKind.PDF: _capture_pdf,
        SourceKind.TEXT_BUNDLE: _capture_text_bundle,
    }

    handler = handlers[kind]
    result = handler(source_input)

    if isinstance(result, ErrorObject):
        return None, make_envelope(
            STAGE_NAME,
            errors=[result],
        )

    # Success
    return result, make_envelope(
        STAGE_NAME,
        data=result.to_dict(),
    )
