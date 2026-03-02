"""Tests for the Compare (Dedupe) stage (stage 5/7) of the ingestion pipeline.

Validates acceptance criteria from §6.1.1 and §7.2 DED-002:
  AC-1: Each extracted claim gets exactly one MatchRecord with match_class
        in {EXACT, NEAR_DUPLICATE, SUPPORTING, CONTRADICTING, NEW}
        and similarity in [0..1].
  AC-2: Total MatchRecords equals total extracted claims (AC-DED-002-1).
  AC-3: When claim index unavailable, returns ERR_INDEX_UNAVAILABLE.
  AC-4: No writes to Canonical Scope during comparison.
  AC-5: MatchRecords include extracted_claim_key, match_class, similarity,
        and matched_claim_id (when applicable).
"""

from __future__ import annotations

from typing import Any

import pytest

from mycelium.canonicalize import extracted_claim_key
from mycelium.comparator import CompareResult, MatchClass, MatchRecord
from mycelium.delta_report import build_delta_report, validate_delta_report
from mycelium.stages.compare import (
    STAGE_NAME,
    ERR_INDEX_UNAVAILABLE,
    ERR_SCHEMA_VALIDATION,
    WARN_NO_EXISTING_CLAIMS,
    ClaimIndex,
    SimilarityFn,
    compare,
    compare_result_to_match_groups,
    _match_record_to_scm006,
)


# ─── Test fixtures ────────────────────────────────────────────────────────

def _claims(*texts: str) -> list[dict[str, Any]]:
    """Build a list of extraction-bundle-style claim dicts."""
    return [{"claim_text": t, "claim_type": "empirical", "polarity": "supports"} for t in texts]


def _index(*claim_pairs: tuple[str, str]) -> ClaimIndex:
    """Build a ClaimIndex from (id, text) pairs."""
    return ClaimIndex(claims=[{"id": cid, "text": text} for cid, text in claim_pairs])


EMPTY_INDEX = ClaimIndex(claims=[])


# ─── ClaimIndex ────────────────────────────────────────────────────────────

class TestClaimIndex:

    def test_available(self):
        idx = ClaimIndex()
        assert idx.available is True

    def test_len_empty(self):
        idx = ClaimIndex()
        assert len(idx) == 0

    def test_len_with_claims(self):
        idx = _index(("c1", "claim one"), ("c2", "claim two"))
        assert len(idx) == 2


# ─── AC-3: Index unavailable → ERR_INDEX_UNAVAILABLE ──────────────────────

class TestIndexUnavailable:
    """AC-3: When claim index is unavailable, returns ERR_INDEX_UNAVAILABLE."""

    def test_none_index_returns_error(self):
        claims = _claims("Exercise reduces heart disease risk")
        result, env = compare(claims, claim_index=None)
        assert result is None
        assert env.ok is False
        assert env.errors[0].code == ERR_INDEX_UNAVAILABLE
        assert env.errors[0].stage == STAGE_NAME

    def test_error_is_retryable(self):
        claims = _claims("A claim")
        _, env = compare(claims, claim_index=None)
        assert env.errors[0].retryable is True


# ─── AC-2: Total MatchRecords == total extracted claims ────────────────────

class TestTotalMatchRecords:
    """AC-2: Total MatchRecords equals total extracted claims."""

    def test_single_claim(self):
        claims = _claims("Exercise is good for health")
        result, env = compare(claims, EMPTY_INDEX)
        assert result is not None
        assert result.total == 1
        assert env.ok is True

    def test_multiple_claims(self):
        claims = _claims(
            "Exercise reduces heart disease risk",
            "Smoking causes lung cancer",
            "Sleep is important for recovery",
        )
        result, env = compare(claims, EMPTY_INDEX)
        assert result is not None
        assert result.total == 3

    def test_empty_claims(self):
        result, env = compare([], EMPTY_INDEX)
        assert result is not None
        assert result.total == 0
        assert env.ok is True

    def test_total_matches_envelope_data(self):
        claims = _claims("A claim", "Another claim")
        result, env = compare(claims, EMPTY_INDEX)
        assert result is not None
        assert env.data["total_extracted_claims"] == result.total


# ─── AC-1: Each claim gets exactly one MatchRecord ─────────────────────────

class TestOneRecordPerClaim:
    """AC-1: Each extracted claim gets exactly one MatchRecord."""

    def test_all_new_when_empty_index(self):
        claims = _claims("Claim A", "Claim B", "Claim C")
        result, _ = compare(claims, EMPTY_INDEX)
        assert result is not None
        new_records = result.match_groups["NEW"]
        assert len(new_records) == 3

    def test_match_record_has_valid_class(self):
        claims = _claims("Exercise reduces heart disease risk")
        result, _ = compare(claims, EMPTY_INDEX)
        assert result is not None
        for mc_value, records in result.match_groups.items():
            assert mc_value in {mc.value for mc in MatchClass}
            for r in records:
                assert r.match_class.value == mc_value

    def test_match_record_similarity_in_range(self):
        claims = _claims("A claim about something")
        existing = _index(("c1", "A related claim about something"))
        result, _ = compare(claims, existing)
        assert result is not None
        for records in result.match_groups.values():
            for r in records:
                assert 0.0 <= r.similarity <= 1.0


# ─── AC-5: MatchRecord fields ─────────────────────────────────────────────

class TestMatchRecordFields:
    """AC-5: MatchRecords include required fields."""

    def test_has_extracted_claim_key(self):
        claims = _claims("Exercise is beneficial")
        result, _ = compare(claims, EMPTY_INDEX)
        assert result is not None
        for records in result.match_groups.values():
            for r in records:
                assert r.extracted_claim_key
                assert r.extracted_claim_key.startswith("h-")

    def test_claim_key_matches_canonicalize(self):
        text = "Exercise is beneficial for health"
        claims = _claims(text)
        result, _ = compare(claims, EMPTY_INDEX)
        assert result is not None
        record = result.match_groups["NEW"][0]
        assert record.extracted_claim_key == extracted_claim_key(text)

    def test_existing_claim_id_for_match(self):
        claims = _claims("Exercise is good for health")
        existing = _index(("c1", "Exercise is good for health"))
        result, _ = compare(claims, existing)
        assert result is not None
        # Should be EXACT match
        exact = result.match_groups["EXACT"]
        assert len(exact) == 1
        assert exact[0].existing_claim_id == "c1"

    def test_existing_claim_id_none_for_new(self):
        claims = _claims("A completely novel claim")
        result, _ = compare(claims, EMPTY_INDEX)
        assert result is not None
        new_records = result.match_groups["NEW"]
        assert len(new_records) == 1
        assert new_records[0].existing_claim_id is None


# ─── Match classification with existing claims ────────────────────────────

class TestMatchClassification:

    def test_exact_match(self):
        text = "Exercise reduces heart disease risk"
        claims = _claims(text)
        existing = _index(("c1", text))
        result, _ = compare(claims, existing)
        assert result is not None
        assert len(result.match_groups["EXACT"]) == 1
        assert result.match_groups["EXACT"][0].similarity >= 0.97

    def test_new_claim_against_unrelated(self):
        claims = _claims("Quantum computing advances rapidly")
        existing = _index(("c1", "Exercise is beneficial for health"))
        result, _ = compare(claims, existing)
        assert result is not None
        # Should be NEW (very low similarity)
        assert len(result.match_groups["NEW"]) == 1

    def test_custom_similarity_fn(self):
        """Test with a custom similarity function for controlled testing."""
        def fixed_sim(a: str, b: str) -> float:
            return 0.90  # Always returns NEAR_DUPLICATE range

        claims = _claims("Any claim text")
        existing = _index(("c1", "Any existing claim"))
        result, _ = compare(claims, existing, similarity_fn=fixed_sim)
        assert result is not None
        assert len(result.match_groups["NEAR_DUPLICATE"]) == 1

    def test_mixed_classifications(self):
        """Multiple claims get different classifications."""
        def controlled_sim(a: str, b: str) -> float:
            if "exact" in a:
                return 1.0
            if "near" in a:
                return 0.90
            return 0.1

        claims = _claims("exact match claim", "near duplicate claim", "novel claim")
        existing = _index(("c1", "some existing claim"))
        result, _ = compare(claims, existing, similarity_fn=controlled_sim)
        assert result is not None
        assert result.total == 3
        assert len(result.match_groups["EXACT"]) == 1
        assert len(result.match_groups["NEAR_DUPLICATE"]) == 1
        assert len(result.match_groups["NEW"]) == 1


# ─── Envelope structure ───────────────────────────────────────────────────

class TestEnvelopeStructure:

    def test_command_is_stage_name(self):
        claims = _claims("A claim")
        _, env = compare(claims, EMPTY_INDEX)
        assert env.command == STAGE_NAME

    def test_ok_on_success(self):
        claims = _claims("A claim")
        _, env = compare(claims, EMPTY_INDEX)
        assert env.ok is True

    def test_data_has_count_keys(self):
        claims = _claims("A claim", "Another claim")
        _, env = compare(claims, EMPTY_INDEX)
        assert "total_extracted_claims" in env.data
        assert "new_count" in env.data
        assert "exact_count" in env.data
        assert "near_duplicate_count" in env.data
        assert "supporting_count" in env.data
        assert "contradicting_count" in env.data

    def test_counts_sum_to_total(self):
        claims = _claims("A claim", "Another claim", "Third claim")
        _, env = compare(claims, EMPTY_INDEX)
        total = env.data["total_extracted_claims"]
        parts_sum = (
            env.data["exact_count"]
            + env.data["near_duplicate_count"]
            + env.data["supporting_count"]
            + env.data["contradicting_count"]
            + env.data["new_count"]
        )
        assert total == parts_sum

    def test_warning_when_empty_index(self):
        claims = _claims("A claim")
        _, env = compare(claims, EMPTY_INDEX)
        warning_codes = [w.code for w in env.warnings]
        assert WARN_NO_EXISTING_CLAIMS in warning_codes

    def test_no_warning_with_existing_claims(self):
        claims = _claims("A claim")
        idx = _index(("c1", "Some existing claim"))
        _, env = compare(claims, idx)
        warning_codes = [w.code for w in env.warnings]
        assert WARN_NO_EXISTING_CLAIMS not in warning_codes


# ─── Error: empty claim_text ──────────────────────────────────────────────

class TestEmptyClaimText:

    def test_empty_claim_text_error(self):
        claims = [{"claim_text": "", "claim_type": "empirical"}]
        result, env = compare(claims, EMPTY_INDEX)
        assert result is None
        assert env.ok is False
        assert env.errors[0].code == ERR_SCHEMA_VALIDATION

    def test_whitespace_only_claim_text_error(self):
        claims = [{"claim_text": "   ", "claim_type": "empirical"}]
        result, env = compare(claims, EMPTY_INDEX)
        assert result is None
        assert env.ok is False

    def test_missing_claim_text_error(self):
        claims = [{"claim_type": "empirical"}]
        result, env = compare(claims, EMPTY_INDEX)
        assert result is None
        assert env.ok is False


# ─── SCH-006 integration ──────────────────────────────────────────────────

class TestSCH006Integration:
    """Verify CompareResult can feed into Delta Report construction."""

    def test_match_groups_to_scm006(self):
        claims = _claims("A claim", "Another claim")
        result, _ = compare(claims, EMPTY_INDEX)
        assert result is not None
        groups = compare_result_to_match_groups(result)
        # All five keys present
        for mc in MatchClass:
            assert mc.value in groups

    def test_match_records_have_existing_claim_id(self):
        claims = _claims("A claim")
        result, _ = compare(claims, EMPTY_INDEX)
        assert result is not None
        groups = compare_result_to_match_groups(result)
        for group_key, records in groups.items():
            for r in records:
                assert "existing_claim_id" in r  # Always present, even if None

    def test_delta_report_validates(self):
        claims = _claims("Exercise is good for health", "Smoking is bad")
        existing = _index(("c1", "Exercise is good for health"))
        result, _ = compare(claims, existing)
        assert result is not None

        groups = compare_result_to_match_groups(result)
        report = build_delta_report(
            run_id="test-run",
            source_id="src-001",
            normalized_locator="https://example.com",
            fingerprint="sha256:" + "a" * 64,
            match_groups=groups,
        )
        errors = validate_delta_report(report)
        assert errors == [], f"Delta Report validation errors: {errors}"

    def test_delta_report_counts_correct(self):
        def controlled_sim(a: str, b: str) -> float:
            if "exact" in a:
                return 1.0
            return 0.1

        claims = _claims("exact match claim", "novel claim")
        existing = _index(("c1", "some existing claim"))
        result, _ = compare(claims, existing, similarity_fn=controlled_sim)
        assert result is not None

        groups = compare_result_to_match_groups(result)
        report = build_delta_report(
            run_id="test-run",
            source_id="src-001",
            normalized_locator="https://example.com",
            fingerprint="sha256:" + "a" * 64,
            match_groups=groups,
        )
        assert report["counts"]["total_extracted_claims"] == 2
        assert report["counts"]["exact_count"] == 1
        assert report["counts"]["new_count"] == 1


# ─── match_record_to_scm006 ──────────────────────────────────────────────

class TestMatchRecordToSCH006:

    def test_all_required_keys(self):
        record = MatchRecord(
            match_class=MatchClass.NEW,
            similarity=0.0,
            extracted_claim_key="h-abc123def456",
        )
        d = _match_record_to_scm006(record)
        assert "extracted_claim_key" in d
        assert "match_class" in d
        assert "similarity" in d
        assert "existing_claim_id" in d

    def test_existing_claim_id_null_for_new(self):
        record = MatchRecord(
            match_class=MatchClass.NEW,
            similarity=0.0,
            extracted_claim_key="h-abc123def456",
        )
        d = _match_record_to_scm006(record)
        assert d["existing_claim_id"] is None

    def test_existing_claim_id_set_for_exact(self):
        record = MatchRecord(
            match_class=MatchClass.EXACT,
            similarity=1.0,
            extracted_claim_key="h-abc123def456",
            existing_claim_id="c1",
        )
        d = _match_record_to_scm006(record)
        assert d["existing_claim_id"] == "c1"

    def test_match_class_is_string(self):
        record = MatchRecord(
            match_class=MatchClass.NEAR_DUPLICATE,
            similarity=0.90,
            extracted_claim_key="h-abc123def456",
        )
        d = _match_record_to_scm006(record)
        assert d["match_class"] == "NEAR_DUPLICATE"


# ─── Determinism ──────────────────────────────────────────────────────────

class TestDeterminism:

    def test_same_input_same_output(self):
        claims = _claims("Exercise reduces heart disease", "Sleep improves recovery")
        existing = _index(("c1", "Exercise reduces cardiovascular disease"))
        r1, _ = compare(claims, existing)
        r2, _ = compare(claims, existing)
        assert r1 is not None and r2 is not None
        d1 = r1.to_dict()
        d2 = r2.to_dict()
        assert d1["match_groups"] == d2["match_groups"]
        assert d1["counts"] == d2["counts"]

    def test_claim_keys_deterministic(self):
        claims = _claims("The same claim text")
        r1, _ = compare(claims, EMPTY_INDEX)
        r2, _ = compare(claims, EMPTY_INDEX)
        assert r1 is not None and r2 is not None
        k1 = r1.match_groups["NEW"][0].extracted_claim_key
        k2 = r2.match_groups["NEW"][0].extracted_claim_key
        assert k1 == k2


# ─── AC-4: No Canonical Scope writes ──────────────────────────────────────

class TestNoCanonicalWrites:
    """AC-4: Compare stage does not write to Canonical Scope."""

    def test_returns_data_not_files(self):
        """Compare only returns in-memory results, no file I/O."""
        claims = _claims("A claim")
        result, env = compare(claims, EMPTY_INDEX)
        assert result is not None
        assert env.ok is True
        # No artifact_path or file references in envelope
        assert "artifact_path" not in env.data
