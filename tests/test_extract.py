"""Tests for the Extract stage (stage 4/7) of the ingestion pipeline.

Validates acceptance criteria from §6.2 EXT-001 and §4.2.8 SCH-008:
  AC-EXT-001-1: For a Source with extractable assertions, claims.length >= 1.
  AC-EXT-001-2: For zero-claim sources, warning WARN_NO_CLAIMS_EXTRACTED.
  AC-SCH-008-1: Bundle YAML exists under Inbox/Sources/ and validates.
  AC-SCH-008-2: Validator rejects bundles missing keys or empty claim_text.
  AC-SCH-008-3: Empty claims requires WARN_NO_CLAIMS_EXTRACTED warning.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml

from mycelium.canonicalize import extracted_claim_key
from mycelium.schema import validate_extraction_bundle
from mycelium.stages.extract import (
    STAGE_NAME,
    ERR_EXTRACTION_FAILED,
    ERR_SCHEMA_VALIDATION,
    WARN_NO_CLAIMS_EXTRACTED,
    Claim,
    ExtractionResult,
    _build_bundle,
    _classify_claim_type,
    _classify_polarity,
    _extract_bullets,
    _extract_claims,
    _extract_gist,
    _make_locator,
    _make_provenance,
    _snippet_hash,
    _split_sentences,
    extract,
)
from mycelium.stages.normalize import NormalizedSource


# ─── Test fixtures ─────────────────────────────────────────────────────────

RICH_TEXT = """\
# Research Summary

Studies show that regular exercise reduces the risk of heart disease.
Exercise is defined as any bodily movement that enhances physical fitness.
Lack of physical activity leads to increased health problems.
- Aerobic exercise improves cardiovascular function
- Resistance training builds muscle mass
- Flexibility exercises reduce injury risk
People should exercise at least 150 minutes per week.
"""

MINIMAL_TEXT = "Hello world."

EMPTY_CLAIMS_TEXT = "###\n---\n***"


def _url_source(text: str = RICH_TEXT, source_ref: str = "https://example.com/article") -> NormalizedSource:
    return NormalizedSource(
        normalized_text=text,
        normalized_locator=source_ref,
        source_kind="url",
        source_ref=source_ref,
        extracted_metadata={"source_kind": "url", "source_ref": source_ref},
    )


def _pdf_source(text: str = RICH_TEXT) -> NormalizedSource:
    return NormalizedSource(
        normalized_text=text,
        normalized_locator="/docs/paper.pdf",
        source_kind="pdf",
        source_ref="/docs/paper.pdf",
        extracted_metadata={"source_kind": "pdf"},
    )


def _text_bundle_source(text: str = RICH_TEXT) -> NormalizedSource:
    return NormalizedSource(
        normalized_text=text,
        normalized_locator="text_bundle:test",
        source_kind="text_bundle",
        source_ref="test",
        extracted_metadata={"source_kind": "text_bundle"},
    )


# ─── Gist extraction ──────────────────────────────────────────────────────

class TestExtractGist:

    def test_extracts_first_meaningful_line(self):
        gist = _extract_gist(RICH_TEXT)
        assert gist == "# Research Summary"

    def test_truncates_long_lines(self):
        long_text = "A" * 300
        gist = _extract_gist(long_text)
        assert len(gist) <= 200
        assert gist.endswith("...")

    def test_skips_empty_lines(self):
        gist = _extract_gist("\n\n\nFirst real line.\n")
        assert gist == "First real line."

    def test_empty_text(self):
        gist = _extract_gist("")
        assert gist == "(empty document)"

    def test_whitespace_only(self):
        gist = _extract_gist("   \n  \n  ")
        assert gist == "(empty document)"


# ─── Bullet extraction ────────────────────────────────────────────────────

class TestExtractBullets:

    def test_extracts_dash_bullets(self):
        bullets = _extract_bullets(RICH_TEXT)
        assert any("Aerobic" in b for b in bullets)

    def test_extracts_numbered_items(self):
        text = "1. First item\n2. Second item\n3. Third item\n"
        bullets = _extract_bullets(text)
        assert len(bullets) == 3
        assert "First item" in bullets[0]

    def test_fallback_to_lines(self):
        text = "No bullet markers here.\nJust plain text.\n"
        bullets = _extract_bullets(text)
        assert len(bullets) >= 1

    def test_empty_text(self):
        bullets = _extract_bullets("")
        assert bullets == []


# ─── Sentence splitting ───────────────────────────────────────────────────

class TestSplitSentences:

    def test_splits_on_period(self):
        sentences = _split_sentences("First sentence. Second sentence.")
        assert len(sentences) == 2

    def test_skips_headings(self):
        sentences = _split_sentences("# Heading\nA sentence here.")
        assert all(not s.startswith("#") for s in sentences)

    def test_skips_short_fragments(self):
        sentences = _split_sentences("OK. This is a real sentence.")
        # "OK." too short
        assert len(sentences) == 1


# ─── Claim classification ─────────────────────────────────────────────────

class TestClassifyClaimType:

    def test_definition(self):
        assert _classify_claim_type("Exercise is defined as bodily movement") == "definition"

    def test_causal(self):
        assert _classify_claim_type("Smoking causes lung cancer in many patients") == "causal"

    def test_normative(self):
        assert _classify_claim_type("People should exercise at least three times per week") == "normative"

    def test_procedural(self):
        assert _classify_claim_type("The process involves first mixing then heating the solution") == "procedural"

    def test_empirical(self):
        assert _classify_claim_type("Studies show that exercise reduces heart disease risk") == "empirical"

    def test_general_assertion(self):
        result = _classify_claim_type("The earth is round and orbits the sun in an elliptical path")
        assert result == "empirical"

    def test_non_claim(self):
        assert _classify_claim_type("Hello!") is None


class TestClassifyPolarity:

    def test_supports(self):
        assert _classify_polarity("Exercise improves health outcomes") == "supports"

    def test_opposes(self):
        assert _classify_polarity("Smoking does not improve health outcomes") == "opposes"

    def test_neutral(self):
        assert _classify_polarity("Although exercise helps, results vary") == "neutral"


# ─── Claim extraction ─────────────────────────────────────────────────────

class TestExtractClaims:

    def test_extracts_from_rich_text(self):
        claims = _extract_claims(RICH_TEXT)
        assert len(claims) >= 1

    def test_claim_has_text(self):
        claims = _extract_claims(RICH_TEXT)
        for c in claims:
            assert c.claim_text.strip()

    def test_claim_has_valid_type(self):
        from mycelium.schema import CLAIM_TYPES
        claims = _extract_claims(RICH_TEXT)
        for c in claims:
            assert c.claim_type in CLAIM_TYPES

    def test_claim_has_valid_polarity(self):
        from mycelium.schema import POLARITIES
        claims = _extract_claims(RICH_TEXT)
        for c in claims:
            assert c.polarity in POLARITIES

    def test_empty_text_no_claims(self):
        claims = _extract_claims("")
        assert claims == []


# ─── Provenance and locator ───────────────────────────────────────────────

class TestProvenance:

    def test_url_locator_keys(self):
        loc = _make_locator("url", "https://example.com", "Some claim text")
        assert "url" in loc
        assert "section" in loc
        assert "paragraph_index" in loc
        assert "snippet_hash" in loc

    def test_pdf_locator_keys(self):
        loc = _make_locator("pdf", "/docs/paper.pdf", "A claim")
        assert "pdf_ref" in loc
        assert "page" in loc
        assert "section" in loc
        assert "snippet_hash" in loc

    def test_other_source_kind_raw_locator(self):
        loc = _make_locator("text_bundle", "test-ref", "A claim")
        assert "raw_locator" in loc

    def test_snippet_hash_format(self):
        h = _snippet_hash("test text")
        assert h.startswith("sha256:")
        assert len(h) == 71  # sha256: + 64 hex

    def test_provenance_structure(self):
        prov = _make_provenance("src-001", "https://x.com", "url", "A claim")
        assert prov["source_id"] == "src-001"
        assert prov["source_ref"] == "https://x.com"
        assert "locator" in prov


# ─── Claim.to_dict ────────────────────────────────────────────────────────

class TestClaimToDict:

    def test_required_keys(self):
        c = Claim(claim_text="Exercise is good for health")
        d = c.to_dict("src-001", "https://x.com", "url")
        assert "extracted_claim_key" in d
        assert "claim_text" in d
        assert "claim_type" in d
        assert "polarity" in d
        assert "provenance" in d

    def test_extracted_claim_key_matches(self):
        text = "Exercise is good for health"
        c = Claim(claim_text=text)
        d = c.to_dict("src-001", "https://x.com", "url")
        assert d["extracted_claim_key"] == extracted_claim_key(text)

    def test_uses_provided_provenance(self):
        prov = {"source_id": "my-src", "source_ref": "ref", "locator": {"raw_locator": "x"}}
        c = Claim(claim_text="A claim", provenance=prov)
        d = c.to_dict("src-001", "https://x.com", "url")
        assert d["provenance"]["source_id"] == "my-src"

    def test_generates_provenance_when_empty(self):
        c = Claim(claim_text="A claim")
        d = c.to_dict("src-001", "https://x.com", "url")
        assert d["provenance"]["source_id"] == "src-001"

    def test_optional_fields(self):
        c = Claim(claim_text="A claim", suggested_note_id="clm-001", notes="A note")
        d = c.to_dict("src-001", "ref", "url")
        assert d["suggested_note_id"] == "clm-001"
        assert d["notes"] == "A note"

    def test_optional_fields_omitted_when_none(self):
        c = Claim(claim_text="A claim")
        d = c.to_dict("src-001", "ref", "url")
        assert "suggested_note_id" not in d
        assert "notes" not in d


# ─── Bundle construction ──────────────────────────────────────────────────

class TestBuildBundle:

    def test_required_keys_present(self):
        source = _url_source()
        result = ExtractionResult(gist="A gist", claims=[Claim(claim_text="A claim")])
        bundle = _build_bundle(source, result, run_id="run-1", source_id="src-1")
        for key in ("run_id", "source_id", "created_at", "gist",
                     "bullets", "claims", "entities", "definitions", "warnings"):
            assert key in bundle, f"Missing key: {key}"

    def test_validates_against_schema(self):
        source = _url_source()
        result = ExtractionResult(gist="A gist", claims=[Claim(claim_text="A claim")])
        bundle = _build_bundle(source, result, run_id="run-1", source_id="src-1")
        errors = validate_extraction_bundle(bundle)
        assert errors == [], f"Schema errors: {errors}"

    def test_empty_claims_has_warning(self):
        source = _url_source()
        result = ExtractionResult(gist="A gist", claims=[])
        bundle = _build_bundle(source, result, run_id="run-1", source_id="src-1")
        warning_codes = [w["code"] for w in bundle["warnings"]]
        assert WARN_NO_CLAIMS_EXTRACTED in warning_codes

    def test_auto_generates_run_id(self):
        source = _url_source()
        result = ExtractionResult(gist="A gist")
        bundle = _build_bundle(source, result)
        assert bundle["run_id"]  # Non-empty

    def test_uses_source_ref_as_default_source_id(self):
        source = _url_source()
        result = ExtractionResult(gist="A gist")
        bundle = _build_bundle(source, result)
        assert bundle["source_id"] == source.source_ref


# ─── AC-EXT-001-1: Successful extraction with claims ──────────────────────

class TestExtractSuccess:
    """AC-EXT-001-1: For sources with extractable assertions, claims >= 1."""

    def test_produces_bundle(self):
        source = _url_source()
        bundle, env = extract(source, run_id="test-run")
        assert bundle is not None
        assert env.ok is True

    def test_claims_extracted(self):
        source = _url_source()
        bundle, env = extract(source, run_id="test-run")
        assert bundle is not None
        assert len(bundle["claims"]) >= 1

    def test_gist_present(self):
        source = _url_source()
        bundle, _ = extract(source, run_id="test-run")
        assert bundle is not None
        assert bundle["gist"]

    def test_bullets_present(self):
        source = _url_source()
        bundle, _ = extract(source, run_id="test-run")
        assert bundle is not None
        assert isinstance(bundle["bullets"], list)

    def test_envelope_has_stage_name(self):
        source = _url_source()
        _, env = extract(source, run_id="test-run")
        assert env.command == STAGE_NAME

    def test_envelope_data_keys(self):
        source = _url_source()
        _, env = extract(source, run_id="test-run")
        assert "run_id" in env.data
        assert "source_id" in env.data
        assert "claims_count" in env.data

    def test_bundle_validates_schema(self):
        source = _url_source()
        bundle, _ = extract(source, run_id="test-run")
        assert bundle is not None
        errors = validate_extraction_bundle(bundle)
        assert errors == [], f"Schema errors: {errors}"


# ─── AC-EXT-001-2: Zero claims → warning ──────────────────────────────────

class TestExtractZeroClaims:
    """AC-EXT-001-2: Zero claims → WARN_NO_CLAIMS_EXTRACTED."""

    def test_warning_present(self):
        source = _url_source(text=EMPTY_CLAIMS_TEXT)
        bundle, env = extract(source, run_id="test-run")
        assert bundle is not None
        warning_codes = [w["code"] for w in bundle["warnings"]]
        assert WARN_NO_CLAIMS_EXTRACTED in warning_codes

    def test_envelope_has_warning(self):
        source = _url_source(text=EMPTY_CLAIMS_TEXT)
        _, env = extract(source, run_id="test-run")
        warning_codes = [w.code for w in env.warnings]
        assert WARN_NO_CLAIMS_EXTRACTED in warning_codes

    def test_still_has_gist(self):
        source = _url_source(text=EMPTY_CLAIMS_TEXT)
        bundle, _ = extract(source, run_id="test-run")
        assert bundle is not None
        assert bundle["gist"]

    def test_bundle_still_valid(self):
        source = _url_source(text=EMPTY_CLAIMS_TEXT)
        bundle, _ = extract(source, run_id="test-run")
        assert bundle is not None
        errors = validate_extraction_bundle(bundle)
        assert errors == []


# ─── AC-SCH-008-1: Bundle written to Inbox/Sources/ ──────────────────────

class TestBundleWriteToDisk:
    """AC-SCH-008-1: Bundle YAML exists under Inbox/Sources/."""

    def test_writes_yaml_file(self, tmp_path: Path):
        source = _url_source()
        bundle, env = extract(source, vault_root=tmp_path, run_id="test-run")
        assert bundle is not None
        assert env.ok is True
        assert "artifact_path" in env.data
        artifact = tmp_path / env.data["artifact_path"]
        assert artifact.exists()

    def test_yaml_parses_back(self, tmp_path: Path):
        source = _url_source()
        bundle, env = extract(source, vault_root=tmp_path, run_id="test-run")
        assert bundle is not None
        artifact = tmp_path / env.data["artifact_path"]
        loaded = yaml.safe_load(artifact.read_text())
        assert loaded["run_id"] == bundle["run_id"]
        assert loaded["gist"] == bundle["gist"]

    def test_written_bundle_validates(self, tmp_path: Path):
        source = _url_source()
        _, env = extract(source, vault_root=tmp_path, run_id="test-run")
        artifact = tmp_path / env.data["artifact_path"]
        loaded = yaml.safe_load(artifact.read_text())
        errors = validate_extraction_bundle(loaded)
        assert errors == [], f"Schema errors: {errors}"

    def test_inbox_sources_dir_created(self, tmp_path: Path):
        source = _url_source()
        extract(source, vault_root=tmp_path, run_id="test-run")
        assert (tmp_path / "Inbox" / "Sources").is_dir()

    def test_artifact_path_is_vault_relative(self, tmp_path: Path):
        source = _url_source()
        _, env = extract(source, vault_root=tmp_path, run_id="test-run")
        assert env.data["artifact_path"].startswith("Inbox/Sources/")


# ─── Error paths ──────────────────────────────────────────────────────────

class TestExtractErrors:

    def test_empty_text_error(self):
        source = NormalizedSource(
            normalized_text="",
            normalized_locator="test",
            source_kind="url",
            source_ref="test",
        )
        bundle, env = extract(source)
        assert bundle is None
        assert env.ok is False
        assert env.errors[0].code == ERR_EXTRACTION_FAILED
        assert env.errors[0].stage == STAGE_NAME

    def test_error_is_retryable_false_for_empty(self):
        source = NormalizedSource(
            normalized_text="",
            normalized_locator="test",
            source_kind="url",
            source_ref="test",
        )
        _, env = extract(source)
        assert env.errors[0].retryable is False


# ─── Source kind handling ─────────────────────────────────────────────────

class TestSourceKindHandling:

    def test_url_source_locator(self):
        source = _url_source()
        bundle, _ = extract(source, run_id="run-1")
        assert bundle is not None
        if bundle["claims"]:
            claim = bundle["claims"][0]
            loc = claim["provenance"]["locator"]
            assert "url" in loc
            assert "snippet_hash" in loc

    def test_pdf_source_locator(self):
        source = _pdf_source()
        bundle, _ = extract(source, run_id="run-1")
        assert bundle is not None
        if bundle["claims"]:
            claim = bundle["claims"][0]
            loc = claim["provenance"]["locator"]
            assert "pdf_ref" in loc
            assert "page" in loc

    def test_text_bundle_locator(self):
        source = _text_bundle_source()
        bundle, _ = extract(source, run_id="run-1")
        assert bundle is not None
        if bundle["claims"]:
            claim = bundle["claims"][0]
            loc = claim["provenance"]["locator"]
            assert "raw_locator" in loc


# ─── Determinism ──────────────────────────────────────────────────────────

class TestDeterminism:

    def test_same_input_same_claim_keys(self):
        source = _url_source()
        b1, _ = extract(source, run_id="run-1", source_id="src-1")
        b2, _ = extract(source, run_id="run-1", source_id="src-1")
        assert b1 is not None and b2 is not None
        keys1 = [c["extracted_claim_key"] for c in b1["claims"]]
        keys2 = [c["extracted_claim_key"] for c in b2["claims"]]
        assert keys1 == keys2

    def test_claim_key_format(self):
        source = _url_source()
        bundle, _ = extract(source, run_id="run-1")
        assert bundle is not None
        for claim in bundle["claims"]:
            key = claim["extracted_claim_key"]
            assert key.startswith("h-")
            assert len(key) == 14


# ─── No vault_root (in-memory only) ───────────────────────────────────────

class TestInMemoryOnly:

    def test_no_artifact_path_without_vault(self):
        source = _url_source()
        _, env = extract(source, run_id="test-run")
        assert "artifact_path" not in env.data

    def test_still_returns_bundle(self):
        source = _url_source()
        bundle, env = extract(source, run_id="test-run")
        assert bundle is not None
        assert env.ok is True
