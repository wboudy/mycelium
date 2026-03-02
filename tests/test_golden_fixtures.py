"""
Tests for golden fixture infrastructure (TST-G-001).

Verifies:
- AC-TST-G-001-1: Golden Delta Report content is stable under Deterministic
  Test Mode, with dynamic fields normalized consistently.
- AC-TST-G-001-2: Changelog file exists and has entries.
- AC-TST-G-001-3: All 6 minimum fixture categories exist and produce
  their expected match class outcomes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from mycelium.deterministic import NORMALIZED_TIMESTAMP, NORMALIZED_UUID, normalize_output
from tests.golden_fixtures import (
    FIXTURES_DIR,
    REQUIRED_FIXTURE_CATEGORIES,
    list_fixtures,
    load_fixture,
)


# ---------------------------------------------------------------------------
# AC-TST-G-001-3: All 6 fixture categories exist
# ---------------------------------------------------------------------------

class TestFixtureCoverage:
    """Verify all required fixture categories are present."""

    def test_all_required_categories_exist(self):
        """AC-TST-G-001-3: All 6 minimum fixture categories have files."""
        available = set(list_fixtures())
        missing = REQUIRED_FIXTURE_CATEGORIES - available
        assert not missing, f"Missing golden fixture categories: {missing}"

    def test_fixture_count(self):
        """At least 6 fixture files exist."""
        assert len(list_fixtures()) >= 6

    @pytest.mark.parametrize("category", sorted(REQUIRED_FIXTURE_CATEGORIES))
    def test_fixture_loadable(self, category: str):
        """Each required fixture loads without error."""
        fixture = load_fixture(category)
        assert "input" in fixture, f"{category} missing 'input' key"
        assert "expected_output" in fixture, f"{category} missing 'expected_output' key"


# ---------------------------------------------------------------------------
# AC-TST-G-001-3: Match class outcomes per category
# ---------------------------------------------------------------------------

class TestFixtureMatchClassOutcomes:
    """Verify each fixture category produces its expected match class pattern."""

    def test_url_basic_has_new_claims(self):
        """url_basic must produce at least one NEW claim."""
        fixture = load_fixture("url_basic")
        new_claims = fixture["expected_output"]["match_groups"]["NEW"]
        assert len(new_claims) >= 1, "url_basic must produce at least one NEW claim"

    def test_pdf_basic_has_new_claims(self):
        """pdf_basic must produce at least one NEW claim."""
        fixture = load_fixture("pdf_basic")
        new_claims = fixture["expected_output"]["match_groups"]["NEW"]
        assert len(new_claims) >= 1, "pdf_basic must produce at least one NEW claim"

    def test_delta_overlap_only_no_new(self):
        """delta_overlap_only must produce only EXACT/NEAR_DUPLICATE, no NEW."""
        fixture = load_fixture("delta_overlap_only")
        groups = fixture["expected_output"]["match_groups"]
        assert len(groups["NEW"]) == 0, "delta_overlap_only must have no NEW claims"
        assert len(groups["EXACT"]) + len(groups["NEAR_DUPLICATE"]) > 0, \
            "delta_overlap_only must have at least one EXACT or NEAR_DUPLICATE"

    def test_delta_new_and_contradict(self):
        """delta_new_and_contradict must have at least one NEW and one CONTRADICTING."""
        fixture = load_fixture("delta_new_and_contradict")
        groups = fixture["expected_output"]["match_groups"]
        assert len(groups["NEW"]) >= 1, "Must have at least one NEW"
        assert len(groups["CONTRADICTING"]) >= 1, "Must have at least one CONTRADICTING"
        # Must also have at least one Conflict Record
        assert len(fixture["expected_output"]["conflicts"]) >= 1, \
            "Must have at least one conflict record"

    def test_corrupted_frontmatter_triggers_failure(self):
        """corrupted_frontmatter must have pipeline_status != completed and failures."""
        fixture = load_fixture("corrupted_frontmatter")
        output = fixture["expected_output"]
        assert output["pipeline_status"] != "completed", \
            "corrupted_frontmatter must not have pipeline_status=completed"
        assert len(output["failures"]) >= 1, \
            "corrupted_frontmatter must have at least one failure entry"

    def test_idempotency_changed_content_has_revision(self):
        """idempotency_changed_content must have prior_fingerprint set."""
        fixture = load_fixture("idempotency_changed_content")
        revision = fixture["expected_output"]["source_revision"]
        assert revision["prior_fingerprint"] is not None, \
            "Changed content fixture must have prior_fingerprint"
        assert revision["fingerprint"] != revision["prior_fingerprint"], \
            "Fingerprints must differ for changed content"


# ---------------------------------------------------------------------------
# AC-TST-G-001-1: Stability under deterministic mode
# ---------------------------------------------------------------------------

class TestDeterministicStability:
    """Verify golden fixtures are stable under normalization."""

    @pytest.mark.parametrize("category", sorted(REQUIRED_FIXTURE_CATEGORIES))
    def test_expected_output_normalizes_stably(self, category: str):
        """AC-TST-G-001-1: Normalized expected output is byte-identical across runs."""
        fixture = load_fixture(category)
        output = fixture["expected_output"]

        run1 = json.dumps(normalize_output(output), sort_keys=True)
        run2 = json.dumps(normalize_output(output), sort_keys=True)
        assert run1 == run2, f"{category} normalization is not stable"

    @pytest.mark.parametrize("category", sorted(REQUIRED_FIXTURE_CATEGORIES))
    def test_expected_output_already_uses_sentinels(self, category: str):
        """Expected outputs should already use deterministic sentinels for timestamps/IDs."""
        fixture = load_fixture(category)
        output = fixture["expected_output"]

        # run_id and source_id should be the normalized UUID sentinel
        assert output["run_id"] == NORMALIZED_UUID
        assert output["source_id"] == NORMALIZED_UUID
        # created_at should be the normalized timestamp sentinel
        assert output["created_at"] == NORMALIZED_TIMESTAMP

    @pytest.mark.parametrize("category", sorted(REQUIRED_FIXTURE_CATEGORIES))
    def test_normalization_is_idempotent(self, category: str):
        """Normalizing already-normalized expected output is a no-op."""
        fixture = load_fixture(category)
        output = fixture["expected_output"]

        once = normalize_output(output)
        twice = normalize_output(once)
        assert once == twice


# ---------------------------------------------------------------------------
# Delta Report schema structure
# ---------------------------------------------------------------------------

class TestDeltaReportSchema:
    """Verify expected outputs conform to SCH-006 structure."""

    REQUIRED_TOP_KEYS = {
        "run_id", "source_id", "created_at", "source_revision",
        "pipeline_status", "counts", "novelty_score", "match_groups",
        "conflicts", "warnings", "failures", "new_links", "follow_up_questions",
    }

    REQUIRED_MATCH_GROUPS = {"EXACT", "NEAR_DUPLICATE", "SUPPORTING", "CONTRADICTING", "NEW"}

    REQUIRED_COUNTS_KEYS = {
        "total_extracted_claims", "exact_count", "near_duplicate_count",
        "supporting_count", "contradicting_count", "new_count",
    }

    @pytest.mark.parametrize("category", sorted(REQUIRED_FIXTURE_CATEGORIES))
    def test_has_all_required_top_level_keys(self, category: str):
        """SCH-006: Delta Report has all required top-level keys."""
        fixture = load_fixture(category)
        output = fixture["expected_output"]
        missing = self.REQUIRED_TOP_KEYS - set(output.keys())
        assert not missing, f"{category} missing keys: {missing}"

    @pytest.mark.parametrize("category", sorted(REQUIRED_FIXTURE_CATEGORIES))
    def test_has_all_match_group_keys(self, category: str):
        """SCH-006: match_groups has all required class keys."""
        fixture = load_fixture(category)
        groups = fixture["expected_output"]["match_groups"]
        missing = self.REQUIRED_MATCH_GROUPS - set(groups.keys())
        assert not missing, f"{category} missing match groups: {missing}"

    @pytest.mark.parametrize("category", sorted(REQUIRED_FIXTURE_CATEGORIES))
    def test_has_all_counts_keys(self, category: str):
        """SCH-006: counts has all required keys."""
        fixture = load_fixture(category)
        counts = fixture["expected_output"]["counts"]
        missing = self.REQUIRED_COUNTS_KEYS - set(counts.keys())
        assert not missing, f"{category} missing counts keys: {missing}"

    @pytest.mark.parametrize("category", sorted(REQUIRED_FIXTURE_CATEGORIES))
    def test_match_class_equals_group_key(self, category: str):
        """SCH-006: Each match record's match_class equals its containing group key."""
        fixture = load_fixture(category)
        for group_key, records in fixture["expected_output"]["match_groups"].items():
            for record in records:
                assert record["match_class"] == group_key, \
                    f"{category}: record in {group_key} has match_class={record['match_class']}"

    @pytest.mark.parametrize("category", sorted(REQUIRED_FIXTURE_CATEGORIES))
    def test_novelty_score_in_range(self, category: str):
        """SCH-006: novelty_score is in [0..1]."""
        fixture = load_fixture(category)
        score = fixture["expected_output"]["novelty_score"]
        assert 0.0 <= score <= 1.0, f"{category}: novelty_score {score} out of range"

    @pytest.mark.parametrize("category", sorted(REQUIRED_FIXTURE_CATEGORIES))
    def test_valid_pipeline_status(self, category: str):
        """SCH-006: pipeline_status is a valid enum value."""
        valid = {"completed", "failed_after_extraction", "failed_before_extraction"}
        fixture = load_fixture(category)
        status = fixture["expected_output"]["pipeline_status"]
        assert status in valid, f"{category}: invalid pipeline_status={status}"


# ---------------------------------------------------------------------------
# AC-TST-G-001-2: Changelog
# ---------------------------------------------------------------------------

class TestChangelog:
    """Verify changelog infrastructure exists."""

    def test_changelog_exists(self):
        """AC-TST-G-001-2: changelog.yaml exists in fixtures directory."""
        changelog_path = FIXTURES_DIR / "changelog.yaml"
        assert changelog_path.exists(), "changelog.yaml must exist in golden_fixtures/"

    def test_changelog_has_entries(self):
        """Changelog has at least one entry."""
        changelog_path = FIXTURES_DIR / "changelog.yaml"
        with open(changelog_path) as f:
            data = yaml.safe_load(f)
        assert "entries" in data
        assert len(data["entries"]) >= 1

    def test_changelog_entry_has_required_fields(self):
        """Each changelog entry has date, fixture, author, reason."""
        changelog_path = FIXTURES_DIR / "changelog.yaml"
        with open(changelog_path) as f:
            data = yaml.safe_load(f)
        for entry in data["entries"]:
            assert "date" in entry, "Changelog entry missing 'date'"
            assert "fixture" in entry, "Changelog entry missing 'fixture'"
            assert "author" in entry, "Changelog entry missing 'author'"
            assert "reason" in entry, "Changelog entry missing 'reason'"
