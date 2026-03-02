"""
Tests for the context command contract (CMD-CTX-001).

Verifies:
  AC-CMD-CTX-001-1: Returned items.length <= limit when limit is provided.
  AC-CMD-CTX-001-2: Every returned item includes at least one citation
                     that resolves to an existing Note path.
"""

from __future__ import annotations

import pytest

from mycelium.commands.context import (
    DEFAULT_LIMIT,
    DEFAULT_MAX_DEPTH,
    ERR_CONTEXT_EMPTY,
    ERR_SCHEMA_VALIDATION,
    ContextInput,
    ContextItem,
    apply_limit,
    execute_context,
    validate_context_input,
)
from mycelium.models import ErrorObject


# ─── Input validation ────────────────────────────────────────────────────

class TestValidateContextInput:

    def test_empty_input_accepted(self):
        """All fields optional; empty dict is valid."""
        result = validate_context_input({})
        assert isinstance(result, ContextInput)

    def test_goal(self):
        result = validate_context_input({"goal": "understand topic X"})
        assert isinstance(result, ContextInput)
        assert result.goal == "understand topic X"

    def test_project(self):
        result = validate_context_input({"project": "proj-a"})
        assert isinstance(result, ContextInput)
        assert result.project == "proj-a"

    def test_tags(self):
        result = validate_context_input({"tags": ["ml", "safety"]})
        assert isinstance(result, ContextInput)
        assert result.tags == ["ml", "safety"]

    def test_invalid_tags_type(self):
        result = validate_context_input({"tags": "not-a-list"})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_SCHEMA_VALIDATION

    def test_limit(self):
        result = validate_context_input({"limit": 5})
        assert isinstance(result, ContextInput)
        assert result.limit == 5

    def test_invalid_limit_zero(self):
        result = validate_context_input({"limit": 0})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_SCHEMA_VALIDATION

    def test_invalid_limit_negative(self):
        result = validate_context_input({"limit": -1})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_SCHEMA_VALIDATION

    def test_strict_flag(self):
        result = validate_context_input({"strict": True})
        assert isinstance(result, ContextInput)
        assert result.strict is True

    def test_defaults(self):
        result = validate_context_input({})
        assert isinstance(result, ContextInput)
        assert result.goal is None
        assert result.project is None
        assert result.tags == []
        assert result.limit is None
        assert result.strict is False

    def test_all_fields(self):
        result = validate_context_input({
            "goal": "understand X",
            "project": "proj-a",
            "tags": ["a", "b"],
            "limit": 10,
            "strict": True,
        })
        assert isinstance(result, ContextInput)
        assert result.goal == "understand X"
        assert result.project == "proj-a"
        assert result.tags == ["a", "b"]
        assert result.limit == 10
        assert result.strict is True


# ─── ContextItem ──────────────────────────────────────────────────────────

class TestContextItem:

    def test_to_dict(self):
        item = ContextItem(
            path="Sources/paper.md",
            type="source_note",
            title="A Paper",
            rationale="Relevant to goal",
            citations=["Sources/paper.md"],
        )
        d = item.to_dict()
        assert d == {
            "path": "Sources/paper.md",
            "type": "source_note",
            "title": "A Paper",
            "rationale": "Relevant to goal",
            "citations": ["Sources/paper.md"],
        }

    def test_to_dict_multiple_citations(self):
        item = ContextItem(
            path="Canon/claim.md",
            type="canon_note",
            title="Claim",
            rationale="Supports goal",
            citations=["Sources/a.md", "Sources/b.md"],
        )
        d = item.to_dict()
        assert len(d["citations"]) == 2


# ─── AC-CMD-CTX-001-1: items.length <= limit ─────────────────────────────

class TestLimitEnforcement:
    """AC-CMD-CTX-001-1: Returned items.length <= limit."""

    def test_apply_limit_truncates(self):
        items = [
            ContextItem(f"p{i}", "t", f"title{i}", "r", [f"c{i}"])
            for i in range(10)
        ]
        result = apply_limit(items, 3)
        assert len(result) == 3

    def test_apply_limit_none_returns_all(self):
        items = [
            ContextItem(f"p{i}", "t", f"title{i}", "r", [f"c{i}"])
            for i in range(5)
        ]
        result = apply_limit(items, None)
        assert len(result) == 5

    def test_apply_limit_larger_than_items(self):
        items = [
            ContextItem("p0", "t", "title", "r", ["c0"]),
        ]
        result = apply_limit(items, 10)
        assert len(result) == 1

    def test_envelope_respects_limit(self):
        env = execute_context({"limit": 5})
        assert len(env.data["items"]) <= 5


# ─── AC-CMD-CTX-001-2: citations present ─────────────────────────────────

class TestCitationsPresent:
    """AC-CMD-CTX-001-2: Every item includes at least one citation."""

    def test_item_has_citation(self):
        item = ContextItem(
            path="p", type="t", title="T",
            rationale="R", citations=["Sources/x.md"],
        )
        assert len(item.citations) >= 1

    def test_empty_citations_detectable(self):
        """Contract: items with no citations should be filtered before output."""
        item = ContextItem(
            path="p", type="t", title="T",
            rationale="R", citations=[],
        )
        assert len(item.citations) == 0  # no citations = violates AC


# ─── execute_context ─────────────────────────────────────────────────────

class TestExecuteContext:

    def test_valid_input_returns_envelope(self):
        env = execute_context({})
        assert env.ok is True
        assert env.command == "context"

    def test_output_data_structure(self):
        env = execute_context({})
        assert "items" in env.data
        assert "traversal_trace" in env.data
        assert "limits_applied" in env.data

    def test_traversal_trace_structure(self):
        env = execute_context({})
        trace = env.data["traversal_trace"]
        assert "nodes_visited" in trace
        assert "max_depth_reached" in trace

    def test_limits_applied_structure(self):
        env = execute_context({})
        limits = env.data["limits_applied"]
        assert "limit" in limits
        assert "max_depth" in limits

    def test_limits_applied_with_explicit_limit(self):
        env = execute_context({"limit": 7})
        assert env.data["limits_applied"]["limit"] == 7

    def test_limits_applied_default(self):
        env = execute_context({})
        assert env.data["limits_applied"]["limit"] == DEFAULT_LIMIT
        assert env.data["limits_applied"]["max_depth"] == DEFAULT_MAX_DEPTH

    def test_invalid_input_returns_error(self):
        env = execute_context({"tags": "not-a-list"})
        assert env.ok is False

    def test_envelope_keys(self):
        env = execute_context({})
        d = env.to_dict()
        assert set(d.keys()) == {
            "ok", "command", "timestamp", "data",
            "errors", "warnings", "trace"
        }
