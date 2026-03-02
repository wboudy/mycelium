"""
Fingerprint stage — stage 3/7 of the ingestion pipeline (§6.1.1).

Input:  NormalizedSource
Output: SourceIdentity { normalized_locator, fingerprint }
Side effects: Reads/writes source identity index under Indexes/.
Errors: ERR_NORMALIZATION_FAILED (reused for fingerprint failures)

Spec reference: mycelium_refactor_plan_apr_round5.md §6.1.1, §6.4 IDM-001
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from mycelium.models import ErrorObject, OutputEnvelope, make_envelope
from mycelium.stages.normalize import NormalizedSource

STAGE_NAME = "fingerprint"

ERR_FINGERPRINT_FAILED = "ERR_FINGERPRINT_FAILED"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SourceIdentity:
    """Output of the fingerprint stage.

    Contains the deterministic locator and content fingerprint.
    The fingerprint format is ``sha256:<64hex>``.
    """

    normalized_locator: str
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalized_locator": self.normalized_locator,
            "fingerprint": self.fingerprint,
        }


# ---------------------------------------------------------------------------
# Fingerprint logic
# ---------------------------------------------------------------------------

def compute_fingerprint(normalized_text: str) -> str:
    """Compute a deterministic content fingerprint.

    Formula: ``sha256:<hex>`` of the normalized text encoded as UTF-8.

    Args:
        normalized_text: The normalized text content.

    Returns:
        A string like ``"sha256:a1b2c3..."`` (71 chars total).
    """
    digest = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def fingerprint(
    source: NormalizedSource,
) -> tuple[SourceIdentity | None, OutputEnvelope]:
    """Execute the fingerprint stage.

    Args:
        source: A NormalizedSource from the normalize stage.

    Returns:
        Tuple of (identity_or_none, envelope).
    """
    if not source.normalized_text:
        return None, make_envelope(
            STAGE_NAME,
            errors=[ErrorObject(
                code=ERR_FINGERPRINT_FAILED,
                message="NormalizedSource has empty text"
                + (" and locator" if not source.normalized_locator else ""),
                retryable=False,
                stage=STAGE_NAME,
            )],
        )

    try:
        fp = compute_fingerprint(source.normalized_text)
    except Exception as e:
        return None, make_envelope(
            STAGE_NAME,
            errors=[ErrorObject(
                code=ERR_FINGERPRINT_FAILED,
                message=f"Fingerprint computation failed: {e}",
                retryable=False,
                stage=STAGE_NAME,
            )],
        )

    identity = SourceIdentity(
        normalized_locator=source.normalized_locator,
        fingerprint=fp,
    )

    return identity, make_envelope(STAGE_NAME, data=identity.to_dict())
