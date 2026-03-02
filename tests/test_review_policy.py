"""
Tests for review_policy.yaml config (§8.1.1, §8.3.1).

Acceptance Criteria:
- AC-1: Absent config → defaults (hold_ttl_days=14, git_mode.enabled=false).
- AC-2: hold_ttl_days=7 → 7-day TTL in hold_until computation.
- AC-3: git_mode.enabled=true activates Git Mode.
- AC-4: Invalid values → ERR_SCHEMA_VALIDATION in Strict Mode.
- AC-5: Invalid values → warnings (not errors) in non-Strict Mode.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from mycelium.review_policy import (
    DEFAULT_GIT_MODE_ENABLED,
    DEFAULT_HOLD_TTL_DAYS,
    ReviewPolicy,
    load_review_policy,
    save_review_policy,
    _validate_config,
)


# ---------------------------------------------------------------------------
# ReviewPolicy dataclass
# ---------------------------------------------------------------------------

class TestReviewPolicy:

    def test_defaults(self):
        p = ReviewPolicy()
        assert p.hold_ttl_days == 14
        assert p.git_mode_enabled is False

    def test_to_dict(self):
        p = ReviewPolicy(hold_ttl_days=7, git_mode_enabled=True)
        d = p.to_dict()
        assert d["hold_ttl_days"] == 7
        assert d["git_mode"]["enabled"] is True

    def test_hold_until_default(self):
        p = ReviewPolicy(hold_ttl_days=14)
        result = p.hold_until(from_date=date(2026, 1, 1))
        assert result == date(2026, 1, 15)

    def test_hold_until_custom_ttl(self):
        p = ReviewPolicy(hold_ttl_days=7)
        result = p.hold_until(from_date=date(2026, 3, 1))
        assert result == date(2026, 3, 8)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidateConfig:

    def test_valid_config(self):
        assert _validate_config({"hold_ttl_days": 7, "git_mode": {"enabled": True}}) == []

    def test_hold_ttl_not_int(self):
        errors = _validate_config({"hold_ttl_days": "abc"})
        assert len(errors) == 1
        assert "integer" in errors[0]

    def test_hold_ttl_bool_rejected(self):
        errors = _validate_config({"hold_ttl_days": True})
        assert len(errors) == 1

    def test_hold_ttl_negative(self):
        errors = _validate_config({"hold_ttl_days": 0})
        assert len(errors) == 1
        assert ">= 1" in errors[0]

    def test_git_mode_not_dict(self):
        errors = _validate_config({"git_mode": "yes"})
        assert len(errors) == 1
        assert "mapping" in errors[0]

    def test_git_mode_enabled_not_bool(self):
        errors = _validate_config({"git_mode": {"enabled": "yes"}})
        assert len(errors) == 1
        assert "boolean" in errors[0]

    def test_empty_config_valid(self):
        assert _validate_config({}) == []


# ---------------------------------------------------------------------------
# AC-1: Absent config → defaults
# ---------------------------------------------------------------------------

class TestAbsentConfig:

    def test_missing_file_returns_defaults(self, tmp_path: Path):
        policy, env = load_review_policy(tmp_path)
        assert env.ok is True
        assert policy.hold_ttl_days == DEFAULT_HOLD_TTL_DAYS
        assert policy.git_mode_enabled is DEFAULT_GIT_MODE_ENABLED

    def test_missing_file_strict_returns_defaults(self, tmp_path: Path):
        policy, env = load_review_policy(tmp_path, strict=True)
        assert env.ok is True
        assert policy.hold_ttl_days == 14


# ---------------------------------------------------------------------------
# AC-2: hold_ttl_days=7 → 7-day TTL
# ---------------------------------------------------------------------------

class TestHoldTTL:

    def test_custom_ttl(self, tmp_path: Path):
        config_dir = tmp_path / "Config"
        config_dir.mkdir()
        (config_dir / "review_policy.yaml").write_text(
            "hold_ttl_days: 7\n", encoding="utf-8"
        )
        policy, env = load_review_policy(tmp_path)
        assert env.ok is True
        assert policy.hold_ttl_days == 7
        assert policy.hold_until(from_date=date(2026, 1, 1)) == date(2026, 1, 8)


# ---------------------------------------------------------------------------
# AC-3: git_mode.enabled=true activates Git Mode
# ---------------------------------------------------------------------------

class TestGitMode:

    def test_git_mode_enabled(self, tmp_path: Path):
        config_dir = tmp_path / "Config"
        config_dir.mkdir()
        (config_dir / "review_policy.yaml").write_text(
            "git_mode:\n  enabled: true\n", encoding="utf-8"
        )
        policy, env = load_review_policy(tmp_path)
        assert env.ok is True
        assert policy.git_mode_enabled is True

    def test_git_mode_disabled(self, tmp_path: Path):
        config_dir = tmp_path / "Config"
        config_dir.mkdir()
        (config_dir / "review_policy.yaml").write_text(
            "git_mode:\n  enabled: false\n", encoding="utf-8"
        )
        policy, env = load_review_policy(tmp_path)
        assert policy.git_mode_enabled is False


# ---------------------------------------------------------------------------
# AC-4: Invalid values → ERR_SCHEMA_VALIDATION in Strict Mode
# ---------------------------------------------------------------------------

class TestStrictModeValidation:

    def test_invalid_ttl_strict(self, tmp_path: Path):
        config_dir = tmp_path / "Config"
        config_dir.mkdir()
        (config_dir / "review_policy.yaml").write_text(
            "hold_ttl_days: abc\n", encoding="utf-8"
        )
        policy, env = load_review_policy(tmp_path, strict=True)
        assert env.ok is False
        assert any(e.code == "ERR_SCHEMA_VALIDATION" for e in env.errors)

    def test_invalid_git_mode_strict(self, tmp_path: Path):
        config_dir = tmp_path / "Config"
        config_dir.mkdir()
        (config_dir / "review_policy.yaml").write_text(
            "git_mode: yes\n", encoding="utf-8"
        )
        policy, env = load_review_policy(tmp_path, strict=True)
        assert env.ok is False

    def test_malformed_yaml_strict(self, tmp_path: Path):
        config_dir = tmp_path / "Config"
        config_dir.mkdir()
        (config_dir / "review_policy.yaml").write_text(
            ": :\n  - [invalid\n", encoding="utf-8"
        )
        policy, env = load_review_policy(tmp_path, strict=True)
        assert env.ok is False


# ---------------------------------------------------------------------------
# AC-5: Invalid values → warnings in non-Strict Mode
# ---------------------------------------------------------------------------

class TestNonStrictModeValidation:

    def test_invalid_ttl_non_strict(self, tmp_path: Path):
        config_dir = tmp_path / "Config"
        config_dir.mkdir()
        (config_dir / "review_policy.yaml").write_text(
            "hold_ttl_days: abc\n", encoding="utf-8"
        )
        policy, env = load_review_policy(tmp_path, strict=False)
        assert env.ok is True
        assert len(env.warnings) >= 1
        assert any(w.code == "WARN_SCHEMA_VALIDATION" for w in env.warnings)
        # Falls back to defaults
        assert policy.hold_ttl_days == DEFAULT_HOLD_TTL_DAYS

    def test_malformed_yaml_non_strict(self, tmp_path: Path):
        config_dir = tmp_path / "Config"
        config_dir.mkdir()
        (config_dir / "review_policy.yaml").write_text(
            ": :\n  - [invalid\n", encoding="utf-8"
        )
        policy, env = load_review_policy(tmp_path, strict=False)
        assert env.ok is True
        assert len(env.warnings) >= 1


# ---------------------------------------------------------------------------
# Round-trip: save then load
# ---------------------------------------------------------------------------

class TestRoundTrip:

    def test_save_then_load(self, tmp_path: Path):
        original = ReviewPolicy(hold_ttl_days=21, git_mode_enabled=True)
        save_review_policy(tmp_path, original)
        loaded, env = load_review_policy(tmp_path)
        assert env.ok is True
        assert loaded.hold_ttl_days == 21
        assert loaded.git_mode_enabled is True

    def test_save_creates_directory(self, tmp_path: Path):
        policy = ReviewPolicy()
        save_review_policy(tmp_path, policy)
        assert (tmp_path / "Config" / "review_policy.yaml").exists()

    def test_round_trip_default_values(self, tmp_path: Path):
        save_review_policy(tmp_path, ReviewPolicy())
        loaded, _ = load_review_policy(tmp_path)
        assert loaded.hold_ttl_days == DEFAULT_HOLD_TTL_DAYS
        assert loaded.git_mode_enabled is DEFAULT_GIT_MODE_ENABLED
