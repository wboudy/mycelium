"""Tests for Review Packet schema validation and persistence (SCH-009).

Verifies acceptance criteria:
  AC-SCH-009-1: Packet YAML files validate against the schema.
  AC-SCH-009-2: Deterministic packet contents for same input.
  AC-SCH-009-3: Validator rejects approve_selected without valid approved_queue_ids.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from mycelium.review_packet import (
    PACKET_ACTIONS,
    REQUIRED_DECISION_KEYS,
    REQUIRED_PACKET_KEYS,
    build_review_packet,
    list_review_packets,
    load_review_packet,
    save_review_packet,
    validate_review_packet,
    validate_review_packet_strict,
)
from mycelium.schema import SchemaValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_packet(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid Review Packet dict."""
    base: dict[str, Any] = {
        "packet_id": "pkt-001",
        "digest_date": "2026-03-01",
        "created_at": "2026-03-01T12:00:00Z",
        "source_id": "s-001",
        "run_ids": ["run-1"],
        "queue_ids": ["q-1", "q-2"],
        "decision": None,
    }
    base.update(overrides)
    return base


def _valid_decision(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid decision object."""
    base: dict[str, Any] = {
        "action": "approve_all",
        "actor": "user:alice",
        "decided_at": "2026-03-01T14:00:00Z",
        "reason": None,
    }
    base.update(overrides)
    return base


# ─── AC-SCH-009-1: Required keys ─────────────────────────────────────────

class TestRequiredKeys:

    def test_valid_minimal(self):
        errors = validate_review_packet(_valid_packet())
        assert errors == []

    @pytest.mark.parametrize("key", sorted(REQUIRED_PACKET_KEYS))
    def test_missing_single_required_key(self, key: str):
        data = _valid_packet()
        del data[key]
        errors = validate_review_packet(data)
        assert any(key in e for e in errors)

    def test_all_keys_missing(self):
        errors = validate_review_packet({})
        assert len(errors) >= 1
        assert "Missing required keys" in errors[0]


# ─── Field validation ────────────────────────────────────────────────────

class TestFieldValidation:

    def test_packet_id_non_empty(self):
        errors = validate_review_packet(_valid_packet(packet_id=""))
        assert any("packet_id" in e for e in errors)

    def test_packet_id_whitespace_only(self):
        errors = validate_review_packet(_valid_packet(packet_id="   "))
        assert any("packet_id" in e for e in errors)

    def test_source_id_non_empty(self):
        errors = validate_review_packet(_valid_packet(source_id=""))
        assert any("source_id" in e for e in errors)

    def test_digest_date_valid(self):
        errors = validate_review_packet(_valid_packet(digest_date="2026-03-15"))
        assert errors == []

    def test_digest_date_invalid(self):
        errors = validate_review_packet(_valid_packet(digest_date="not-a-date"))
        assert any("digest_date" in e for e in errors)

    def test_digest_date_wrong_type(self):
        errors = validate_review_packet(_valid_packet(digest_date=12345))
        assert any("digest_date" in e for e in errors)

    def test_created_at_valid(self):
        errors = validate_review_packet(
            _valid_packet(created_at="2026-03-01T00:00:00+00:00")
        )
        assert errors == []

    def test_created_at_invalid(self):
        errors = validate_review_packet(_valid_packet(created_at="bad-dt"))
        assert any("created_at" in e for e in errors)

    def test_run_ids_non_empty(self):
        errors = validate_review_packet(_valid_packet(run_ids=[]))
        assert any("run_ids" in e for e in errors)

    def test_run_ids_not_array(self):
        errors = validate_review_packet(_valid_packet(run_ids="single"))
        assert any("run_ids" in e for e in errors)

    def test_run_ids_entries_must_be_strings(self):
        errors = validate_review_packet(_valid_packet(run_ids=[123]))
        assert any("run_ids" in e for e in errors)

    def test_queue_ids_non_empty(self):
        errors = validate_review_packet(_valid_packet(queue_ids=[]))
        assert any("queue_ids" in e for e in errors)

    def test_queue_ids_entries_must_be_strings(self):
        errors = validate_review_packet(_valid_packet(queue_ids=["", "q-2"]))
        assert any("queue_ids" in e for e in errors)

    def test_decision_null_is_valid(self):
        errors = validate_review_packet(_valid_packet(decision=None))
        assert errors == []

    def test_decision_wrong_type(self):
        errors = validate_review_packet(_valid_packet(decision="not-a-dict"))
        assert any("decision" in e for e in errors)


# ─── Decision validation ─────────────────────────────────────────────────

class TestDecisionValidation:

    def test_valid_approve_all(self):
        decision = _valid_decision(action="approve_all")
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert errors == []

    def test_valid_reject(self):
        decision = _valid_decision(action="reject", reason="Low quality")
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert errors == []

    @pytest.mark.parametrize("key", sorted(REQUIRED_DECISION_KEYS))
    def test_missing_decision_key(self, key: str):
        decision = _valid_decision()
        del decision[key]
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert any(key in e for e in errors)

    def test_invalid_action(self):
        decision = _valid_decision(action="invalid_action")
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert any("action" in e for e in errors)

    @pytest.mark.parametrize("action", sorted(PACKET_ACTIONS))
    def test_all_valid_actions(self, action: str):
        decision = _valid_decision(action=action)
        # Add required fields for conditional actions
        if action == "approve_selected":
            decision["approved_queue_ids"] = ["q-1"]
        elif action == "hold":
            decision["hold_until"] = "2026-04-01"
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert errors == []

    def test_actor_non_empty(self):
        decision = _valid_decision(actor="")
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert any("actor" in e for e in errors)

    def test_decided_at_invalid(self):
        decision = _valid_decision(decided_at="bad")
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert any("decided_at" in e for e in errors)

    def test_reason_null_valid(self):
        decision = _valid_decision(reason=None)
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert errors == []

    def test_reason_string_valid(self):
        decision = _valid_decision(reason="Looks good")
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert errors == []

    def test_reason_wrong_type(self):
        decision = _valid_decision(reason=123)
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert any("reason" in e for e in errors)


# ─── AC-SCH-009-3: approve_selected constraints ──────────────────────────

class TestApproveSelectedConstraints:
    """AC-SCH-009-3: Validator rejects approve_selected packets that
    omit approved_queue_ids or include ids not in queue_ids."""

    def test_approve_selected_valid(self):
        decision = _valid_decision(
            action="approve_selected",
            approved_queue_ids=["q-1"],
        )
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert errors == []

    def test_approve_selected_multiple_ids(self):
        decision = _valid_decision(
            action="approve_selected",
            approved_queue_ids=["q-1", "q-2"],
        )
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert errors == []

    def test_approve_selected_missing_approved_queue_ids(self):
        decision = _valid_decision(action="approve_selected")
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert any("approved_queue_ids" in e for e in errors)

    def test_approve_selected_empty_approved_queue_ids(self):
        decision = _valid_decision(
            action="approve_selected",
            approved_queue_ids=[],
        )
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert any("approved_queue_ids" in e for e in errors)

    def test_approve_selected_ids_not_in_queue_ids(self):
        decision = _valid_decision(
            action="approve_selected",
            approved_queue_ids=["q-999"],
        )
        errors = validate_review_packet(
            _valid_packet(queue_ids=["q-1", "q-2"], decision=decision)
        )
        assert any("not in queue_ids" in e for e in errors)

    def test_approve_selected_partial_invalid_ids(self):
        decision = _valid_decision(
            action="approve_selected",
            approved_queue_ids=["q-1", "q-999"],
        )
        errors = validate_review_packet(
            _valid_packet(queue_ids=["q-1", "q-2"], decision=decision)
        )
        assert any("q-999" in e for e in errors)


# ─── Hold constraints ────────────────────────────────────────────────────

class TestHoldConstraints:

    def test_hold_valid(self):
        decision = _valid_decision(
            action="hold",
            hold_until="2026-04-01",
        )
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert errors == []

    def test_hold_missing_hold_until(self):
        decision = _valid_decision(action="hold")
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert any("hold_until" in e for e in errors)

    def test_hold_invalid_hold_until_format(self):
        decision = _valid_decision(
            action="hold",
            hold_until="not-a-date",
        )
        errors = validate_review_packet(_valid_packet(decision=decision))
        assert any("hold_until" in e for e in errors)


# ─── Strict validation ───────────────────────────────────────────────────

class TestStrictValidation:

    def test_strict_valid_passes(self):
        validate_review_packet_strict(_valid_packet())

    def test_strict_invalid_raises(self):
        data = _valid_packet()
        del data["packet_id"]
        with pytest.raises(SchemaValidationError):
            validate_review_packet_strict(data)


# ─── Builder ─────────────────────────────────────────────────────────────

class TestBuilder:

    def test_build_minimal(self):
        pkt = build_review_packet(
            packet_id="pkt-001",
            digest_date="2026-03-01",
            created_at="2026-03-01T12:00:00Z",
            source_id="s-001",
            run_ids=["run-1"],
            queue_ids=["q-1"],
        )
        errors = validate_review_packet(pkt)
        assert errors == []
        assert pkt["decision"] is None

    def test_build_with_decision(self):
        pkt = build_review_packet(
            packet_id="pkt-002",
            digest_date="2026-03-01",
            created_at="2026-03-01T12:00:00Z",
            source_id="s-002",
            run_ids=["run-1"],
            queue_ids=["q-1"],
            decision={
                "action": "approve_all",
                "actor": "user:bob",
                "decided_at": "2026-03-01T15:00:00Z",
                "reason": None,
            },
        )
        errors = validate_review_packet(pkt)
        assert errors == []
        assert pkt["decision"]["action"] == "approve_all"


# ─── AC-SCH-009-1 / AC-SCH-009-2: Persistence ────────────────────────────

class TestPersistence:
    """AC-SCH-009-1: Packet YAML files validate against schema.
    AC-SCH-009-2: Deterministic contents for same input."""

    def test_save_creates_file(self, tmp_path: Path):
        pkt = _valid_packet()
        path = save_review_packet(tmp_path, pkt)
        assert path.exists()
        assert path.suffix == ".yaml"

    def test_save_under_inbox_review_digest(self, tmp_path: Path):
        pkt = _valid_packet()
        path = save_review_packet(tmp_path, pkt)
        assert "Inbox/ReviewDigest" in str(path)

    def test_roundtrip(self, tmp_path: Path):
        original = _valid_packet()
        path = save_review_packet(tmp_path, original)
        loaded = load_review_packet(path)
        assert loaded["packet_id"] == original["packet_id"]
        assert loaded["source_id"] == original["source_id"]
        assert loaded["queue_ids"] == original["queue_ids"]
        assert loaded["run_ids"] == original["run_ids"]
        assert loaded["decision"] is None

    def test_roundtrip_with_decision(self, tmp_path: Path):
        decision = _valid_decision(action="reject", reason="Spam")
        original = _valid_packet(decision=decision)
        path = save_review_packet(tmp_path, original)
        loaded = load_review_packet(path)
        assert loaded["decision"]["action"] == "reject"
        assert loaded["decision"]["reason"] == "Spam"

    def test_load_nonexistent_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_review_packet(tmp_path / "nope.yaml")

    def test_load_invalid_raises(self, tmp_path: Path):
        bad_path = tmp_path / "Inbox" / "ReviewDigest" / "bad.yaml"
        bad_path.parent.mkdir(parents=True)
        bad_path.write_text("packet_id: pkt-bad\n")
        with pytest.raises(SchemaValidationError):
            load_review_packet(bad_path)

    def test_save_invalid_raises(self, tmp_path: Path):
        bad = {"packet_id": "pkt-bad"}
        with pytest.raises(SchemaValidationError):
            save_review_packet(tmp_path, bad)

    def test_deterministic_yaml_output(self, tmp_path: Path):
        """AC-SCH-009-2: Same input produces identical YAML output."""
        pkt = _valid_packet()
        p1 = save_review_packet(tmp_path, pkt)
        content1 = p1.read_text()

        # Overwrite with same data
        p2 = save_review_packet(tmp_path, pkt)
        content2 = p2.read_text()

        assert content1 == content2

    def test_n_sources_n_packets(self, tmp_path: Path):
        """AC-SCH-009-1: For N sources, exactly N packet files created."""
        n = 5
        for i in range(n):
            pkt = _valid_packet(
                packet_id=f"pkt-{i:03d}",
                source_id=f"s-{i:03d}",
            )
            save_review_packet(tmp_path, pkt)

        paths = list_review_packets(tmp_path)
        assert len(paths) == n

    def test_list_empty_vault(self, tmp_path: Path):
        paths = list_review_packets(tmp_path)
        assert paths == []

    def test_list_sorted(self, tmp_path: Path):
        for pid in ["pkt-c", "pkt-a", "pkt-b"]:
            save_review_packet(tmp_path, _valid_packet(packet_id=pid))
        paths = list_review_packets(tmp_path)
        names = [p.stem for p in paths]
        assert names == ["pkt-a", "pkt-b", "pkt-c"]
