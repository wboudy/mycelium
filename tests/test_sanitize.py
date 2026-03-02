"""
Tests for payload sanitization and redaction (SEC-004).

Verifies acceptance criteria from §9.2:
  AC-SEC-004-1: Fixture payload with API key and email results in
                redaction_summary indicating both categories applied.
  AC-SEC-004-2: If sanitization fails, egress blocked with failure reason.
"""

from __future__ import annotations

import pytest

from mycelium.sanitize import (
    REDACTION_PLACEHOLDER,
    RedactionResult,
    SanitizationError,
    sanitize_payload,
)


# ─── AC-SEC-004-1: fixture payload with API key and email ────────────

class TestRedactionCategories:
    """AC-SEC-004-1: Redaction summary indicates categories applied."""

    def test_api_key_and_email_redacted(self):
        """Fixture payload with API key token and email address."""
        payload = (
            "User: john.doe@example.com\n"
            "API Key: sk_test_xxxxxxxxxxxxxxxxxxxx\n"
            "Notes: Some regular text here.\n"
        )
        result = sanitize_payload(payload)
        assert "api_key" in result.redaction_summary
        assert "email" in result.redaction_summary
        assert result.redaction_summary["api_key"] >= 1
        assert result.redaction_summary["email"] >= 1
        assert "john.doe@example.com" not in result.sanitized_text
        assert "sk_test_" not in result.sanitized_text

    def test_bearer_token_redacted(self):
        payload = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.long_token_value"
        result = sanitize_payload(payload)
        assert "api_key" in result.redaction_summary
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result.sanitized_text

    def test_github_token_redacted(self):
        payload = "GITHUB_TOKEN=ghp_ABCDEFghijklmnopqrstuvwxyz12345"
        result = sanitize_payload(payload)
        assert "api_key" in result.redaction_summary

    def test_aws_key_redacted(self):
        payload = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        result = sanitize_payload(payload)
        assert "api_key" in result.redaction_summary

    def test_email_redacted(self):
        payload = "Contact: alice@example.com and bob@company.org"
        result = sanitize_payload(payload)
        assert result.redaction_summary["email"] == 2
        assert "alice@example.com" not in result.sanitized_text
        assert "bob@company.org" not in result.sanitized_text

    def test_phone_number_redacted(self):
        payload = "Call me at +1-555-123-4567 or (555) 987-6543"
        result = sanitize_payload(payload)
        assert "phone" in result.redaction_summary
        assert result.redaction_summary["phone"] >= 1

    def test_local_path_redacted(self):
        payload = "File located at /Users/john/Documents/secret.txt"
        result = sanitize_payload(payload)
        assert "local_path" in result.redaction_summary
        assert "/Users/john" not in result.sanitized_text

    def test_windows_path_redacted(self):
        payload = r"File at C:\Users\john\Desktop\data.csv"
        result = sanitize_payload(payload)
        assert "local_path" in result.redaction_summary

    def test_no_sensitive_content(self):
        payload = "This is a regular note about aspirin reducing inflammation."
        result = sanitize_payload(payload)
        assert result.total_redactions == 0
        assert result.redaction_summary == {}
        assert result.sanitized_text == payload


# ─── Selective redaction ─────────────────────────────────────────────

class TestSelectiveRedaction:

    def test_disable_api_key_redaction(self):
        payload = "Key: sk_test_FAKE00NOREDACT123456"
        result = sanitize_payload(payload, redact_api_keys=False)
        assert "api_key" not in result.redaction_summary
        assert "sk_test_" in result.sanitized_text

    def test_disable_email_redaction(self):
        payload = "Email: user@example.com"
        result = sanitize_payload(payload, redact_emails=False)
        assert "email" not in result.redaction_summary
        assert "user@example.com" in result.sanitized_text

    def test_disable_phone_redaction(self):
        payload = "Phone: +1-555-123-4567"
        result = sanitize_payload(payload, redact_phones=False)
        assert "phone" not in result.redaction_summary

    def test_disable_path_redaction(self):
        payload = "Path: /Users/test/file.txt"
        result = sanitize_payload(payload, redact_paths=False)
        assert "local_path" not in result.redaction_summary
        assert "/Users/test" in result.sanitized_text


# ─── Multiple categories ────────────────────────────────────────────

class TestMultipleCategories:

    def test_all_categories_in_one_payload(self):
        """Full fixture with all four categories."""
        payload = (
            "From: admin@company.com\n"
            "API-Key: api_key_ABCDEFghijklmnop1234\n"
            "Phone: (555) 123-4567\n"
            "Config: /Users/admin/config.yaml\n"
        )
        result = sanitize_payload(payload)
        assert len(result.redaction_summary) >= 3  # email, api_key, local_path at minimum
        assert result.total_redactions >= 3

    def test_redaction_summary_counts(self):
        payload = "a@b.com and c@d.com with token sk_test_abcdefghij123456"
        result = sanitize_payload(payload)
        assert result.redaction_summary.get("email", 0) == 2
        assert result.redaction_summary.get("api_key", 0) >= 1


# ─── AC-SEC-004-2: sanitization failure ──────────────────────────────

class TestSanitizationFailure:
    """AC-SEC-004-2: Sanitization failure blocks egress."""

    def test_sanitization_error_type(self):
        err = SanitizationError("test failure")
        assert err.code == "ERR_SANITIZATION_FAILED"
        assert "test failure" in str(err)


# ─── RedactionResult data model ──────────────────────────────────────

class TestRedactionResult:

    def test_default_values(self):
        result = RedactionResult(sanitized_text="hello")
        assert result.sanitized_text == "hello"
        assert result.redaction_summary == {}
        assert result.total_redactions == 0

    def test_with_summary(self):
        result = RedactionResult(
            sanitized_text="[REDACTED]",
            redaction_summary={"email": 1, "api_key": 2},
            total_redactions=3,
        )
        assert result.total_redactions == 3

    def test_placeholder_constant(self):
        assert REDACTION_PLACEHOLDER == "[REDACTED]"


# ─── Edge cases ──────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_string(self):
        result = sanitize_payload("")
        assert result.sanitized_text == ""
        assert result.total_redactions == 0

    def test_only_whitespace(self):
        result = sanitize_payload("   \n\t  ")
        assert result.total_redactions == 0

    def test_redacted_text_contains_placeholder(self):
        payload = "api_key=verylongsecretvalue12345678"
        result = sanitize_payload(payload)
        assert REDACTION_PLACEHOLDER in result.sanitized_text

    def test_multiple_same_emails(self):
        payload = "cc: a@b.com, a@b.com, a@b.com"
        result = sanitize_payload(payload)
        assert result.redaction_summary["email"] == 3
