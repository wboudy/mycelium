"""
Future command stubs: connect, trace, ideas (CMD-FUT-001).

These commands are post-MVP2 scope. This module defines their contract stubs
to ensure they conform to IF-001 Output Envelope when implemented.

Each stub:
- Defines the command contract (inputs, outputs, side effects, errors)
- Returns a NOT_IMPLEMENTED envelope per IF-001
- Validates that future implementations will conform to the envelope schema

Spec reference: §5.2.8 CMD-FUT-001
"""

from __future__ import annotations

from typing import Any

from mycelium.models import ErrorObject, OutputEnvelope, make_envelope


ERR_NOT_IMPLEMENTED = "ERR_NOT_IMPLEMENTED"


# ---------------------------------------------------------------------------
# connect: Cross-vault knowledge graph connections (post-MVP2)
# ---------------------------------------------------------------------------

CONNECT_CONTRACT = {
    "command": "connect",
    "inputs": {
        "source_id": "str — ID of the source note to connect from",
        "target_id": "str — ID of the target note to connect to",
        "link_type": "str — Relationship type (supports, opposes, extends, etc.)",
        "reason": "str | None — Optional reason for the connection",
    },
    "outputs": {
        "link_id": "str — Unique identifier for the created link",
        "source_id": "str — Source note ID",
        "target_id": "str — Target note ID",
        "link_type": "str — The relationship type",
    },
    "side_effects": [
        "Creates a link record under Links/ directory",
        "Updates both source and target note frontmatter with link references",
    ],
    "errors": [
        "ERR_NOTE_NOT_FOUND — source or target note does not exist",
        "ERR_LINK_DUPLICATE — identical link already exists",
        "ERR_SCHEMA_VALIDATION — link type not in allowed set",
    ],
}


def connect(raw_input: dict[str, Any]) -> OutputEnvelope:
    """Connect command stub (post-MVP2).

    Contract: Creates a typed link between two notes in the knowledge graph.

    Args:
        raw_input: Command input dict with source_id, target_id, link_type.

    Returns:
        OutputEnvelope — currently returns ERR_NOT_IMPLEMENTED.
    """
    return make_envelope(
        "connect",
        errors=[ErrorObject(
            code=ERR_NOT_IMPLEMENTED,
            message="connect command is not yet implemented (post-MVP2 scope)",
            retryable=False,
        )],
    )


# ---------------------------------------------------------------------------
# trace: Provenance chain tracing (post-MVP2)
# ---------------------------------------------------------------------------

TRACE_CONTRACT = {
    "command": "trace",
    "inputs": {
        "note_id": "str — ID of the note to trace",
        "depth": "int — Maximum traversal depth (default 3)",
        "direction": "str — 'upstream' | 'downstream' | 'both' (default 'upstream')",
    },
    "outputs": {
        "root_id": "str — Starting note ID",
        "chain": "list[dict] — Ordered provenance chain entries",
        "depth_reached": "int — Actual depth traversed",
    },
    "side_effects": [],
    "errors": [
        "ERR_NOTE_NOT_FOUND — starting note does not exist",
        "ERR_CYCLE_DETECTED — provenance graph contains a cycle",
    ],
}


def trace(raw_input: dict[str, Any]) -> OutputEnvelope:
    """Trace command stub (post-MVP2).

    Contract: Walks the provenance chain from a note, reporting ancestors
    or descendants up to a configurable depth.

    Args:
        raw_input: Command input dict with note_id, depth, direction.

    Returns:
        OutputEnvelope — currently returns ERR_NOT_IMPLEMENTED.
    """
    return make_envelope(
        "trace",
        errors=[ErrorObject(
            code=ERR_NOT_IMPLEMENTED,
            message="trace command is not yet implemented (post-MVP2 scope)",
            retryable=False,
        )],
    )


# ---------------------------------------------------------------------------
# ideas: Idea generation from knowledge graph (post-MVP2)
# ---------------------------------------------------------------------------

IDEAS_CONTRACT = {
    "command": "ideas",
    "inputs": {
        "scope": "str | None — Limit to a specific MOC or project",
        "count": "int — Number of ideas to generate (default 5)",
        "seed_notes": "list[str] | None — Optional seed note IDs for focused ideation",
    },
    "outputs": {
        "ideas": "list[dict] — Generated idea objects with title, rationale, related_notes",
        "count": "int — Number of ideas generated",
    },
    "side_effects": [
        "May create draft Question Notes for generated ideas",
    ],
    "errors": [
        "ERR_INSUFFICIENT_DATA — not enough notes to generate ideas",
    ],
}


def ideas(raw_input: dict[str, Any]) -> OutputEnvelope:
    """Ideas command stub (post-MVP2).

    Contract: Generates research ideas by analyzing gaps and connections
    in the knowledge graph.

    Args:
        raw_input: Command input dict with scope, count, seed_notes.

    Returns:
        OutputEnvelope — currently returns ERR_NOT_IMPLEMENTED.
    """
    return make_envelope(
        "ideas",
        errors=[ErrorObject(
            code=ERR_NOT_IMPLEMENTED,
            message="ideas command is not yet implemented (post-MVP2 scope)",
            retryable=False,
        )],
    )


# ---------------------------------------------------------------------------
# Contract registry
# ---------------------------------------------------------------------------

FUTURE_COMMAND_CONTRACTS: dict[str, dict[str, Any]] = {
    "connect": CONNECT_CONTRACT,
    "trace": TRACE_CONTRACT,
    "ideas": IDEAS_CONTRACT,
}
