"""Stage-scoped pipeline error types with deterministic codes (ERR-001).

Pipeline failures MUST be explicit, stage-scoped, and recoverable without
manual deletion of Canonical Scope files.

Each error carries:
- A deterministic error code (e.g., ERR_CAPTURE_FAILED)
- The pipeline stage name where the failure occurred (§6.1.2)
- Whether the error is retryable

Spec reference: mycelium_refactor_plan_apr_round5.md §10.1 (ERR-001),
                §6.1.2 (PIPE-003 Stage Names),
                §5.1 (ErrorObject)
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from mycelium.models import ErrorObject


# ── Canonical Stage Names (PIPE-003, §6.1.2) ─────────────────────────────

class StageName(str, Enum):
    """Canonical pipeline stage names per §6.1.2.

    Errors and audit records that reference a stage MUST use one of these.
    """
    CAPTURE = "capture"
    NORMALIZE = "normalize"
    FINGERPRINT = "fingerprint"
    EXTRACT = "extract"
    COMPARE = "compare"
    DELTA = "delta"
    PROPOSE_QUEUE = "propose_queue"


VALID_STAGE_NAMES = frozenset(s.value for s in StageName)


# ── Error code registry ──────────────────────────────────────────────────

# Deterministic error codes from the spec (§5.2 command contracts)
# Each code maps to: (default_retryable, typical_stage_or_None)

ERROR_CODES: dict[str, tuple[bool, str | None]] = {
    # Ingestion errors (§5.2.1)
    "ERR_INVALID_INPUT": (False, None),
    "ERR_UNSUPPORTED_SOURCE": (False, StageName.CAPTURE.value),
    "ERR_CAPTURE_FAILED": (True, StageName.CAPTURE.value),
    "ERR_NORMALIZATION_FAILED": (False, StageName.NORMALIZE.value),
    "ERR_EXTRACTION_FAILED": (True, StageName.EXTRACT.value),
    "ERR_SCHEMA_VALIDATION": (False, None),
    "ERR_CORRUPTED_NOTE": (False, None),
    # Scope protection
    "ERR_CANON_WRITE_FORBIDDEN": (False, None),
    # Delta/review errors (§5.2.2, §5.2.3)
    "ERR_SOURCE_NOT_FOUND": (False, None),
    "ERR_DELTA_NOT_FOUND": (False, None),
    "ERR_QUEUE_ITEM_INVALID": (False, None),
    "ERR_QUEUE_IMMUTABLE": (False, None),
    "ERR_REVIEW_DECISION_INVALID": (False, None),
    # Digest errors (§5.2.4)
    "ERR_REVIEW_DIGEST_EMPTY": (False, None),
    # Graduate/promote errors (§5.2.5)
    "ERR_PROVENANCE_MISSING": (False, None),
    "ERR_PROMOTION_CONFLICT": (False, None),
    # Context errors (§5.2.6)
    "ERR_CONTEXT_EMPTY": (False, None),
    # Frontier errors (§5.2.7)
    "ERR_NO_FRONTIER_DATA": (False, None),
}


# ── Pipeline error class ────────────────────────────────────────────────

class PipelineError(Exception):
    """Stage-scoped pipeline error (ERR-001).

    Carries a deterministic code, the failing stage name, retryability,
    and optional details. Can be converted to an ErrorObject for inclusion
    in an OutputEnvelope.

    Attributes:
        code: Deterministic error code (e.g., ERR_CAPTURE_FAILED).
        stage: Pipeline stage name where the failure occurred.
        retryable: Whether the caller can retry the operation.
        details: Optional additional context.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        stage: str | None = None,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        # Validate stage name if provided
        if stage is not None and stage not in VALID_STAGE_NAMES:
            raise ValueError(
                f"Invalid stage name: {stage!r}. "
                f"Must be one of: {sorted(VALID_STAGE_NAMES)}"
            )

        self.code = code
        self.stage = stage
        self.details = details

        # Determine retryability: explicit > registry default > False
        if retryable is not None:
            self.retryable = retryable
        elif code in ERROR_CODES:
            self.retryable = ERROR_CODES[code][0]
        else:
            self.retryable = False

        super().__init__(message)

    def to_error_object(self) -> ErrorObject:
        """Convert to an ErrorObject for OutputEnvelope inclusion."""
        return ErrorObject(
            code=self.code,
            message=str(self),
            retryable=self.retryable,
            stage=self.stage,
            details=self.details,
        )


# ── Convenience constructors ────────────────────────────────────────────

def capture_error(
    message: str,
    *,
    retryable: bool = True,
    details: dict[str, Any] | None = None,
) -> PipelineError:
    """Create an ERR_CAPTURE_FAILED error scoped to the capture stage."""
    return PipelineError(
        "ERR_CAPTURE_FAILED",
        message,
        stage=StageName.CAPTURE.value,
        retryable=retryable,
        details=details,
    )


def normalize_error(
    message: str,
    *,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> PipelineError:
    """Create an ERR_NORMALIZATION_FAILED error scoped to the normalize stage."""
    return PipelineError(
        "ERR_NORMALIZATION_FAILED",
        message,
        stage=StageName.NORMALIZE.value,
        retryable=retryable,
        details=details,
    )


def extraction_error(
    message: str,
    *,
    retryable: bool = True,
    details: dict[str, Any] | None = None,
) -> PipelineError:
    """Create an ERR_EXTRACTION_FAILED error scoped to the extract stage."""
    return PipelineError(
        "ERR_EXTRACTION_FAILED",
        message,
        stage=StageName.EXTRACT.value,
        retryable=retryable,
        details=details,
    )


def schema_validation_error(
    message: str,
    *,
    stage: str | None = None,
    details: dict[str, Any] | None = None,
) -> PipelineError:
    """Create an ERR_SCHEMA_VALIDATION error, optionally scoped to a stage."""
    return PipelineError(
        "ERR_SCHEMA_VALIDATION",
        message,
        stage=stage,
        retryable=False,
        details=details,
    )


def canon_write_forbidden(
    message: str = "Writes to Canonical Scope require Promotion",
    *,
    details: dict[str, Any] | None = None,
) -> PipelineError:
    """Create an ERR_CANON_WRITE_FORBIDDEN error."""
    return PipelineError(
        "ERR_CANON_WRITE_FORBIDDEN",
        message,
        retryable=False,
        details=details,
    )
