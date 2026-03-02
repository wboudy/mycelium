"""Tests for Strict Mode flag (IF-003).

Validates acceptance criteria from §5.1.2:
  AC-IF-003-1: A fixture with an invalid Note schema causes ok=false when
               strict=true and produces a warning (not an error) when
               strict=false for a read-only command.
  AC-IF-003-2: For ingestion-associated warnings, the Delta Report includes
               corresponding warning entries (§4.2.6).
"""

from __future__ import annotations

import pytest

from mycelium.models import ErrorObject, WarningObject
from mycelium.strict import apply_strict_mode, collect_strict_warnings


# ─── Test fixtures ────────────────────────────────────────────────────────

SAMPLE_VALIDATION_ERRORS = [
    "Missing required key: type",
    "Invalid status: 'archived' (expected one of ['canon', 'draft', 'reviewed'])",
]


# ─── AC-IF-003-1: strict=true → ok=false; strict=false read-only → warning ─


class TestStrictTrue:
    """strict=true: validation errors produce ok=false."""

    def test_strict_true_with_errors_yields_ok_false(self):
        env = apply_strict_mode(
            "review",
            strict=True,
            validation_errors=SAMPLE_VALIDATION_ERRORS,
        )
        assert env.ok is False

    def test_strict_true_errors_contain_all_validation_messages(self):
        env = apply_strict_mode(
            "context",
            strict=True,
            validation_errors=SAMPLE_VALIDATION_ERRORS,
        )
        assert len(env.errors) == len(SAMPLE_VALIDATION_ERRORS)
        messages = [e.message for e in env.errors]
        for msg in SAMPLE_VALIDATION_ERRORS:
            assert msg in messages

    def test_strict_true_error_code_is_schema_validation(self):
        env = apply_strict_mode(
            "ingest",
            strict=True,
            validation_errors=["Missing required key: id"],
        )
        assert env.errors[0].code == "ERR_SCHEMA_VALIDATION"

    def test_strict_true_errors_not_retryable(self):
        env = apply_strict_mode(
            "ingest",
            strict=True,
            validation_errors=["bad type"],
        )
        assert env.errors[0].retryable is False

    def test_strict_true_no_warnings(self):
        env = apply_strict_mode(
            "review",
            strict=True,
            validation_errors=SAMPLE_VALIDATION_ERRORS,
        )
        assert env.warnings == []

    def test_strict_true_preserves_data(self):
        env = apply_strict_mode(
            "context",
            strict=True,
            validation_errors=["bad"],
            data={"partial": True},
        )
        assert env.data == {"partial": True}

    def test_strict_true_preserves_command(self):
        env = apply_strict_mode(
            "frontier",
            strict=True,
            validation_errors=["bad"],
        )
        assert env.command == "frontier"


class TestStrictFalseReadOnly:
    """strict=false + read_only: validation errors downgraded to warnings."""

    def test_strict_false_readonly_yields_ok_true(self):
        env = apply_strict_mode(
            "context",
            strict=False,
            validation_errors=SAMPLE_VALIDATION_ERRORS,
            read_only=True,
        )
        assert env.ok is True

    def test_strict_false_readonly_has_warnings_not_errors(self):
        env = apply_strict_mode(
            "review",
            strict=False,
            validation_errors=SAMPLE_VALIDATION_ERRORS,
            read_only=True,
        )
        assert env.errors == []
        assert len(env.warnings) == len(SAMPLE_VALIDATION_ERRORS)

    def test_strict_false_readonly_warning_code(self):
        env = apply_strict_mode(
            "context",
            strict=False,
            validation_errors=["Missing required key: type"],
            read_only=True,
        )
        assert env.warnings[0].code == "WARN_SCHEMA_VALIDATION"

    def test_strict_false_readonly_warning_messages_match(self):
        env = apply_strict_mode(
            "review",
            strict=False,
            validation_errors=SAMPLE_VALIDATION_ERRORS,
            read_only=True,
        )
        messages = [w.message for w in env.warnings]
        for msg in SAMPLE_VALIDATION_ERRORS:
            assert msg in messages

    def test_strict_false_readonly_preserves_data(self):
        env = apply_strict_mode(
            "context",
            strict=False,
            validation_errors=["bad"],
            read_only=True,
            data={"notes": 5},
        )
        assert env.data == {"notes": 5}


class TestStrictFalseWriteCommand:
    """strict=false + write command: validation errors still produce ok=false."""

    def test_strict_false_write_yields_ok_false(self):
        env = apply_strict_mode(
            "ingest",
            strict=False,
            validation_errors=SAMPLE_VALIDATION_ERRORS,
            read_only=False,
        )
        assert env.ok is False

    def test_strict_false_write_has_errors(self):
        env = apply_strict_mode(
            "ingest",
            strict=False,
            validation_errors=["Missing required key: type"],
            read_only=False,
        )
        assert len(env.errors) == 1
        assert env.errors[0].code == "ERR_SCHEMA_VALIDATION"


class TestNoValidationErrors:
    """When there are no validation errors, strict mode has no effect."""

    def test_no_errors_strict_true(self):
        env = apply_strict_mode("review", strict=True, validation_errors=[])
        assert env.ok is True
        assert env.errors == []
        assert env.warnings == []

    def test_no_errors_strict_false(self):
        env = apply_strict_mode("review", strict=False, validation_errors=[])
        assert env.ok is True
        assert env.errors == []
        assert env.warnings == []

    def test_no_errors_with_data(self):
        env = apply_strict_mode(
            "context",
            strict=True,
            validation_errors=[],
            data={"results": [1, 2, 3]},
        )
        assert env.ok is True
        assert env.data == {"results": [1, 2, 3]}


class TestTrace:
    """Trace passthrough."""

    def test_trace_passed_on_success(self):
        env = apply_strict_mode(
            "review",
            strict=True,
            validation_errors=[],
            trace={"elapsed_ms": 42},
        )
        assert env.trace == {"elapsed_ms": 42}

    def test_trace_passed_on_error(self):
        env = apply_strict_mode(
            "ingest",
            strict=True,
            validation_errors=["bad"],
            trace={"debug": True},
        )
        assert env.trace == {"debug": True}


# ─── AC-IF-003-2: Delta Report warning collection ─────────────────────────


class TestCollectStrictWarnings:
    """AC-IF-003-2: For ingestion-associated warnings, the Delta Report
    includes corresponding warning entries."""

    def test_strict_false_readonly_collects_warnings(self):
        warnings = collect_strict_warnings(
            SAMPLE_VALIDATION_ERRORS,
            strict=False,
            read_only=True,
        )
        assert len(warnings) == len(SAMPLE_VALIDATION_ERRORS)
        for w in warnings:
            assert "code" in w
            assert "message" in w
            assert w["code"] == "WARN_SCHEMA_VALIDATION"

    def test_strict_true_returns_empty(self):
        warnings = collect_strict_warnings(
            SAMPLE_VALIDATION_ERRORS,
            strict=True,
        )
        assert warnings == []

    def test_no_errors_returns_empty(self):
        warnings = collect_strict_warnings(
            [],
            strict=False,
            read_only=True,
        )
        assert warnings == []

    def test_strict_false_write_returns_empty(self):
        warnings = collect_strict_warnings(
            SAMPLE_VALIDATION_ERRORS,
            strict=False,
            read_only=False,
        )
        assert warnings == []

    def test_warning_format_matches_delta_report_schema(self):
        """Delta Report warnings schema: {code: string, message: string}."""
        warnings = collect_strict_warnings(
            ["Missing required key: type"],
            strict=False,
            read_only=True,
        )
        assert len(warnings) == 1
        w = warnings[0]
        assert isinstance(w["code"], str)
        assert isinstance(w["message"], str)
        assert w["message"] == "Missing required key: type"


# ─── Integration: strict mode with real schema validation ──────────────────


class TestIntegrationWithSchemaValidator:
    """Integration test combining schema.validate_shared_frontmatter with
    apply_strict_mode to verify the full AC-IF-003-1 scenario."""

    def test_invalid_note_strict_true_ok_false(self):
        from mycelium.schema import validate_shared_frontmatter

        # Fixture with invalid schema (missing type)
        frontmatter = {
            "id": "src-001",
            "status": "draft",
            "created": "2025-06-15T10:30:00Z",
            "updated": "2025-06-15T12:00:00Z",
        }
        errors = validate_shared_frontmatter(frontmatter)
        assert len(errors) > 0  # precondition: there are validation errors

        env = apply_strict_mode(
            "review",
            strict=True,
            validation_errors=errors,
            read_only=True,
        )
        assert env.ok is False
        assert len(env.errors) >= 1

    def test_invalid_note_strict_false_readonly_warning(self):
        from mycelium.schema import validate_shared_frontmatter

        frontmatter = {
            "id": "src-001",
            "status": "draft",
            "created": "2025-06-15T10:30:00Z",
            "updated": "2025-06-15T12:00:00Z",
        }
        errors = validate_shared_frontmatter(frontmatter)
        assert len(errors) > 0

        env = apply_strict_mode(
            "context",
            strict=False,
            validation_errors=errors,
            read_only=True,
        )
        assert env.ok is True
        assert len(env.warnings) >= 1
        assert env.errors == []

    def test_valid_note_strict_true_ok_true(self):
        from mycelium.schema import validate_shared_frontmatter

        frontmatter = {
            "type": "source",
            "id": "src-001",
            "status": "draft",
            "created": "2025-06-15T10:30:00Z",
            "updated": "2025-06-15T12:00:00Z",
        }
        errors = validate_shared_frontmatter(frontmatter)
        assert errors == []

        env = apply_strict_mode(
            "review",
            strict=True,
            validation_errors=errors,
        )
        assert env.ok is True
