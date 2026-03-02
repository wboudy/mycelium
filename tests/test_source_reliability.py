"""
Tests for source_reliability config (CONF-001 resolution).

Verifies:
  AC-1: Optional config file at Config/source_reliability.yaml.
  AC-2: Schema: map of key -> numeric in [0..1], plus "default".
  AC-3: Lookup order: exact match, parent-domain fallback, then "default".
  AC-4: Absent config → default 0.5.
  AC-5: Invalid values fail Strict Mode with ERR_SCHEMA_VALIDATION.
  AC-6: Non-Strict mode: invalid values produce warnings.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mycelium.source_reliability import (
    DEFAULT_RELIABILITY,
    _parent_domain,
    _validate_config,
    load_source_reliability,
    lookup_reliability,
)


# ─── Validation ──────────────────────────────────────────────────────────

class TestValidateConfig:

    def test_valid_entries(self):
        raw = {"example.com": 0.8, "default": 0.5}
        entries, errors = _validate_config(raw)
        assert errors == []
        assert entries == {"example.com": 0.8, "default": 0.5}

    def test_invalid_value_type(self):
        raw = {"example.com": "high"}
        entries, errors = _validate_config(raw)
        assert len(errors) == 1
        assert "number" in errors[0]
        assert entries == {}

    def test_boolean_rejected(self):
        raw = {"example.com": True}
        entries, errors = _validate_config(raw)
        assert len(errors) == 1

    def test_out_of_range_high(self):
        raw = {"example.com": 1.5}
        entries, errors = _validate_config(raw)
        assert len(errors) == 1
        assert "[0..1]" in errors[0]

    def test_out_of_range_low(self):
        raw = {"example.com": -0.1}
        entries, errors = _validate_config(raw)
        assert len(errors) == 1

    def test_int_accepted(self):
        raw = {"example.com": 1}
        entries, errors = _validate_config(raw)
        assert errors == []
        assert entries["example.com"] == 1.0

    def test_boundary_values(self):
        raw = {"a": 0.0, "b": 1.0}
        entries, errors = _validate_config(raw)
        assert errors == []
        assert entries == {"a": 0.0, "b": 1.0}

    def test_mixed_valid_invalid(self):
        raw = {"good.com": 0.7, "bad.com": "invalid", "ok.com": 0.3}
        entries, errors = _validate_config(raw)
        assert len(errors) == 1
        assert "good.com" in entries
        assert "ok.com" in entries
        assert "bad.com" not in entries


# ─── Parent domain ──────────────────────────────────────────────────────

class TestParentDomain:

    def test_subdomain(self):
        assert _parent_domain("blog.example.com") == "example.com"

    def test_deep_subdomain(self):
        assert _parent_domain("a.b.example.com") == "b.example.com"

    def test_no_parent(self):
        assert _parent_domain("example.com") is None

    def test_tld_only(self):
        assert _parent_domain("com") is None


# ─── AC-3: Lookup order ─────────────────────────────────────────────────

class TestLookupOrder:
    """AC-3: exact match, parent-domain fallback, then "default"."""

    def test_exact_match(self):
        entries = {"example.com": 0.9, "default": 0.5}
        assert lookup_reliability(entries, "example.com") == 0.9

    def test_parent_domain_fallback(self):
        entries = {"example.com": 0.8}
        assert lookup_reliability(entries, "blog.example.com") == 0.8

    def test_deep_parent_fallback(self):
        entries = {"example.com": 0.7}
        assert lookup_reliability(entries, "a.b.example.com") == 0.7

    def test_default_key_fallback(self):
        entries = {"other.com": 0.9, "default": 0.6}
        assert lookup_reliability(entries, "unknown.com") == 0.6

    def test_global_default_fallback(self):
        entries = {"other.com": 0.9}
        assert lookup_reliability(entries, "unknown.com") == DEFAULT_RELIABILITY

    def test_empty_entries(self):
        assert lookup_reliability({}, "anything.com") == DEFAULT_RELIABILITY

    def test_exact_takes_priority_over_parent(self):
        entries = {
            "blog.example.com": 0.9,
            "example.com": 0.7,
        }
        assert lookup_reliability(entries, "blog.example.com") == 0.9


# ─── AC-4: Absent config → default 0.5 ──────────────────────────────────

class TestAbsentConfig:
    """AC-4: If config absent, default is 0.5."""

    def test_absent_config(self, tmp_path):
        entries, env = load_source_reliability(tmp_path)
        assert entries == {}
        assert env.ok is True
        assert env.data["default"] == DEFAULT_RELIABILITY

    def test_default_constant(self):
        assert DEFAULT_RELIABILITY == 0.5


# ─── AC-1/2: Valid config loading ────────────────────────────────────────

class TestValidConfig:

    def test_load_valid(self, tmp_path):
        config = {"example.com": 0.8, "default": 0.6}
        config_path = tmp_path / "Config" / "source_reliability.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(yaml.dump(config))

        entries, env = load_source_reliability(tmp_path)
        assert env.ok is True
        assert entries["example.com"] == 0.8
        assert entries["default"] == 0.6

    def test_load_empty_yaml(self, tmp_path):
        config_path = tmp_path / "Config" / "source_reliability.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text("")

        entries, env = load_source_reliability(tmp_path)
        assert env.ok is True
        assert entries == {}


# ─── AC-5: Strict mode errors ───────────────────────────────────────────

class TestStrictMode:
    """AC-5: Invalid values fail Strict Mode with ERR_SCHEMA_VALIDATION."""

    def test_invalid_strict(self, tmp_path):
        config = {"example.com": "bad"}
        config_path = tmp_path / "Config" / "source_reliability.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(yaml.dump(config))

        entries, env = load_source_reliability(tmp_path, strict=True)
        assert env.ok is False
        assert any(e.code == "ERR_SCHEMA_VALIDATION" for e in env.errors)

    def test_out_of_range_strict(self, tmp_path):
        config = {"example.com": 2.0}
        config_path = tmp_path / "Config" / "source_reliability.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(yaml.dump(config))

        entries, env = load_source_reliability(tmp_path, strict=True)
        assert env.ok is False

    def test_invalid_yaml_strict(self, tmp_path):
        config_path = tmp_path / "Config" / "source_reliability.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text("[invalid yaml that is not a mapping")

        entries, env = load_source_reliability(tmp_path, strict=True)
        assert env.ok is False


# ─── AC-6: Non-strict warnings ──────────────────────────────────────────

class TestNonStrictWarnings:
    """AC-6: Non-Strict mode: invalid values produce warnings."""

    def test_invalid_non_strict(self, tmp_path):
        config = {"good.com": 0.7, "bad.com": "invalid"}
        config_path = tmp_path / "Config" / "source_reliability.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(yaml.dump(config))

        entries, env = load_source_reliability(tmp_path, strict=False)
        assert env.ok is True
        assert len(env.warnings) >= 1
        assert "good.com" in entries
        assert "bad.com" not in entries

    def test_not_mapping_non_strict(self, tmp_path):
        config_path = tmp_path / "Config" / "source_reliability.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text("- a list\n- not a mapping")

        entries, env = load_source_reliability(tmp_path, strict=False)
        assert env.ok is True
        assert len(env.warnings) >= 1
        assert entries == {}
