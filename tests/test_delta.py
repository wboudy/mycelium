"""
Tests for the delta command contract (CMD-DEL-001).

Verifies:
  AC-CMD-DEL-001-1: match_groups includes all five match class keys.
  AC-CMD-DEL-001-2: counts.total_extracted_claims equals sum of class counts.
"""

from __future__ import annotations

import pytest

from mycelium.commands.delta import (
    ERR_DELTA_NOT_FOUND,
    ERR_SOURCE_NOT_FOUND,
    MATCH_CLASS_KEYS,
    DeltaInput,
    MatchClass,
    execute_delta,
    make_counts,
    make_empty_match_groups,
    validate_delta_input,
)
from mycelium.models import ErrorObject


# ─── MatchClass enum ─────────────────────────────────────────────────────

class TestMatchClass:

    def test_five_classes(self):
        assert len(MatchClass) == 5

    def test_class_values(self):
        assert set(mc.value for mc in MatchClass) == {
            "EXACT", "NEAR_DUPLICATE", "SUPPORTING", "CONTRADICTING", "NEW"
        }


# ─── Input validation ────────────────────────────────────────────────────

class TestValidateDeltaInput:

    def test_source_id(self):
        result = validate_delta_input({"source_id": "src-1"})
        assert isinstance(result, DeltaInput)
        assert result.source_id == "src-1"

    def test_delta_report_path(self):
        result = validate_delta_input({
            "delta_report_path": "Reports/Delta/r1.md"
        })
        assert isinstance(result, DeltaInput)
        assert result.delta_report_path == "Reports/Delta/r1.md"

    def test_no_input_rejected(self):
        result = validate_delta_input({})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_SOURCE_NOT_FOUND

    def test_both_inputs_rejected(self):
        result = validate_delta_input({
            "source_id": "src-1",
            "delta_report_path": "path.md",
        })
        assert isinstance(result, ErrorObject)

    def test_strict_flag(self):
        result = validate_delta_input({
            "source_id": "src-1", "strict": True
        })
        assert isinstance(result, DeltaInput)
        assert result.strict is True


# ─── AC-CMD-DEL-001-1: match_groups keys ─────────────────────────────────

class TestMatchGroupKeys:
    """AC-CMD-DEL-001-1: match_groups includes all five keys."""

    def test_empty_match_groups_has_all_keys(self):
        mg = make_empty_match_groups()
        assert set(mg.keys()) == set(MATCH_CLASS_KEYS)

    def test_envelope_match_groups_has_all_keys(self):
        env = execute_delta({"source_id": "src-1"})
        assert set(env.data["match_groups"].keys()) == set(MATCH_CLASS_KEYS)


# ─── AC-CMD-DEL-001-2: total_extracted_claims consistency ─────────────────

class TestCountsConsistency:
    """AC-CMD-DEL-001-2: total = sum of five class counts."""

    def test_empty_counts(self):
        mg = make_empty_match_groups()
        counts = make_counts(mg)
        assert counts["total_extracted_claims"] == 0

    def test_counts_sum_matches(self):
        mg = {
            "EXACT": ["a", "b"],
            "NEAR_DUPLICATE": ["c"],
            "SUPPORTING": [],
            "CONTRADICTING": ["d", "e", "f"],
            "NEW": ["g"],
        }
        counts = make_counts(mg)
        assert counts["total_extracted_claims"] == 7
        assert counts["EXACT"] == 2
        assert counts["CONTRADICTING"] == 3

    def test_envelope_counts(self):
        env = execute_delta({"source_id": "src-1"})
        counts = env.data["counts"]
        assert "total_extracted_claims" in counts
        class_sum = sum(
            counts[mc] for mc in MATCH_CLASS_KEYS
        )
        assert counts["total_extracted_claims"] == class_sum


# ─── execute_delta ───────────────────────────────────────────────────────

class TestExecuteDelta:

    def test_valid_input_returns_envelope(self):
        env = execute_delta({"source_id": "src-1"})
        assert env.ok is True
        assert env.command == "delta"

    def test_output_data_structure(self):
        env = execute_delta({"source_id": "src-1"})
        for key in ("run_id", "source_id", "counts", "match_groups",
                     "conflicts", "new_links", "follow_up_questions",
                     "citations"):
            assert key in env.data, f"Missing key: {key}"

    def test_invalid_input_returns_error(self):
        env = execute_delta({})
        assert env.ok is False

    def test_envelope_keys(self):
        env = execute_delta({"source_id": "x"})
        d = env.to_dict()
        assert set(d.keys()) == {
            "ok", "command", "timestamp", "data",
            "errors", "warnings", "trace"
        }
