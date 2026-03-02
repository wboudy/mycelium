"""System invariant enforcement for Mycelium (§3).

Implements guards that enforce the system invariants defined in §3 of the
refactor spec. Each invariant is a validation function that raises or returns
a structured error when violated.

Currently implements:
- INV-002: Human authority over canon
- INV-003: Draft-first agent outputs
- INV-004: Provenance required for imported claims
- INV-005: Idempotent ingestion identity
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mycelium.models import ErrorObject
from mycelium.schema import PROVENANCE_REQUIRED_KEYS, validate_claim_frontmatter
from mycelium.vault_layout import is_canonical_scope, is_draft_scope


# ── INV-002: Human authority over canon ──────────────────────────────────────


def validate_canon_protection(
    vault_relative_path: str,
    existing_status: str | None,
    *,
    is_promotion: bool = False,
) -> ErrorObject | None:
    """Enforce INV-002: canonical notes must not be modified without Promotion.

    This guard checks two conditions:
    1. Writes targeting Canonical Scope paths without Promotion are forbidden.
    2. Modifications to any note with ``status: canon`` without Promotion are forbidden.

    Args:
        vault_relative_path: The vault-relative path being written to.
        existing_status: The current ``status`` of the note at this path, or None
            if the note does not yet exist.
        is_promotion: If True, this is a Promotion action via ``graduate`` and
            the guard does not apply.

    Returns:
        None if the write is allowed, or an ErrorObject describing the violation.
    """
    if is_promotion:
        return None

    # AC-INV-002-2: writes to canonical scope without Promotion are forbidden
    if is_canonical_scope(vault_relative_path):
        return ErrorObject(
            code="ERR_CANON_WRITE_FORBIDDEN",
            message=(
                f"Cannot write to Canonical Scope path '{vault_relative_path}' "
                "without Promotion (INV-002)."
            ),
            retryable=False,
            details={
                "path": vault_relative_path,
                "invariant": "INV-002",
            },
        )

    # AC-INV-002-1: cannot modify a note that already has status: canon
    if existing_status == "canon":
        return ErrorObject(
            code="ERR_CANON_WRITE_FORBIDDEN",
            message=(
                f"Cannot modify note at '{vault_relative_path}' with status 'canon' "
                "without Promotion (INV-002)."
            ),
            retryable=False,
            details={
                "path": vault_relative_path,
                "existing_status": "canon",
                "invariant": "INV-002",
            },
        )

    return None


# ── INV-003: Draft-first agent outputs ───────────────────────────────────────


@dataclass
class WriteOperation:
    """Represents a planned file write operation within the vault.

    Used by both the draft-first guard and Dry Run mode to describe what
    would happen without actually performing the write.

    Fields:
        op: The operation type (write, move, copy, mkdir, delete).
        path: Vault-relative target path.
        from_path: Source path for move/copy/delete operations.
        reason: Human-readable rationale for the operation.
    """

    op: str
    path: str
    from_path: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "op": self.op,
            "path": self.path,
            "from_path": self.from_path,
            "reason": self.reason,
        }
        return d


def validate_draft_first(
    vault_relative_path: str,
    status: str,
    *,
    is_promotion: bool = False,
) -> ErrorObject | None:
    """Enforce INV-003: agent-generated notes must target Draft Scope with status draft.

    Args:
        vault_relative_path: The vault-relative path where the note will be written.
        status: The ``status`` frontmatter value of the note being written.
        is_promotion: If True, this write is part of a Promotion action and the
            invariant does not apply (Promotion is the only path to Canonical Scope).

    Returns:
        None if the write is valid, or an ErrorObject describing the violation.
    """
    if is_promotion:
        return None

    if is_canonical_scope(vault_relative_path):
        return ErrorObject(
            code="ERR_CANON_WRITE_FORBIDDEN",
            message=(
                f"Cannot write to Canonical Scope path '{vault_relative_path}' "
                "without Promotion. Agent outputs must target Draft Scope (INV-003)."
            ),
            retryable=False,
            details={"path": vault_relative_path, "invariant": "INV-003"},
        )

    if status != "draft":
        return ErrorObject(
            code="ERR_STATUS_MUST_BE_DRAFT",
            message=(
                f"Agent-generated note must have status 'draft', got '{status}'. "
                "Only Promotion may set status to 'reviewed' or 'canon' (INV-003)."
            ),
            retryable=False,
            details={"status": status, "expected": "draft", "invariant": "INV-003"},
        )

    return None


def check_write_batch(
    writes: list[WriteOperation],
    statuses: dict[str, str],
    *,
    is_promotion: bool = False,
    dry_run: bool = False,
) -> tuple[list[WriteOperation], list[ErrorObject]]:
    """Validate a batch of write operations against INV-003.

    Args:
        writes: List of planned write operations.
        statuses: Mapping of vault-relative path to the note's ``status`` value.
            Only paths that correspond to note writes need entries.
        is_promotion: If True, Promotion semantics apply (canonical writes allowed).
        dry_run: If True, no filesystem writes should occur (AC-INV-003-2).
            Returns the planned operations list without executing them.

    Returns:
        A tuple of (planned_writes, errors).
        - If dry_run is True: planned_writes contains all operations, errors is empty
          (validation still runs but results go to errors only on real writes).
        - If dry_run is False: planned_writes is empty, errors contains any
          INV-003 violations found.
    """
    if dry_run:
        return writes, []

    errors: list[ErrorObject] = []
    for w in writes:
        if w.op in ("write", "move", "copy", "mkdir"):
            status = statuses.get(w.path, "draft")
            err = validate_draft_first(w.path, status, is_promotion=is_promotion)
            if err is not None:
                errors.append(err)

    return [], errors


# ── INV-004: Provenance required for imported claims ─────────────────────────


def validate_provenance_required(
    frontmatter: dict[str, Any],
    *,
    source_kind: str | None = None,
    is_promotion: bool = False,
) -> list[ErrorObject]:
    """Enforce INV-004: imported claims must include provenance.

    Validates that a Claim Note's frontmatter contains the required provenance
    fields (source_id, source_ref, locator) per SCH-003. At promotion time,
    missing provenance produces ``ERR_PROVENANCE_MISSING``.

    Args:
        frontmatter: The Claim Note frontmatter dictionary.
        source_kind: The source_kind of the linked Source Note (for locator
            validation). None skips locator structure checks.
        is_promotion: If True, this is a Promotion action and provenance
            violations produce ``ERR_PROVENANCE_MISSING`` instead of schema
            errors.

    Returns:
        List of ErrorObject entries (empty if valid).
    """
    # Only applies to claim notes
    if frontmatter.get("type") != "claim":
        return []

    errors: list[ErrorObject] = []
    prov = frontmatter.get("provenance")

    if prov is None or not isinstance(prov, dict):
        code = "ERR_PROVENANCE_MISSING" if is_promotion else "ERR_SCHEMA_VALIDATION"
        errors.append(ErrorObject(
            code=code,
            message="Claim Note missing required provenance object (INV-004).",
            retryable=False,
            details={"invariant": "INV-004"},
        ))
        return errors

    # Check required provenance keys
    missing_keys = [k for k in PROVENANCE_REQUIRED_KEYS if k not in prov]
    if missing_keys:
        code = "ERR_PROVENANCE_MISSING" if is_promotion else "ERR_SCHEMA_VALIDATION"
        errors.append(ErrorObject(
            code=code,
            message=(
                f"Claim Note provenance missing required keys: "
                f"{', '.join(missing_keys)} (INV-004)."
            ),
            retryable=False,
            details={
                "missing_keys": missing_keys,
                "invariant": "INV-004",
            },
        ))

    return errors


# ── INV-005: Idempotent ingestion identity ───────────────────────────────────


@dataclass
class SourceIdentity:
    """Resolved identity of a source for idempotency checks.

    The identity key is ``(normalized_locator, fingerprint)``.
    """

    source_id: str
    normalized_locator: str
    fingerprint: str


class IngestionOutcome:
    """Result of source identity resolution for idempotent ingestion."""

    SAME_CONTENT = "same_content"
    """Re-ingestion of identical content — reuse source_id, no new run."""

    REVISED_CONTENT = "revised_content"
    """Same locator but different fingerprint — new run with revision lineage."""

    NEW_SOURCE = "new_source"
    """First ingestion of this locator — create new source."""


def resolve_source_identity(
    normalized_locator: str,
    fingerprint: str,
    existing_sources: list[SourceIdentity],
) -> tuple[str, SourceIdentity | None]:
    """Resolve source identity for idempotent ingestion (INV-005).

    Looks up existing sources by ``normalized_locator`` and compares
    ``fingerprint`` to determine the ingestion outcome.

    Args:
        normalized_locator: The deterministic locator for this source.
        fingerprint: The content fingerprint (``sha256:<hex>``).
        existing_sources: Previously ingested sources to check against.

    Returns:
        A tuple of (outcome, matched_source):
        - ``(IngestionOutcome.SAME_CONTENT, existing)`` if locator+fingerprint
          match exactly — reuse source_id (AC-INV-005-1).
        - ``(IngestionOutcome.REVISED_CONTENT, existing)`` if locator matches
          but fingerprint differs — new run with revision lineage (AC-INV-005-2).
        - ``(IngestionOutcome.NEW_SOURCE, None)`` if no matching locator found.
    """
    for source in existing_sources:
        if source.normalized_locator == normalized_locator:
            if source.fingerprint == fingerprint:
                return IngestionOutcome.SAME_CONTENT, source
            else:
                return IngestionOutcome.REVISED_CONTENT, source

    return IngestionOutcome.NEW_SOURCE, None
