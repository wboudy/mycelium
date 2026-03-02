"""
Context command contract (CMD-CTX-001).

Read-only command that assembles a Context Pack for a user goal by
traversing the knowledge graph and collecting relevant items with citations.

Spec reference: §5.2.6 CMD-CTX-001
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mycelium.models import (
    ErrorObject,
    OutputEnvelope,
    error_envelope,
    make_envelope,
)


# ─── Error codes ──────────────────────────────────────────────────────────

ERR_CONTEXT_EMPTY = "ERR_CONTEXT_EMPTY"
ERR_SCHEMA_VALIDATION = "ERR_SCHEMA_VALIDATION"

# ─── Defaults ─────────────────────────────────────────────────────────────

DEFAULT_LIMIT = 20
DEFAULT_MAX_DEPTH = 3


# ─── Input model ─────────────────────────────────────────────────────────

@dataclass
class ContextInput:
    """Validated input for the context command."""
    goal: str | None = None
    project: str | None = None
    tags: list[str] = field(default_factory=list)
    limit: int | None = None
    strict: bool = False


# ─── Output models ────────────────────────────────────────────────────────

@dataclass
class ContextItem:
    """A single item in the context pack."""
    path: str
    type: str
    title: str
    rationale: str
    citations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "type": self.type,
            "title": self.title,
            "rationale": self.rationale,
            "citations": self.citations,
        }


# ─── Validation ───────────────────────────────────────────────────────────

def validate_context_input(raw: dict[str, Any]) -> ContextInput | ErrorObject:
    """Validate raw input dict into ContextInput."""
    # Validate tags
    tags = raw.get("tags", [])
    if not isinstance(tags, list):
        return ErrorObject(
            code=ERR_SCHEMA_VALIDATION,
            message="tags must be an array of strings",
            retryable=False,
        )

    # Validate limit
    limit = raw.get("limit")
    if limit is not None:
        if not isinstance(limit, int) or limit < 1:
            return ErrorObject(
                code=ERR_SCHEMA_VALIDATION,
                message="limit must be a positive integer",
                retryable=False,
            )

    return ContextInput(
        goal=raw.get("goal"),
        project=raw.get("project"),
        tags=tags,
        limit=limit,
        strict=bool(raw.get("strict", False)),
    )


def apply_limit(items: list[ContextItem], limit: int | None) -> list[ContextItem]:
    """Apply limit to items list (AC-CMD-CTX-001-1)."""
    if limit is not None:
        return items[:limit]
    return items


def execute_context(raw_input: dict[str, Any]) -> OutputEnvelope:
    """Execute the context command contract.

    Read-only: traverses the knowledge graph to assemble a Context Pack.
    Actual vault queries are wired in during integration.

    Args:
        raw_input: Raw command input dict.

    Returns:
        OutputEnvelope with context results.
    """
    result = validate_context_input(raw_input)
    if isinstance(result, ErrorObject):
        return make_envelope("context", errors=[result])

    ctx_input = result

    # Stub: in integration, graph traversal populates items
    items: list[ContextItem] = []

    # AC-CMD-CTX-001-1: apply limit
    items = apply_limit(items, ctx_input.limit)

    effective_limit = ctx_input.limit or DEFAULT_LIMIT

    return make_envelope(
        "context",
        data={
            "items": [item.to_dict() for item in items],
            "traversal_trace": {
                "nodes_visited": 0,
                "max_depth_reached": 0,
            },
            "limits_applied": {
                "limit": effective_limit,
                "max_depth": DEFAULT_MAX_DEPTH,
            },
        },
    )
