"""
Tests for egress policy configuration (§9.2 TODO-Q-SEC-1 resolution).

Verifies acceptance criteria:
  AC-1: Missing Config/egress_policy.yaml defaults to report_only mode.
  AC-2: Config with mode=enforce is loaded and respected.
  AC-3: burn_in_started_at computes elapsed days deterministically.
  AC-4: Invalid mode produces validation error.
  AC-5: Config round-trips: write then read produces identical values.
  AC-6: last_transition_at and transitioned_by are null until first transition.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import yaml

from mycelium.egress_config import (
    CONFIG_RELATIVE_PATH,
    DEFAULT_MODE,
    EGRESS_MODES,
    EgressPolicyConfig,
    load_egress_policy,
    save_egress_policy,
    validate_egress_policy_config,
)


# ── AC-1: Missing config defaults to report_only ─────────────────────

class TestDefaultConfig:

    def test_missing_file_defaults_to_report_only(self, tmp_path):
        """AC-1: Missing config file defaults to report_only mode."""
        config = load_egress_policy(tmp_path)
        assert config.mode == "report_only"

    def test_default_mode_constant(self):
        assert DEFAULT_MODE == "report_only"

    def test_default_config_has_burn_in_started(self, tmp_path):
        config = load_egress_policy(tmp_path)
        assert config.burn_in_started_at != ""

    def test_default_config_null_transition_fields(self, tmp_path):
        """AC-6: last_transition_at and transitioned_by are null initially."""
        config = load_egress_policy(tmp_path)
        assert config.last_transition_at is None
        assert config.transitioned_by is None
        assert config.transition_reason is None


# ── AC-2: Config with mode=enforce is loaded ─────────────────────────

class TestLoadEnforceMode:

    def test_enforce_mode_loaded(self, tmp_path):
        """AC-2: Config with mode=enforce is loaded and respected."""
        config_path = tmp_path / CONFIG_RELATIVE_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.dump({
            "mode": "enforce",
            "burn_in_started_at": "2026-01-01T00:00:00+00:00",
            "last_transition_at": "2026-02-15T12:00:00+00:00",
            "transitioned_by": "admin",
            "transition_reason": "Burn-in complete",
        }))
        config = load_egress_policy(tmp_path)
        assert config.mode == "enforce"
        assert config.transitioned_by == "admin"
        assert config.transition_reason == "Burn-in complete"

    def test_report_only_mode_loaded(self, tmp_path):
        config_path = tmp_path / CONFIG_RELATIVE_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.dump({
            "mode": "report_only",
            "burn_in_started_at": "2026-01-01T00:00:00+00:00",
        }))
        config = load_egress_policy(tmp_path)
        assert config.mode == "report_only"


# ── AC-3: burn_in_started_at computes elapsed days ───────────────────

class TestBurnInElapsedDays:

    def test_elapsed_days_deterministic(self):
        """AC-3: Elapsed days computed deterministically at evaluation time."""
        config = EgressPolicyConfig(
            burn_in_started_at="2026-01-01T00:00:00+00:00",
        )
        now = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        assert config.burn_in_elapsed_days(now) == 14.0

    def test_elapsed_days_fractional(self):
        config = EgressPolicyConfig(
            burn_in_started_at="2026-01-01T00:00:00+00:00",
        )
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert config.burn_in_elapsed_days(now) == 0.5

    def test_elapsed_days_z_suffix(self):
        config = EgressPolicyConfig(
            burn_in_started_at="2026-01-01T00:00:00Z",
        )
        now = datetime(2026, 1, 8, 0, 0, 0, tzinfo=timezone.utc)
        assert config.burn_in_elapsed_days(now) == 7.0

    def test_elapsed_days_zero(self):
        ts = "2026-03-01T10:00:00+00:00"
        config = EgressPolicyConfig(burn_in_started_at=ts)
        now = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
        assert config.burn_in_elapsed_days(now) == 0.0

    def test_elapsed_days_uses_now_by_default(self):
        """When now is omitted, uses current time."""
        past = datetime.now(timezone.utc) - timedelta(days=5)
        config = EgressPolicyConfig(
            burn_in_started_at=past.isoformat(),
        )
        elapsed = config.burn_in_elapsed_days()
        assert 4.9 < elapsed < 5.1


# ── AC-4: Invalid mode validation ────────────────────────────────────

class TestValidation:

    def test_valid_report_only(self):
        errors = validate_egress_policy_config({
            "mode": "report_only",
            "burn_in_started_at": "2026-01-01T00:00:00+00:00",
        })
        assert errors == []

    def test_valid_enforce(self):
        errors = validate_egress_policy_config({
            "mode": "enforce",
            "burn_in_started_at": "2026-01-01T00:00:00+00:00",
        })
        assert errors == []

    def test_invalid_mode(self):
        """AC-4: Invalid mode value produces ERR_SCHEMA_VALIDATION."""
        errors = validate_egress_policy_config({
            "mode": "partial",
            "burn_in_started_at": "2026-01-01T00:00:00+00:00",
        })
        assert any("Invalid mode" in e for e in errors)

    def test_missing_mode(self):
        errors = validate_egress_policy_config({
            "burn_in_started_at": "2026-01-01T00:00:00+00:00",
        })
        assert any("mode" in e for e in errors)

    def test_missing_burn_in_started_at(self):
        errors = validate_egress_policy_config({
            "mode": "report_only",
        })
        assert any("burn_in_started_at" in e for e in errors)

    def test_invalid_burn_in_datetime(self):
        errors = validate_egress_policy_config({
            "mode": "report_only",
            "burn_in_started_at": "not-a-date",
        })
        assert any("burn_in_started_at" in e for e in errors)

    def test_invalid_last_transition_at(self):
        errors = validate_egress_policy_config({
            "mode": "enforce",
            "burn_in_started_at": "2026-01-01T00:00:00+00:00",
            "last_transition_at": "invalid-date",
        })
        assert any("last_transition_at" in e for e in errors)

    def test_null_last_transition_at_is_valid(self):
        errors = validate_egress_policy_config({
            "mode": "report_only",
            "burn_in_started_at": "2026-01-01T00:00:00+00:00",
            "last_transition_at": None,
        })
        assert errors == []

    def test_egress_modes_constant(self):
        assert EGRESS_MODES == {"report_only", "enforce"}


# ── AC-5: Config round-trip ──────────────────────────────────────────

class TestRoundTrip:

    def test_write_then_read_identical(self, tmp_path):
        """AC-5: Writing then reading produces identical values."""
        original = EgressPolicyConfig(
            mode="enforce",
            burn_in_started_at="2026-01-01T00:00:00+00:00",
            last_transition_at="2026-02-15T12:00:00+00:00",
            transitioned_by="admin-user",
            transition_reason="Burn-in period complete",
        )
        save_egress_policy(tmp_path, original)
        loaded = load_egress_policy(tmp_path)

        assert loaded.mode == original.mode
        assert loaded.burn_in_started_at == original.burn_in_started_at
        assert loaded.last_transition_at == original.last_transition_at
        assert loaded.transitioned_by == original.transitioned_by
        assert loaded.transition_reason == original.transition_reason

    def test_round_trip_with_nulls(self, tmp_path):
        """AC-5 + AC-6: Null fields round-trip correctly."""
        original = EgressPolicyConfig(
            mode="report_only",
            burn_in_started_at="2026-03-01T00:00:00+00:00",
            last_transition_at=None,
            transitioned_by=None,
            transition_reason=None,
        )
        save_egress_policy(tmp_path, original)
        loaded = load_egress_policy(tmp_path)

        assert loaded.mode == "report_only"
        assert loaded.last_transition_at is None
        assert loaded.transitioned_by is None
        assert loaded.transition_reason is None

    def test_to_dict_matches_fields(self):
        config = EgressPolicyConfig(
            mode="enforce",
            burn_in_started_at="2026-01-01T00:00:00+00:00",
            last_transition_at="2026-02-01T00:00:00+00:00",
            transitioned_by="test",
            transition_reason="testing",
        )
        d = config.to_dict()
        assert d["mode"] == "enforce"
        assert d["burn_in_started_at"] == "2026-01-01T00:00:00+00:00"
        assert d["last_transition_at"] == "2026-02-01T00:00:00+00:00"
        assert d["transitioned_by"] == "test"
        assert d["transition_reason"] == "testing"


# ── Save creates directory ───────────────────────────────────────────

class TestSaveCreatesDirectory:

    def test_creates_config_directory(self, tmp_path):
        config = EgressPolicyConfig()
        path = save_egress_policy(tmp_path, config)
        assert path.exists()
        assert path.parent.name == "Config"

    def test_config_file_is_valid_yaml(self, tmp_path):
        config = EgressPolicyConfig(
            mode="report_only",
            burn_in_started_at="2026-01-01T00:00:00+00:00",
        )
        path = save_egress_policy(tmp_path, config)
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["mode"] == "report_only"
        assert data["burn_in_started_at"] == "2026-01-01T00:00:00+00:00"
