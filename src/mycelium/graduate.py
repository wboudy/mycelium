"""Graduate command: Promotion of Draft Notes to Canonical Scope (CMD-GRD-001).

Implements the ``graduate`` command contract from §5.2.5. This is the sole path
for Draft->Canon promotion per INV-002.

Spec reference: mycelium_refactor_plan_apr_round5.md §5.2.5, lines 651-685
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mycelium.audit import EventType, emit_event
from mycelium.invariants import validate_provenance_required
from mycelium.models import ErrorObject, OutputEnvelope, make_envelope
from mycelium.note_io import read_note, write_note
from mycelium.schema import validate_shared_frontmatter
from mycelium.vault_layout import CANONICAL_DIRS, is_draft_scope


@dataclass
class PromotionResult:
    """Result of promoting a single queue item."""

    queue_id: str
    from_path: str
    to_path: str


@dataclass
class RejectionResult:
    """Result of rejecting a single queue item during promotion."""

    queue_id: str
    reason: str


@dataclass
class GraduateInput:
    """Input parameters for the graduate command.

    Exactly one of queue_id, queue_item_paths, all_approved, or from_digest
    must be provided.
    """

    queue_id: str | None = None
    queue_item_paths: list[str] | None = None
    all_approved: bool = False
    from_digest: str | None = None
    dry_run: bool = False
    strict: bool = True
    actor: str = "unknown"


def _resolve_canonical_path(note_type: str, note_id: str) -> str:
    """Determine the canonical scope path for a note based on its type.

    Args:
        note_type: The note's ``type`` field (source, claim, concept, etc.).
        note_id: The note's ``id`` field.

    Returns:
        Vault-relative path in canonical scope.

    Raises:
        PathTraversalError: If note_id contains path traversal sequences.
    """
    from mycelium.vault_layout import sanitize_path_component

    sanitize_path_component(note_id)

    type_to_dir = {
        "source": "Sources",
        "claim": "Claims",
        "concept": "Concepts",
        "question": "Questions",
        "project": "Projects",
        "moc": "MOCs",
    }
    directory = type_to_dir.get(note_type, "Sources")
    return f"{directory}/{note_id}.md"


def _validate_queue_item(
    frontmatter: dict[str, Any],
    vault_relative_path: str,
) -> list[ErrorObject]:
    """Validate a queue item for promotion eligibility.

    Checks schema validity, provenance (for claims), and draft scope location.
    """
    errors: list[ErrorObject] = []

    # Schema validation
    schema_errors = validate_shared_frontmatter(frontmatter)
    if schema_errors:
        errors.append(ErrorObject(
            code="ERR_SCHEMA_VALIDATION",
            message=f"Schema validation failed: {'; '.join(schema_errors)}",
            retryable=False,
            details={"validation_errors": schema_errors},
        ))

    # Provenance check for claims (INV-004)
    prov_errors = validate_provenance_required(
        frontmatter, is_promotion=True
    )
    errors.extend(prov_errors)

    # Must be in draft scope
    if not is_draft_scope(vault_relative_path):
        errors.append(ErrorObject(
            code="ERR_QUEUE_ITEM_INVALID",
            message=f"Queue item at '{vault_relative_path}' is not in Draft Scope.",
            retryable=False,
            details={"path": vault_relative_path},
        ))

    return errors


def graduate(
    vault_dir: Path,
    params: GraduateInput,
    queue_items: list[dict[str, Any]],
) -> OutputEnvelope:
    """Execute the graduate command (CMD-GRD-001).

    Promotes approved queue items from Draft Scope to Canonical Scope.

    Args:
        vault_dir: Path to the vault root directory.
        params: Graduate command input parameters.
        queue_items: List of queue item dicts, each with ``queue_id``,
            ``path`` (vault-relative), and ``decision`` (approve/hold/reject).

    Returns:
        OutputEnvelope with promotion results.
    """
    # AC-CMD-GRD-001-3: dry_run=false + strict=false is forbidden
    if not params.dry_run and not params.strict:
        return make_envelope(
            "graduate",
            ok=False,
            errors=[ErrorObject(
                code="ERR_SCHEMA_VALIDATION",
                message=(
                    "graduate with dry_run=false requires strict=true. "
                    "Non-strict mode is only permitted when dry_run=true "
                    "(AC-CMD-GRD-001-3)."
                ),
                retryable=False,
            )],
        )

    promoted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    audit_event_ids: list[str] = []

    for item in queue_items:
        queue_id = item["queue_id"]
        vault_path = item["path"]
        decision = item.get("decision", "approve")

        # AC-CMD-GRD-001-4: held items remain pending
        if decision == "hold":
            skipped.append({"queue_id": queue_id, "reason": "held"})
            continue

        if decision == "reject":
            skipped.append({"queue_id": queue_id, "reason": "rejected by reviewer"})
            continue

        # Only process approved items
        if decision != "approve":
            skipped.append({"queue_id": queue_id, "reason": f"unknown decision: {decision}"})
            continue

        # Read the note (with path containment check)
        from mycelium.vault_layout import PathTraversalError, safe_vault_path

        try:
            note_path = safe_vault_path(vault_dir, vault_path)
        except PathTraversalError:
            rejected.append({
                "queue_id": queue_id,
                "reason": f"Path traversal detected in queue item path: {vault_path}",
            })
            continue

        try:
            frontmatter, body = read_note(note_path)
        except (FileNotFoundError, ValueError) as exc:
            rejected.append({
                "queue_id": queue_id,
                "reason": f"Cannot read note: {exc}",
            })
            continue

        # Validate (AC-CMD-GRD-001-1: per-item atomicity)
        validation_errors = _validate_queue_item(frontmatter, vault_path)
        if validation_errors:
            rejected.append({
                "queue_id": queue_id,
                "reason": "; ".join(e.message for e in validation_errors),
            })
            continue

        # Determine canonical target path
        from mycelium.vault_layout import PathTraversalError

        note_type = frontmatter.get("type", "source")
        note_id = frontmatter.get("id", queue_id)
        try:
            canonical_path = _resolve_canonical_path(note_type, note_id)
        except PathTraversalError:
            rejected.append({
                "queue_id": queue_id,
                "reason": f"Path traversal detected in note id: {note_id}",
            })
            continue

        if params.dry_run:
            promoted.append({
                "queue_id": queue_id,
                "from_path": vault_path,
                "to_path": canonical_path,
            })
            continue

        # AC-CMD-GRD-001-2: Update status to canon and write to canonical scope
        frontmatter["status"] = "canon"
        target = vault_dir / canonical_path
        try:
            write_note(target, frontmatter, body)
        except OSError as exc:
            rejected.append({
                "queue_id": queue_id,
                "reason": f"Failed to write canonical note: {exc}",
            })
            continue

        promoted.append({
            "queue_id": queue_id,
            "from_path": vault_path,
            "to_path": canonical_path,
        })

    # AC-REV-003-2: emit audit event for promoted items
    if promoted and not params.dry_run:
        promoted_paths = [p["to_path"] for p in promoted]
        audit_evt = emit_event(
            vault_dir,
            EventType.PROMOTION_APPLIED,
            actor=params.actor,
            targets=promoted_paths,
            details={
                "promoted_count": len(promoted),
                "items": [
                    {"queue_id": p["queue_id"], "from": p["from_path"], "to": p["to_path"]}
                    for p in promoted
                ],
            },
        )
        audit_event_ids.append(audit_evt.event_id)

    data = {
        "promoted": promoted,
        "rejected": rejected,
        "skipped": skipped,
        "audit_event_ids": audit_event_ids,
    }

    # If any items were rejected, the overall result still succeeds
    # (per-item atomicity means other items can proceed)
    return make_envelope("graduate", data=data)
