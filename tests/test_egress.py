"""
Tests for egress policy enforcement (SEC-001, SEC-002, SEC-003).

Verifies acceptance criteria from §9.2:
  AC-SEC-001-1: Blocklisted path fails with ERR_EGRESS_POLICY_BLOCK
                and emits egress_blocked audit event.
  AC-SEC-001-2: Allowlisted payload emits egress_completed audit event
                including bytes_sent and destination.
  AC-SEC-002-1: Egress audit events include either locally stored payload
                reference or payload digest plus source file paths.
  AC-SEC-002-2: Egress audit events include a reason field.
  AC-SEC-003-1: In report_only, blocked content logged as simulation.
  AC-SEC-003-2: In enforce, blocklisted payloads rejected.
  AC-SEC-003-3: Mode transitions emit audit event.
"""

from __future__ import annotations

import json

import pytest
import yaml

from mycelium.audit import EventType, read_audit_log
from mycelium.egress import (
    DEFAULT_ALLOWLIST,
    DEFAULT_BLOCKLIST,
    EgressPolicyError,
    check_egress_policy,
    compute_payload_digest,
    egress,
    egress_with_policy,
)
from mycelium.egress_config import (
    CONFIG_RELATIVE_PATH,
    EgressPolicyConfig,
    EgressTransitionError,
    load_egress_policy,
    save_egress_policy,
    transition_egress_mode,
)


# ─── Policy check (no side effects) ─────────────────────────────────────

class TestCheckEgressPolicy:

    @pytest.mark.parametrize("path", [
        "Sources/src-001.md",
        "Claims/clm-001.md",
        "Concepts/concept.md",
        "Questions/q-001.md",
        "Projects/project.md",
        "MOCs/moc.md",
        "Inbox/ReviewDigest/digest.yaml",
        "Reports/Delta/run-001.yaml",
    ])
    def test_default_allowlist_paths(self, path: str):
        allowed, pattern = check_egress_policy(path)
        assert allowed is True
        assert pattern is not None

    @pytest.mark.parametrize("path", [
        "Logs/Audit/audit-2025-06-15.jsonl",
        "Indexes/dedupe.json",
        "Quarantine/bad-note.md",
        "some/.git/config",
        "keys/server.key",
        "certs/ca.pem",
        "Config/secret-api.yaml",
    ])
    def test_default_blocklist_paths(self, path: str):
        allowed, pattern = check_egress_policy(path)
        assert allowed is False
        assert pattern is not None

    def test_default_deny_unknown_path(self):
        allowed, pattern = check_egress_policy("unknown/random-file.txt")
        assert allowed is False
        assert pattern is None  # no matching pattern

    def test_blocklist_takes_priority(self):
        """A path matching both allowlist and blocklist is blocked."""
        allowed, pattern = check_egress_policy(
            "Sources/secret.key",
            allowlist=["Sources/**"],
            blocklist=["**/*.key"],
        )
        assert allowed is False

    def test_custom_allowlist(self):
        allowed, _ = check_egress_policy(
            "Custom/data.json",
            allowlist=["Custom/**"],
            blocklist=[],
        )
        assert allowed is True

    def test_empty_patterns_default_deny(self):
        allowed, _ = check_egress_policy("any/path.md", allowlist=[], blocklist=[])
        assert allowed is False


# ─── AC-SEC-001-1: blocklisted path emits egress_blocked ─────────────────

class TestEgressBlocked:
    """AC-SEC-001-1: Blocklisted egress fails and emits audit event."""

    def test_blocked_raises_policy_error(self, tmp_path):
        with pytest.raises(EgressPolicyError) as exc_info:
            egress(
                tmp_path,
                "Logs/Audit/audit.jsonl",
                payload_bytes=1024,
                destination="api.example.com",
                actor="test",
            )
        assert exc_info.value.code == "ERR_EGRESS_POLICY_BLOCK"

    def test_blocked_emits_audit_event(self, tmp_path):
        with pytest.raises(EgressPolicyError):
            egress(
                tmp_path,
                "Quarantine/bad.md",
                payload_bytes=512,
                destination="api.example.com",
                actor="test-agent",
            )
        # Verify audit event was written
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        assert len(log_files) == 1
        events = read_audit_log(log_files[0])
        assert len(events) == 1
        assert events[0].event_type == EventType.EGRESS_BLOCKED.value
        assert "Quarantine/bad.md" in events[0].targets
        assert events[0].details["reason"] == "ERR_EGRESS_POLICY_BLOCK"

    def test_default_deny_emits_audit_event(self, tmp_path):
        with pytest.raises(EgressPolicyError):
            egress(
                tmp_path,
                "unknown/file.txt",
                payload_bytes=100,
                destination="somewhere",
            )
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        assert len(log_files) == 1


# ─── AC-SEC-001-2: allowlisted path emits egress_completed ──────────────

class TestEgressAllowed:
    """AC-SEC-001-2: Allowlisted egress emits egress_completed audit event."""

    def test_allowed_returns_result(self, tmp_path):
        result = egress(
            tmp_path,
            "Sources/src-001.md",
            payload_bytes=2048,
            destination="api.example.com",
            actor="test-agent",
        )
        assert result["allowed"] is True
        assert result["bytes_sent"] == 2048
        assert result["destination"] == "api.example.com"

    def test_allowed_emits_audit_event(self, tmp_path):
        egress(
            tmp_path,
            "Claims/clm-001.md",
            payload_bytes=4096,
            destination="review-service",
            actor="test-agent",
        )
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        assert len(log_files) == 1
        events = read_audit_log(log_files[0])
        assert len(events) == 1
        assert events[0].event_type == EventType.EGRESS_COMPLETED.value
        assert events[0].details["bytes_sent"] == 4096
        assert events[0].details["destination"] == "review-service"

    def test_actor_recorded(self, tmp_path):
        egress(
            tmp_path,
            "Sources/src.md",
            payload_bytes=100,
            destination="dest",
            actor="my-agent",
        )
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        events = read_audit_log(log_files[0])
        assert events[0].actor == "my-agent"


# ─── Default pattern coverage ───────────────────────────────────────────

class TestDefaultPatterns:

    def test_allowlist_has_expected_entries(self):
        assert len(DEFAULT_ALLOWLIST) == 8

    def test_blocklist_has_expected_entries(self):
        assert len(DEFAULT_BLOCKLIST) == 7


# ─── AC-SEC-002-1: payload reference or digest + source paths ────────

class TestEgressContentLogging:
    """AC-SEC-002-1: Egress audit includes payload ref or digest + paths."""

    def test_payload_ref_in_audit_event(self, tmp_path):
        """AC-SEC-002-1a: Locally stored payload reference."""
        egress(
            tmp_path,
            "Sources/src-001.md",
            payload_bytes=2048,
            destination="api.example.com",
            actor="test-agent",
            payload_ref="Outbox/payload-abc123.json",
        )
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        events = read_audit_log(log_files[0])
        assert events[0].details["payload_ref"] == "Outbox/payload-abc123.json"

    def test_payload_ref_in_result(self, tmp_path):
        result = egress(
            tmp_path,
            "Sources/src-001.md",
            payload_bytes=2048,
            destination="api.example.com",
            payload_ref="Outbox/payload-abc123.json",
        )
        assert result["payload_ref"] == "Outbox/payload-abc123.json"

    def test_payload_digest_and_source_paths_in_audit(self, tmp_path):
        """AC-SEC-002-1b: Payload digest plus source file paths."""
        digest = "sha256:" + "a" * 64
        paths = ["Sources/src-001.md", "Sources/src-002.md"]
        egress(
            tmp_path,
            "Claims/clm-001.md",
            payload_bytes=4096,
            destination="review-service",
            actor="test-agent",
            payload_digest=digest,
            source_paths=paths,
        )
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        events = read_audit_log(log_files[0])
        assert events[0].details["payload_digest"] == digest
        assert events[0].details["source_paths"] == paths

    def test_payload_digest_and_source_paths_in_result(self, tmp_path):
        digest = "sha256:" + "b" * 64
        paths = ["Sources/src-003.md"]
        result = egress(
            tmp_path,
            "Claims/clm-001.md",
            payload_bytes=1024,
            destination="dest",
            payload_digest=digest,
            source_paths=paths,
        )
        assert result["payload_digest"] == digest
        assert result["source_paths"] == paths

    def test_no_content_fields_when_omitted(self, tmp_path):
        """When no payload ref/digest/paths supplied, fields are absent."""
        egress(
            tmp_path,
            "Sources/src.md",
            payload_bytes=100,
            destination="dest",
        )
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        events = read_audit_log(log_files[0])
        assert "payload_ref" not in events[0].details
        assert "payload_digest" not in events[0].details
        assert "source_paths" not in events[0].details

    def test_both_ref_and_digest_allowed(self, tmp_path):
        """Callers may supply both ref and digest (belt-and-suspenders)."""
        result = egress(
            tmp_path,
            "Sources/src.md",
            payload_bytes=100,
            destination="dest",
            payload_ref="Outbox/p.json",
            payload_digest="sha256:" + "c" * 64,
            source_paths=["Sources/src.md"],
        )
        assert "payload_ref" in result
        assert "payload_digest" in result
        assert "source_paths" in result


# ─── AC-SEC-002-2: reason field in egress audit events ───────────────

class TestEgressReason:
    """AC-SEC-002-2: Egress audit events include a reason field."""

    def test_reason_in_completed_audit_event(self, tmp_path):
        egress(
            tmp_path,
            "Sources/src-001.md",
            payload_bytes=2048,
            destination="api.example.com",
            actor="test-agent",
            reason="review-digest command: user requested weekly summary",
        )
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        events = read_audit_log(log_files[0])
        assert events[0].details["reason"] == (
            "review-digest command: user requested weekly summary"
        )

    def test_reason_in_result(self, tmp_path):
        result = egress(
            tmp_path,
            "Sources/src-001.md",
            payload_bytes=100,
            destination="dest",
            reason="delta-report command",
        )
        assert result["reason"] == "delta-report command"

    def test_reason_in_blocked_audit_event(self, tmp_path):
        """Blocked events store reason as egress_reason (separate from ERR code)."""
        with pytest.raises(EgressPolicyError):
            egress(
                tmp_path,
                "Quarantine/bad.md",
                payload_bytes=100,
                destination="dest",
                reason="user requested export",
            )
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        events = read_audit_log(log_files[0])
        # "reason" key holds ERR_EGRESS_POLICY_BLOCK, "egress_reason" holds the why
        assert events[0].details["reason"] == "ERR_EGRESS_POLICY_BLOCK"
        assert events[0].details["egress_reason"] == "user requested export"

    def test_no_reason_when_omitted(self, tmp_path):
        egress(
            tmp_path,
            "Sources/src.md",
            payload_bytes=100,
            destination="dest",
        )
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        events = read_audit_log(log_files[0])
        assert "reason" not in events[0].details

    def test_reason_with_digest_and_paths(self, tmp_path):
        """Full SEC-002 audit event: reason + digest + source paths."""
        digest = "sha256:" + "d" * 64
        paths = ["Sources/a.md", "Sources/b.md"]
        egress(
            tmp_path,
            "Claims/clm.md",
            payload_bytes=8192,
            destination="llm-api",
            actor="extract-agent",
            reason="extract command: processing new sources",
            payload_digest=digest,
            source_paths=paths,
        )
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        events = read_audit_log(log_files[0])
        d = events[0].details
        assert d["reason"] == "extract command: processing new sources"
        assert d["payload_digest"] == digest
        assert d["source_paths"] == paths
        assert d["bytes_sent"] == 8192
        assert d["destination"] == "llm-api"


# ─── compute_payload_digest ──────────────────────────────────────────

class TestComputePayloadDigest:

    def test_returns_sha256_prefixed(self):
        digest = compute_payload_digest(b"hello world")
        assert digest.startswith("sha256:")

    def test_correct_hash(self):
        import hashlib
        expected = "sha256:" + hashlib.sha256(b"test data").hexdigest()
        assert compute_payload_digest(b"test data") == expected

    def test_deterministic(self):
        d1 = compute_payload_digest(b"same content")
        d2 = compute_payload_digest(b"same content")
        assert d1 == d2

    def test_different_content_different_digest(self):
        d1 = compute_payload_digest(b"content a")
        d2 = compute_payload_digest(b"content b")
        assert d1 != d2

    def test_empty_payload(self):
        digest = compute_payload_digest(b"")
        assert digest.startswith("sha256:")
        assert len(digest) == 7 + 64  # "sha256:" + 64 hex chars


# ═══════════════════════════════════════════════════════════════════════
# SEC-003: Egress mode transitions (§9.2)
# ═══════════════════════════════════════════════════════════════════════

# ─── AC-SEC-003-1: report_only mode ──────────────────────────────────

class TestReportOnlyMode:
    """AC-SEC-003-1: In report_only, blocked content is logged as simulation
    but send path remains allowed."""

    def test_blocked_path_not_raised_in_report_only(self, tmp_path):
        """Blocklisted path does NOT raise in report_only mode."""
        result = egress_with_policy(
            tmp_path,
            "Quarantine/bad.md",
            payload_bytes=512,
            destination="api.example.com",
            mode="report_only",
            actor="test",
        )
        assert result["allowed"] is True
        assert result["simulated_block"] is True

    def test_simulation_event_emitted(self, tmp_path):
        """Simulation egress_blocked event is emitted with simulation=True."""
        egress_with_policy(
            tmp_path,
            "Logs/Audit/audit.jsonl",
            payload_bytes=1024,
            destination="api.example.com",
            mode="report_only",
            actor="test-agent",
        )
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        assert len(log_files) == 1
        events = read_audit_log(log_files[0])
        assert len(events) == 1
        assert events[0].event_type == EventType.EGRESS_BLOCKED.value
        assert events[0].details["simulation"] is True
        assert events[0].details["reason"] == "ERR_EGRESS_POLICY_BLOCK"

    def test_report_only_returns_would_block_pattern(self, tmp_path):
        result = egress_with_policy(
            tmp_path,
            "Quarantine/bad.md",
            payload_bytes=100,
            destination="dest",
            mode="report_only",
        )
        assert result["would_block_pattern"] == "Quarantine/**"

    def test_allowed_path_in_report_only_works_normally(self, tmp_path):
        """Allowed paths go through normal egress in report_only mode."""
        result = egress_with_policy(
            tmp_path,
            "Sources/src.md",
            payload_bytes=100,
            destination="dest",
            mode="report_only",
        )
        assert result["allowed"] is True
        assert "simulated_block" not in result

    def test_report_only_reason_included(self, tmp_path):
        result = egress_with_policy(
            tmp_path,
            "Quarantine/bad.md",
            payload_bytes=100,
            destination="dest",
            mode="report_only",
            reason="test export",
        )
        assert result["reason"] == "test export"

    def test_default_deny_in_report_only(self, tmp_path):
        """Default-denied paths also get simulation treatment."""
        result = egress_with_policy(
            tmp_path,
            "unknown/random.txt",
            payload_bytes=100,
            destination="dest",
            mode="report_only",
        )
        assert result["simulated_block"] is True


# ─── AC-SEC-003-2: enforce mode ──────────────────────────────────────

class TestEnforceMode:
    """AC-SEC-003-2: In enforce, blocklisted payloads rejected."""

    def test_blocked_path_raises_in_enforce(self, tmp_path):
        with pytest.raises(EgressPolicyError):
            egress_with_policy(
                tmp_path,
                "Quarantine/bad.md",
                payload_bytes=512,
                destination="api.example.com",
                mode="enforce",
                actor="test",
            )

    def test_allowed_path_succeeds_in_enforce(self, tmp_path):
        result = egress_with_policy(
            tmp_path,
            "Sources/src.md",
            payload_bytes=100,
            destination="dest",
            mode="enforce",
        )
        assert result["allowed"] is True

    def test_enforce_is_default_mode(self, tmp_path):
        """Default mode parameter is enforce."""
        with pytest.raises(EgressPolicyError):
            egress_with_policy(
                tmp_path,
                "Quarantine/bad.md",
                payload_bytes=100,
                destination="dest",
            )


# ─── AC-SEC-003-3: mode transition audit events ─────────────────────

class TestModeTransition:
    """AC-SEC-003-3: Mode transitions emit audit event."""

    def _setup_report_only(self, vault_root):
        config = EgressPolicyConfig(
            mode="report_only",
            burn_in_started_at="2026-01-01T00:00:00+00:00",
        )
        save_egress_policy(vault_root, config)

    def _setup_enforce(self, vault_root):
        config = EgressPolicyConfig(
            mode="enforce",
            burn_in_started_at="2026-01-01T00:00:00+00:00",
        )
        save_egress_policy(vault_root, config)

    def test_transition_report_only_to_enforce(self, tmp_path):
        self._setup_report_only(tmp_path)
        config = transition_egress_mode(
            tmp_path,
            "enforce",
            actor="admin",
            reason="Burn-in complete",
        )
        assert config.mode == "enforce"
        assert config.transitioned_by == "admin"
        assert config.transition_reason == "Burn-in complete"
        assert config.last_transition_at is not None

    def test_transition_enforce_to_report_only(self, tmp_path):
        self._setup_enforce(tmp_path)
        config = transition_egress_mode(
            tmp_path,
            "report_only",
            actor="admin",
            reason="Reverting for investigation",
        )
        assert config.mode == "report_only"

    def test_transition_emits_audit_event(self, tmp_path):
        self._setup_report_only(tmp_path)
        transition_egress_mode(
            tmp_path,
            "enforce",
            actor="admin",
            reason="Ready to enforce",
        )
        log_files = list((tmp_path / "Logs" / "Audit").glob("*.jsonl"))
        assert len(log_files) == 1
        events = read_audit_log(log_files[0])
        assert len(events) == 1
        assert events[0].event_type == EventType.EGRESS_MODE_TRANSITION.value
        assert events[0].details["old_mode"] == "report_only"
        assert events[0].details["new_mode"] == "enforce"
        assert events[0].details["reason"] == "Ready to enforce"
        assert events[0].actor == "admin"

    def test_transition_persists_config(self, tmp_path):
        self._setup_report_only(tmp_path)
        transition_egress_mode(tmp_path, "enforce", actor="admin")
        loaded = load_egress_policy(tmp_path)
        assert loaded.mode == "enforce"
        assert loaded.transitioned_by == "admin"

    def test_same_mode_raises(self, tmp_path):
        self._setup_report_only(tmp_path)
        with pytest.raises(EgressTransitionError):
            transition_egress_mode(tmp_path, "report_only", actor="admin")

    def test_invalid_mode_raises(self, tmp_path):
        self._setup_report_only(tmp_path)
        with pytest.raises(EgressTransitionError):
            transition_egress_mode(tmp_path, "partial", actor="admin")

    def test_transition_without_reason(self, tmp_path):
        self._setup_report_only(tmp_path)
        config = transition_egress_mode(tmp_path, "enforce", actor="admin")
        assert config.transition_reason is None
