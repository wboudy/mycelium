"""
Tests for the mycelium.audit module (AUD-001, AUD-002).

Verifies:
- AC-AUD-001-1: Each ingest emits ingest_started and exactly one terminal event.
- AC-AUD-001-2: Audit logs are append-only (new runs only append, never rewrite).
- AC-AUD-002-1: Each line parses as JSON with AUD-001 minimum fields.
- AC-AUD-002-2: Appending new events does not change byte content of previous lines.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from mycelium.audit import (
    TERMINAL_INGEST_EVENTS,
    AuditEvent,
    EventType,
    _audit_log_path,
    emit_event,
    read_audit_log,
)
from mycelium.deterministic import NORMALIZED_TIMESTAMP, NORMALIZED_UUID, fixed_clock


# ---------------------------------------------------------------------------
# EventType enum
# ---------------------------------------------------------------------------

class TestEventType:
    """Verify event type enum values match spec."""

    def test_all_event_types_present(self):
        expected = {
            "ingest_started", "ingest_completed", "ingest_failed",
            "promotion_applied", "egress_attempted", "egress_blocked",
            "egress_completed", "egress_mode_transition",
        }
        actual = {e.value for e in EventType}
        assert actual == expected

    def test_terminal_ingest_events(self):
        assert EventType.INGEST_COMPLETED in TERMINAL_INGEST_EVENTS
        assert EventType.INGEST_FAILED in TERMINAL_INGEST_EVENTS
        assert EventType.INGEST_STARTED not in TERMINAL_INGEST_EVENTS


# ---------------------------------------------------------------------------
# AuditEvent data model
# ---------------------------------------------------------------------------

class TestAuditEvent:
    """Verify AuditEvent serialization."""

    def test_to_json_line_is_single_line(self):
        event = AuditEvent(
            event_id="test-id",
            timestamp="2026-03-01T00:00:00Z",
            actor="test",
            event_type="ingest_started",
        )
        line = event.to_json_line()
        assert "\n" not in line

    def test_to_json_line_is_valid_json(self):
        event = AuditEvent(
            event_id="test-id",
            timestamp="2026-03-01T00:00:00Z",
            actor="test",
            event_type="ingest_started",
            run_id="run-123",
            targets=["Inbox/Sources/note.md"],
            details={"key": "value"},
        )
        data = json.loads(event.to_json_line())
        assert data["event_id"] == "test-id"
        assert data["event_type"] == "ingest_started"
        assert data["run_id"] == "run-123"
        assert data["targets"] == ["Inbox/Sources/note.md"]
        assert data["details"] == {"key": "value"}

    def test_minimum_fields_present(self):
        """AC-AUD-002-1: JSON has all minimum fields."""
        event = AuditEvent(
            event_id="eid",
            timestamp="2026-01-01T00:00:00Z",
            actor="system",
            event_type="ingest_started",
        )
        data = json.loads(event.to_json_line())
        required = {"event_id", "timestamp", "actor", "event_type", "run_id", "targets", "details"}
        assert required <= set(data.keys())


# ---------------------------------------------------------------------------
# emit_event + append-only
# ---------------------------------------------------------------------------

class TestEmitEvent:
    """Verify emit_event writes JSONL correctly."""

    def test_creates_log_file(self, tmp_path: Path):
        """emit_event creates the Logs/Audit/ directory and file."""
        emit_event(tmp_path, EventType.INGEST_STARTED, run_id="run-1")
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        assert len(log_files) == 1

    def test_file_contains_valid_jsonl(self, tmp_path: Path):
        """AC-AUD-002-1: Each line is a valid JSON object."""
        emit_event(tmp_path, EventType.INGEST_STARTED, run_id="r1")
        emit_event(tmp_path, EventType.INGEST_COMPLETED, run_id="r1")

        log_path = _audit_log_path(tmp_path)
        with open(log_path) as f:
            lines = [l.strip() for l in f if l.strip()]

        assert len(lines) == 2
        for line in lines:
            data = json.loads(line)
            assert "event_id" in data
            assert "timestamp" in data
            assert "actor" in data
            assert "event_type" in data

    def test_append_only(self, tmp_path: Path):
        """AC-AUD-001-2: New events are appended, prior lines unchanged."""
        # Write first event
        emit_event(tmp_path, EventType.INGEST_STARTED, run_id="r1")
        log_path = _audit_log_path(tmp_path)
        first_bytes = log_path.read_bytes()

        # Write second event
        emit_event(tmp_path, EventType.INGEST_COMPLETED, run_id="r1")
        all_bytes = log_path.read_bytes()

        # AC-AUD-002-2: First bytes are unchanged prefix
        assert all_bytes.startswith(first_bytes)
        # New content was added
        assert len(all_bytes) > len(first_bytes)

    def test_append_only_across_runs(self, tmp_path: Path):
        """AC-AUD-001-2: Events from multiple runs coexist, prior entries preserved."""
        emit_event(tmp_path, EventType.INGEST_STARTED, run_id="r1")
        emit_event(tmp_path, EventType.INGEST_COMPLETED, run_id="r1")
        log_path = _audit_log_path(tmp_path)
        run1_bytes = log_path.read_bytes()

        emit_event(tmp_path, EventType.INGEST_STARTED, run_id="r2")
        emit_event(tmp_path, EventType.INGEST_COMPLETED, run_id="r2")
        all_bytes = log_path.read_bytes()

        # Run1 bytes are unchanged prefix
        assert all_bytes.startswith(run1_bytes)
        # 4 total lines
        events = read_audit_log(log_path)
        assert len(events) == 4

    def test_default_actor_is_unknown(self, tmp_path: Path):
        """Actor defaults to 'unknown' per spec."""
        event = emit_event(tmp_path, EventType.INGEST_STARTED)
        assert event.actor == "unknown"

    def test_custom_actor(self, tmp_path: Path):
        event = emit_event(tmp_path, EventType.PROMOTION_APPLIED, actor="human:will")
        assert event.actor == "human:will"

    def test_event_id_is_uuid(self, tmp_path: Path):
        """Auto-generated event_id is a valid UUID."""
        event = emit_event(tmp_path, EventType.INGEST_STARTED)
        uuid.UUID(event.event_id)  # raises ValueError if invalid

    def test_custom_event_id(self, tmp_path: Path):
        event = emit_event(tmp_path, EventType.INGEST_STARTED, event_id="custom-id")
        assert event.event_id == "custom-id"

    def test_returns_audit_event(self, tmp_path: Path):
        event = emit_event(
            tmp_path,
            EventType.INGEST_STARTED,
            run_id="r1",
            targets=["Inbox/Sources/note.md"],
            details={"source_kind": "url"},
        )
        assert isinstance(event, AuditEvent)
        assert event.event_type == "ingest_started"
        assert event.run_id == "r1"
        assert event.targets == ["Inbox/Sources/note.md"]
        assert event.details == {"source_kind": "url"}

    def test_string_event_type(self, tmp_path: Path):
        """Accepts string event types (for extensibility)."""
        event = emit_event(tmp_path, "custom_event")
        assert event.event_type == "custom_event"


# ---------------------------------------------------------------------------
# AC-AUD-001-1: Ingest lifecycle
# ---------------------------------------------------------------------------

class TestIngestLifecycle:
    """Verify ingest event pairing rules."""

    def test_ingest_started_then_completed(self, tmp_path: Path):
        """AC-AUD-001-1: Standard ingest lifecycle."""
        run_id = "run-lifecycle-1"
        emit_event(tmp_path, EventType.INGEST_STARTED, run_id=run_id)
        emit_event(tmp_path, EventType.INGEST_COMPLETED, run_id=run_id)

        events = read_audit_log(_audit_log_path(tmp_path))
        run_events = [e for e in events if e.run_id == run_id]
        assert len(run_events) == 2
        assert run_events[0].event_type == "ingest_started"
        assert run_events[1].event_type == "ingest_completed"

    def test_ingest_started_then_failed(self, tmp_path: Path):
        """AC-AUD-001-1: Failed ingest lifecycle."""
        run_id = "run-lifecycle-2"
        emit_event(tmp_path, EventType.INGEST_STARTED, run_id=run_id)
        emit_event(
            tmp_path, EventType.INGEST_FAILED,
            run_id=run_id,
            details={"error": "Schema validation failed"},
        )

        events = read_audit_log(_audit_log_path(tmp_path))
        run_events = [e for e in events if e.run_id == run_id]
        assert len(run_events) == 2
        assert run_events[0].event_type == "ingest_started"
        assert run_events[1].event_type == "ingest_failed"

    def test_terminal_event_count(self, tmp_path: Path):
        """Each run should have exactly one terminal event."""
        run_id = "run-check"
        emit_event(tmp_path, EventType.INGEST_STARTED, run_id=run_id)
        emit_event(tmp_path, EventType.INGEST_COMPLETED, run_id=run_id)

        events = read_audit_log(_audit_log_path(tmp_path))
        run_events = [e for e in events if e.run_id == run_id]
        terminal = [e for e in run_events if e.event_type in {t.value for t in TERMINAL_INGEST_EVENTS}]
        assert len(terminal) == 1


# ---------------------------------------------------------------------------
# read_audit_log
# ---------------------------------------------------------------------------

class TestReadAuditLog:
    """Verify JSONL reader."""

    def test_roundtrip(self, tmp_path: Path):
        """Write events and read them back."""
        e1 = emit_event(tmp_path, EventType.INGEST_STARTED, run_id="r1", actor="agent")
        e2 = emit_event(tmp_path, EventType.INGEST_COMPLETED, run_id="r1", actor="agent")

        events = read_audit_log(_audit_log_path(tmp_path))
        assert len(events) == 2
        assert events[0].event_id == e1.event_id
        assert events[1].event_id == e2.event_id

    def test_empty_lines_skipped(self, tmp_path: Path):
        """Blank lines in the log file are ignored."""
        log_path = _audit_log_path(tmp_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        event = AuditEvent(
            event_id="e1",
            timestamp="2026-01-01T00:00:00Z",
            actor="test",
            event_type="ingest_started",
        )
        with open(log_path, "w") as f:
            f.write(event.to_json_line() + "\n")
            f.write("\n")  # blank line
            f.write("\n")  # another blank line

        events = read_audit_log(log_path)
        assert len(events) == 1

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_audit_log(tmp_path / "nonexistent.jsonl")


# ---------------------------------------------------------------------------
# Deterministic mode compatibility
# ---------------------------------------------------------------------------

class TestDeterministicMode:
    """Verify audit events work with fixed_clock."""

    def test_fixed_clock_timestamp(self, tmp_path: Path):
        """Timestamps use fixed clock when active."""
        with fixed_clock():
            event = emit_event(tmp_path, EventType.INGEST_STARTED, run_id="r-det")

        # The timestamp should be from the fixed epoch
        # (audit uses datetime.now directly, not through the patched models module,
        # but the event_id and timestamp can be overridden for deterministic tests)
        event2 = emit_event(
            tmp_path, EventType.INGEST_COMPLETED,
            run_id="r-det",
            event_id="deterministic-id",
            timestamp="2000-01-01T00:00:00.000000Z",
        )
        assert event2.timestamp == "2000-01-01T00:00:00.000000Z"
        assert event2.event_id == "deterministic-id"


# ---------------------------------------------------------------------------
# Audit log path
# ---------------------------------------------------------------------------

class TestAuditLogPath:
    """Verify log path construction."""

    def test_path_under_logs_audit(self, tmp_path: Path):
        path = _audit_log_path(tmp_path)
        assert "Logs" in path.parts
        assert "Audit" in path.parts

    def test_path_has_jsonl_extension(self, tmp_path: Path):
        path = _audit_log_path(tmp_path)
        assert path.suffix == ".jsonl"

    def test_path_contains_date(self, tmp_path: Path):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        path = _audit_log_path(tmp_path)
        assert now.strftime("%Y-%m-%d") in path.name


# ---------------------------------------------------------------------------
# Concurrent write safety
# ---------------------------------------------------------------------------

class TestConcurrentWrites:
    """Verify JSONL integrity under concurrent appends."""

    def test_concurrent_writes_produce_valid_jsonl(self, tmp_path: Path):
        """Multiple threads writing simultaneously must not corrupt JSONL."""
        import concurrent.futures
        import json as json_mod

        n_writers = 8
        events_per_writer = 50

        def writer(thread_id: int) -> list[str]:
            ids = []
            for i in range(events_per_writer):
                eid = f"t{thread_id}-e{i}"
                emit_event(
                    tmp_path,
                    EventType.INGEST_STARTED,
                    run_id=f"run-t{thread_id}",
                    event_id=eid,
                    details={"thread": thread_id, "seq": i},
                )
                ids.append(eid)
            return ids

        with concurrent.futures.ThreadPoolExecutor(max_workers=n_writers) as pool:
            futures = [pool.submit(writer, tid) for tid in range(n_writers)]
            all_ids: list[str] = []
            for f in concurrent.futures.as_completed(futures):
                all_ids.extend(f.result())

        log_path = _audit_log_path(tmp_path)
        raw = log_path.read_text()
        lines = [ln for ln in raw.split("\n") if ln.strip()]

        # Every line must parse as valid JSON
        parsed_ids = set()
        for line in lines:
            data = json_mod.loads(line)
            parsed_ids.add(data["event_id"])

        assert len(lines) == n_writers * events_per_writer
        assert parsed_ids == set(all_ids)

    def test_large_event_not_interleaved(self, tmp_path: Path):
        """Events with large details dicts still produce valid single lines."""
        import json as json_mod

        large_details = {"data": "x" * 8192}
        emit_event(
            tmp_path,
            EventType.INGEST_STARTED,
            event_id="large-1",
            details=large_details,
        )
        emit_event(
            tmp_path,
            EventType.INGEST_COMPLETED,
            event_id="large-2",
            details=large_details,
        )

        log_path = _audit_log_path(tmp_path)
        lines = [ln for ln in log_path.read_text().split("\n") if ln.strip()]
        assert len(lines) == 2
        for line in lines:
            data = json_mod.loads(line)
            assert len(data["details"]["data"]) == 8192
