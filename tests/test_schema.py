"""
Tests for frontmatter schema validation (SCH-001, SCH-002, SCH-003, SCH-005, SCH-008).

Verifies acceptance criteria from §4.2.1, §4.2.2, §4.2.3, §4.2.5, §4.2.8.
"""

from __future__ import annotations

import pytest

from mycelium.schema import (
    CLAIM_REQUIRED_KEYS,
    CLAIM_TYPES,
    EXTRACTION_BUNDLE_REQUIRED_KEYS,
    EXTRACTION_CLAIM_REQUIRED_KEYS,
    NOTE_STATUSES,
    NOTE_TYPES,
    POLARITIES,
    PROVENANCE_REQUIRED_KEYS,
    REQUIRED_KEYS,
    SOURCE_KINDS,
    SOURCE_REQUIRED_KEYS,
    SchemaValidationError,
    check_concept_promotion_links,
    validate_claim_frontmatter,
    validate_claim_frontmatter_strict,
    validate_concept_frontmatter,
    validate_concept_frontmatter_strict,
    validate_extraction_bundle,
    validate_extraction_bundle_strict,
    validate_question_frontmatter,
    validate_question_frontmatter_strict,
    validate_shared_frontmatter,
    validate_shared_frontmatter_strict,
    validate_source_frontmatter,
    validate_source_frontmatter_strict,
)


def _valid_frontmatter(**overrides: object) -> dict:
    """Return a minimal valid frontmatter dict, with optional overrides."""
    base = {
        "type": "source",
        "id": "src-001",
        "status": "draft",
        "created": "2025-06-15T10:30:00Z",
        "updated": "2025-06-15T12:00:00Z",
    }
    base.update(overrides)
    return base


# ─── AC-SCH-001-1: required keys present ────────────────────────────────

class TestRequiredKeys:
    """AC-SCH-001-1: Validator rejects missing required keys and reports which."""

    def test_valid_minimal(self):
        errors = validate_shared_frontmatter(_valid_frontmatter())
        assert errors == []

    @pytest.mark.parametrize("missing_key", REQUIRED_KEYS)
    def test_missing_single_required_key(self, missing_key: str):
        fm = _valid_frontmatter()
        del fm[missing_key]
        errors = validate_shared_frontmatter(fm)
        assert any(missing_key in e for e in errors), f"Expected error mentioning {missing_key}"

    def test_missing_multiple_required_keys(self):
        fm = {"tags": ["test"]}
        errors = validate_shared_frontmatter(fm)
        for key in REQUIRED_KEYS:
            assert any(key in e for e in errors), f"Expected error mentioning {key}"

    def test_empty_frontmatter(self):
        errors = validate_shared_frontmatter({})
        assert len(errors) == len(REQUIRED_KEYS)

    def test_invalid_type_enum(self):
        errors = validate_shared_frontmatter(_valid_frontmatter(type="notebook"))
        assert any("type" in e and "notebook" in e for e in errors)

    def test_all_valid_types_accepted(self):
        for t in NOTE_TYPES:
            errors = validate_shared_frontmatter(_valid_frontmatter(type=t))
            assert errors == [], f"Type {t!r} should be valid"

    def test_invalid_status_enum(self):
        errors = validate_shared_frontmatter(_valid_frontmatter(status="archived"))
        assert any("status" in e and "archived" in e for e in errors)

    def test_all_valid_statuses_accepted(self):
        for s in NOTE_STATUSES:
            errors = validate_shared_frontmatter(_valid_frontmatter(status=s))
            assert errors == [], f"Status {s!r} should be valid"

    def test_empty_id_rejected(self):
        errors = validate_shared_frontmatter(_valid_frontmatter(id=""))
        assert any("id" in e for e in errors)

    def test_whitespace_only_id_rejected(self):
        errors = validate_shared_frontmatter(_valid_frontmatter(id="   "))
        assert any("id" in e for e in errors)

    def test_non_string_id_rejected(self):
        errors = validate_shared_frontmatter(_valid_frontmatter(id=42))
        assert any("id" in e for e in errors)


# ─── AC-SCH-001-2: created/updated ISO-8601 UTC ─────────────────────────

class TestDatetimeFields:
    """AC-SCH-001-2: created/updated parse as ISO-8601 UTC; reject invalid."""

    def test_valid_z_suffix(self):
        errors = validate_shared_frontmatter(_valid_frontmatter(
            created="2025-01-01T00:00:00Z",
            updated="2025-06-15T23:59:59Z",
        ))
        assert errors == []

    def test_valid_offset(self):
        errors = validate_shared_frontmatter(_valid_frontmatter(
            created="2025-01-01T00:00:00+00:00",
            updated="2025-06-15T12:00:00+00:00",
        ))
        assert errors == []

    def test_valid_microseconds(self):
        errors = validate_shared_frontmatter(_valid_frontmatter(
            created="2025-01-01T00:00:00.123456Z",
        ))
        assert errors == []

    @pytest.mark.parametrize("bad_value", [
        "not-a-date",
        "2025-13-01T00:00:00Z",  # month 13
        "yesterday",
        "",
        12345,
        None,
        True,
    ])
    def test_invalid_created_rejected(self, bad_value: object):
        errors = validate_shared_frontmatter(_valid_frontmatter(created=bad_value))
        assert any("created" in e for e in errors)

    @pytest.mark.parametrize("bad_value", [
        "not-a-date",
        "2025/06/15",
        "",
        42,
    ])
    def test_invalid_updated_rejected(self, bad_value: object):
        errors = validate_shared_frontmatter(_valid_frontmatter(updated=bad_value))
        assert any("updated" in e for e in errors)


# ─── AC-SCH-001-3: confidence in [0.0..1.0] ─────────────────────────────

class TestConfidence:
    """AC-SCH-001-3: confidence outside [0.0..1.0] is rejected."""

    def test_valid_confidence_boundaries(self):
        for val in (0.0, 0.5, 1.0):
            errors = validate_shared_frontmatter(_valid_frontmatter(confidence=val))
            assert errors == [], f"confidence={val} should be valid"

    def test_valid_confidence_int(self):
        # 0 and 1 as ints are valid
        for val in (0, 1):
            errors = validate_shared_frontmatter(_valid_frontmatter(confidence=val))
            assert errors == [], f"confidence={val} (int) should be valid"

    def test_confidence_below_zero(self):
        errors = validate_shared_frontmatter(_valid_frontmatter(confidence=-0.1))
        assert any("confidence" in e for e in errors)

    def test_confidence_above_one(self):
        errors = validate_shared_frontmatter(_valid_frontmatter(confidence=1.1))
        assert any("confidence" in e for e in errors)

    def test_confidence_non_numeric(self):
        errors = validate_shared_frontmatter(_valid_frontmatter(confidence="high"))
        assert any("confidence" in e for e in errors)

    def test_no_confidence_is_ok(self):
        """confidence is optional — omitting it is valid."""
        errors = validate_shared_frontmatter(_valid_frontmatter())
        assert errors == []


# ─── AC-SCH-001-4: last_reviewed_at datetime ─────────────────────────────

class TestLastReviewedAt:
    """AC-SCH-001-4: last_reviewed_at rejects invalid datetime formats."""

    def test_valid_last_reviewed_at(self):
        errors = validate_shared_frontmatter(_valid_frontmatter(
            last_reviewed_at="2025-08-01T09:00:00Z",
        ))
        assert errors == []

    def test_invalid_last_reviewed_at(self):
        errors = validate_shared_frontmatter(_valid_frontmatter(
            last_reviewed_at="not-a-date",
        ))
        assert any("last_reviewed_at" in e for e in errors)

    def test_no_last_reviewed_at_is_ok(self):
        """last_reviewed_at is optional — omitting it is valid."""
        errors = validate_shared_frontmatter(_valid_frontmatter())
        assert errors == []


# ─── Forward compatibility: unknown keys ignored ─────────────────────────

class TestForwardCompatibility:
    """Validators MUST ignore unknown keys (§4.2.1)."""

    def test_extra_keys_ignored(self):
        fm = _valid_frontmatter(
            custom_field="hello",
            future_key=42,
            nested={"a": 1},
        )
        errors = validate_shared_frontmatter(fm)
        assert errors == []


# ─── Strict wrapper ──────────────────────────────────────────────────────

class TestStrictWrapper:

    def test_valid_does_not_raise(self):
        validate_shared_frontmatter_strict(_valid_frontmatter())

    def test_invalid_raises_schema_error(self):
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_shared_frontmatter_strict({})
        assert len(exc_info.value.errors) == len(REQUIRED_KEYS)

    def test_error_message_contains_details(self):
        with pytest.raises(SchemaValidationError, match="Missing required key"):
            validate_shared_frontmatter_strict({"type": "source"})


# ═══════════════════════════════════════════════════════════════════════════
# SCH-002: Source Note Schema (§4.2.2)
# ═══════════════════════════════════════════════════════════════════════════

VALID_FINGERPRINT = "sha256:" + "a" * 64


def _valid_source_frontmatter(**overrides: object) -> dict:
    """Return a minimal valid Source Note frontmatter dict."""
    base = {
        "type": "source",
        "id": "src-001",
        "status": "draft",
        "created": "2025-06-15T10:30:00Z",
        "updated": "2025-06-15T12:00:00Z",
        "source_ref": "https://example.com/article",
        "source_kind": "url",
        "normalized_locator": "https://example.com/article",
        "fingerprint": VALID_FINGERPRINT,
        "captured_at": "2025-06-15T10:30:00Z",
    }
    base.update(overrides)
    return base


# ─── AC-SCH-002-3: missing required Source Note keys ────────────────────

class TestSourceRequiredKeys:
    """AC-SCH-002-3: Rejects Source Notes missing any required Source Note key."""

    def test_valid_source_note(self):
        errors = validate_source_frontmatter(_valid_source_frontmatter())
        assert errors == []

    @pytest.mark.parametrize("missing_key", SOURCE_REQUIRED_KEYS)
    def test_missing_single_source_key(self, missing_key: str):
        fm = _valid_source_frontmatter()
        del fm[missing_key]
        errors = validate_source_frontmatter(fm)
        assert any(missing_key in e for e in errors)

    def test_missing_all_source_keys(self):
        fm = _valid_frontmatter()  # has shared keys but no source keys
        errors = validate_source_frontmatter(fm)
        for key in SOURCE_REQUIRED_KEYS:
            assert any(key in e for e in errors)

    def test_shared_errors_also_reported(self):
        """Source validator includes shared validation errors."""
        fm = _valid_source_frontmatter()
        del fm["type"]
        errors = validate_source_frontmatter(fm)
        assert any("type" in e for e in errors)


# ─── AC-SCH-002-2: fingerprint format ───────────────────────────────────

class TestSourceFingerprint:
    """AC-SCH-002-2: Rejects fingerprint not matching sha256:<64-hex>."""

    def test_valid_fingerprint(self):
        errors = validate_source_frontmatter(_valid_source_frontmatter(
            fingerprint="sha256:" + "0" * 64,
        ))
        assert errors == []

    def test_valid_fingerprint_mixed_hex(self):
        errors = validate_source_frontmatter(_valid_source_frontmatter(
            fingerprint="sha256:" + "abcdef0123456789" * 4,
        ))
        assert errors == []

    @pytest.mark.parametrize("bad_fp", [
        "md5:abcdef",                      # wrong prefix
        "sha256:" + "g" * 64,              # non-hex chars
        "sha256:" + "a" * 63,              # too short
        "sha256:" + "a" * 65,              # too long
        "SHA256:" + "a" * 64,              # wrong case prefix
        "sha256:" + "A" * 64,              # uppercase hex
        "sha256:abc",                       # way too short
        "",                                 # empty
        "plain-hash",                       # no prefix
    ])
    def test_invalid_fingerprint_rejected(self, bad_fp: str):
        errors = validate_source_frontmatter(_valid_source_frontmatter(
            fingerprint=bad_fp,
        ))
        assert any("fingerprint" in e for e in errors)

    def test_non_string_fingerprint_rejected(self):
        errors = validate_source_frontmatter(_valid_source_frontmatter(
            fingerprint=12345,
        ))
        assert any("fingerprint" in e for e in errors)


# ─── source_kind enum ───────────────────────────────────────────────────

class TestSourceKind:

    def test_all_valid_source_kinds(self):
        for kind in SOURCE_KINDS:
            errors = validate_source_frontmatter(_valid_source_frontmatter(
                source_kind=kind,
            ))
            assert errors == [], f"source_kind={kind!r} should be valid"

    def test_invalid_source_kind(self):
        errors = validate_source_frontmatter(_valid_source_frontmatter(
            source_kind="youtube",
        ))
        assert any("source_kind" in e for e in errors)


# ─── captured_at datetime ───────────────────────────────────────────────

class TestCapturedAt:

    def test_valid_captured_at(self):
        errors = validate_source_frontmatter(_valid_source_frontmatter(
            captured_at="2025-06-15T10:30:00Z",
        ))
        assert errors == []

    def test_invalid_captured_at(self):
        errors = validate_source_frontmatter(_valid_source_frontmatter(
            captured_at="not-a-date",
        ))
        assert any("captured_at" in e for e in errors)


# ─── source_ref and normalized_locator ──────────────────────────────────

class TestSourceRefAndLocator:

    def test_empty_source_ref_rejected(self):
        errors = validate_source_frontmatter(_valid_source_frontmatter(
            source_ref="",
        ))
        assert any("source_ref" in e for e in errors)

    def test_empty_normalized_locator_rejected(self):
        errors = validate_source_frontmatter(_valid_source_frontmatter(
            normalized_locator="",
        ))
        assert any("normalized_locator" in e for e in errors)


# ─── Source strict wrapper ──────────────────────────────────────────────

class TestSourceStrictWrapper:

    def test_valid_does_not_raise(self):
        validate_source_frontmatter_strict(_valid_source_frontmatter())

    def test_invalid_raises(self):
        with pytest.raises(SchemaValidationError):
            validate_source_frontmatter_strict({})


# ─── AC-SCH-002-1: deterministic fingerprint ────────────────────────────

class TestFingerprintDeterminism:
    """AC-SCH-002-1: same normalized payload => same fingerprint."""

    def test_same_fingerprint_accepted_multiple_times(self):
        """Validator accepts the same valid fingerprint on repeated calls."""
        fp = "sha256:" + "b" * 64
        for _ in range(3):
            errors = validate_source_frontmatter(_valid_source_frontmatter(
                fingerprint=fp,
            ))
            assert errors == []


# ─── Forward compatibility: unknown source keys ignored ──────────────────

class TestSourceForwardCompatibility:

    def test_extra_source_keys_ignored(self):
        fm = _valid_source_frontmatter(
            future_source_field="hello",
            extra_metadata={"x": 1},
        )
        errors = validate_source_frontmatter(fm)
        assert errors == []


# ═══════════════════════════════════════════════════════════════════════════
# SCH-003: Claim Note Schema (§4.2.3)
# ═══════════════════════════════════════════════════════════════════════════

VALID_SNIPPET_HASH = "sha256:" + "c" * 64


def _valid_claim_frontmatter(**overrides: object) -> dict:
    """Return a minimal valid Claim Note frontmatter dict."""
    base = {
        "type": "claim",
        "id": "clm-001",
        "status": "draft",
        "created": "2025-06-15T10:30:00Z",
        "updated": "2025-06-15T12:00:00Z",
        "claim_text": "Aspirin reduces inflammation in most adults.",
        "claim_type": "empirical",
        "polarity": "supports",
        "provenance": {
            "source_id": "src-001",
            "source_ref": "https://example.com/study",
            "locator": {
                "url": "https://example.com/study",
                "section": "Results",
                "paragraph_index": 3,
                "snippet_hash": VALID_SNIPPET_HASH,
            },
        },
    }
    base.update(overrides)
    return base


# ─── AC-SCH-003-1: empty claim_text rejected ────────────────────────────

class TestClaimText:
    """AC-SCH-003-1: Rejects Claim Notes with empty claim_text."""

    def test_valid_claim(self):
        errors, warnings = validate_claim_frontmatter(_valid_claim_frontmatter())
        assert errors == []

    def test_empty_claim_text(self):
        errors, _ = validate_claim_frontmatter(_valid_claim_frontmatter(claim_text=""))
        assert any("claim_text" in e for e in errors)

    def test_whitespace_only_claim_text(self):
        errors, _ = validate_claim_frontmatter(_valid_claim_frontmatter(claim_text="   "))
        assert any("claim_text" in e for e in errors)

    def test_non_string_claim_text(self):
        errors, _ = validate_claim_frontmatter(_valid_claim_frontmatter(claim_text=42))
        assert any("claim_text" in e for e in errors)


# ─── Claim required keys ────────────────────────────────────────────────

class TestClaimRequiredKeys:

    @pytest.mark.parametrize("missing_key", CLAIM_REQUIRED_KEYS)
    def test_missing_single_claim_key(self, missing_key: str):
        fm = _valid_claim_frontmatter()
        del fm[missing_key]
        errors, _ = validate_claim_frontmatter(fm)
        assert any(missing_key in e for e in errors)

    def test_shared_errors_also_reported(self):
        fm = _valid_claim_frontmatter()
        del fm["type"]
        errors, _ = validate_claim_frontmatter(fm)
        assert any("type" in e for e in errors)


# ─── Claim enums ────────────────────────────────────────────────────────

class TestClaimEnums:

    def test_all_valid_claim_types(self):
        for ct in CLAIM_TYPES:
            errors, _ = validate_claim_frontmatter(_valid_claim_frontmatter(claim_type=ct))
            assert errors == [], f"claim_type={ct!r} should be valid"

    def test_invalid_claim_type(self):
        errors, _ = validate_claim_frontmatter(_valid_claim_frontmatter(claim_type="opinion"))
        assert any("claim_type" in e for e in errors)

    def test_all_valid_polarities(self):
        for p in POLARITIES:
            errors, _ = validate_claim_frontmatter(_valid_claim_frontmatter(polarity=p))
            assert errors == [], f"polarity={p!r} should be valid"

    def test_invalid_polarity(self):
        errors, _ = validate_claim_frontmatter(_valid_claim_frontmatter(polarity="mixed"))
        assert any("polarity" in e for e in errors)


# ─── AC-SCH-003-2: provenance required fields ───────────────────────────

class TestProvenanceRequired:
    """AC-SCH-003-2: Rejects missing provenance.source_id/source_ref/locator."""

    def test_valid_provenance(self):
        errors, _ = validate_claim_frontmatter(_valid_claim_frontmatter())
        assert errors == []

    def test_provenance_not_object(self):
        errors, _ = validate_claim_frontmatter(_valid_claim_frontmatter(
            provenance="not-an-object",
        ))
        assert any("provenance" in e and "object" in e for e in errors)

    @pytest.mark.parametrize("missing_key", PROVENANCE_REQUIRED_KEYS)
    def test_missing_provenance_key(self, missing_key: str):
        fm = _valid_claim_frontmatter()
        del fm["provenance"][missing_key]
        errors, _ = validate_claim_frontmatter(fm)
        assert any(missing_key in e for e in errors)

    def test_empty_source_id(self):
        fm = _valid_claim_frontmatter()
        fm["provenance"]["source_id"] = ""
        errors, _ = validate_claim_frontmatter(fm)
        assert any("source_id" in e for e in errors)

    def test_empty_source_ref(self):
        fm = _valid_claim_frontmatter()
        fm["provenance"]["source_ref"] = ""
        errors, _ = validate_claim_frontmatter(fm)
        assert any("source_ref" in e for e in errors)


# ─── AC-SCH-003-4: URL/PDF locator validation ───────────────────────────

class TestURLLocator:
    """AC-SCH-003-4: URL locator required keys and snippet_hash format."""

    def test_valid_url_locator(self):
        errors, _ = validate_claim_frontmatter(
            _valid_claim_frontmatter(), source_kind="url",
        )
        assert errors == []

    def test_url_locator_allows_null_section(self):
        fm = _valid_claim_frontmatter()
        fm["provenance"]["locator"]["section"] = None
        errors, _ = validate_claim_frontmatter(fm, source_kind="url")
        assert errors == []

    def test_url_locator_allows_null_paragraph_index(self):
        fm = _valid_claim_frontmatter()
        fm["provenance"]["locator"]["paragraph_index"] = None
        errors, _ = validate_claim_frontmatter(fm, source_kind="url")
        assert errors == []

    @pytest.mark.parametrize("missing_key", ["url", "section", "paragraph_index", "snippet_hash"])
    def test_url_locator_missing_key(self, missing_key: str):
        fm = _valid_claim_frontmatter()
        del fm["provenance"]["locator"][missing_key]
        errors, _ = validate_claim_frontmatter(fm, source_kind="url")
        assert any(missing_key in e for e in errors)

    def test_url_locator_bad_snippet_hash(self):
        fm = _valid_claim_frontmatter()
        fm["provenance"]["locator"]["snippet_hash"] = "md5:abc"
        errors, _ = validate_claim_frontmatter(fm, source_kind="url")
        assert any("snippet_hash" in e for e in errors)


class TestPDFLocator:
    """AC-SCH-003-4: PDF locator required keys and snippet_hash format."""

    def _pdf_claim(self, **locator_overrides: object) -> dict:
        fm = _valid_claim_frontmatter()
        fm["provenance"]["locator"] = {
            "pdf_ref": "study.pdf",
            "page": 5,
            "section": "Methods",
            "snippet_hash": VALID_SNIPPET_HASH,
            **locator_overrides,
        }
        return fm

    def test_valid_pdf_locator(self):
        errors, _ = validate_claim_frontmatter(self._pdf_claim(), source_kind="pdf")
        assert errors == []

    @pytest.mark.parametrize("missing_key", ["pdf_ref", "page", "section", "snippet_hash"])
    def test_pdf_locator_missing_key(self, missing_key: str):
        fm = self._pdf_claim()
        del fm["provenance"]["locator"][missing_key]
        errors, _ = validate_claim_frontmatter(fm, source_kind="pdf")
        assert any(missing_key in e for e in errors)

    def test_pdf_page_must_be_int(self):
        errors, _ = validate_claim_frontmatter(
            self._pdf_claim(page="five"), source_kind="pdf",
        )
        assert any("page" in e for e in errors)

    def test_pdf_bad_snippet_hash(self):
        errors, _ = validate_claim_frontmatter(
            self._pdf_claim(snippet_hash="bad"), source_kind="pdf",
        )
        assert any("snippet_hash" in e for e in errors)


# ─── AC-SCH-003-5: raw_locator for other source kinds ───────────────────

class TestRawLocator:
    """AC-SCH-003-5: Non-URL/PDF MVP1 kinds accept raw_locator with warning."""

    @pytest.mark.parametrize("kind", ["doi", "arxiv", "highlights", "book", "text_bundle"])
    def test_raw_locator_accepted_with_warning(self, kind: str):
        fm = _valid_claim_frontmatter()
        fm["provenance"]["locator"] = {"raw_locator": "some-reference"}
        errors, warnings = validate_claim_frontmatter(fm, source_kind=kind)
        assert errors == []
        assert any("deferred" in w.lower() or "mvp2" in w.lower() for w in warnings)

    @pytest.mark.parametrize("kind", ["doi", "arxiv"])
    def test_missing_raw_locator_warns(self, kind: str):
        fm = _valid_claim_frontmatter()
        fm["provenance"]["locator"] = {}
        errors, warnings = validate_claim_frontmatter(fm, source_kind=kind)
        assert errors == []  # not an error, just a warning
        assert any("raw_locator" in w for w in warnings)


# ─── No source_kind: locator not validated ───────────────────────────────

class TestNoSourceKind:
    """When source_kind is None, locator structure is not validated."""

    def test_any_locator_accepted(self):
        fm = _valid_claim_frontmatter()
        fm["provenance"]["locator"] = {"anything": "goes"}
        errors, warnings = validate_claim_frontmatter(fm, source_kind=None)
        assert errors == []
        assert warnings == []


# ─── Claim strict wrapper ───────────────────────────────────────────────

class TestClaimStrictWrapper:

    def test_valid_does_not_raise(self):
        warnings = validate_claim_frontmatter_strict(_valid_claim_frontmatter())
        assert isinstance(warnings, list)

    def test_invalid_raises(self):
        with pytest.raises(SchemaValidationError):
            validate_claim_frontmatter_strict({})

    def test_returns_warnings_on_success(self):
        fm = _valid_claim_frontmatter()
        fm["provenance"]["locator"] = {"raw_locator": "ref"}
        warnings = validate_claim_frontmatter_strict(fm, source_kind="doi")
        assert len(warnings) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# SCH-008: Extraction Bundle Schema (§4.2.8)
# ═══════════════════════════════════════════════════════════════════════════

def _valid_extraction_bundle(**overrides: object) -> dict:
    """Return a minimal valid Extraction Bundle dict."""
    base = {
        "run_id": "run-001",
        "source_id": "src-001",
        "created_at": "2025-06-15T10:30:00Z",
        "gist": "Summary of the source material.",
        "bullets": ["Key point 1", "Key point 2"],
        "claims": [
            {
                "extracted_claim_key": "sha256:" + "d" * 64,
                "claim_text": "Aspirin reduces inflammation.",
                "claim_type": "empirical",
                "polarity": "supports",
                "provenance": {
                    "source_id": "src-001",
                    "source_ref": "https://example.com",
                    "locator": {"raw_locator": "page 5"},
                },
            },
        ],
        "entities": ["aspirin", "inflammation"],
        "definitions": [],
        "warnings": [],
    }
    base.update(overrides)
    return base


# ─── AC-SCH-008-2: required keys and claim_text ─────────────────────────

class TestExtractionBundleRequired:
    """AC-SCH-008-2: Rejects bundles missing required keys or empty claim_text."""

    def test_valid_bundle(self):
        errors = validate_extraction_bundle(_valid_extraction_bundle())
        assert errors == []

    @pytest.mark.parametrize("missing_key", EXTRACTION_BUNDLE_REQUIRED_KEYS)
    def test_missing_top_level_key(self, missing_key: str):
        bundle = _valid_extraction_bundle()
        del bundle[missing_key]
        errors = validate_extraction_bundle(bundle)
        assert any(missing_key in e for e in errors)

    def test_empty_bundle(self):
        errors = validate_extraction_bundle({})
        assert len(errors) == len(EXTRACTION_BUNDLE_REQUIRED_KEYS)

    def test_claim_missing_required_key(self):
        bundle = _valid_extraction_bundle()
        del bundle["claims"][0]["claim_text"]
        errors = validate_extraction_bundle(bundle)
        assert any("claim_text" in e for e in errors)

    @pytest.mark.parametrize("missing_key", EXTRACTION_CLAIM_REQUIRED_KEYS)
    def test_claim_missing_each_key(self, missing_key: str):
        bundle = _valid_extraction_bundle()
        del bundle["claims"][0][missing_key]
        errors = validate_extraction_bundle(bundle)
        assert any(missing_key in e for e in errors)

    def test_empty_claim_text_rejected(self):
        bundle = _valid_extraction_bundle()
        bundle["claims"][0]["claim_text"] = ""
        errors = validate_extraction_bundle(bundle)
        assert any("claim_text" in e for e in errors)

    def test_whitespace_claim_text_rejected(self):
        bundle = _valid_extraction_bundle()
        bundle["claims"][0]["claim_text"] = "   "
        errors = validate_extraction_bundle(bundle)
        assert any("claim_text" in e for e in errors)

    def test_invalid_claim_type(self):
        bundle = _valid_extraction_bundle()
        bundle["claims"][0]["claim_type"] = "opinion"
        errors = validate_extraction_bundle(bundle)
        assert any("claim_type" in e for e in errors)

    def test_invalid_polarity(self):
        bundle = _valid_extraction_bundle()
        bundle["claims"][0]["polarity"] = "maybe"
        errors = validate_extraction_bundle(bundle)
        assert any("polarity" in e for e in errors)


# ─── AC-SCH-008-3: empty claims requires WARN_NO_CLAIMS_EXTRACTED ────────

class TestExtractionBundleEmptyClaims:
    """AC-SCH-008-3: Empty claims must have WARN_NO_CLAIMS_EXTRACTED."""

    def test_empty_claims_with_warning_ok(self):
        bundle = _valid_extraction_bundle(
            claims=[],
            warnings=[{"code": "WARN_NO_CLAIMS_EXTRACTED", "message": "No claims found"}],
        )
        errors = validate_extraction_bundle(bundle)
        assert errors == []

    def test_empty_claims_without_warning_rejected(self):
        bundle = _valid_extraction_bundle(claims=[], warnings=[])
        errors = validate_extraction_bundle(bundle)
        assert any("WARN_NO_CLAIMS_EXTRACTED" in e for e in errors)

    def test_non_empty_claims_no_warning_needed(self):
        bundle = _valid_extraction_bundle()
        assert len(bundle["claims"]) > 0
        errors = validate_extraction_bundle(bundle)
        assert errors == []


# ─── Extraction Bundle validation: datetimes, strings, arrays ────────────

class TestExtractionBundleFields:

    def test_invalid_created_at(self):
        errors = validate_extraction_bundle(
            _valid_extraction_bundle(created_at="not-a-date")
        )
        assert any("created_at" in e for e in errors)

    def test_empty_run_id(self):
        errors = validate_extraction_bundle(
            _valid_extraction_bundle(run_id="")
        )
        assert any("run_id" in e for e in errors)

    def test_empty_source_id(self):
        errors = validate_extraction_bundle(
            _valid_extraction_bundle(source_id="")
        )
        assert any("source_id" in e for e in errors)

    def test_gist_must_be_string(self):
        errors = validate_extraction_bundle(
            _valid_extraction_bundle(gist=42)
        )
        assert any("gist" in e for e in errors)

    def test_claims_not_array(self):
        errors = validate_extraction_bundle(
            _valid_extraction_bundle(claims="not-an-array")
        )
        assert any("claims" in e for e in errors)

    def test_claim_not_object(self):
        bundle = _valid_extraction_bundle(claims=["not-an-object"])
        errors = validate_extraction_bundle(bundle)
        assert any("claims[0]" in e for e in errors)


# ─── Warning entry validation ────────────────────────────────────────────

class TestExtractionBundleWarnings:

    def test_warning_missing_code(self):
        bundle = _valid_extraction_bundle(
            warnings=[{"message": "something"}],
        )
        errors = validate_extraction_bundle(bundle)
        assert any("code" in e for e in errors)

    def test_warning_missing_message(self):
        bundle = _valid_extraction_bundle(
            warnings=[{"code": "W_TEST"}],
        )
        errors = validate_extraction_bundle(bundle)
        assert any("message" in e for e in errors)

    def test_valid_warning(self):
        bundle = _valid_extraction_bundle(
            warnings=[{"code": "W_TEST", "message": "test warning"}],
        )
        errors = validate_extraction_bundle(bundle)
        assert errors == []


# ─── Extraction Bundle strict wrapper ────────────────────────────────────

class TestExtractionBundleStrict:

    def test_valid_does_not_raise(self):
        validate_extraction_bundle_strict(_valid_extraction_bundle())

    def test_invalid_raises(self):
        with pytest.raises(SchemaValidationError):
            validate_extraction_bundle_strict({})


# ═══════════════════════════════════════════════════════════════════════
# SCH-004: Concept Note Schema (§4.2.4)
# ═══════════════════════════════════════════════════════════════════════

def _valid_concept_frontmatter(**overrides: object) -> dict:
    """Return minimal valid Concept Note frontmatter."""
    base = _valid_frontmatter(type="concept", id="con-001")
    base["term"] = "Neuroplasticity"
    base.update(overrides)
    return base


class TestConceptFrontmatter:
    """AC-SCH-004-1: Validator rejects Concept Notes missing term."""

    def test_valid_concept_note(self):
        errors = validate_concept_frontmatter(_valid_concept_frontmatter())
        assert errors == []

    def test_missing_term(self):
        fm = _valid_concept_frontmatter()
        del fm["term"]
        errors = validate_concept_frontmatter(fm)
        assert any("term" in e for e in errors)

    def test_empty_term(self):
        errors = validate_concept_frontmatter(
            _valid_concept_frontmatter(term="")
        )
        assert any("term" in e and "non-empty" in e for e in errors)

    def test_whitespace_only_term(self):
        errors = validate_concept_frontmatter(
            _valid_concept_frontmatter(term="   \t\n  ")
        )
        assert any("term" in e and "non-empty" in e for e in errors)

    def test_non_string_term(self):
        errors = validate_concept_frontmatter(
            _valid_concept_frontmatter(term=42)
        )
        assert any("term" in e for e in errors)

    def test_shared_validation_runs(self):
        """SCH-001 validation is included (missing shared keys fail)."""
        errors = validate_concept_frontmatter({"term": "Something"})
        assert any("Missing required key" in e for e in errors)

    def test_unknown_keys_ignored(self):
        fm = _valid_concept_frontmatter(extra_field="ignored")
        errors = validate_concept_frontmatter(fm)
        assert errors == []

    def test_term_with_leading_trailing_spaces_valid(self):
        """Non-empty after trimming means valid even with surrounding spaces."""
        errors = validate_concept_frontmatter(
            _valid_concept_frontmatter(term="  Neuroplasticity  ")
        )
        assert errors == []


class TestConceptFrontmatterStrict:

    def test_valid_does_not_raise(self):
        validate_concept_frontmatter_strict(_valid_concept_frontmatter())

    def test_invalid_raises(self):
        with pytest.raises(SchemaValidationError):
            validate_concept_frontmatter_strict({})


class TestConceptPromotionLinks:
    """AC-SCH-004-2: Promotion fails for Concept Notes with zero resolved wikilinks."""

    def test_no_links_rejected(self):
        errors = check_concept_promotion_links("No links here.", "/tmp/fake")
        assert len(errors) == 1
        assert "zero outbound" in errors[0]

    def test_unresolved_link_rejected(self, tmp_path):
        errors = check_concept_promotion_links(
            "See [[nonexistent-note]].", tmp_path
        )
        assert len(errors) == 1
        assert "none resolve" in errors[0]

    def test_resolved_link_accepted(self, tmp_path):
        # Create a note that the wikilink resolves to
        (tmp_path / "Sources").mkdir()
        (tmp_path / "Sources" / "s-001.md").write_text("content")
        errors = check_concept_promotion_links(
            "See [[Sources/s-001]].", tmp_path
        )
        assert errors == []

    def test_mixed_resolved_unresolved_accepted(self, tmp_path):
        """At least one resolved link is sufficient."""
        (tmp_path / "Sources").mkdir()
        (tmp_path / "Sources" / "s-001.md").write_text("content")
        errors = check_concept_promotion_links(
            "See [[Sources/s-001]] and [[missing]].", tmp_path
        )
        assert errors == []

    def test_empty_body_rejected(self):
        errors = check_concept_promotion_links("", "/tmp/fake")
        assert len(errors) == 1


# ═══════════════════════════════════════════════════════════════════════
# SCH-005: Question Note Schema (§4.2.5)
# ═══════════════════════════════════════════════════════════════════════

def _valid_question_frontmatter(**overrides: object) -> dict:
    """Return minimal valid Question Note frontmatter."""
    base = _valid_frontmatter(type="question", id="q-001")
    base["question_text"] = "What is the mechanism of aspirin?"
    base.update(overrides)
    return base


class TestQuestionFrontmatter:
    """AC-SCH-005-1: Validator rejects Question Notes missing question_text."""

    def test_valid_question_note(self):
        errors = validate_question_frontmatter(_valid_question_frontmatter())
        assert errors == []

    def test_missing_question_text(self):
        fm = _valid_question_frontmatter()
        del fm["question_text"]
        errors = validate_question_frontmatter(fm)
        assert any("question_text" in e for e in errors)

    def test_empty_question_text(self):
        errors = validate_question_frontmatter(
            _valid_question_frontmatter(question_text="")
        )
        assert any("question_text" in e and "non-empty" in e for e in errors)

    def test_whitespace_only_question_text(self):
        errors = validate_question_frontmatter(
            _valid_question_frontmatter(question_text="   \t\n  ")
        )
        assert any("question_text" in e and "non-empty" in e for e in errors)

    def test_non_string_question_text(self):
        errors = validate_question_frontmatter(
            _valid_question_frontmatter(question_text=42)
        )
        assert any("question_text" in e for e in errors)

    def test_shared_validation_runs(self):
        """SCH-001 validation is included (missing shared keys fail)."""
        errors = validate_question_frontmatter({"question_text": "A question?"})
        assert any("Missing required key" in e for e in errors)

    def test_unknown_keys_ignored(self):
        fm = _valid_question_frontmatter(extra_field="ignored")
        errors = validate_question_frontmatter(fm)
        assert errors == []

    def test_question_text_with_leading_trailing_spaces_valid(self):
        """Non-empty after trimming means valid even with surrounding spaces."""
        errors = validate_question_frontmatter(
            _valid_question_frontmatter(question_text="  What is X?  ")
        )
        assert errors == []


class TestQuestionFrontmatterStrict:

    def test_valid_does_not_raise(self):
        validate_question_frontmatter_strict(_valid_question_frontmatter())

    def test_invalid_raises(self):
        with pytest.raises(SchemaValidationError):
            validate_question_frontmatter_strict({})
