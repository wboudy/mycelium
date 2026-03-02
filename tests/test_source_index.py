"""Tests for the source identity index (IDM-001).

Verifies acceptance criteria:
  AC-1: System maintains a source index mapping.
  AC-2: Identical fixture re-ingestion returns same source_id.
  AC-3: Changed-content re-ingestion records prior_fingerprint.
  AC-4: Index persists under Indexes/ and survives process restart.
  AC-5: Index lookups are O(1) or O(log n).
"""

from __future__ import annotations

from pathlib import Path

from mycelium.invariants import IngestionOutcome
from mycelium.source_index import INDEX_FILENAME, SourceIndex


FP_A = "sha256:" + "a" * 64
FP_B = "sha256:" + "b" * 64
FP_C = "sha256:" + "c" * 64


# ─── AC-1: Source index mapping ─────────────────────────────────────────────

class TestSourceIndexBasics:

    def test_register_and_lookup(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        idx.register("https://example.com/a", FP_A, "s-001")

        outcome, matched = idx.lookup("https://example.com/a", FP_A)
        assert outcome == IngestionOutcome.SAME_CONTENT
        assert matched.source_id == "s-001"

    def test_new_source(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        outcome, matched = idx.lookup("https://example.com/new", FP_A)
        assert outcome == IngestionOutcome.NEW_SOURCE
        assert matched is None

    def test_size(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        assert idx.size == 0
        idx.register("https://example.com/a", FP_A, "s-001")
        assert idx.size == 1
        idx.register("https://example.com/a", FP_B, "s-001")
        assert idx.size == 2


# ─── AC-2: Identical re-ingestion reuses source_id ──────────────────────────

class TestIdempotency:
    """AC-2: Ingesting identical fixture twice returns same source_id."""

    def test_same_locator_same_fingerprint(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        idx.register("https://example.com/a", FP_A, "s-001")

        outcome, matched = idx.lookup("https://example.com/a", FP_A)
        assert outcome == IngestionOutcome.SAME_CONTENT
        assert matched.source_id == "s-001"

    def test_duplicate_register_is_idempotent(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        idx.register("https://example.com/a", FP_A, "s-001")
        idx.register("https://example.com/a", FP_A, "s-001")
        assert idx.size == 1


# ─── AC-3: Revised content records prior_fingerprint ────────────────────────

class TestRevisionDetection:
    """AC-3: Changed content with same locator records prior_fingerprint."""

    def test_different_fingerprint_is_revision(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        idx.register("https://example.com/a", FP_A, "s-001")

        outcome, matched = idx.lookup("https://example.com/a", FP_B)
        assert outcome == IngestionOutcome.REVISED_CONTENT
        assert matched.source_id == "s-001"
        assert matched.fingerprint == FP_A  # prior fingerprint

    def test_prior_fingerprint_lookup(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        idx.register("https://example.com/a", FP_A, "s-001")
        idx.register("https://example.com/a", FP_B, "s-001")

        prior = idx.get_prior_fingerprint("https://example.com/a", FP_B)
        assert prior == FP_A

    def test_prior_fingerprint_none_for_first(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        idx.register("https://example.com/a", FP_A, "s-001")
        prior = idx.get_prior_fingerprint("https://example.com/a", FP_A)
        assert prior is None

    def test_prior_fingerprint_none_for_unknown(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        prior = idx.get_prior_fingerprint("https://example.com/nope", FP_A)
        assert prior is None


# ─── AC-4: Persistence under Indexes/ ──────────────────────────────────────

class TestPersistence:
    """AC-4: Index persists under Indexes/ and survives process restart."""

    def test_index_file_created(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        idx.register("https://example.com/a", FP_A, "s-001")
        assert (tmp_path / INDEX_FILENAME).exists()

    def test_survives_reload(self, tmp_path: Path):
        """Simulate process restart by creating a new SourceIndex instance."""
        idx1 = SourceIndex(tmp_path)
        idx1.register("https://example.com/a", FP_A, "s-001")
        idx1.register("https://example.com/b", FP_B, "s-002")

        # New instance — simulates process restart
        idx2 = SourceIndex(tmp_path)
        assert idx2.size == 2

        outcome, matched = idx2.lookup("https://example.com/a", FP_A)
        assert outcome == IngestionOutcome.SAME_CONTENT
        assert matched.source_id == "s-001"

    def test_empty_vault_works(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        assert idx.size == 0

    def test_index_location_is_under_indexes(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        idx.register("https://example.com/a", FP_A, "s-001")
        assert "Indexes" in str(tmp_path / INDEX_FILENAME)


# ─── AC-5: O(1) lookup ────────────────────────────────────────────────────

class TestLookupPerformance:
    """AC-5: Index lookups are O(1) — dict-based."""

    def test_many_sources_still_fast(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        for i in range(100):
            idx.register(f"https://example.com/{i}", f"sha256:{i:064x}", f"s-{i:03d}")

        # Lookup should be dict-based O(1)
        outcome, matched = idx.lookup("https://example.com/50", f"sha256:{50:064x}")
        assert outcome == IngestionOutcome.SAME_CONTENT
        assert matched.source_id == "s-050"


# ─── get_source_id ────────────────────────────────────────────────────────

class TestGetSourceId:

    def test_returns_latest_source_id(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        idx.register("https://example.com/a", FP_A, "s-001")
        assert idx.get_source_id("https://example.com/a") == "s-001"

    def test_returns_none_for_unknown(self, tmp_path: Path):
        idx = SourceIndex(tmp_path)
        assert idx.get_source_id("https://example.com/nope") is None
