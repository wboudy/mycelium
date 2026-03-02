"""
Normalize stage — stage 2/7 of the ingestion pipeline (§6.1.1).

Input:  RawSourcePayload
Output: NormalizedSource { normalized_text, normalized_locator, source_kind,
        source_ref, extracted_metadata }
Side effects: None (pure transform).
Errors: ERR_NORMALIZATION_FAILED

Spec reference: mycelium_refactor_plan_apr_round5.md §6.1.1
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse, urlunparse

from mycelium.models import ErrorObject, OutputEnvelope, make_envelope
from mycelium.stages.capture import RawSourcePayload, SourceKind

STAGE_NAME = "normalize"

ERR_NORMALIZATION_FAILED = "ERR_NORMALIZATION_FAILED"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class NormalizedSource:
    """Output of the normalize stage.

    A pure-transform result containing cleaned text and a deterministic
    locator string for identity matching.
    """

    normalized_text: str
    normalized_locator: str
    source_kind: str
    source_ref: str
    extracted_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalized_text_length": len(self.normalized_text),
            "normalized_locator": self.normalized_locator,
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "extracted_metadata": self.extracted_metadata,
        }


# ---------------------------------------------------------------------------
# Normalization logic
# ---------------------------------------------------------------------------

def _normalize_url_locator(url: str) -> str:
    """Produce a deterministic locator from a URL.

    Strips fragments, lowercases scheme/host, removes trailing slashes,
    sorts query parameters.
    """
    parsed = urlparse(url)

    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove default ports
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    # Normalize path: remove trailing slash (unless root)
    path = parsed.path.rstrip("/") or "/"

    # Sort query parameters for determinism
    query = parsed.query
    if query:
        pairs = sorted(query.split("&"))
        query = "&".join(pairs)

    # Strip fragment
    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def _normalize_pdf_locator(pdf_path: str) -> str:
    """Produce a deterministic locator from a PDF path.

    Uses the resolved absolute path.
    """
    from pathlib import Path
    return str(Path(pdf_path).resolve())


def _normalize_text(raw_text: str) -> str:
    """Normalize raw text content.

    - Strip leading/trailing whitespace
    - Normalize line endings to LF
    - Collapse runs of 3+ blank lines to 2
    """
    text = raw_text.strip()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def normalize(payload: RawSourcePayload) -> tuple[NormalizedSource | None, OutputEnvelope]:
    """Execute the normalize stage (pure transform).

    Args:
        payload: A RawSourcePayload from the capture stage.

    Returns:
        Tuple of (normalized_source_or_none, envelope).
    """
    # Validate input
    if payload.text is None and payload.raw_bytes is None:
        return None, make_envelope(
            STAGE_NAME,
            errors=[ErrorObject(
                code=ERR_NORMALIZATION_FAILED,
                message="RawSourcePayload has neither text nor bytes",
                retryable=False,
                stage=STAGE_NAME,
            )],
        )

    # Get text content
    raw_text = payload.text
    if raw_text is None and payload.raw_bytes is not None:
        try:
            raw_text = payload.raw_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            return None, make_envelope(
                STAGE_NAME,
                errors=[ErrorObject(
                    code=ERR_NORMALIZATION_FAILED,
                    message=f"Failed to decode bytes: {e}",
                    retryable=False,
                    stage=STAGE_NAME,
                )],
            )

    assert raw_text is not None
    normalized_text = _normalize_text(raw_text)

    # Compute normalized locator
    source_kind = payload.source_kind
    source_ref = payload.source_ref

    try:
        if source_kind == SourceKind.URL.value:
            normalized_locator = _normalize_url_locator(source_ref)
        elif source_kind == SourceKind.PDF.value:
            normalized_locator = _normalize_pdf_locator(source_ref)
        elif source_kind == SourceKind.TEXT_BUNDLE.value:
            normalized_locator = f"text_bundle:{source_ref}"
        else:
            normalized_locator = source_ref
    except Exception as e:
        return None, make_envelope(
            STAGE_NAME,
            errors=[ErrorObject(
                code=ERR_NORMALIZATION_FAILED,
                message=f"Failed to normalize locator: {e}",
                retryable=False,
                stage=STAGE_NAME,
                details={"source_kind": source_kind, "source_ref": source_ref},
            )],
        )

    result = NormalizedSource(
        normalized_text=normalized_text,
        normalized_locator=normalized_locator,
        source_kind=source_kind,
        source_ref=source_ref,
        extracted_metadata={
            "source_kind": source_kind,
            "source_ref": source_ref,
            "media_type": payload.media_type,
        },
    )

    return result, make_envelope(STAGE_NAME, data=result.to_dict())
