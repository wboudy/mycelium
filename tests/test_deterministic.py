"""
Tests for the mycelium.deterministic module (TST-G-002).

Verifies:
- AC-TST-G-002-1: Same fixture twice → byte-identical normalized outputs.
- AC-TST-G-002-2: Deterministic mode affects only nondeterministic fields.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from mycelium.deterministic import (
    FIXED_EPOCH,
    NORMALIZED_TIMESTAMP,
    NORMALIZED_UUID,
    fixed_clock,
    normalize_output,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_output() -> dict:
    """A realistic pipeline output with nondeterministic fields."""
    return {
        "ok": True,
        "command": "ingest",
        "timestamp": "2026-03-01T14:23:45.123456Z",
        "data": {
            "source_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "claims": [
                {
                    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "match_class": "NEW",
                    "score": 0.95,
                    "content": "The mitochondria is the powerhouse of the cell.",
                    "created_at": "2026-03-01T14:23:45.200000Z",
                },
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "match_class": "NEAR_DUPLICATE",
                    "score": 0.82,
                    "content": "Photosynthesis converts light energy.",
                    "created_at": "2026-03-01T14:23:45.300000Z",
                },
            ],
            "delta_report": {
                "trace_id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
                "match_groups": {
                    "NEW": {"length": 1},
                    "NEAR_DUPLICATE": {"length": 1},
                },
            },
        },
        "errors": [],
        "warnings": [],
        "trace": {
            "request_id": "deadbeef-cafe-babe-feed-123456789abc",
            "duration_ms": 142,
        },
    }


# ---------------------------------------------------------------------------
# normalize_output tests
# ---------------------------------------------------------------------------

class TestNormalizeOutput:
    """Tests for the normalization mechanism."""

    def test_timestamps_replaced(self):
        """Timestamp-keyed values are replaced with sentinel."""
        data = _sample_output()
        result = normalize_output(data)
        assert result["timestamp"] == NORMALIZED_TIMESTAMP
        for claim in result["data"]["claims"]:
            assert claim["created_at"] == NORMALIZED_TIMESTAMP

    def test_ids_replaced(self):
        """ID-keyed values are replaced with sentinel."""
        data = _sample_output()
        result = normalize_output(data)
        for claim in result["data"]["claims"]:
            assert claim["id"] == NORMALIZED_UUID
        assert result["data"]["delta_report"]["trace_id"] == NORMALIZED_UUID
        assert result["trace"]["request_id"] == NORMALIZED_UUID

    def test_semantic_fields_preserved(self):
        """Match classes, scores, content, and structure are unchanged (AC-TST-G-002-2)."""
        data = _sample_output()
        result = normalize_output(data)

        assert result["ok"] is True
        assert result["command"] == "ingest"
        assert result["errors"] == []
        assert result["warnings"] == []

        claims = result["data"]["claims"]
        assert claims[0]["match_class"] == "NEW"
        assert claims[0]["score"] == 0.95
        assert claims[0]["content"] == "The mitochondria is the powerhouse of the cell."

        assert claims[1]["match_class"] == "NEAR_DUPLICATE"
        assert claims[1]["score"] == 0.82

        groups = result["data"]["delta_report"]["match_groups"]
        assert groups["NEW"]["length"] == 1
        assert groups["NEAR_DUPLICATE"]["length"] == 1

    def test_numeric_fields_preserved(self):
        """Numeric values (duration, counts) are not touched."""
        data = _sample_output()
        result = normalize_output(data)
        assert result["trace"]["duration_ms"] == 142

    def test_idempotent(self):
        """Normalizing an already-normalized output is a no-op."""
        data = _sample_output()
        once = normalize_output(data)
        twice = normalize_output(once)
        assert once == twice

    def test_byte_identical_across_runs(self):
        """AC-TST-G-002-1: Same fixture → byte-identical normalized JSON."""
        data = _sample_output()
        run1 = json.dumps(normalize_output(data), sort_keys=True)
        run2 = json.dumps(normalize_output(data), sort_keys=True)
        assert run1 == run2

    def test_different_timestamps_same_normalized(self):
        """Two outputs differing only in timestamps normalize identically."""
        a = _sample_output()
        b = _sample_output()
        b["timestamp"] = "2099-12-31T23:59:59.999999Z"
        b["data"]["claims"][0]["created_at"] = "2099-12-31T23:59:59.100000Z"
        b["data"]["claims"][1]["created_at"] = "2099-12-31T23:59:59.200000Z"

        assert normalize_output(a) == normalize_output(b)

    def test_different_ids_same_normalized(self):
        """Two outputs differing only in IDs normalize identically."""
        a = _sample_output()
        b = _sample_output()
        b["data"]["claims"][0]["id"] = "11111111-1111-1111-1111-111111111111"
        b["data"]["claims"][1]["id"] = "22222222-2222-2222-2222-222222222222"
        b["data"]["delta_report"]["trace_id"] = "33333333-3333-3333-3333-333333333333"

        assert normalize_output(a) == normalize_output(b)

    def test_different_semantic_fields_stay_different(self):
        """AC-TST-G-002-2: Semantic differences are preserved after normalization."""
        a = _sample_output()
        b = _sample_output()
        b["data"]["claims"][0]["match_class"] = "CONTRADICTING"

        assert normalize_output(a) != normalize_output(b)

    def test_original_not_mutated(self):
        """normalize_output deep-copies — original data is untouched."""
        data = _sample_output()
        original_ts = data["timestamp"]
        normalize_output(data)
        assert data["timestamp"] == original_ts

    def test_inline_timestamps_in_strings(self):
        """ISO-8601 timestamps embedded in strings are replaced."""
        data = {"message": "Created at 2026-03-01T14:23:45Z by system"}
        result = normalize_output(data)
        assert "2026" not in result["message"]
        assert NORMALIZED_TIMESTAMP in result["message"]

    def test_inline_uuids_in_strings(self):
        """UUIDs embedded in strings are replaced."""
        data = {"ref": "See item a1b2c3d4-e5f6-7890-abcd-ef1234567890 for details"}
        result = normalize_output(data)
        assert "a1b2c3d4" not in result["ref"]
        assert NORMALIZED_UUID in result["ref"]

    def test_list_input(self):
        """Accepts lists as top-level input."""
        data = [{"timestamp": "2026-03-01T00:00:00Z"}, {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}]
        result = normalize_output(data)
        assert result[0]["timestamp"] == NORMALIZED_TIMESTAMP
        assert result[1]["id"] == NORMALIZED_UUID

    def test_string_input(self):
        """Accepts bare strings as input."""
        data = "Event at 2026-03-01T14:23:45.123Z with ref a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = normalize_output(data)
        assert "2026" not in result
        assert "a1b2c3d4" not in result

    def test_empty_dict(self):
        """Handles empty dict."""
        assert normalize_output({}) == {}

    def test_nested_structure(self):
        """Deeply nested nondeterministic fields are normalized."""
        data = {
            "a": {"b": {"c": {"timestamp": "2026-01-01T00:00:00Z"}}},
        }
        result = normalize_output(data)
        assert result["a"]["b"]["c"]["timestamp"] == NORMALIZED_TIMESTAMP


# ---------------------------------------------------------------------------
# fixed_clock tests
# ---------------------------------------------------------------------------

class TestFixedClock:
    """Tests for the fixed_clock context manager."""

    def test_freezes_make_envelope(self):
        """make_envelope uses frozen clock inside context."""
        from mycelium.models import make_envelope

        with fixed_clock():
            envelope = make_envelope("test_cmd", data={"key": "val"})
        assert envelope.timestamp == "2000-01-01T00:00:00.000000Z"

    def test_yields_epoch(self):
        """Context manager yields the epoch datetime."""
        with fixed_clock() as now:
            assert now == FIXED_EPOCH

    def test_custom_epoch(self):
        """Accepts a custom epoch."""
        custom = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        with fixed_clock(custom) as now:
            assert now == custom

    def test_freezes_datetime_now_utc(self):
        """datetime.now(utc) returns the frozen epoch inside patches."""
        # We can't easily test this outside of the patched modules,
        # but we can test it through make_envelope which uses datetime.now.
        from mycelium.models import make_envelope

        with fixed_clock():
            e1 = make_envelope("a")
            e2 = make_envelope("b")
        assert e1.timestamp == e2.timestamp

    def test_does_not_affect_semantic_fields(self):
        """AC-TST-G-002-2: fixed_clock doesn't alter semantic data."""
        from mycelium.models import make_envelope

        with fixed_clock():
            envelope = make_envelope(
                "test",
                data={"match_class": "NEW", "score": 0.95},
            )
        assert envelope.data["match_class"] == "NEW"
        assert envelope.data["score"] == 0.95
        assert envelope.ok is True
        assert envelope.command == "test"

    def test_clock_unfreezes_after_context(self):
        """After exiting the context, datetime.now returns real time."""
        from mycelium.models import make_envelope

        with fixed_clock():
            pass

        envelope = make_envelope("after")
        assert envelope.timestamp != "2000-01-01T00:00:00.000000Z"


# ---------------------------------------------------------------------------
# Integration: both mechanisms together
# ---------------------------------------------------------------------------

class TestDeterministicIntegration:
    """Verify both mechanisms produce consistent, byte-identical results."""

    def test_fixed_clock_plus_normalization(self):
        """AC-TST-G-002-1: fixed_clock output normalizes to same sentinel."""
        from mycelium.models import make_envelope

        with fixed_clock():
            e1 = make_envelope("ingest", data={"source_id": "abc"})
            e2 = make_envelope("ingest", data={"source_id": "abc"})

        d1 = normalize_output(e1.to_dict())
        d2 = normalize_output(e2.to_dict())
        assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)

    def test_different_runs_normalize_identically(self):
        """AC-TST-G-002-1: Two independent runs → byte-identical after normalization."""
        from mycelium.models import make_envelope

        # Simulate two "runs" at different real times
        e1 = make_envelope("ingest", data={"claims": [{"match_class": "NEW"}]})
        e2 = make_envelope("ingest", data={"claims": [{"match_class": "NEW"}]})

        n1 = normalize_output(e1.to_dict())
        n2 = normalize_output(e2.to_dict())
        assert json.dumps(n1, sort_keys=True) == json.dumps(n2, sort_keys=True)
