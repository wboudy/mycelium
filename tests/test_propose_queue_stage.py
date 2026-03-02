"""Tests for the Propose+Queue stage (stage 7/7) of the ingestion pipeline.

Validates acceptance criteria from §4.2.7 SCH-007 and §8.1 REV-001:
  AC-1: NEW claims → claim_note with promote_to_canon.
  AC-2: CONTRADICTING → human-review only, never auto-approved.
  AC-3: [0.70..0.85) similarity → merge/create recommendation.
  AC-4: EXACT → auto-approvable provenance-attachment items.
  AC-5: Queue items include checks with provenance_present.
  AC-6: Written to Inbox/ReviewQueue/.
  AC-7: Queue items conform to SCH-007.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from mycelium.delta_report import MATCH_CLASS_KEYS, build_delta_report
from mycelium.review_queue import validate_queue_item
from mycelium.stages.propose_queue import (
    STAGE_NAME,
    ERR_SCHEMA_VALIDATION,
    WARN_AMBIGUOUS_REQUIRES_REVIEW,
    WARN_CONTRADICTING_REQUIRES_REVIEW,
    WARN_NO_QUEUE_ITEMS,
    propose_queue,
)


# ─── Helpers ──────────────────────────────────────────────────────────────

FP = "sha256:" + "a" * 64


def _delta_with_new(n: int) -> dict[str, Any]:
    """Build a Delta Report with n NEW claims."""
    new_records = [
        {
            "extracted_claim_key": f"h-{i:012d}",
            "match_class": "NEW",
            "similarity": 0.1,
            "existing_claim_id": None,
        }
        for i in range(n)
    ]
    return build_delta_report(
        run_id="run-1",
        source_id="src-1",
        normalized_locator="https://example.com",
        fingerprint=FP,
        match_groups={"NEW": new_records, **{k: [] for k in MATCH_CLASS_KEYS if k != "NEW"}},
    )


def _delta_with_contradicting(n: int) -> dict[str, Any]:
    """Build a Delta Report with n CONTRADICTING claims."""
    records = [
        {
            "extracted_claim_key": f"h-{i:012d}",
            "match_class": "CONTRADICTING",
            "similarity": 0.5,
            "existing_claim_id": f"c-{i}",
        }
        for i in range(n)
    ]
    return build_delta_report(
        run_id="run-1",
        source_id="src-1",
        normalized_locator="https://example.com",
        fingerprint=FP,
        match_groups={"CONTRADICTING": records, **{k: [] for k in MATCH_CLASS_KEYS if k != "CONTRADICTING"}},
    )


def _delta_overlap_only() -> dict[str, Any]:
    """Build a Delta Report with only EXACT matches."""
    records = [
        {
            "extracted_claim_key": "h-000000000001",
            "match_class": "EXACT",
            "similarity": 1.0,
            "existing_claim_id": "c-1",
        },
    ]
    return build_delta_report(
        run_id="run-1",
        source_id="src-1",
        normalized_locator="https://example.com",
        fingerprint=FP,
        match_groups={"EXACT": records, **{k: [] for k in MATCH_CLASS_KEYS if k != "EXACT"}},
    )


def _delta_mixed() -> dict[str, Any]:
    """Build a Delta Report with mixed match classes."""
    return build_delta_report(
        run_id="run-1",
        source_id="src-1",
        normalized_locator="https://example.com",
        fingerprint=FP,
        match_groups={
            "EXACT": [{"extracted_claim_key": "h-000000000001", "match_class": "EXACT", "similarity": 1.0, "existing_claim_id": "c-1"}],
            "NEAR_DUPLICATE": [],
            "SUPPORTING": [],
            "CONTRADICTING": [{"extracted_claim_key": "h-000000000002", "match_class": "CONTRADICTING", "similarity": 0.5, "existing_claim_id": "c-2"}],
            "NEW": [{"extracted_claim_key": "h-000000000003", "match_class": "NEW", "similarity": 0.1, "existing_claim_id": None}],
        },
    )


def _delta_empty() -> dict[str, Any]:
    """Build a Delta Report with no match records."""
    return build_delta_report(
        run_id="run-1",
        source_id="src-1",
        normalized_locator="https://example.com",
        fingerprint=FP,
    )


# ─── AC-1: NEW claims → claim_note with promote_to_canon ──────────────────

class TestNewClaims:
    """AC-1: NEW claims generate claim_note items with promote_to_canon."""

    def test_new_claims_produce_items(self):
        dr = _delta_with_new(3)
        items, env = propose_queue(dr)
        assert items is not None
        assert env.ok is True
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        assert len(claim_items) == 3

    def test_item_type_is_claim_note(self):
        dr = _delta_with_new(1)
        items, _ = propose_queue(dr)
        assert items is not None
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        assert all(i["item_type"] == "claim_note" for i in claim_items)

    def test_proposed_action_is_promote(self):
        dr = _delta_with_new(1)
        items, _ = propose_queue(dr)
        assert items is not None
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        assert all(i["proposed_action"] == "promote_to_canon" for i in claim_items)

    def test_source_note_created_with_new(self):
        dr = _delta_with_new(2)
        items, _ = propose_queue(dr)
        assert items is not None
        source_items = [i for i in items if i["item_type"] == "source_note"]
        assert len(source_items) == 1


# ─── AC-2: CONTRADICTING → human-review only ──────────────────────────────

class TestContradicting:
    """AC-2: CONTRADICTING items require human review."""

    def test_contradicting_produces_items(self):
        dr = _delta_with_contradicting(2)
        items, _ = propose_queue(dr)
        assert items is not None
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        assert len(claim_items) == 2

    def test_contradicting_has_requires_human_review(self):
        dr = _delta_with_contradicting(1)
        items, _ = propose_queue(dr)
        assert items is not None
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        for item in claim_items:
            assert item["checks"].get("requires_human_review") is True

    def test_contradicting_warning(self):
        dr = _delta_with_contradicting(1)
        _, env = propose_queue(dr)
        warning_codes = [w.code for w in env.warnings]
        assert WARN_CONTRADICTING_REQUIRES_REVIEW in warning_codes


# ─── AC-5: Checks include provenance_present ──────────────────────────────

class TestChecks:
    """AC-5: Queue items include provenance_present for claim items."""

    def test_provenance_present_in_new(self):
        dr = _delta_with_new(1)
        items, _ = propose_queue(dr)
        assert items is not None
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        for item in claim_items:
            assert "provenance_present" in item["checks"]

    def test_provenance_present_in_contradicting(self):
        dr = _delta_with_contradicting(1)
        items, _ = propose_queue(dr)
        assert items is not None
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        for item in claim_items:
            assert "provenance_present" in item["checks"]

    def test_match_class_in_checks(self):
        dr = _delta_with_new(1)
        items, _ = propose_queue(dr)
        assert items is not None
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        assert claim_items[0]["checks"]["match_class"] == "NEW"


# ─── AC-7: SCH-007 compliance ─────────────────────────────────────────────

class TestSCH007Compliance:
    """AC-7: All queue items conform to SCH-007."""

    def test_all_items_validate(self):
        dr = _delta_mixed()
        items, _ = propose_queue(dr)
        assert items is not None
        for item in items:
            errors = validate_queue_item(item)
            assert errors == [], f"Item {item.get('queue_id')} failed: {errors}"

    def test_items_have_required_keys(self):
        dr = _delta_with_new(1)
        items, _ = propose_queue(dr)
        assert items is not None
        for item in items:
            assert "queue_id" in item
            assert "run_id" in item
            assert "item_type" in item
            assert "target_path" in item
            assert "proposed_action" in item
            assert "status" in item
            assert "created_at" in item
            assert "checks" in item

    def test_status_is_pending_review(self):
        dr = _delta_with_new(1)
        items, _ = propose_queue(dr)
        assert items is not None
        for item in items:
            assert item["status"] == "pending_review"

    def test_unique_queue_ids(self):
        dr = _delta_with_new(5)
        items, _ = propose_queue(dr)
        assert items is not None
        ids = [i["queue_id"] for i in items]
        assert len(ids) == len(set(ids))


# ─── AC-6: Written to Inbox/ReviewQueue/ ──────────────────────────────────

class TestWriteToDisk:
    """AC-6: Queue items written to Inbox/ReviewQueue/."""

    def test_writes_yaml_files(self, tmp_path: Path):
        dr = _delta_with_new(2)
        items, env = propose_queue(dr, vault_root=tmp_path)
        assert items is not None
        assert env.ok is True
        assert "artifact_paths" in env.data
        for path in env.data["artifact_paths"]:
            assert (tmp_path / path).exists()

    def test_yaml_roundtrips(self, tmp_path: Path):
        dr = _delta_with_new(1)
        items, env = propose_queue(dr, vault_root=tmp_path)
        assert items is not None
        artifact = tmp_path / env.data["artifact_paths"][0]
        loaded = yaml.safe_load(artifact.read_text())
        assert loaded["queue_id"] == items[0]["queue_id"]

    def test_written_items_validate(self, tmp_path: Path):
        dr = _delta_mixed()
        items, env = propose_queue(dr, vault_root=tmp_path)
        assert items is not None
        for path in env.data["artifact_paths"]:
            loaded = yaml.safe_load((tmp_path / path).read_text())
            errors = validate_queue_item(loaded)
            assert errors == [], f"Written item failed: {errors}"

    def test_inbox_reviewqueue_dir_created(self, tmp_path: Path):
        dr = _delta_with_new(1)
        propose_queue(dr, vault_root=tmp_path)
        assert (tmp_path / "Inbox" / "ReviewQueue").is_dir()

    def test_artifact_paths_vault_relative(self, tmp_path: Path):
        dr = _delta_with_new(1)
        _, env = propose_queue(dr, vault_root=tmp_path)
        for path in env.data["artifact_paths"]:
            assert path.startswith("Inbox/ReviewQueue/")


# ─── Overlap-only (no queue items) ────────────────────────────────────────

class TestOverlapOnly:
    """Overlap-only Delta Reports produce provenance-attachment items (AC-4)."""

    def test_exact_only_produces_provenance_items(self):
        dr = _delta_overlap_only()
        items, env = propose_queue(dr)
        assert items is not None
        # EXACT matches produce auto-approvable provenance-attachment items (AC-4)
        assert len(items) == 1
        assert items[0]["item_type"] == "claim_note"
        assert items[0]["checks"]["match_class"] == "EXACT"
        assert env.ok is True

    def test_exact_only_no_source_note(self):
        """EXACT-only doesn't generate a source_note (only NEW/CONTRADICTING do)."""
        dr = _delta_overlap_only()
        items, _ = propose_queue(dr)
        assert items is not None
        source_items = [i for i in items if i["item_type"] == "source_note"]
        assert len(source_items) == 0

    def test_empty_delta_no_items(self):
        dr = _delta_empty()
        items, env = propose_queue(dr)
        assert items is not None
        assert len(items) == 0


# ─── Envelope structure ───────────────────────────────────────────────────

class TestEnvelopeStructure:

    def test_command_is_stage_name(self):
        dr = _delta_with_new(1)
        _, env = propose_queue(dr)
        assert env.command == STAGE_NAME

    def test_envelope_data_keys(self):
        dr = _delta_with_new(2)
        _, env = propose_queue(dr)
        assert "run_id" in env.data
        assert "queue_items_count" in env.data
        assert "claim_items_count" in env.data
        assert "new_claim_items" in env.data

    def test_counts_correct(self):
        dr = _delta_mixed()
        _, env = propose_queue(dr)
        # 1 NEW + 1 CONTRADICTING + 1 EXACT = 3 claim items + 1 source item
        assert env.data["claim_items_count"] == 3
        assert env.data["source_items_count"] == 1
        assert env.data["queue_items_count"] == 4

    def test_no_artifact_paths_without_vault(self):
        dr = _delta_with_new(1)
        _, env = propose_queue(dr)
        assert "artifact_paths" not in env.data


# ─── Mixed match groups ───────────────────────────────────────────────────

class TestMixed:

    def test_mixed_delta_correct_items(self):
        dr = _delta_mixed()
        items, _ = propose_queue(dr)
        assert items is not None
        # 1 NEW + 1 CONTRADICTING + 1 EXACT claim_notes + 1 source_note
        assert len(items) == 4

    def test_new_and_contradicting_claim_items(self):
        dr = _delta_mixed()
        items, _ = propose_queue(dr)
        assert items is not None
        claim_items = [i for i in items if i["item_type"] == "claim_note"]
        match_classes = {i["checks"]["match_class"] for i in claim_items}
        assert "NEW" in match_classes
        assert "CONTRADICTING" in match_classes

    def test_run_id_propagated(self):
        dr = _delta_mixed()
        items, _ = propose_queue(dr)
        assert items is not None
        for item in items:
            assert item["run_id"] == "run-1"


# ─── AC-3: Ambiguous similarity band [0.70..0.85) ─────────────────────────

def _delta_ambiguous() -> dict[str, Any]:
    """Build a Delta Report with claims in the ambiguous band."""
    return build_delta_report(
        run_id="run-1",
        source_id="src-1",
        normalized_locator="https://example.com",
        fingerprint=FP,
        match_groups={
            "EXACT": [],
            "NEAR_DUPLICATE": [{
                "extracted_claim_key": "h-000000000010",
                "match_class": "NEAR_DUPLICATE",
                "similarity": 0.78,
                "existing_claim_id": "c-10",
            }],
            "SUPPORTING": [{
                "extracted_claim_key": "h-000000000011",
                "match_class": "SUPPORTING",
                "similarity": 0.72,
                "existing_claim_id": "c-11",
            }],
            "CONTRADICTING": [],
            "NEW": [],
        },
    )


def _delta_near_dup_outside_band() -> dict[str, Any]:
    """NEAR_DUPLICATE with similarity outside the ambiguous band."""
    return build_delta_report(
        run_id="run-1",
        source_id="src-1",
        normalized_locator="https://example.com",
        fingerprint=FP,
        match_groups={
            "EXACT": [],
            "NEAR_DUPLICATE": [{
                "extracted_claim_key": "h-000000000020",
                "match_class": "NEAR_DUPLICATE",
                "similarity": 0.90,
                "existing_claim_id": "c-20",
            }],
            "SUPPORTING": [],
            "CONTRADICTING": [],
            "NEW": [],
        },
    )


class TestAmbiguousBand:
    """AC-3: Claims in [0.70..0.85) get merge/create recommendation."""

    def test_ambiguous_claims_produce_items(self):
        dr = _delta_ambiguous()
        items, env = propose_queue(dr)
        assert items is not None
        ambig = [i for i in items if i["checks"].get("review_recommendation") == "merge_or_create"]
        assert len(ambig) == 2

    def test_ambiguous_items_have_merge_action(self):
        dr = _delta_ambiguous()
        items, _ = propose_queue(dr)
        for item in items:
            if item["checks"].get("review_recommendation") == "merge_or_create":
                assert item["proposed_action"] == "merge"

    def test_ambiguous_items_not_auto_approved(self):
        dr = _delta_ambiguous()
        items, _ = propose_queue(dr)
        for item in items:
            if item["checks"].get("review_recommendation") == "merge_or_create":
                approval = item["checks"].get("auto_approval", {})
                assert approval.get("auto_approve") is False

    def test_ambiguous_items_require_human_review(self):
        dr = _delta_ambiguous()
        items, _ = propose_queue(dr)
        for item in items:
            if item["checks"].get("review_recommendation") == "merge_or_create":
                assert item["checks"]["requires_human_review"] is True

    def test_ambiguous_warning_emitted(self):
        dr = _delta_ambiguous()
        _, env = propose_queue(dr)
        warning_codes = [w.code for w in env.warnings]
        assert WARN_AMBIGUOUS_REQUIRES_REVIEW in warning_codes

    def test_ambiguous_count_in_envelope(self):
        dr = _delta_ambiguous()
        _, env = propose_queue(dr)
        assert env.data["ambiguous_count"] == 2

    def test_lower_bound_included(self):
        """Similarity exactly at 0.70 IS in the ambiguous band."""
        dr = build_delta_report(
            run_id="run-lb",
            source_id="src-lb",
            normalized_locator="https://example.com/lb",
            fingerprint=FP,
            match_groups={
                "EXACT": [],
                "NEAR_DUPLICATE": [{
                    "extracted_claim_key": "h-lb",
                    "match_class": "NEAR_DUPLICATE",
                    "similarity": 0.70,
                    "existing_claim_id": "c-lb",
                }],
                "SUPPORTING": [],
                "CONTRADICTING": [],
                "NEW": [],
            },
        )
        items, _ = propose_queue(dr)
        assert len(items) == 1
        assert items[0]["checks"].get("review_recommendation") == "merge_or_create"

    def test_upper_bound_excluded(self):
        """Similarity at 0.85 is NOT in the ambiguous band."""
        dr = build_delta_report(
            run_id="run-ub",
            source_id="src-ub",
            normalized_locator="https://example.com/ub",
            fingerprint=FP,
            match_groups={
                "EXACT": [],
                "NEAR_DUPLICATE": [{
                    "extracted_claim_key": "h-ub",
                    "match_class": "NEAR_DUPLICATE",
                    "similarity": 0.85,
                    "existing_claim_id": "c-ub",
                }],
                "SUPPORTING": [],
                "CONTRADICTING": [],
                "NEW": [],
            },
        )
        items, _ = propose_queue(dr)
        ambig = [i for i in items if i["checks"].get("review_recommendation") == "merge_or_create"]
        assert len(ambig) == 0

    def test_outside_band_no_items(self):
        """NEAR_DUPLICATE with similarity >= 0.85 produces no queue items."""
        dr = _delta_near_dup_outside_band()
        items, _ = propose_queue(dr)
        assert len(items) == 0

    def test_ambiguous_items_validate(self):
        dr = _delta_ambiguous()
        items, _ = propose_queue(dr)
        for item in items:
            errors = validate_queue_item(item)
            assert errors == [], f"Item {item['queue_id']} failed: {errors}"


# ─── AC-4: EXACT auto-approval + auto_approval annotations ──────────────

class TestAutoApproval:
    """AC-4: EXACT matches are auto-approvable; auto_approval annotated on all items."""

    def test_exact_items_auto_approved(self):
        dr = _delta_overlap_only()
        items, _ = propose_queue(dr)
        assert items is not None
        for item in items:
            approval = item["checks"].get("auto_approval", {})
            assert approval.get("auto_approve") is True

    def test_exact_has_provenance_present(self):
        dr = _delta_overlap_only()
        items, _ = propose_queue(dr)
        for item in items:
            assert item["checks"]["provenance_present"] is True

    def test_exact_has_existing_claim_id(self):
        dr = _delta_overlap_only()
        items, _ = propose_queue(dr)
        for item in items:
            assert item["checks"].get("existing_claim_id") is not None

    def test_auto_approved_count_in_envelope(self):
        dr = _delta_overlap_only()
        _, env = propose_queue(dr)
        assert env.data["auto_approved_count"] == 1

    def test_new_claims_not_auto_approved(self):
        dr = _delta_with_new(2)
        items, _ = propose_queue(dr)
        for item in items:
            if item["checks"].get("match_class") == "NEW":
                approval = item["checks"]["auto_approval"]
                assert approval["auto_approve"] is False

    def test_contradicting_not_auto_approved(self):
        dr = _delta_with_contradicting(1)
        items, _ = propose_queue(dr)
        for item in items:
            if item["checks"].get("match_class") == "CONTRADICTING":
                approval = item["checks"]["auto_approval"]
                assert approval["auto_approve"] is False

    def test_all_items_have_auto_approval(self):
        """Every queue item gets auto_approval annotation in checks."""
        dr = _delta_mixed()
        items, _ = propose_queue(dr)
        for item in items:
            assert "auto_approval" in item["checks"]
            approval = item["checks"]["auto_approval"]
            assert "auto_approve" in approval
            assert "reason_code" in approval
            assert "reason_detail" in approval

    def test_mixed_auto_approved_count(self):
        dr = _delta_mixed()
        _, env = propose_queue(dr)
        # Only EXACT should be auto-approved
        assert env.data["auto_approved_count"] == 1


# ─── AC-6 extended: writing ambiguous + exact items ──────────────────────

class TestWriteExtended:
    """AC-6 extended: writing EXACT and ambiguous items to disk."""

    def test_exact_written_to_disk(self, tmp_path: Path):
        dr = _delta_overlap_only()
        items, env = propose_queue(dr, vault_root=tmp_path)
        assert env.ok is True
        queue_dir = tmp_path / "Inbox" / "ReviewQueue"
        assert len(list(queue_dir.glob("*.yaml"))) == 1

    def test_ambiguous_written_to_disk(self, tmp_path: Path):
        dr = _delta_ambiguous()
        items, env = propose_queue(dr, vault_root=tmp_path)
        assert env.ok is True
        queue_dir = tmp_path / "Inbox" / "ReviewQueue"
        assert len(list(queue_dir.glob("*.yaml"))) == 2

    def test_mixed_all_written(self, tmp_path: Path):
        dr = _delta_mixed()
        items, env = propose_queue(dr, vault_root=tmp_path)
        queue_dir = tmp_path / "Inbox" / "ReviewQueue"
        assert len(list(queue_dir.glob("*.yaml"))) == len(items)

    def test_written_items_have_auto_approval(self, tmp_path: Path):
        dr = _delta_mixed()
        items, env = propose_queue(dr, vault_root=tmp_path)
        for path in env.data["artifact_paths"]:
            loaded = yaml.safe_load((tmp_path / path).read_text())
            assert "auto_approval" in loaded["checks"]
