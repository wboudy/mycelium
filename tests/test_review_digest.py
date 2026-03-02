"""
Tests for the review_digest command contract (CMD-RDG-001).

Verifies:
  AC-CMD-RDG-001-1: Digest includes one Review Packet per Source with
                     queue_ids and run_ids.
  AC-CMD-RDG-001-2: Packet actions are exactly approve_all,
                     approve_selected, hold, reject.
  AC-CMD-RDG-001-3: Digest generation is deterministic (contract-level).
"""

from __future__ import annotations

import pytest

from mycelium.commands.review_digest import (
    ERR_REVIEW_DIGEST_EMPTY,
    ERR_SCHEMA_VALIDATION,
    PacketAction,
    ReviewDigestInput,
    ReviewPacket,
    execute_review_digest,
    validate_review_digest_input,
)
from mycelium.models import ErrorObject


# ─── PacketAction enum ────────────────────────────────────────────────────

class TestPacketAction:
    """AC-CMD-RDG-001-2: Packet actions are exactly four values."""

    def test_exactly_four_actions(self):
        assert len(PacketAction) == 4

    def test_action_values(self):
        assert set(a.value for a in PacketAction) == {
            "approve_all", "approve_selected", "hold", "reject"
        }


# ─── Input validation ────────────────────────────────────────────────────

class TestValidateInput:

    def test_defaults(self):
        result = validate_review_digest_input({})
        assert isinstance(result, ReviewDigestInput)
        assert result.include_claim_cards is True
        assert result.run_ids == []
        assert result.limit_sources is None

    def test_explicit_date(self):
        result = validate_review_digest_input({"date": "2026-03-01"})
        assert isinstance(result, ReviewDigestInput)
        assert result.date == "2026-03-01"

    def test_invalid_date_format(self):
        result = validate_review_digest_input({"date": "not-a-date"})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_SCHEMA_VALIDATION

    def test_run_ids(self):
        result = validate_review_digest_input({"run_ids": ["r1", "r2"]})
        assert isinstance(result, ReviewDigestInput)
        assert result.run_ids == ["r1", "r2"]

    def test_invalid_run_ids_type(self):
        result = validate_review_digest_input({"run_ids": "not-a-list"})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_SCHEMA_VALIDATION

    def test_limit_sources(self):
        result = validate_review_digest_input({"limit_sources": 5})
        assert isinstance(result, ReviewDigestInput)
        assert result.limit_sources == 5

    def test_invalid_limit_sources(self):
        result = validate_review_digest_input({"limit_sources": 0})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_SCHEMA_VALIDATION

    def test_negative_limit_sources(self):
        result = validate_review_digest_input({"limit_sources": -1})
        assert isinstance(result, ErrorObject)

    def test_include_claim_cards_false(self):
        result = validate_review_digest_input({"include_claim_cards": False})
        assert isinstance(result, ReviewDigestInput)
        assert result.include_claim_cards is False

    def test_actor_recorded(self):
        result = validate_review_digest_input({"actor": "user:alice"})
        assert isinstance(result, ReviewDigestInput)
        assert result.actor == "user:alice"


# ─── ReviewPacket model ──────────────────────────────────────────────────

class TestReviewPacket:
    """AC-CMD-RDG-001-1: Each packet includes queue_ids and run_ids."""

    def test_packet_has_queue_ids_and_run_ids(self):
        pkt = ReviewPacket(
            source_id="src-1",
            queue_ids=["q1", "q2"],
            run_ids=["r1"],
            packet_path="Inbox/ReviewDigest/packets/src-1.md",
        )
        d = pkt.to_dict()
        assert d["queue_ids"] == ["q1", "q2"]
        assert d["run_ids"] == ["r1"]
        assert d["source_id"] == "src-1"
        assert d["packet_path"] == "Inbox/ReviewDigest/packets/src-1.md"

    def test_packet_has_allowed_actions(self):
        """AC-CMD-RDG-001-2: Default allowed_actions matches PacketAction."""
        pkt = ReviewPacket(
            source_id="src-1",
            queue_ids=["q1"],
            run_ids=["r1"],
            packet_path="p.md",
        )
        assert set(pkt.allowed_actions) == {
            "approve_all", "approve_selected", "hold", "reject"
        }


# ─── execute_review_digest ───────────────────────────────────────────────

class TestExecuteReviewDigest:

    def test_valid_input_returns_envelope(self):
        env = execute_review_digest({"date": "2026-03-01"})
        assert env.ok is True
        assert env.command == "review_digest"

    def test_output_data_structure(self):
        env = execute_review_digest({})
        assert "digest_path" in env.data
        assert "packet_paths" in env.data
        assert "source_count" in env.data
        assert "pending_item_count" in env.data

    def test_invalid_input_returns_error(self):
        env = execute_review_digest({"date": "bad"})
        assert env.ok is False
        assert env.errors[0].code == ERR_SCHEMA_VALIDATION

    def test_envelope_keys(self):
        env = execute_review_digest({})
        d = env.to_dict()
        assert set(d.keys()) == {"ok", "command", "timestamp", "data", "errors", "warnings", "trace"}

    def test_deterministic_output_structure(self):
        """AC-CMD-RDG-001-3: Same input produces same output structure."""
        env1 = execute_review_digest({"date": "2026-03-01"})
        env2 = execute_review_digest({"date": "2026-03-01"})
        assert env1.data.keys() == env2.data.keys()
        assert env1.command == env2.command == "review_digest"
