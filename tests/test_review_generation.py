"""
Tests for mycelium.review_generation module (REV-001).

Verifies:
- AC-REV-001-1: Ingestion with >=1 new claim produces >=1 queue item
  with item_type=claim_note, proposed_action=promote_to_canon.
- AC-REV-001-2: Queue items include checks.provenance_present for claims.
"""

from __future__ import annotations

from typing import Any

import pytest

from mycelium.delta_report import build_delta_report
from mycelium.review_generation import generate_queue_items
from mycelium.review_queue import validate_queue_item


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _report_with_new_claims(n: int = 2) -> dict[str, Any]:
    """Build a Delta Report with N NEW claims."""
    new_records = [
        {
            "extracted_claim_key": f"h-{i:012x}",
            "match_class": "NEW",
            "similarity": 0.0,
            "existing_claim_id": None,
        }
        for i in range(n)
    ]
    return build_delta_report(
        run_id="run-new",
        source_id="src-new",
        normalized_locator="example.com/new",
        fingerprint="sha256:" + "a" * 64,
        match_groups={
            "EXACT": [],
            "NEAR_DUPLICATE": [],
            "SUPPORTING": [],
            "CONTRADICTING": [],
            "NEW": new_records,
        },
        created_at="2026-03-01T00:00:00Z",
    )


def _report_with_contradicting() -> dict[str, Any]:
    """Build a Delta Report with a CONTRADICTING claim."""
    return build_delta_report(
        run_id="run-contra",
        source_id="src-contra",
        normalized_locator="example.com/contra",
        fingerprint="sha256:" + "b" * 64,
        match_groups={
            "EXACT": [],
            "NEAR_DUPLICATE": [],
            "SUPPORTING": [],
            "CONTRADICTING": [{
                "extracted_claim_key": "h-contra000001",
                "match_class": "CONTRADICTING",
                "similarity": 0.45,
                "existing_claim_id": "existing-claim-1",
            }],
            "NEW": [{
                "extracted_claim_key": "h-new000000001",
                "match_class": "NEW",
                "similarity": 0.0,
                "existing_claim_id": None,
            }],
        },
        conflicts=[{
            "new_extracted_claim_key": "h-contra000001",
            "existing_claim_id": "existing-claim-1",
            "evidence": {"reason": "test"},
        }],
        created_at="2026-03-01T00:00:00Z",
    )


def _report_overlap_only() -> dict[str, Any]:
    """Build a Delta Report with only EXACT matches (no canonical impact)."""
    return build_delta_report(
        run_id="run-overlap",
        source_id="src-overlap",
        normalized_locator="example.com/overlap",
        fingerprint="sha256:" + "c" * 64,
        match_groups={
            "EXACT": [{
                "extracted_claim_key": "h-exact0000001",
                "match_class": "EXACT",
                "similarity": 1.0,
                "existing_claim_id": "existing-1",
            }],
            "NEAR_DUPLICATE": [],
            "SUPPORTING": [],
            "CONTRADICTING": [],
            "NEW": [],
        },
        created_at="2026-03-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenerateQueueItems:

    # AC-REV-001-1: NEW claims produce claim_note queue items
    def test_new_claims_produce_queue_items(self):
        report = _report_with_new_claims(2)
        items = generate_queue_items(report)
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        assert len(claim_items) >= 1

    def test_claim_items_have_promote_action(self):
        report = _report_with_new_claims(2)
        items = generate_queue_items(report)
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        for item in claim_items:
            assert item["proposed_action"] == "promote_to_canon"

    def test_one_queue_item_per_new_claim(self):
        report = _report_with_new_claims(3)
        items = generate_queue_items(report)
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        # 3 NEW claims should produce 3 claim queue items
        assert len(claim_items) == 3

    # AC-REV-001-2: checks include provenance_present
    def test_claim_items_have_provenance_check(self):
        report = _report_with_new_claims()
        items = generate_queue_items(report)
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        for item in claim_items:
            assert "provenance_present" in item["checks"]
            assert item["checks"]["provenance_present"] is True

    def test_claim_items_include_match_class(self):
        report = _report_with_new_claims()
        items = generate_queue_items(report)
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        for item in claim_items:
            assert item["checks"]["match_class"] == "NEW"

    # Contradicting claims
    def test_contradicting_claims_produce_queue_items(self):
        report = _report_with_contradicting()
        items = generate_queue_items(report)
        contra_items = [
            i for i in items
            if i["item_type"] == "claim_note"
            and i["checks"].get("match_class") == "CONTRADICTING"
        ]
        assert len(contra_items) == 1

    def test_contradicting_items_require_human_review(self):
        report = _report_with_contradicting()
        items = generate_queue_items(report)
        contra_items = [
            i for i in items
            if i["checks"].get("match_class") == "CONTRADICTING"
        ]
        for item in contra_items:
            assert item["checks"].get("requires_human_review") is True

    # Source note queue item
    def test_source_note_created_when_new_claims(self):
        report = _report_with_new_claims()
        items = generate_queue_items(report)
        source_items = [i for i in items if i["item_type"] == "source_note"]
        assert len(source_items) == 1
        assert source_items[0]["proposed_action"] == "create"

    def test_source_note_has_claim_counts(self):
        report = _report_with_new_claims(3)
        items = generate_queue_items(report)
        source_items = [i for i in items if i["item_type"] == "source_note"]
        assert source_items[0]["checks"]["new_claim_count"] == 3

    # Overlap-only (EXACT → provenance-attachment items, AC-4)
    def test_overlap_produces_provenance_items(self):
        report = _report_overlap_only()
        items = generate_queue_items(report)
        assert len(items) == 1
        assert items[0]["item_type"] == "claim_note"
        assert items[0]["checks"]["match_class"] == "EXACT"
        assert items[0]["checks"]["provenance_present"] is True

    # All items are pending_review
    def test_all_items_pending_review(self):
        report = _report_with_new_claims()
        items = generate_queue_items(report)
        for item in items:
            assert item["status"] == "pending_review"

    # All items have valid run_id
    def test_all_items_have_run_id(self):
        report = _report_with_new_claims()
        items = generate_queue_items(report)
        for item in items:
            assert item["run_id"] == "run-new"

    # All items pass schema validation
    def test_all_items_validate(self):
        report = _report_with_contradicting()
        items = generate_queue_items(report)
        for item in items:
            errors = validate_queue_item(item)
            assert errors == [], f"Item {item['queue_id']} failed validation: {errors}"

    # Unique queue_ids
    def test_unique_queue_ids(self):
        report = _report_with_new_claims(5)
        items = generate_queue_items(report)
        ids = [i["queue_id"] for i in items]
        assert len(ids) == len(set(ids)), "Queue IDs must be unique"

    # Custom source_note_path
    def test_custom_source_note_path(self):
        report = _report_with_new_claims()
        items = generate_queue_items(
            report,
            source_note_path="Inbox/Sources/custom-note.md",
        )
        source_items = [i for i in items if i["item_type"] == "source_note"]
        assert source_items[0]["target_path"] == "Inbox/Sources/custom-note.md"

    # Empty report
    def test_empty_report_no_items(self):
        report = build_delta_report(
            run_id="run-empty",
            source_id="src-empty",
            normalized_locator="example.com/empty",
            fingerprint="sha256:" + "d" * 64,
            created_at="2026-03-01T00:00:00Z",
        )
        items = generate_queue_items(report)
        assert len(items) == 0
