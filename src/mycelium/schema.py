"""
Frontmatter schema validation for Mycelium Notes.

Implements:
  SCH-001 (§4.2.1): Shared frontmatter keys.
  SCH-002 (§4.2.2): Source Note schema.
  SCH-003 (§4.2.3): Claim Note schema with provenance.
  SCH-004 (§4.2.4): Concept Note schema.
  SCH-005 (§4.2.5): Question Note schema.
  SCH-008 (§4.2.8): Extraction Bundle schema.

Validators MUST ignore unknown keys (forward compatibility per §4.2.1).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


# ── Enums ────────────────────────────────────────────────────────────────

NOTE_TYPES = frozenset({"source", "claim", "concept", "question", "project", "moc"})
NOTE_STATUSES = frozenset({"draft", "reviewed", "canon"})
SOURCE_KINDS = frozenset({
    "url", "pdf", "doi", "arxiv", "highlights", "book", "text_bundle",
})
CLAIM_TYPES = frozenset({
    "empirical", "definition", "causal", "normative", "procedural",
})
POLARITIES = frozenset({"supports", "opposes", "neutral"})

# ── Required shared keys ────────────────────────────────────────────────

REQUIRED_KEYS = ("type", "id", "status", "created", "updated")


class SchemaValidationError(Exception):
    """Raised when frontmatter fails schema validation.

    Attributes:
        errors: list of individual validation failure descriptions.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"Schema validation failed: {'; '.join(errors)}")


def _parse_iso8601_utc(value: Any) -> datetime:
    """Parse and return a UTC datetime from an ISO-8601 string.

    Raises ValueError if the string is not valid ISO-8601 or cannot be
    interpreted as UTC.
    """
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValueError(f"Expected ISO-8601 string, got {type(value).__name__}")
    # Handle trailing Z (common UTC shorthand)
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


def validate_shared_frontmatter(frontmatter: dict[str, Any]) -> list[str]:
    """Validate shared frontmatter keys per SCH-001.

    Returns a list of validation error strings (empty means valid).
    Unknown keys are silently ignored per §4.2.1.

    Checks:
      - AC-SCH-001-1: Required keys present.
      - AC-SCH-001-2: created/updated are valid ISO-8601 UTC.
      - AC-SCH-001-3: confidence in [0.0..1.0] if present.
      - AC-SCH-001-4: last_reviewed_at is valid ISO-8601 if present.
    """
    errors: list[str] = []

    # AC-SCH-001-1: Check required keys
    for key in REQUIRED_KEYS:
        if key not in frontmatter:
            errors.append(f"Missing required key: {key}")

    # If required keys are missing, skip further validation on those fields
    has_type = "type" in frontmatter
    has_status = "status" in frontmatter
    has_created = "created" in frontmatter
    has_updated = "updated" in frontmatter

    # Validate type enum
    if has_type:
        t = frontmatter["type"]
        if t not in NOTE_TYPES:
            errors.append(
                f"Invalid type: {t!r} (expected one of {sorted(NOTE_TYPES)})"
            )

    # Validate id is a non-empty string
    if "id" in frontmatter:
        fid = frontmatter["id"]
        if not isinstance(fid, str) or not fid.strip():
            errors.append("id must be a non-empty string")

    # Validate status enum
    if has_status:
        s = frontmatter["status"]
        if s not in NOTE_STATUSES:
            errors.append(
                f"Invalid status: {s!r} (expected one of {sorted(NOTE_STATUSES)})"
            )

    # AC-SCH-001-2: Validate created/updated as ISO-8601 UTC
    for key in ("created", "updated"):
        if key in frontmatter:
            try:
                _parse_iso8601_utc(frontmatter[key])
            except (ValueError, TypeError) as exc:
                errors.append(f"Invalid {key} datetime: {exc}")

    # AC-SCH-001-3: Validate confidence range if present
    if "confidence" in frontmatter:
        conf = frontmatter["confidence"]
        if not isinstance(conf, (int, float)):
            errors.append(f"confidence must be a number, got {type(conf).__name__}")
        elif not (0.0 <= conf <= 1.0):
            errors.append(
                f"confidence must be in [0.0..1.0], got {conf}"
            )

    # AC-SCH-001-4: Validate last_reviewed_at if present
    if "last_reviewed_at" in frontmatter:
        try:
            _parse_iso8601_utc(frontmatter["last_reviewed_at"])
        except (ValueError, TypeError) as exc:
            errors.append(f"Invalid last_reviewed_at datetime: {exc}")

    return errors


def validate_shared_frontmatter_strict(frontmatter: dict[str, Any]) -> None:
    """Validate and raise SchemaValidationError on failure.

    Convenience wrapper around validate_shared_frontmatter that raises
    instead of returning error lists.
    """
    errors = validate_shared_frontmatter(frontmatter)
    if errors:
        raise SchemaValidationError(errors)


# ── SCH-002: Source Note Schema ──────────────────────────────────────────

_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

SOURCE_REQUIRED_KEYS = (
    "source_ref", "source_kind", "normalized_locator", "fingerprint", "captured_at",
)


def validate_source_frontmatter(frontmatter: dict[str, Any]) -> list[str]:
    """Validate Source Note frontmatter per SCH-002.

    Runs shared validation (SCH-001) first, then checks Source-specific
    required keys and format constraints.

    Returns a list of validation error strings (empty means valid).

    Checks:
      - AC-SCH-002-3: Rejects Source Notes missing any required Source Note key.
      - AC-SCH-002-2: Rejects fingerprint not matching sha256:<64-hex>.
      - captured_at must be valid ISO-8601.
      - source_kind must be a known enum value.
    """
    errors = validate_shared_frontmatter(frontmatter)

    # AC-SCH-002-3: Check Source-specific required keys
    for key in SOURCE_REQUIRED_KEYS:
        if key not in frontmatter:
            errors.append(f"Missing required Source Note key: {key}")

    # Validate source_kind enum
    if "source_kind" in frontmatter:
        sk = frontmatter["source_kind"]
        if sk not in SOURCE_KINDS:
            errors.append(
                f"Invalid source_kind: {sk!r} (expected one of {sorted(SOURCE_KINDS)})"
            )

    # AC-SCH-002-2: Validate fingerprint format
    if "fingerprint" in frontmatter:
        fp = frontmatter["fingerprint"]
        if not isinstance(fp, str) or not _FINGERPRINT_RE.match(fp):
            errors.append(
                f"Invalid fingerprint: must match sha256:<64-hex>, got {fp!r}"
            )

    # Validate captured_at as ISO-8601
    if "captured_at" in frontmatter:
        try:
            _parse_iso8601_utc(frontmatter["captured_at"])
        except (ValueError, TypeError) as exc:
            errors.append(f"Invalid captured_at datetime: {exc}")

    # Validate source_ref is non-empty string
    if "source_ref" in frontmatter:
        sr = frontmatter["source_ref"]
        if not isinstance(sr, str) or not sr.strip():
            errors.append("source_ref must be a non-empty string")

    # Validate normalized_locator is non-empty string
    if "normalized_locator" in frontmatter:
        nl = frontmatter["normalized_locator"]
        if not isinstance(nl, str) or not nl.strip():
            errors.append("normalized_locator must be a non-empty string")

    return errors


def validate_source_frontmatter_strict(frontmatter: dict[str, Any]) -> None:
    """Validate Source Note and raise SchemaValidationError on failure."""
    errors = validate_source_frontmatter(frontmatter)
    if errors:
        raise SchemaValidationError(errors)


# ── SCH-003: Claim Note Schema ───────────────────────────────────────────

CLAIM_REQUIRED_KEYS = ("claim_text", "claim_type", "polarity", "provenance")
PROVENANCE_REQUIRED_KEYS = ("source_id", "source_ref", "locator")

# URL locator required keys per §4.2.3
_URL_LOCATOR_REQUIRED = ("url", "section", "paragraph_index", "snippet_hash")
# PDF locator required keys per §4.2.3
_PDF_LOCATOR_REQUIRED = ("pdf_ref", "page", "section", "snippet_hash")
# Source kinds that use raw_locator fallback in MVP1
_RAW_LOCATOR_KINDS = frozenset({"doi", "arxiv", "highlights", "book", "text_bundle"})


def _validate_snippet_hash(value: Any) -> str | None:
    """Return error string if snippet_hash is invalid, else None."""
    if not isinstance(value, str) or not _FINGERPRINT_RE.match(value):
        return f"Invalid snippet_hash: must match sha256:<64-hex>, got {value!r}"
    return None


def validate_claim_frontmatter(
    frontmatter: dict[str, Any],
    source_kind: str | None = None,
) -> tuple[list[str], list[str]]:
    """Validate Claim Note frontmatter per SCH-003.

    Runs shared validation (SCH-001) first, then checks Claim-specific
    required keys, provenance structure, and locator format.

    Args:
        frontmatter: The Claim Note frontmatter dict.
        source_kind: The source_kind of the linked Source Note. When provided,
            enables locator structure validation (AC-SCH-003-4, AC-SCH-003-5).
            When None, locator structure checks are skipped.

    Returns:
        Tuple of (errors, warnings). Errors are validation failures;
        warnings are advisory notices (e.g. AC-SCH-003-5 deferred locator).
    """
    errors = validate_shared_frontmatter(frontmatter)
    warnings: list[str] = []

    # Check Claim-specific required keys
    for key in CLAIM_REQUIRED_KEYS:
        if key not in frontmatter:
            errors.append(f"Missing required Claim Note key: {key}")

    # AC-SCH-003-1: claim_text must be non-empty after trimming
    if "claim_text" in frontmatter:
        ct = frontmatter["claim_text"]
        if not isinstance(ct, str) or not ct.strip():
            errors.append("claim_text must be a non-empty string (after trimming)")

    # Validate claim_type enum
    if "claim_type" in frontmatter:
        ctype = frontmatter["claim_type"]
        if ctype not in CLAIM_TYPES:
            errors.append(
                f"Invalid claim_type: {ctype!r} (expected one of {sorted(CLAIM_TYPES)})"
            )

    # Validate polarity enum
    if "polarity" in frontmatter:
        pol = frontmatter["polarity"]
        if pol not in POLARITIES:
            errors.append(
                f"Invalid polarity: {pol!r} (expected one of {sorted(POLARITIES)})"
            )

    # AC-SCH-003-2: Validate provenance structure
    if "provenance" in frontmatter:
        prov = frontmatter["provenance"]
        if not isinstance(prov, dict):
            errors.append("provenance must be an object")
        else:
            for pkey in PROVENANCE_REQUIRED_KEYS:
                if pkey not in prov:
                    errors.append(f"Missing required provenance key: {pkey}")

            # Validate source_id is non-empty string
            if "source_id" in prov:
                sid = prov["source_id"]
                if not isinstance(sid, str) or not sid.strip():
                    errors.append("provenance.source_id must be a non-empty string")

            # Validate source_ref is non-empty string
            if "source_ref" in prov:
                sref = prov["source_ref"]
                if not isinstance(sref, str) or not sref.strip():
                    errors.append("provenance.source_ref must be a non-empty string")

            # AC-SCH-003-4 / AC-SCH-003-5: Validate locator structure
            if "locator" in prov and source_kind is not None:
                locator = prov["locator"]
                if not isinstance(locator, dict):
                    errors.append("provenance.locator must be an object")
                else:
                    _validate_locator(locator, source_kind, errors, warnings)

    return errors, warnings


def _validate_locator(
    locator: dict[str, Any],
    source_kind: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Validate provenance.locator based on source_kind."""
    if source_kind == "url":
        # AC-SCH-003-4: URL locator required keys
        for key in _URL_LOCATOR_REQUIRED:
            if key not in locator:
                errors.append(f"URL locator missing required key: {key}")
        if "snippet_hash" in locator:
            err = _validate_snippet_hash(locator["snippet_hash"])
            if err:
                errors.append(err)

    elif source_kind == "pdf":
        # AC-SCH-003-4: PDF locator required keys
        for key in _PDF_LOCATOR_REQUIRED:
            if key not in locator:
                errors.append(f"PDF locator missing required key: {key}")
        if "snippet_hash" in locator:
            err = _validate_snippet_hash(locator["snippet_hash"])
            if err:
                errors.append(err)
        if "page" in locator:
            page = locator["page"]
            if not isinstance(page, int):
                errors.append(f"PDF locator page must be an integer, got {type(page).__name__}")

    elif source_kind in _RAW_LOCATOR_KINDS:
        # AC-SCH-003-5: MVP1 fallback — accept raw_locator, emit warning
        if "raw_locator" not in locator:
            warnings.append(
                f"Locator for source_kind={source_kind!r} missing raw_locator; "
                f"deferred locator strictness applies (MVP2)"
            )
        else:
            warnings.append(
                f"Locator for source_kind={source_kind!r} uses raw_locator; "
                f"stricter structured locator deferred to MVP2"
            )


def validate_claim_frontmatter_strict(
    frontmatter: dict[str, Any],
    source_kind: str | None = None,
) -> list[str]:
    """Validate Claim Note and raise SchemaValidationError on failure.

    Returns warnings list on success.
    """
    errors, warnings = validate_claim_frontmatter(frontmatter, source_kind)
    if errors:
        raise SchemaValidationError(errors)
    return warnings


# ── SCH-004: Concept Note Schema ──────────────────────────────────────

CONCEPT_REQUIRED_KEYS = ("term",)


def validate_concept_frontmatter(frontmatter: dict[str, Any]) -> list[str]:
    """Validate Concept Note frontmatter per SCH-004.

    Runs shared validation (SCH-001) first, then checks that
    ``term`` is present and non-empty after trimming.

    Returns a list of validation error strings (empty means valid).

    Checks:
      - AC-SCH-004-1: Rejects Concept Notes missing term.
    """
    errors = validate_shared_frontmatter(frontmatter)

    # AC-SCH-004-1: term required
    if "term" not in frontmatter:
        errors.append("Missing required Concept Note key: term")
    else:
        t = frontmatter["term"]
        if not isinstance(t, str) or not t.strip():
            errors.append(
                "term must be a non-empty string (after trimming)"
            )

    return errors


def validate_concept_frontmatter_strict(frontmatter: dict[str, Any]) -> None:
    """Validate Concept Note and raise SchemaValidationError on failure."""
    errors = validate_concept_frontmatter(frontmatter)
    if errors:
        raise SchemaValidationError(errors)


def check_concept_promotion_links(
    body: str,
    vault_root: Any,
) -> list[str]:
    """Check AC-SCH-004-2: Concept Notes must have at least one resolved wikilink.

    This is a promotion-time check, not a schema validator. It verifies
    that the note body contains at least one Obsidian Wikilink that
    resolves to an existing note.

    Args:
        body: The Markdown body of the Concept Note.
        vault_root: Absolute path to the vault root (Path-like).

    Returns:
        List of error strings (empty means valid for promotion).
    """
    from pathlib import Path

    from mycelium.wikilink import extract_wikilinks, resolve_wikilink

    vault_path = Path(vault_root)
    targets = extract_wikilinks(body)

    if not targets:
        return [
            "Concept Note has zero outbound Obsidian Wikilinks; "
            "at least one resolved wikilink is required for promotion (AC-SCH-004-2)"
        ]

    # Check if at least one resolves
    for target in targets:
        if resolve_wikilink(target, vault_path) is not None:
            return []

    return [
        "Concept Note has outbound Wikilinks but none resolve to an existing note; "
        "at least one resolved wikilink is required for promotion (AC-SCH-004-2)"
    ]


# ── SCH-005: Question Note Schema ─────────────────────────────────────

QUESTION_REQUIRED_KEYS = ("question_text",)


def validate_question_frontmatter(frontmatter: dict[str, Any]) -> list[str]:
    """Validate Question Note frontmatter per SCH-005.

    Runs shared validation (SCH-001) first, then checks that
    ``question_text`` is present and non-empty after trimming.

    Returns a list of validation error strings (empty means valid).

    Checks:
      - AC-SCH-005-1: Rejects Question Notes missing question_text
        or with empty question_text after trimming.
    """
    errors = validate_shared_frontmatter(frontmatter)

    # AC-SCH-005-1: question_text required
    if "question_text" not in frontmatter:
        errors.append("Missing required Question Note key: question_text")
    else:
        qt = frontmatter["question_text"]
        if not isinstance(qt, str) or not qt.strip():
            errors.append(
                "question_text must be a non-empty string (after trimming)"
            )

    return errors


def validate_question_frontmatter_strict(frontmatter: dict[str, Any]) -> None:
    """Validate Question Note and raise SchemaValidationError on failure."""
    errors = validate_question_frontmatter(frontmatter)
    if errors:
        raise SchemaValidationError(errors)


# ── SCH-008: Extraction Bundle Schema ────────────────────────────────────

EXTRACTION_BUNDLE_REQUIRED_KEYS = (
    "run_id", "source_id", "created_at", "gist",
    "bullets", "claims", "entities", "definitions", "warnings",
)

EXTRACTION_CLAIM_REQUIRED_KEYS = (
    "extracted_claim_key", "claim_text", "claim_type", "polarity", "provenance",
)


def validate_extraction_bundle(bundle: dict[str, Any]) -> list[str]:
    """Validate an Extraction Bundle per SCH-008.

    Returns a list of validation error strings (empty means valid).

    Checks:
      - AC-SCH-008-2: Rejects bundles missing required top-level keys or
        containing claims with empty claim_text.
      - AC-SCH-008-3: If claims is empty, warnings must contain
        WARN_NO_CLAIMS_EXTRACTED.
    """
    errors: list[str] = []

    # AC-SCH-008-2: Check required top-level keys
    for key in EXTRACTION_BUNDLE_REQUIRED_KEYS:
        if key not in bundle:
            errors.append(f"Missing required Extraction Bundle key: {key}")

    # Validate run_id is non-empty string
    if "run_id" in bundle:
        rid = bundle["run_id"]
        if not isinstance(rid, str) or not rid.strip():
            errors.append("run_id must be a non-empty string")

    # Validate source_id is non-empty string
    if "source_id" in bundle:
        sid = bundle["source_id"]
        if not isinstance(sid, str) or not sid.strip():
            errors.append("source_id must be a non-empty string")

    # Validate created_at as ISO-8601
    if "created_at" in bundle:
        try:
            _parse_iso8601_utc(bundle["created_at"])
        except (ValueError, TypeError) as exc:
            errors.append(f"Invalid created_at datetime: {exc}")

    # Validate gist is a string
    if "gist" in bundle:
        if not isinstance(bundle["gist"], str):
            errors.append("gist must be a string")

    # Validate array fields exist as lists
    for array_key in ("bullets", "claims", "entities", "definitions", "warnings"):
        if array_key in bundle and not isinstance(bundle[array_key], list):
            errors.append(f"{array_key} must be an array")

    # Validate individual claims
    if "claims" in bundle and isinstance(bundle["claims"], list):
        for i, claim in enumerate(bundle["claims"]):
            if not isinstance(claim, dict):
                errors.append(f"claims[{i}] must be an object")
                continue
            # Check required claim keys
            for key in EXTRACTION_CLAIM_REQUIRED_KEYS:
                if key not in claim:
                    errors.append(f"claims[{i}] missing required key: {key}")
            # AC-SCH-008-2: claim_text must be non-empty
            if "claim_text" in claim:
                ct = claim["claim_text"]
                if not isinstance(ct, str) or not ct.strip():
                    errors.append(
                        f"claims[{i}].claim_text must be non-empty (after trimming)"
                    )
            # Validate claim_type enum
            if "claim_type" in claim:
                ctype = claim["claim_type"]
                if ctype not in CLAIM_TYPES:
                    errors.append(
                        f"claims[{i}].claim_type invalid: {ctype!r}"
                    )
            # Validate polarity enum
            if "polarity" in claim:
                pol = claim["polarity"]
                if pol not in POLARITIES:
                    errors.append(
                        f"claims[{i}].polarity invalid: {pol!r}"
                    )

    # AC-SCH-008-3: empty claims requires WARN_NO_CLAIMS_EXTRACTED
    if "claims" in bundle and isinstance(bundle["claims"], list):
        if len(bundle["claims"]) == 0:
            has_warn = False
            if "warnings" in bundle and isinstance(bundle["warnings"], list):
                has_warn = any(
                    isinstance(w, dict) and w.get("code") == "WARN_NO_CLAIMS_EXTRACTED"
                    for w in bundle["warnings"]
                )
            if not has_warn:
                errors.append(
                    "Empty claims array requires a warning with code "
                    "WARN_NO_CLAIMS_EXTRACTED (AC-SCH-008-3)"
                )

    # Validate warning entries
    if "warnings" in bundle and isinstance(bundle["warnings"], list):
        for i, w in enumerate(bundle["warnings"]):
            if not isinstance(w, dict):
                errors.append(f"warnings[{i}] must be an object")
                continue
            if "code" not in w:
                errors.append(f"warnings[{i}] missing required key: code")
            if "message" not in w:
                errors.append(f"warnings[{i}] missing required key: message")

    return errors


def validate_extraction_bundle_strict(bundle: dict[str, Any]) -> None:
    """Validate and raise SchemaValidationError on failure."""
    errors = validate_extraction_bundle(bundle)
    if errors:
        raise SchemaValidationError(errors)
