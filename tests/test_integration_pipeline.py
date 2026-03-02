"""Integration tests for pipeline chain and draft/canon boundaries (TST-I-001).

Verifies acceptance criteria:
  AC-TST-I-001-1: Full pipeline run from capture→delta→queue completes.
  AC-TST-I-001-2: No writes occur under Canonical Scope without Promotion.
  AC-TST-I-001-3: Review transitions enforce legal states and immutability.
  AC-TST-I-001-4: review_digest Source packet grouping and schema (SCH-009).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from mycelium.comparator import CompareResult, MatchClass, MatchRecord
from mycelium.review_packet import (
    build_review_packet,
    save_review_packet,
    validate_review_packet,
)
from mycelium.review_queue import (
    build_queue_item,
    check_mutable,
    load_queue_item,
    save_queue_item,
    update_queue_item,
    validate_queue_item,
)
from mycelium.schema import SchemaValidationError
from mycelium.stages.capture import RawSourcePayload, SourceInput, capture
from mycelium.stages.compare import ClaimIndex, compare
from mycelium.stages.delta import delta
from mycelium.stages.extract import extract
from mycelium.stages.fingerprint import fingerprint
from mycelium.stages.normalize import NormalizedSource, normalize
from mycelium.stages.propose_queue import propose_queue
from mycelium.vault_layout import CANONICAL_DIRS, is_canonical_scope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_TEXT = (
    "Machine learning models require large datasets for training. "
    "Neural networks can approximate any continuous function. "
    "The transformer architecture revolutionized natural language processing."
)


def _text_bundle_source(
    text: str = SAMPLE_TEXT,
    source_id: str = "test-001",
) -> SourceInput:
    return SourceInput(text_bundle=text, source_id=source_id)


def _run_pipeline_through_delta(
    tmp_path: Path,
    text: str = SAMPLE_TEXT,
    source_id: str = "test-001",
    run_id: str = "run-001",
) -> tuple[
    dict[str, Any] | None,  # delta_report
    list[Any],  # envelopes
]:
    """Run capture→normalize→fingerprint→extract→compare→delta."""
    envelopes = []

    # 1. Capture
    si = _text_bundle_source(text, source_id)
    payload, env = capture(si)
    envelopes.append(env)
    if payload is None:
        return None, envelopes

    # 2. Normalize
    norm, env = normalize(payload)
    envelopes.append(env)
    if norm is None:
        return None, envelopes

    # 3. Fingerprint
    ident, env = fingerprint(norm)
    envelopes.append(env)
    if ident is None:
        return None, envelopes

    # 4. Extract
    bundle, env = extract(
        norm,
        vault_root=tmp_path,
        run_id=run_id,
        source_id=source_id,
    )
    envelopes.append(env)
    if bundle is None:
        return None, envelopes

    # 5. Compare (empty index — all NEW)
    claim_index = ClaimIndex(claims=[])
    compare_result, env = compare(
        bundle.get("claims", []),
        claim_index=claim_index,
    )
    envelopes.append(env)

    # 6. Delta
    delta_report, env = delta(
        run_id=run_id,
        source_id=source_id,
        normalized_locator=ident.normalized_locator,
        fingerprint=ident.fingerprint,
        compare_result=compare_result,
        vault_root=tmp_path,
    )
    envelopes.append(env)

    return delta_report, envelopes


# ═══════════════════════════════════════════════════════════════════════
# AC-TST-I-001-1: Full pipeline run
# ═══════════════════════════════════════════════════════════════════════

class TestFullPipelineRun:
    """AC-TST-I-001-1: Full pipeline from capture→delta→queue completes."""

    def test_text_bundle_pipeline(self, tmp_path: Path):
        """Text bundle source kind runs through full pipeline."""
        delta_report, envelopes = _run_pipeline_through_delta(tmp_path)

        # All stages succeeded
        for env in envelopes:
            assert env.ok is True, f"Stage failed: {env.command} — {env.errors}"

        assert delta_report is not None
        assert delta_report["pipeline_status"] == "completed"
        assert delta_report["run_id"] == "run-001"
        assert delta_report["source_id"] == "test-001"

    def test_pipeline_produces_delta_report(self, tmp_path: Path):
        """Delta report file is written to Reports/Delta/."""
        delta_report, _ = _run_pipeline_through_delta(tmp_path)
        assert delta_report is not None

        delta_files = list((tmp_path / "Reports" / "Delta").glob("*.yaml"))
        assert len(delta_files) >= 1

    def test_pipeline_produces_extraction_bundle(self, tmp_path: Path):
        """Extraction bundle file is written to Inbox/Sources/."""
        _run_pipeline_through_delta(tmp_path)

        bundle_files = list((tmp_path / "Inbox" / "Sources").glob("*extraction*.yaml"))
        assert len(bundle_files) >= 1

    def test_pipeline_through_propose_queue(self, tmp_path: Path):
        """Full pipeline including propose+queue generates queue items."""
        delta_report, envelopes = _run_pipeline_through_delta(tmp_path)
        assert delta_report is not None

        queue_items, env = propose_queue(
            delta_report,
            vault_root=tmp_path,
        )
        assert env.ok is True
        assert queue_items is not None

    def test_queue_items_written_to_disk(self, tmp_path: Path):
        """Queue items are written to Inbox/ReviewQueue/."""
        delta_report, _ = _run_pipeline_through_delta(tmp_path)
        assert delta_report is not None

        queue_items, _ = propose_queue(
            delta_report,
            vault_root=tmp_path,
        )

        if queue_items:
            queue_files = list(
                (tmp_path / "Inbox" / "ReviewQueue").glob("*.yaml")
            )
            assert len(queue_files) == len(queue_items)

    def test_delta_report_has_all_match_groups(self, tmp_path: Path):
        """Delta report contains all 5 match group keys."""
        delta_report, _ = _run_pipeline_through_delta(tmp_path)
        assert delta_report is not None

        for group in ["EXACT", "NEAR_DUPLICATE", "SUPPORTING", "CONTRADICTING", "NEW"]:
            assert group in delta_report["match_groups"]

    def test_delta_counts_consistent(self, tmp_path: Path):
        """counts.total_extracted_claims matches sum of match groups."""
        delta_report, _ = _run_pipeline_through_delta(tmp_path)
        assert delta_report is not None

        total = sum(
            len(delta_report["match_groups"][k])
            for k in delta_report["match_groups"]
        )
        assert delta_report["counts"]["total_extracted_claims"] == total

    def test_idempotent_fingerprint(self, tmp_path: Path):
        """Same text produces identical fingerprint across runs."""
        text = "Deterministic content for fingerprint verification."

        si = _text_bundle_source(text, "idem-1")
        p1, _ = capture(si)
        n1, _ = normalize(p1)
        f1, _ = fingerprint(n1)

        si2 = _text_bundle_source(text, "idem-1")
        p2, _ = capture(si2)
        n2, _ = normalize(p2)
        f2, _ = fingerprint(n2)

        assert f1.fingerprint == f2.fingerprint
        assert f1.normalized_locator == f2.normalized_locator

    def test_different_text_different_fingerprint(self, tmp_path: Path):
        """Different text produces different fingerprints."""
        si1 = _text_bundle_source("Text A.", "src-a")
        p1, _ = capture(si1)
        n1, _ = normalize(p1)
        f1, _ = fingerprint(n1)

        si2 = _text_bundle_source("Text B.", "src-b")
        p2, _ = capture(si2)
        n2, _ = normalize(p2)
        f2, _ = fingerprint(n2)

        assert f1.fingerprint != f2.fingerprint


# ═══════════════════════════════════════════════════════════════════════
# AC-TST-I-001-2: Draft/Canon boundary enforcement
# ═══════════════════════════════════════════════════════════════════════

class TestDraftCanonBoundary:
    """AC-TST-I-001-2: No writes under Canonical Scope without Promotion."""

    def test_pipeline_writes_only_to_draft_scope(self, tmp_path: Path):
        """Pipeline stages only write to draft scope directories."""
        delta_report, _ = _run_pipeline_through_delta(tmp_path)
        assert delta_report is not None

        queue_items, _ = propose_queue(delta_report, vault_root=tmp_path)

        # Check that no canonical scope directories were created
        for canon_dir in CANONICAL_DIRS:
            canon_path = tmp_path / canon_dir
            if canon_path.exists():
                # Directory may exist from test setup but should have no
                # pipeline-written files
                files = list(canon_path.rglob("*"))
                pipeline_files = [
                    f for f in files
                    if f.is_file() and f.suffix in (".yaml", ".md")
                ]
                assert pipeline_files == [], (
                    f"Pipeline wrote to canonical scope: {pipeline_files}"
                )

    def test_extraction_bundle_in_draft_scope(self, tmp_path: Path):
        """Extraction bundle is written under Inbox/ (draft scope)."""
        _run_pipeline_through_delta(tmp_path)

        bundle_files = list((tmp_path / "Inbox" / "Sources").glob("*.yaml"))
        for f in bundle_files:
            rel = str(f.relative_to(tmp_path))
            assert not is_canonical_scope(rel), f"Bundle in canonical scope: {rel}"

    def test_delta_report_in_draft_scope(self, tmp_path: Path):
        """Delta report is written under Reports/ (draft scope)."""
        _run_pipeline_through_delta(tmp_path)

        delta_files = list((tmp_path / "Reports" / "Delta").glob("*.yaml"))
        for f in delta_files:
            rel = str(f.relative_to(tmp_path))
            assert not is_canonical_scope(rel), f"Delta in canonical scope: {rel}"

    def test_queue_items_in_draft_scope(self, tmp_path: Path):
        """Queue items are written under Inbox/ReviewQueue/ (draft scope)."""
        delta_report, _ = _run_pipeline_through_delta(tmp_path)
        if delta_report:
            propose_queue(delta_report, vault_root=tmp_path)

        queue_dir = tmp_path / "Inbox" / "ReviewQueue"
        if queue_dir.exists():
            for f in queue_dir.glob("*.yaml"):
                rel = str(f.relative_to(tmp_path))
                assert not is_canonical_scope(rel)


# ═══════════════════════════════════════════════════════════════════════
# AC-TST-I-001-3: Review transition enforcement
# ═══════════════════════════════════════════════════════════════════════

class TestReviewTransitions:
    """AC-TST-I-001-3: Review transitions enforce legal states."""

    def _save_pending_item(self, vault: Path) -> Path:
        item = build_queue_item(
            queue_id="q-001",
            run_id="run-001",
            item_type="claim_note",
            target_path="Inbox/Sources/c-001.md",
            proposed_action="promote_to_canon",
            created_at="2026-03-01T00:00:00Z",
        )
        return save_queue_item(vault, item)

    def test_pending_review_is_mutable(self, tmp_path: Path):
        path = self._save_pending_item(tmp_path)
        item = load_queue_item(path)
        check_mutable(item)  # Should not raise

    def test_approved_is_immutable(self, tmp_path: Path):
        path = self._save_pending_item(tmp_path)
        # Transition to approved via explicit state transition
        updated = update_queue_item(
            path, {"status": "approved"}, is_state_transition=True,
        )
        with pytest.raises(SchemaValidationError, match="ERR_QUEUE_IMMUTABLE"):
            check_mutable(updated)

    def test_rejected_is_immutable(self, tmp_path: Path):
        path = self._save_pending_item(tmp_path)
        updated = update_queue_item(
            path, {"status": "rejected"}, is_state_transition=True,
        )
        with pytest.raises(SchemaValidationError, match="ERR_QUEUE_IMMUTABLE"):
            check_mutable(updated)

    def test_non_transition_mutation_blocked(self, tmp_path: Path):
        """Non-state-transition mutation of approved item is blocked."""
        path = self._save_pending_item(tmp_path)
        update_queue_item(
            path, {"status": "approved"}, is_state_transition=True,
        )
        with pytest.raises(SchemaValidationError):
            update_queue_item(path, {"status": "rejected"})

    def test_state_transition_allowed(self, tmp_path: Path):
        """Explicit state transitions can change status."""
        path = self._save_pending_item(tmp_path)
        updated = update_queue_item(
            path, {"status": "approved"}, is_state_transition=True,
        )
        assert updated["status"] == "approved"

    def test_queue_item_validates_on_save(self, tmp_path: Path):
        """Invalid queue items are rejected on save."""
        bad_item = {"queue_id": "q-bad"}
        with pytest.raises(SchemaValidationError):
            save_queue_item(tmp_path, bad_item)

    def test_queue_item_roundtrip(self, tmp_path: Path):
        """Save and load preserves all fields."""
        path = self._save_pending_item(tmp_path)
        loaded = load_queue_item(path)
        assert loaded["queue_id"] == "q-001"
        assert loaded["status"] == "pending_review"
        assert loaded["item_type"] == "claim_note"


# ═══════════════════════════════════════════════════════════════════════
# AC-TST-I-001-4: Review digest packet grouping and schema
# ═══════════════════════════════════════════════════════════════════════

class TestReviewDigestPackets:
    """AC-TST-I-001-4: Source packet grouping and schema (SCH-009)."""

    def test_packet_per_source(self, tmp_path: Path):
        """One packet per source validates against SCH-009."""
        for i in range(3):
            pkt = build_review_packet(
                packet_id=f"pkt-{i:03d}",
                digest_date="2026-03-01",
                created_at="2026-03-01T12:00:00Z",
                source_id=f"s-{i:03d}",
                run_ids=[f"run-{i}"],
                queue_ids=[f"q-{i}"],
            )
            errors = validate_review_packet(pkt)
            assert errors == [], f"Packet {i} invalid: {errors}"
            save_review_packet(tmp_path, pkt)

        packet_files = list(
            (tmp_path / "Inbox" / "ReviewDigest").glob("*.yaml")
        )
        assert len(packet_files) == 3

    def test_packet_groups_queue_ids_by_source(self, tmp_path: Path):
        """Packets correctly group queue_ids belonging to same source."""
        pkt = build_review_packet(
            packet_id="pkt-multi",
            digest_date="2026-03-01",
            created_at="2026-03-01T12:00:00Z",
            source_id="s-001",
            run_ids=["run-1", "run-2"],
            queue_ids=["q-1", "q-2", "q-3"],
        )
        path = save_review_packet(tmp_path, pkt)
        loaded = yaml.safe_load(path.read_text())
        assert loaded["queue_ids"] == ["q-1", "q-2", "q-3"]
        assert loaded["source_id"] == "s-001"

    def test_packet_with_approve_all_decision(self, tmp_path: Path):
        pkt = build_review_packet(
            packet_id="pkt-approved",
            digest_date="2026-03-01",
            created_at="2026-03-01T12:00:00Z",
            source_id="s-001",
            run_ids=["run-1"],
            queue_ids=["q-1"],
            decision={
                "action": "approve_all",
                "actor": "user:alice",
                "decided_at": "2026-03-01T14:00:00Z",
                "reason": None,
            },
        )
        errors = validate_review_packet(pkt)
        assert errors == []

    def test_packet_approve_selected_validates_ids(self, tmp_path: Path):
        """approve_selected with invalid ids is rejected."""
        pkt = build_review_packet(
            packet_id="pkt-bad",
            digest_date="2026-03-01",
            created_at="2026-03-01T12:00:00Z",
            source_id="s-001",
            run_ids=["run-1"],
            queue_ids=["q-1", "q-2"],
            decision={
                "action": "approve_selected",
                "actor": "user:alice",
                "decided_at": "2026-03-01T14:00:00Z",
                "reason": None,
                "approved_queue_ids": ["q-999"],
            },
        )
        errors = validate_review_packet(pkt)
        assert any("not in queue_ids" in e for e in errors)

    def test_packet_hold_requires_hold_until(self, tmp_path: Path):
        pkt = build_review_packet(
            packet_id="pkt-hold",
            digest_date="2026-03-01",
            created_at="2026-03-01T12:00:00Z",
            source_id="s-001",
            run_ids=["run-1"],
            queue_ids=["q-1"],
            decision={
                "action": "hold",
                "actor": "user:alice",
                "decided_at": "2026-03-01T14:00:00Z",
                "reason": "Needs more context",
            },
        )
        errors = validate_review_packet(pkt)
        assert any("hold_until" in e for e in errors)

    def test_deterministic_packet_output(self, tmp_path: Path):
        """AC-SCH-009-2: Same input produces identical packet YAML."""
        pkt = build_review_packet(
            packet_id="pkt-det",
            digest_date="2026-03-01",
            created_at="2026-03-01T12:00:00Z",
            source_id="s-001",
            run_ids=["run-1"],
            queue_ids=["q-1"],
        )
        p1 = save_review_packet(tmp_path, pkt)
        c1 = p1.read_text()

        p2 = save_review_packet(tmp_path, pkt)
        c2 = p2.read_text()

        assert c1 == c2
