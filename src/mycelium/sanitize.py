"""
Payload sanitization and redaction for egress (SEC-004).

When sanitization is enabled, outbound payloads are scanned for sensitive
patterns (API keys, email addresses, phone numbers, local absolute paths)
and those patterns are redacted. A ``redaction_summary`` records which
categories were applied and how many redactions per category.

Fail-closed: if sanitization cannot parse or redact, the payload is blocked
and an ``egress_blocked`` audit event is emitted with a failure reason.

Spec reference: §9.2 SEC-004
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ── Redaction patterns ────────────────────────────────────────────────

# API keys/tokens: common patterns like sk_live_..., AKIA..., bearer tokens
_API_KEY_PATTERNS = [
    # Prefixed API key/token patterns (hex/base64-ish, >= 8 chars after prefix)
    re.compile(
        r"(?:sk_live_|sk_test_|AKIA|ghp_|gho_|ghs_|ghu_|glpat-|xoxb-|xoxp-)"
        r"[A-Za-z0-9_\-/.+=]{8,}",
        re.IGNORECASE,
    ),
    # Key=value patterns (api_key=..., api-secret=..., token=...)
    re.compile(
        r"(?:api[_-]?key|api[_-]?secret|token)"
        r"[=:]\s*[A-Za-z0-9_\-/.+=]{8,}",
        re.IGNORECASE,
    ),
    # Bearer token (with space between Bearer and token)
    re.compile(
        r"[Bb]earer\s+[A-Za-z0-9_\-/.+=]{16,}",
    ),
]

# Email addresses
_EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
)

# Phone numbers (various formats)
_PHONE_PATTERN = re.compile(
    r"(?:\+\d{1,3}[-.\s]?)?"          # optional country code
    r"(?:\(?\d{2,4}\)?[-.\s]?)"       # area code
    r"(?:\d{3,4}[-.\s]?)"             # first part
    r"\d{3,4}",                        # second part
)

# Local absolute paths (Unix and Windows)
_PATH_PATTERNS = [
    re.compile(r"/(?:Users|home|root|var|etc|opt)/[^\s\"'`,;}{)(\]]+"),
    re.compile(r"[A-Z]:\\(?:Users|Windows|Program Files)[^\s\"'`,;}{)(\]]*"),
]

# Redaction placeholder
REDACTION_PLACEHOLDER = "[REDACTED]"


# ── Data model ────────────────────────────────────────────────────────

@dataclass
class RedactionResult:
    """Result of sanitizing a payload.

    Attributes:
        sanitized_text: The redacted text.
        redaction_summary: Dict mapping category names to redaction counts.
        total_redactions: Total number of redactions applied.
    """

    sanitized_text: str
    redaction_summary: dict[str, int] = field(default_factory=dict)
    total_redactions: int = 0


class SanitizationError(Exception):
    """Raised when sanitization fails to parse or redact."""

    def __init__(self, message: str) -> None:
        self.code = "ERR_SANITIZATION_FAILED"
        super().__init__(message)


# ── Core sanitization ─────────────────────────────────────────────────

def sanitize_payload(
    text: str,
    *,
    redact_api_keys: bool = True,
    redact_emails: bool = True,
    redact_phones: bool = True,
    redact_paths: bool = True,
) -> RedactionResult:
    """Apply redaction rules to a text payload.

    Scans for sensitive patterns and replaces them with ``[REDACTED]``.
    Returns a ``RedactionResult`` with the sanitized text and a summary
    of which categories were redacted and how many times.

    Args:
        text: The raw payload text to sanitize.
        redact_api_keys: Whether to redact API key/token patterns.
        redact_emails: Whether to redact email addresses.
        redact_phones: Whether to redact phone numbers.
        redact_paths: Whether to redact local absolute paths.

    Returns:
        RedactionResult with sanitized text and summary.

    Raises:
        SanitizationError: If the sanitization process fails.
    """
    try:
        return _apply_redactions(
            text,
            redact_api_keys=redact_api_keys,
            redact_emails=redact_emails,
            redact_phones=redact_phones,
            redact_paths=redact_paths,
        )
    except SanitizationError:
        raise
    except Exception as exc:
        raise SanitizationError(f"Sanitization failed: {exc}") from exc


def _apply_redactions(
    text: str,
    *,
    redact_api_keys: bool,
    redact_emails: bool,
    redact_phones: bool,
    redact_paths: bool,
) -> RedactionResult:
    """Internal: apply all configured redaction patterns."""
    summary: dict[str, int] = {}
    result_text = text

    if redact_api_keys:
        result_text, count = _redact_patterns(result_text, _API_KEY_PATTERNS)
        if count > 0:
            summary["api_key"] = count

    if redact_emails:
        result_text, count = _redact_pattern(result_text, _EMAIL_PATTERN)
        if count > 0:
            summary["email"] = count

    if redact_phones:
        result_text, count = _redact_pattern(result_text, _PHONE_PATTERN)
        if count > 0:
            summary["phone"] = count

    if redact_paths:
        result_text, count = _redact_patterns(result_text, _PATH_PATTERNS)
        if count > 0:
            summary["local_path"] = count

    total = sum(summary.values())
    return RedactionResult(
        sanitized_text=result_text,
        redaction_summary=summary,
        total_redactions=total,
    )


def _redact_pattern(text: str, pattern: re.Pattern[str]) -> tuple[str, int]:
    """Replace all matches of a single pattern. Returns (new_text, count)."""
    count = len(pattern.findall(text))
    new_text = pattern.sub(REDACTION_PLACEHOLDER, text)
    return new_text, count


def _redact_patterns(
    text: str, patterns: list[re.Pattern[str]]
) -> tuple[str, int]:
    """Replace all matches of multiple patterns. Returns (new_text, total_count)."""
    total = 0
    for pattern in patterns:
        text, count = _redact_pattern(text, pattern)
        total += count
    return text, total
