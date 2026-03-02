"""
Ingest command contract (CMD-ING-001, CMD-ING-002).

Primary entry point for the ingestion pipeline. Creates Source Notes,
Extraction Bundles, and Delta Reports. Returns self-consistent
idempotency records.

Spec reference: §5.2.1 CMD-ING-001, CMD-ING-002
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mycelium.models import (
    ErrorObject,
    OutputEnvelope,
    PlannedOperation,
    WarningObject,
    dry_run_envelope,
    make_envelope,
)


# ─── Error codes ──────────────────────────────────────────────────────────

ERR_INVALID_INPUT = "ERR_INVALID_INPUT"
ERR_UNSUPPORTED_SOURCE = "ERR_UNSUPPORTED_SOURCE"
ERR_CAPTURE_FAILED = "ERR_CAPTURE_FAILED"
ERR_NORMALIZATION_FAILED = "ERR_NORMALIZATION_FAILED"
ERR_EXTRACTION_FAILED = "ERR_EXTRACTION_FAILED"
ERR_SCHEMA_VALIDATION = "ERR_SCHEMA_VALIDATION"
ERR_CORRUPTED_NOTE = "ERR_CORRUPTED_NOTE"
ERR_CANON_WRITE_FORBIDDEN = "ERR_CANON_WRITE_FORBIDDEN"


# ─── Input models ─────────────────────────────────────────────────────────

SOURCE_INPUT_FIELDS = ("url", "pdf_path", "id", "text_bundle")


@dataclass
class IngestInput:
    """Validated input for the ingest command."""
    # Source (exactly one must be provided)
    url: str | None = None
    pdf_path: str | None = None
    id: str | None = None
    text_bundle: dict[str, Any] | None = None
    # Optional flags
    why_saved: str | None = None
    tags: list[str] = field(default_factory=list)
    strict: bool = False
    dry_run: bool = False

    @property
    def source_type(self) -> str:
        """Return the type of source input provided."""
        if self.url is not None:
            return "url"
        if self.pdf_path is not None:
            return "pdf_path"
        if self.id is not None:
            return "id"
        if self.text_bundle is not None:
            return "text_bundle"
        return "unknown"


# ─── Output models ────────────────────────────────────────────────────────

@dataclass
class IdempotencyRecord:
    """Self-consistent idempotency record (CMD-ING-002).

    AC-CMD-ING-002-1: normalized_locator matches Source Note and Delta Report.
    AC-CMD-ING-002-2: fingerprint matches Source Note and Delta Report.
    AC-CMD-ING-002-3: prior_fingerprint matches Delta Report when non-null.
    """
    normalized_locator: str
    fingerprint: str
    reused_source_id: bool
    prior_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalized_locator": self.normalized_locator,
            "fingerprint": self.fingerprint,
            "reused_source_id": self.reused_source_id,
            "prior_fingerprint": self.prior_fingerprint,
        }


# ─── Validation ───────────────────────────────────────────────────────────

def validate_ingest_input(raw: dict[str, Any]) -> IngestInput | ErrorObject:
    """Validate raw input dict into IngestInput.

    Returns IngestInput on success, ErrorObject on validation failure.
    """
    # Exactly one source input required
    source_count = sum(
        1 for f in SOURCE_INPUT_FIELDS if raw.get(f) is not None
    )
    if source_count == 0:
        return ErrorObject(
            code=ERR_INVALID_INPUT,
            message=(
                "One of url, pdf_path, id, or text_bundle is required"
            ),
            retryable=False,
        )
    if source_count > 1:
        return ErrorObject(
            code=ERR_INVALID_INPUT,
            message=(
                "Provide exactly one of url, pdf_path, id, or text_bundle"
            ),
            retryable=False,
        )

    # Validate tags
    tags = raw.get("tags", [])
    if not isinstance(tags, list):
        return ErrorObject(
            code=ERR_INVALID_INPUT,
            message="tags must be an array of strings",
            retryable=False,
        )

    # Validate text_bundle if provided
    text_bundle = raw.get("text_bundle")
    if text_bundle is not None and not isinstance(text_bundle, dict):
        return ErrorObject(
            code=ERR_INVALID_INPUT,
            message="text_bundle must be an object",
            retryable=False,
        )

    return IngestInput(
        url=raw.get("url"),
        pdf_path=raw.get("pdf_path"),
        id=raw.get("id"),
        text_bundle=text_bundle,
        why_saved=raw.get("why_saved"),
        tags=tags,
        strict=bool(raw.get("strict", False)),
        dry_run=bool(raw.get("dry_run", False)),
    )


def execute_ingest(raw_input: dict[str, Any]) -> OutputEnvelope:
    """Execute the ingest command contract.

    This implements the command contract layer. Actual pipeline execution
    is delegated to the ingestion pipeline module (§6) during integration.

    Args:
        raw_input: Raw command input dict.

    Returns:
        OutputEnvelope with ingest results.
    """
    result = validate_ingest_input(raw_input)
    if isinstance(result, ErrorObject):
        return make_envelope("ingest", errors=[result])

    ingest_input = result

    # Dry run: return planned writes without filesystem mutations
    if ingest_input.dry_run:
        return dry_run_envelope("ingest", planned_writes=[])

    # Full execution contract structure
    return make_envelope(
        "ingest",
        data={
            "run_id": "",
            "source_id": "",
            "source_note_path": "",
            "delta_report_path": "",
            "review_queue_item_paths": [],
            "artifact_paths": [],
            "idempotency": IdempotencyRecord(
                normalized_locator="",
                fingerprint="",
                reused_source_id=False,
            ).to_dict(),
        },
    )
