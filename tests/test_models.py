"""
Tests for Output Envelope data models (IF-001).

Verifies all four acceptance criteria from §5.1:
  AC-IF-001-1: All commands return envelope keys exactly as specified.
  AC-IF-001-2: If a command fails, ok=false and errors.length>=1.
  AC-IF-001-3: Error objects always include code, message, and retryable.
  AC-IF-001-4: timestamp parses as ISO-8601 UTC and command equals the
               invoked command name.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mycelium.models import (
    ErrorObject,
    FileOp,
    OutputEnvelope,
    PlannedOperation,
    WarningObject,
    dry_run_envelope,
    error_envelope,
    make_envelope,
)


# ─── AC-IF-001-1: envelope keys exactly as specified ───────────────────────

class TestEnvelopeKeys:
    """AC-IF-001-1: All commands return envelope keys exactly as specified."""

    REQUIRED_KEYS = {"ok", "command", "timestamp", "data", "errors", "warnings", "trace"}

    def test_success_envelope_has_all_keys(self):
        env = make_envelope("ingest", data={"notes": 3})
        d = env.to_dict()
        assert set(d.keys()) == self.REQUIRED_KEYS

    def test_failure_envelope_has_all_keys(self):
        env = error_envelope("ingest", "E_PARSE", "bad yaml")
        d = env.to_dict()
        assert set(d.keys()) == self.REQUIRED_KEYS

    def test_no_extra_keys(self):
        env = make_envelope("review", data={"items": []})
        d = env.to_dict()
        assert set(d.keys()) == self.REQUIRED_KEYS

    def test_envelope_with_trace_has_all_keys(self):
        env = make_envelope("frontier", data={}, trace={"elapsed_ms": 42})
        d = env.to_dict()
        assert set(d.keys()) == self.REQUIRED_KEYS
        assert d["trace"] == {"elapsed_ms": 42}


# ─── AC-IF-001-2: ok=false requires errors.length>=1 ──────────────────────

class TestOkErrorConsistency:
    """AC-IF-001-2: If a command fails, ok=false and errors.length>=1."""

    def test_ok_true_has_no_errors(self):
        env = make_envelope("ingest")
        assert env.ok is True
        assert env.errors == []

    def test_ok_false_has_at_least_one_error(self):
        env = error_envelope("delta", "E_NOT_FOUND", "note not found")
        assert env.ok is False
        assert len(env.errors) >= 1

    def test_errors_force_ok_false(self):
        """If errors are provided, ok must be False even if caller passes ok=True."""
        env = make_envelope(
            "ingest",
            ok=True,  # caller says ok, but errors override
            errors=[ErrorObject(code="E_X", message="x", retryable=False)],
        )
        assert env.ok is False

    def test_ok_false_without_errors_raises(self):
        """Cannot have ok=False with empty errors list."""
        with pytest.raises(ValueError, match="AC-IF-001-2"):
            make_envelope("ingest", ok=False)

    def test_multiple_errors(self):
        errs = [
            ErrorObject(code="E_A", message="a", retryable=False),
            ErrorObject(code="E_B", message="b", retryable=True),
        ]
        env = make_envelope("ingest", errors=errs)
        assert env.ok is False
        assert len(env.errors) == 2


# ─── AC-IF-001-3: ErrorObject always includes code, message, retryable ────

class TestErrorObjectFields:
    """AC-IF-001-3: Error objects always include code, message, and retryable."""

    REQUIRED_ERROR_KEYS = {"code", "message", "retryable"}

    def test_minimal_error_has_required_fields(self):
        e = ErrorObject(code="E_TEST", message="test error", retryable=False)
        d = e.to_dict()
        assert self.REQUIRED_ERROR_KEYS <= set(d.keys())
        assert d["code"] == "E_TEST"
        assert d["message"] == "test error"
        assert d["retryable"] is False

    def test_error_with_optional_fields(self):
        e = ErrorObject(
            code="E_STAGE",
            message="pipeline failed",
            retryable=True,
            details={"line": 42},
            stage="normalize",
        )
        d = e.to_dict()
        assert self.REQUIRED_ERROR_KEYS <= set(d.keys())
        assert d["details"] == {"line": 42}
        assert d["stage"] == "normalize"

    def test_error_omits_none_optionals(self):
        """Optional fields (details, stage) are omitted when None."""
        e = ErrorObject(code="E_X", message="x", retryable=False)
        d = e.to_dict()
        assert "details" not in d
        assert "stage" not in d

    def test_error_in_envelope_has_required_fields(self):
        env = error_envelope("review", "E_HOLD", "on hold", retryable=False)
        for err_dict in env.to_dict()["errors"]:
            assert self.REQUIRED_ERROR_KEYS <= set(err_dict.keys())


# ─── AC-IF-001-4: timestamp is ISO-8601 UTC, command matches ──────────────

class TestTimestampAndCommand:
    """AC-IF-001-4: timestamp parses as ISO-8601 UTC and command equals
    the invoked command name."""

    def test_timestamp_is_iso8601_utc(self):
        env = make_envelope("ingest")
        ts = env.timestamp
        # Must parse without error
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        # Must be UTC (offset-aware, offset=0)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset().total_seconds() == 0

    def test_timestamp_is_recent(self):
        before = datetime.now(timezone.utc)
        env = make_envelope("delta")
        after = datetime.now(timezone.utc)
        parsed = datetime.fromisoformat(env.timestamp.replace("Z", "+00:00"))
        assert before <= parsed <= after

    def test_command_matches_invoked(self):
        for cmd in ("ingest", "delta", "review", "review_digest", "graduate",
                     "context", "frontier", "connect", "trace", "ideas"):
            env = make_envelope(cmd)
            assert env.command == cmd

    def test_command_preserved_in_failure(self):
        env = error_envelope("frontier", "E_EMPTY", "no notes")
        assert env.command == "frontier"


# ─── WarningObject ─────────────────────────────────────────────────────────

class TestWarningObject:

    def test_minimal_warning(self):
        w = WarningObject(code="W_STALE", message="stale cache")
        d = w.to_dict()
        assert d["code"] == "W_STALE"
        assert d["message"] == "stale cache"
        assert "details" not in d

    def test_warning_with_details(self):
        w = WarningObject(code="W_LINK", message="unresolved", details={"path": "foo.md"})
        d = w.to_dict()
        assert d["details"] == {"path": "foo.md"}

    def test_warnings_in_envelope(self):
        env = make_envelope(
            "ingest",
            warnings=[WarningObject(code="W_A", message="a")],
        )
        assert env.ok is True
        assert len(env.warnings) == 1


# ─── Convenience helpers ──────────────────────────────────────────────────

class TestErrorEnvelopeHelper:

    def test_basic_error_envelope(self):
        env = error_envelope("ingest", "E_IO", "disk full", retryable=True)
        assert env.ok is False
        assert env.command == "ingest"
        assert len(env.errors) == 1
        assert env.errors[0].code == "E_IO"
        assert env.errors[0].retryable is True

    def test_error_envelope_with_stage(self):
        env = error_envelope("ingest", "E_NORM", "bad encoding", stage="normalize")
        assert env.errors[0].stage == "normalize"

    def test_error_envelope_with_partial_data(self):
        env = error_envelope(
            "ingest", "E_PARTIAL", "partial failure",
            data={"processed": 3, "failed": 1},
        )
        assert env.data == {"processed": 3, "failed": 1}


# ─── to_dict round-trip ──────────────────────────────────────────────────

class TestToDict:

    def test_success_envelope_serializes(self):
        env = make_envelope("review", data={"decisions": ["accept"]})
        d = env.to_dict()
        assert d["ok"] is True
        assert d["data"] == {"decisions": ["accept"]}
        assert d["errors"] == []
        assert d["warnings"] == []

    def test_complex_envelope_serializes(self):
        env = make_envelope(
            "delta",
            errors=[
                ErrorObject("E_A", "a", retryable=False, stage="extract"),
            ],
            warnings=[
                WarningObject("W_B", "b", details={"x": 1}),
            ],
            data={"partial": True},
            trace={"run_id": "abc123"},
        )
        d = env.to_dict()
        assert d["ok"] is False
        assert len(d["errors"]) == 1
        assert d["errors"][0]["stage"] == "extract"
        assert len(d["warnings"]) == 1
        assert d["warnings"][0]["details"] == {"x": 1}
        assert d["trace"]["run_id"] == "abc123"


# ─── IF-002: Dry Run / PlannedOperation ──────────────────────────────────

class TestPlannedOperation:
    """Tests for PlannedOperation dataclass (§5.1.1)."""

    def test_write_op(self):
        po = PlannedOperation(op=FileOp.WRITE, path="notes/new.md", reason="ingest")
        d = po.to_dict()
        assert d["op"] == "write"
        assert d["path"] == "notes/new.md"
        assert d["from_path"] is None
        assert d["reason"] == "ingest"

    def test_move_op_requires_from_path(self):
        po = PlannedOperation(op=FileOp.MOVE, path="notes/b.md", from_path="notes/a.md")
        assert po.from_path == "notes/a.md"

    def test_move_without_from_path_raises(self):
        with pytest.raises(ValueError, match="from_path is required"):
            PlannedOperation(op=FileOp.MOVE, path="notes/b.md")

    def test_copy_without_from_path_raises(self):
        with pytest.raises(ValueError, match="from_path is required"):
            PlannedOperation(op=FileOp.COPY, path="notes/b.md")

    def test_delete_without_from_path_raises(self):
        with pytest.raises(ValueError, match="from_path is required"):
            PlannedOperation(op=FileOp.DELETE, path="notes/b.md")

    def test_write_does_not_require_from_path(self):
        po = PlannedOperation(op=FileOp.WRITE, path="notes/x.md")
        assert po.from_path is None

    def test_mkdir_does_not_require_from_path(self):
        po = PlannedOperation(op=FileOp.MKDIR, path="notes/subdir")
        assert po.from_path is None

    def test_string_op_coerced_to_enum(self):
        po = PlannedOperation(op="write", path="notes/x.md")
        assert po.op is FileOp.WRITE

    def test_invalid_op_raises(self):
        with pytest.raises(ValueError):
            PlannedOperation(op="invalid", path="x.md")

    def test_to_dict_all_fields(self):
        po = PlannedOperation(
            op=FileOp.MOVE, path="notes/b.md",
            from_path="notes/a.md", reason="rename"
        )
        d = po.to_dict()
        assert d == {
            "op": "move",
            "path": "notes/b.md",
            "from_path": "notes/a.md",
            "reason": "rename",
        }


class TestFileOp:

    def test_all_ops_exist(self):
        expected = {"write", "move", "copy", "mkdir", "delete"}
        assert {op.value for op in FileOp} == expected


class TestDryRunEnvelope:
    """AC-IF-002-1: Dry Run returns planned_writes in data."""

    def test_basic_dry_run(self):
        ops = [
            PlannedOperation(op=FileOp.WRITE, path="notes/new.md", reason="ingest"),
            PlannedOperation(op=FileOp.MKDIR, path="notes/subdir"),
        ]
        env = dry_run_envelope("ingest", ops)
        assert env.ok is True
        assert env.command == "ingest"
        assert "planned_writes" in env.data
        assert len(env.data["planned_writes"]) == 2
        assert env.data["planned_writes"][0]["op"] == "write"
        assert env.data["planned_writes"][1]["op"] == "mkdir"

    def test_dry_run_empty_writes(self):
        env = dry_run_envelope("ingest", [])
        assert env.ok is True
        assert env.data["planned_writes"] == []

    def test_dry_run_with_warnings(self):
        """AC-IF-002-2: Dry Run reports schema validation as warnings."""
        ops = [PlannedOperation(op=FileOp.WRITE, path="notes/bad.md")]
        warnings = [WarningObject(code="W_SCHEMA", message="missing title field")]
        env = dry_run_envelope("ingest", ops, warnings=warnings)
        assert env.ok is True
        assert len(env.warnings) == 1
        assert env.warnings[0].code == "W_SCHEMA"

    def test_dry_run_serializes(self):
        ops = [
            PlannedOperation(
                op=FileOp.MOVE, path="notes/b.md",
                from_path="notes/a.md", reason="normalize"
            ),
        ]
        env = dry_run_envelope("graduate", ops)
        d = env.to_dict()
        assert d["data"]["planned_writes"][0] == {
            "op": "move",
            "path": "notes/b.md",
            "from_path": "notes/a.md",
            "reason": "normalize",
        }
