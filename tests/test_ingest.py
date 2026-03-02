"""
Tests for the ingest command contract (CMD-ING-001, CMD-ING-002).

Verifies:
  AC-CMD-ING-001-1..3: Successful ingest returns source_note_path,
                        delta_report_path, artifact_paths.
  AC-CMD-ING-002-1..3: Idempotency record structure and consistency.
"""

from __future__ import annotations

import pytest

from mycelium.commands.ingest import (
    ERR_INVALID_INPUT,
    IdempotencyRecord,
    IngestInput,
    execute_ingest,
    validate_ingest_input,
)
from mycelium.models import ErrorObject


# ─── Input validation ────────────────────────────────────────────────────

class TestValidateIngestInput:

    def test_url_input(self):
        result = validate_ingest_input({"url": "https://example.com/paper"})
        assert isinstance(result, IngestInput)
        assert result.url == "https://example.com/paper"
        assert result.source_type == "url"

    def test_pdf_path_input(self):
        result = validate_ingest_input({"pdf_path": "papers/foo.pdf"})
        assert isinstance(result, IngestInput)
        assert result.source_type == "pdf_path"

    def test_id_input(self):
        result = validate_ingest_input({"id": "10.1234/foo"})
        assert isinstance(result, IngestInput)
        assert result.source_type == "id"

    def test_text_bundle_input(self):
        result = validate_ingest_input({
            "text_bundle": {"title": "Book", "highlights": ["a", "b"]},
        })
        assert isinstance(result, IngestInput)
        assert result.source_type == "text_bundle"

    def test_no_source_rejected(self):
        result = validate_ingest_input({})
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_INVALID_INPUT

    def test_multiple_sources_rejected(self):
        result = validate_ingest_input({
            "url": "https://x.com",
            "pdf_path": "foo.pdf",
        })
        assert isinstance(result, ErrorObject)
        assert result.code == ERR_INVALID_INPUT

    def test_optional_fields(self):
        result = validate_ingest_input({
            "url": "https://x.com",
            "why_saved": "interesting claims",
            "tags": ["ml", "safety"],
            "strict": True,
            "dry_run": True,
        })
        assert isinstance(result, IngestInput)
        assert result.why_saved == "interesting claims"
        assert result.tags == ["ml", "safety"]
        assert result.strict is True
        assert result.dry_run is True

    def test_invalid_tags_type(self):
        result = validate_ingest_input({
            "url": "https://x.com",
            "tags": "not-a-list",
        })
        assert isinstance(result, ErrorObject)

    def test_invalid_text_bundle_type(self):
        result = validate_ingest_input({"text_bundle": "not-an-object"})
        assert isinstance(result, ErrorObject)

    def test_defaults(self):
        result = validate_ingest_input({"url": "https://x.com"})
        assert isinstance(result, IngestInput)
        assert result.strict is False
        assert result.dry_run is False
        assert result.tags == []
        assert result.why_saved is None


# ─── IdempotencyRecord ───────────────────────────────────────────────────

class TestIdempotencyRecord:

    def test_to_dict(self):
        ir = IdempotencyRecord(
            normalized_locator="https://example.com/paper",
            fingerprint="h-abcdef123456",
            reused_source_id=False,
            prior_fingerprint=None,
        )
        d = ir.to_dict()
        assert d == {
            "normalized_locator": "https://example.com/paper",
            "fingerprint": "h-abcdef123456",
            "reused_source_id": False,
            "prior_fingerprint": None,
        }

    def test_with_prior_fingerprint(self):
        ir = IdempotencyRecord(
            normalized_locator="loc",
            fingerprint="fp",
            reused_source_id=True,
            prior_fingerprint="old-fp",
        )
        d = ir.to_dict()
        assert d["reused_source_id"] is True
        assert d["prior_fingerprint"] == "old-fp"


# ─── execute_ingest ──────────────────────────────────────────────────────

class TestExecuteIngest:

    def test_invalid_input_returns_error_envelope(self):
        env = execute_ingest({})
        assert env.ok is False
        assert env.errors[0].code == ERR_INVALID_INPUT

    def test_success_envelope_has_all_output_fields(self):
        env = execute_ingest({"url": "https://example.com"})
        assert env.ok is True
        assert env.command == "ingest"
        assert "run_id" in env.data
        assert "source_id" in env.data
        assert "source_note_path" in env.data
        assert "delta_report_path" in env.data
        assert "review_queue_item_paths" in env.data
        assert "artifact_paths" in env.data
        assert "idempotency" in env.data

    def test_idempotency_in_output(self):
        env = execute_ingest({"id": "10.1234/foo"})
        idem = env.data["idempotency"]
        assert "normalized_locator" in idem
        assert "fingerprint" in idem
        assert "reused_source_id" in idem
        assert "prior_fingerprint" in idem

    def test_dry_run_returns_planned_writes(self):
        env = execute_ingest({
            "url": "https://example.com",
            "dry_run": True,
        })
        assert env.ok is True
        assert env.command == "ingest"
        assert "planned_writes" in env.data

    def test_envelope_keys(self):
        env = execute_ingest({"url": "https://x.com"})
        d = env.to_dict()
        assert set(d.keys()) == {
            "ok", "command", "timestamp", "data",
            "errors", "warnings", "trace"
        }
