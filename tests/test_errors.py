"""Tests for stage-scoped pipeline error types (ERR-001).

Validates acceptance criteria from §10.1:
  AC-ERR-001-1: For induced failures in each Stage, the returned error
                includes `stage` and a deterministic `code`.
  AC-ERR-001-2: Retrying the same ingestion after a transient failure
                produces a successful run without requiring manual cleanup
                of Canonical Scope. (Verified via retryable flag semantics.)

Also validates PIPE-003 Stage Name constraints from §6.1.2.
"""

from __future__ import annotations

import pytest

from mycelium.errors import (
    ERROR_CODES,
    VALID_STAGE_NAMES,
    PipelineError,
    StageName,
    canon_write_forbidden,
    capture_error,
    extraction_error,
    normalize_error,
    schema_validation_error,
)
from mycelium.models import ErrorObject


# ─── StageName enum ────────────────────────────────────────────────────────

class TestStageName:
    """PIPE-003: Canonical Stage Names from §6.1.2."""

    EXPECTED_STAGES = {
        "capture", "normalize", "fingerprint",
        "extract", "compare", "delta", "propose_queue",
    }

    def test_all_expected_stages_defined(self):
        assert {s.value for s in StageName} == self.EXPECTED_STAGES

    def test_valid_stage_names_matches_enum(self):
        assert VALID_STAGE_NAMES == self.EXPECTED_STAGES

    def test_stage_is_string_enum(self):
        assert StageName.CAPTURE == "capture"
        assert isinstance(StageName.CAPTURE, str)


# ─── PipelineError ─────────────────────────────────────────────────────────

class TestPipelineError:
    """ERR-001: Pipeline failures are explicit, stage-scoped, and carry
    deterministic codes."""

    def test_basic_construction(self):
        err = PipelineError("ERR_CAPTURE_FAILED", "timeout", stage="capture")
        assert err.code == "ERR_CAPTURE_FAILED"
        assert str(err) == "timeout"
        assert err.stage == "capture"

    def test_is_exception(self):
        err = PipelineError("ERR_X", "fail")
        assert isinstance(err, Exception)
        with pytest.raises(PipelineError):
            raise err

    def test_invalid_stage_rejected(self):
        with pytest.raises(ValueError, match="Invalid stage name"):
            PipelineError("ERR_X", "fail", stage="invalid_stage")

    def test_none_stage_allowed(self):
        err = PipelineError("ERR_INVALID_INPUT", "bad url")
        assert err.stage is None

    def test_details_stored(self):
        err = PipelineError(
            "ERR_CAPTURE_FAILED", "timeout",
            stage="capture",
            details={"url": "http://example.com", "elapsed_ms": 30000},
        )
        assert err.details == {"url": "http://example.com", "elapsed_ms": 30000}

    def test_retryable_explicit(self):
        err = PipelineError("ERR_X", "fail", retryable=True)
        assert err.retryable is True

    def test_retryable_from_registry(self):
        # ERR_CAPTURE_FAILED is retryable by default
        err = PipelineError("ERR_CAPTURE_FAILED", "timeout")
        assert err.retryable is True

        # ERR_SCHEMA_VALIDATION is not retryable
        err2 = PipelineError("ERR_SCHEMA_VALIDATION", "bad schema")
        assert err2.retryable is False

    def test_retryable_explicit_overrides_registry(self):
        err = PipelineError(
            "ERR_CAPTURE_FAILED", "permanent failure",
            retryable=False,
        )
        assert err.retryable is False

    def test_unknown_code_defaults_not_retryable(self):
        err = PipelineError("ERR_CUSTOM_UNKNOWN", "something")
        assert err.retryable is False


# ─── AC-ERR-001-1: stage and deterministic code in errors ─────────────────

class TestErrorInEachStage:
    """AC-ERR-001-1: For induced failures in each Stage, the returned error
    includes `stage` and a deterministic `code`."""

    @pytest.mark.parametrize("stage", VALID_STAGE_NAMES)
    def test_error_carries_stage(self, stage: str):
        err = PipelineError("ERR_TEST", "test failure", stage=stage)
        assert err.stage == stage
        assert err.code == "ERR_TEST"

    @pytest.mark.parametrize("stage", VALID_STAGE_NAMES)
    def test_error_object_carries_stage(self, stage: str):
        err = PipelineError("ERR_TEST", "test failure", stage=stage)
        obj = err.to_error_object()
        assert isinstance(obj, ErrorObject)
        d = obj.to_dict()
        assert d["stage"] == stage
        assert d["code"] == "ERR_TEST"
        assert "message" in d
        assert "retryable" in d


# ─── AC-ERR-001-2: retryable semantics ───────────────────────────────────

class TestRetryableSemantics:
    """AC-ERR-001-2: Retrying after transient failure works without manual
    Canonical cleanup. Validated via retryable flag semantics."""

    def test_capture_errors_retryable_by_default(self):
        err = capture_error("network timeout")
        assert err.retryable is True

    def test_extraction_errors_retryable_by_default(self):
        err = extraction_error("LLM timeout")
        assert err.retryable is True

    def test_schema_errors_not_retryable(self):
        err = schema_validation_error("missing required key: type")
        assert err.retryable is False

    def test_normalize_errors_not_retryable_by_default(self):
        err = normalize_error("encoding error")
        assert err.retryable is False


# ─── to_error_object conversion ──────────────────────────────────────────

class TestToErrorObject:
    """PipelineError → ErrorObject conversion for OutputEnvelope."""

    def test_basic_conversion(self):
        err = PipelineError("ERR_CAPTURE_FAILED", "timeout", stage="capture")
        obj = err.to_error_object()
        assert isinstance(obj, ErrorObject)
        assert obj.code == "ERR_CAPTURE_FAILED"
        assert obj.message == "timeout"
        assert obj.stage == "capture"
        assert obj.retryable is True

    def test_conversion_with_details(self):
        err = PipelineError(
            "ERR_EXTRACTION_FAILED", "LLM error",
            stage="extract",
            details={"model": "gpt-4"},
        )
        obj = err.to_error_object()
        assert obj.details == {"model": "gpt-4"}

    def test_conversion_no_stage(self):
        err = PipelineError("ERR_INVALID_INPUT", "bad url")
        obj = err.to_error_object()
        assert obj.stage is None

    def test_serialization_round_trip(self):
        err = PipelineError(
            "ERR_NORMALIZATION_FAILED", "encoding error",
            stage="normalize",
            retryable=False,
            details={"encoding": "utf-16"},
        )
        d = err.to_error_object().to_dict()
        assert d["code"] == "ERR_NORMALIZATION_FAILED"
        assert d["message"] == "encoding error"
        assert d["stage"] == "normalize"
        assert d["retryable"] is False
        assert d["details"] == {"encoding": "utf-16"}


# ─── Convenience constructors ────────────────────────────────────────────

class TestConvenienceConstructors:

    def test_capture_error(self):
        err = capture_error("timeout")
        assert err.code == "ERR_CAPTURE_FAILED"
        assert err.stage == "capture"
        assert err.retryable is True

    def test_normalize_error(self):
        err = normalize_error("bad encoding")
        assert err.code == "ERR_NORMALIZATION_FAILED"
        assert err.stage == "normalize"
        assert err.retryable is False

    def test_extraction_error(self):
        err = extraction_error("LLM timeout")
        assert err.code == "ERR_EXTRACTION_FAILED"
        assert err.stage == "extract"
        assert err.retryable is True

    def test_schema_validation_error_no_stage(self):
        err = schema_validation_error("missing type")
        assert err.code == "ERR_SCHEMA_VALIDATION"
        assert err.stage is None
        assert err.retryable is False

    def test_schema_validation_error_with_stage(self):
        err = schema_validation_error("bad frontmatter", stage="extract")
        assert err.stage == "extract"

    def test_canon_write_forbidden(self):
        err = canon_write_forbidden()
        assert err.code == "ERR_CANON_WRITE_FORBIDDEN"
        assert err.retryable is False
        assert err.stage is None

    def test_canon_write_forbidden_custom_message(self):
        err = canon_write_forbidden("agent tried to write to Claims/")
        assert str(err) == "agent tried to write to Claims/"


# ─── Error code registry ────────────────────────────────────────────────

class TestErrorCodeRegistry:

    def test_all_spec_codes_registered(self):
        """All error codes from §5.2 command contracts are in the registry."""
        spec_codes = {
            "ERR_INVALID_INPUT",
            "ERR_UNSUPPORTED_SOURCE",
            "ERR_CAPTURE_FAILED",
            "ERR_NORMALIZATION_FAILED",
            "ERR_EXTRACTION_FAILED",
            "ERR_SCHEMA_VALIDATION",
            "ERR_CORRUPTED_NOTE",
            "ERR_CANON_WRITE_FORBIDDEN",
            "ERR_SOURCE_NOT_FOUND",
            "ERR_DELTA_NOT_FOUND",
            "ERR_QUEUE_ITEM_INVALID",
            "ERR_QUEUE_IMMUTABLE",
            "ERR_REVIEW_DECISION_INVALID",
            "ERR_REVIEW_DIGEST_EMPTY",
            "ERR_PROVENANCE_MISSING",
            "ERR_PROMOTION_CONFLICT",
            "ERR_CONTEXT_EMPTY",
            "ERR_NO_FRONTIER_DATA",
        }
        assert spec_codes <= set(ERROR_CODES.keys())

    def test_registry_values_are_tuples(self):
        for code, (retryable, stage) in ERROR_CODES.items():
            assert isinstance(retryable, bool), f"{code} retryable must be bool"
            assert stage is None or stage in VALID_STAGE_NAMES, (
                f"{code} stage must be None or valid stage name"
            )


# ─── Integration with OutputEnvelope ─────────────────────────────────────

class TestIntegrationWithEnvelope:

    def test_pipeline_error_in_envelope(self):
        from mycelium.models import make_envelope

        err = capture_error("network timeout", details={"url": "http://x.com"})
        env = make_envelope(
            "ingest",
            ok=False,
            errors=[err.to_error_object()],
        )
        d = env.to_dict()
        assert d["ok"] is False
        assert len(d["errors"]) == 1
        assert d["errors"][0]["code"] == "ERR_CAPTURE_FAILED"
        assert d["errors"][0]["stage"] == "capture"
        assert d["errors"][0]["retryable"] is True

    def test_error_envelope_helper(self):
        from mycelium.models import error_envelope

        err = extraction_error("LLM rate limit")
        env = error_envelope(
            "ingest",
            err.code,
            str(err),
            retryable=err.retryable,
            stage=err.stage,
        )
        d = env.to_dict()
        assert d["errors"][0]["stage"] == "extract"
        assert d["errors"][0]["retryable"] is True
