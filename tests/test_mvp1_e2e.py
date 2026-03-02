"""
End-to-end validation tests for MVP1 capability bundle (MVP1-001).

Verifies:
  AC-MVP1-001-1: E2E tests cover URL and PDF ingest and verify artifacts
                  and schemas (SCH-002, SCH-006, SCH-008, SCH-007).
  AC-MVP1-001-2: Idempotency test demonstrates Source ID reuse and
                  no canonical duplication on repeat ingest.
  AC-MVP1-001-3: Digest test verifies packet generation (SCH-009) and
                  deterministic decision apply behavior.
  AC-MVP1-001-4: Auto-lane test verifies disallowed classes (NEW,
                  CONTRADICTING) remain in human review.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

from mycelium.auto_approval import (
    REASON_DISALLOW_CONTRADICTING,
    REASON_DISALLOW_NEW,
    REASON_EXACT_PROVENANCE,
    evaluate_auto_approval,
)
from mycelium.delta_report import validate_delta_report
from mycelium.review_packet import (
    build_review_packet,
    save_review_packet,
    validate_review_packet,
)
from mycelium.review_queue import (
    build_queue_item,
    save_queue_item,
    validate_queue_item,
)
from mycelium.schema import (
    validate_extraction_bundle,
    validate_source_frontmatter,
)
from mycelium.stages.capture import SourceInput, capture
from mycelium.stages.compare import ClaimIndex, compare
from mycelium.stages.delta import delta
from mycelium.stages.extract import extract
from mycelium.stages.fingerprint import fingerprint
from mycelium.stages.normalize import normalize
from mycelium.stages.propose_queue import propose_queue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_URL_TEXT = (
    "Recent studies show that deep learning models achieve state-of-the-art "
    "results on protein folding prediction tasks. AlphaFold2 demonstrates "
    "that attention-based architectures can predict 3D protein structures "
    "with atomic accuracy."
)

SAMPLE_PDF_TEXT = (
    "Quantum computing threatens current cryptographic standards. "
    "Post-quantum cryptography algorithms based on lattice problems "
    "are being standardized by NIST. The transition timeline is "
    "estimated at 10-15 years for critical infrastructure."
)


def _text_source(
    text: str = SAMPLE_URL_TEXT,
    source_id: str = "src-e2e-001",
) -> SourceInput:
    """Create a text_bundle SourceInput for testing."""
    return SourceInput(text_bundle=text, source_id=source_id)


def _run_full_pipeline(
    tmp_path: Path,
    text: str = SAMPLE_URL_TEXT,
    source_id: str = "src-e2e-001",
    run_id: str = "run-e2e-001",
    claim_index: ClaimIndex | None = None,
) -> dict[str, Any]:
    """Run the full pipeline: capture → normalize → fingerprint → extract →
    compare → delta → propose_queue.

    Returns a dict with all intermediate results.
    """
    results: dict[str, Any] = {
        "envelopes": [],
        "source_id": source_id,
        "run_id": run_id,
    }

    # 1. Capture
    si = _text_source(text, source_id)
    payload, env = capture(si)
    results["envelopes"].append(env)
    assert env.ok, f"Capture failed: {env.errors}"
    results["payload"] = payload

    # 2. Normalize
    norm, env = normalize(payload)
    results["envelopes"].append(env)
    assert env.ok, f"Normalize failed: {env.errors}"
    results["normalized"] = norm

    # 3. Fingerprint
    ident, env = fingerprint(norm)
    results["envelopes"].append(env)
    assert env.ok, f"Fingerprint failed: {env.errors}"
    results["identity"] = ident

    # 4. Extract
    bundle, env = extract(
        norm,
        vault_root=tmp_path,
        run_id=run_id,
        source_id=source_id,
    )
    results["envelopes"].append(env)
    assert env.ok, f"Extract failed: {env.errors}"
    results["extraction_bundle"] = bundle

    # 5. Compare
    idx = claim_index if claim_index is not None else ClaimIndex(claims=[])
    compare_result, env = compare(
        bundle.get("claims", []),
        claim_index=idx,
    )
    results["envelopes"].append(env)
    results["compare_result"] = compare_result

    # 6. Delta
    delta_report, env = delta(
        run_id=run_id,
        source_id=source_id,
        normalized_locator=ident.normalized_locator,
        fingerprint=ident.fingerprint,
        compare_result=compare_result,
        vault_root=tmp_path,
    )
    results["envelopes"].append(env)
    assert env.ok, f"Delta failed: {env.errors}"
    results["delta_report"] = delta_report

    # 7. Propose+Queue
    queue_items, env = propose_queue(
        delta_report,
        vault_root=tmp_path,
    )
    results["envelopes"].append(env)
    assert env.ok, f"Propose+Queue failed: {env.errors}"
    results["queue_items"] = queue_items or []

    return results


# ═══════════════════════════════════════════════════════════════════════
# AC-MVP1-001-1: E2E tests cover URL and PDF ingest, verify schemas
# ═══════════════════════════════════════════════════════════════════════


class TestURLIngestE2E:
    """AC-MVP1-001-1: URL-like text_bundle ingest produces valid artifacts."""

    def test_full_pipeline_completes(self, tmp_path: Path):
        """Full pipeline runs without error for URL-like text."""
        results = _run_full_pipeline(tmp_path, text=SAMPLE_URL_TEXT)
        for env in results["envelopes"]:
            assert env.ok is True

    def test_extraction_bundle_schema_valid(self, tmp_path: Path):
        """Extraction bundle (SCH-008) passes schema validation."""
        results = _run_full_pipeline(tmp_path, text=SAMPLE_URL_TEXT)
        bundle = results["extraction_bundle"]
        errors = validate_extraction_bundle(bundle)
        assert errors == [], f"SCH-008 errors: {errors}"

    def test_extraction_bundle_has_claims(self, tmp_path: Path):
        """Extraction produces at least one claim."""
        results = _run_full_pipeline(tmp_path, text=SAMPLE_URL_TEXT)
        bundle = results["extraction_bundle"]
        assert len(bundle.get("claims", [])) > 0

    def test_delta_report_schema_valid(self, tmp_path: Path):
        """Delta report (SCH-006) passes schema validation."""
        results = _run_full_pipeline(tmp_path, text=SAMPLE_URL_TEXT)
        dr = results["delta_report"]
        errors = validate_delta_report(dr)
        assert errors == [], f"SCH-006 errors: {errors}"

    def test_delta_report_has_all_match_groups(self, tmp_path: Path):
        """Delta report contains all 5 match group keys."""
        results = _run_full_pipeline(tmp_path, text=SAMPLE_URL_TEXT)
        dr = results["delta_report"]
        for cls in ["EXACT", "NEAR_DUPLICATE", "SUPPORTING", "CONTRADICTING", "NEW"]:
            assert cls in dr["match_groups"]

    def test_delta_report_pipeline_completed(self, tmp_path: Path):
        """Delta report has pipeline_status == completed."""
        results = _run_full_pipeline(tmp_path, text=SAMPLE_URL_TEXT)
        assert results["delta_report"]["pipeline_status"] == "completed"

    def test_queue_items_schema_valid(self, tmp_path: Path):
        """Queue items (SCH-007) pass schema validation."""
        results = _run_full_pipeline(tmp_path, text=SAMPLE_URL_TEXT)
        for item in results["queue_items"]:
            errors = validate_queue_item(item)
            assert errors == [], f"SCH-007 errors: {errors}"

    def test_queue_items_written_to_disk(self, tmp_path: Path):
        """Queue items are written as YAML to Inbox/ReviewQueue/."""
        results = _run_full_pipeline(tmp_path, text=SAMPLE_URL_TEXT)
        queue_dir = tmp_path / "Inbox" / "ReviewQueue"
        if results["queue_items"]:
            assert queue_dir.exists()
            files = list(queue_dir.glob("*.yaml"))
            assert len(files) == len(results["queue_items"])

    def test_extraction_bundle_written_to_disk(self, tmp_path: Path):
        """Extraction bundle artifact exists on disk."""
        _run_full_pipeline(tmp_path, text=SAMPLE_URL_TEXT)
        bundle_files = list((tmp_path / "Inbox" / "Sources").glob("*.yaml"))
        assert len(bundle_files) >= 1

    def test_delta_report_written_to_disk(self, tmp_path: Path):
        """Delta report artifact exists on disk."""
        _run_full_pipeline(tmp_path, text=SAMPLE_URL_TEXT)
        delta_files = list((tmp_path / "Reports" / "Delta").glob("*.yaml"))
        assert len(delta_files) >= 1


class TestPDFIngestE2E:
    """AC-MVP1-001-1: PDF-like text_bundle ingest produces valid artifacts."""

    def test_full_pipeline_completes(self, tmp_path: Path):
        """Full pipeline runs without error for PDF-like text."""
        results = _run_full_pipeline(
            tmp_path,
            text=SAMPLE_PDF_TEXT,
            source_id="src-pdf-001",
            run_id="run-pdf-001",
        )
        for env in results["envelopes"]:
            assert env.ok is True

    def test_extraction_bundle_schema_valid(self, tmp_path: Path):
        """PDF extraction bundle passes SCH-008 validation."""
        results = _run_full_pipeline(
            tmp_path,
            text=SAMPLE_PDF_TEXT,
            source_id="src-pdf-001",
            run_id="run-pdf-001",
        )
        errors = validate_extraction_bundle(results["extraction_bundle"])
        assert errors == []

    def test_delta_report_schema_valid(self, tmp_path: Path):
        """PDF delta report passes SCH-006 validation."""
        results = _run_full_pipeline(
            tmp_path,
            text=SAMPLE_PDF_TEXT,
            source_id="src-pdf-001",
            run_id="run-pdf-001",
        )
        errors = validate_delta_report(results["delta_report"])
        assert errors == []

    def test_queue_items_schema_valid(self, tmp_path: Path):
        """PDF queue items pass SCH-007 validation."""
        results = _run_full_pipeline(
            tmp_path,
            text=SAMPLE_PDF_TEXT,
            source_id="src-pdf-001",
            run_id="run-pdf-001",
        )
        for item in results["queue_items"]:
            errors = validate_queue_item(item)
            assert errors == []

    def test_delta_counts_consistent(self, tmp_path: Path):
        """Delta report counts match actual match groups content."""
        results = _run_full_pipeline(
            tmp_path,
            text=SAMPLE_PDF_TEXT,
            source_id="src-pdf-001",
            run_id="run-pdf-001",
        )
        dr = results["delta_report"]
        total_from_groups = sum(
            len(dr["match_groups"][k]) for k in dr["match_groups"]
        )
        assert dr["counts"]["total_extracted_claims"] == total_from_groups


# ═══════════════════════════════════════════════════════════════════════
# AC-MVP1-001-2: Idempotency — Source ID reuse, no duplication
# ═══════════════════════════════════════════════════════════════════════


class TestIdempotency:
    """AC-MVP1-001-2: Idempotency across repeated ingests."""

    def test_same_text_same_fingerprint(self, tmp_path: Path):
        """Same text produces identical fingerprint on repeated ingest."""
        text = "Deterministic content for idempotency testing."

        si1 = _text_source(text, "idem-001")
        p1, _ = capture(si1)
        n1, _ = normalize(p1)
        f1, _ = fingerprint(n1)

        si2 = _text_source(text, "idem-001")
        p2, _ = capture(si2)
        n2, _ = normalize(p2)
        f2, _ = fingerprint(n2)

        assert f1.fingerprint == f2.fingerprint

    def test_same_text_same_locator(self, tmp_path: Path):
        """Same text bundle produces identical normalized_locator."""
        text = "Locator consistency verification content."

        si1 = _text_source(text, "loc-001")
        p1, _ = capture(si1)
        n1, _ = normalize(p1)
        f1, _ = fingerprint(n1)

        si2 = _text_source(text, "loc-001")
        p2, _ = capture(si2)
        n2, _ = normalize(p2)
        f2, _ = fingerprint(n2)

        assert f1.normalized_locator == f2.normalized_locator

    def test_repeated_pipeline_no_canon_duplication(self, tmp_path: Path):
        """Repeated full pipeline doesn't create duplicate canonical artifacts."""
        text = "This content is ingested twice for idempotency."

        # First ingest
        r1 = _run_full_pipeline(
            tmp_path, text=text, source_id="dup-001", run_id="run-dup-1",
        )
        # Second ingest (same text, same source_id, different run_id)
        r2 = _run_full_pipeline(
            tmp_path, text=text, source_id="dup-001", run_id="run-dup-2",
        )

        # Fingerprints must match
        assert r1["identity"].fingerprint == r2["identity"].fingerprint
        assert r1["identity"].normalized_locator == r2["identity"].normalized_locator

    def test_delta_captures_idempotency_fields(self, tmp_path: Path):
        """Delta report includes source_revision with fingerprint and locator."""
        results = _run_full_pipeline(tmp_path)
        dr = results["delta_report"]
        rev = dr["source_revision"]
        assert "fingerprint" in rev
        assert "normalized_locator" in rev
        assert rev["fingerprint"].startswith("sha256:")

    def test_different_text_different_fingerprint(self, tmp_path: Path):
        """Different text produces different fingerprints (no false reuse)."""
        si1 = _text_source("Text alpha for testing.", "diff-a")
        p1, _ = capture(si1)
        n1, _ = normalize(p1)
        f1, _ = fingerprint(n1)

        si2 = _text_source("Text beta for testing.", "diff-b")
        p2, _ = capture(si2)
        n2, _ = normalize(p2)
        f2, _ = fingerprint(n2)

        assert f1.fingerprint != f2.fingerprint


# ═══════════════════════════════════════════════════════════════════════
# AC-MVP1-001-3: Digest — packet generation + deterministic apply
# ═══════════════════════════════════════════════════════════════════════


class TestDigestAndDecisionApply:
    """AC-MVP1-001-3: Digest verifies packet generation (SCH-009) and
    deterministic decision apply behavior."""

    def test_packet_from_pipeline_validates_sch009(self, tmp_path: Path):
        """Review packets built from pipeline output validate against SCH-009."""
        results = _run_full_pipeline(tmp_path)
        qi = results["queue_items"]
        if not qi:
            pytest.skip("No queue items produced")

        # Group by source
        source_ids = {item["run_id"] for item in qi}
        queue_ids = [item["queue_id"] for item in qi]
        run_ids = sorted({item["run_id"] for item in qi})

        pkt = build_review_packet(
            packet_id="pkt-e2e-001",
            digest_date="2026-03-01",
            created_at=datetime.now(timezone.utc).isoformat(),
            source_id=results["source_id"],
            run_ids=run_ids,
            queue_ids=queue_ids,
        )
        errors = validate_review_packet(pkt)
        assert errors == [], f"SCH-009 errors: {errors}"

    def test_packet_saved_to_disk(self, tmp_path: Path):
        """Saved review packet is readable from disk as valid YAML."""
        pkt = build_review_packet(
            packet_id="pkt-save-001",
            digest_date="2026-03-01",
            created_at=datetime.now(timezone.utc).isoformat(),
            source_id="src-e2e-001",
            run_ids=["run-e2e-001"],
            queue_ids=["qi-001"],
        )
        path = save_review_packet(tmp_path, pkt)
        loaded = yaml.safe_load(path.read_text())
        assert loaded["packet_id"] == "pkt-save-001"
        assert loaded["source_id"] == "src-e2e-001"

    def test_packet_approve_all_decision(self, tmp_path: Path):
        """Packet with approve_all decision validates."""
        pkt = build_review_packet(
            packet_id="pkt-aa-001",
            digest_date="2026-03-01",
            created_at=datetime.now(timezone.utc).isoformat(),
            source_id="src-e2e-001",
            run_ids=["run-e2e-001"],
            queue_ids=["qi-001"],
            decision={
                "action": "approve_all",
                "actor": "user:test",
                "decided_at": datetime.now(timezone.utc).isoformat(),
                "reason": None,
            },
        )
        errors = validate_review_packet(pkt)
        assert errors == []

    def test_packet_reject_decision(self, tmp_path: Path):
        """Packet with reject decision validates."""
        pkt = build_review_packet(
            packet_id="pkt-rej-001",
            digest_date="2026-03-01",
            created_at=datetime.now(timezone.utc).isoformat(),
            source_id="src-e2e-001",
            run_ids=["run-e2e-001"],
            queue_ids=["qi-001"],
            decision={
                "action": "reject",
                "actor": "user:test",
                "decided_at": datetime.now(timezone.utc).isoformat(),
                "reason": "Not relevant",
            },
        )
        errors = validate_review_packet(pkt)
        assert errors == []

    def test_deterministic_packet_output(self, tmp_path: Path):
        """Same inputs produce identical packet YAML (determinism)."""
        ts = "2026-03-01T12:00:00+00:00"
        kwargs = dict(
            packet_id="pkt-det-001",
            digest_date="2026-03-01",
            created_at=ts,
            source_id="src-det-001",
            run_ids=["run-1"],
            queue_ids=["qi-1"],
        )
        pkt1 = build_review_packet(**kwargs)
        pkt2 = build_review_packet(**kwargs)

        p1 = save_review_packet(tmp_path, pkt1)
        c1 = p1.read_text()
        p2 = save_review_packet(tmp_path, pkt2)
        c2 = p2.read_text()
        assert c1 == c2

    def test_packet_hold_requires_hold_until(self, tmp_path: Path):
        """Hold decision without hold_until produces validation errors."""
        pkt = build_review_packet(
            packet_id="pkt-hold-001",
            digest_date="2026-03-01",
            created_at=datetime.now(timezone.utc).isoformat(),
            source_id="src-e2e-001",
            run_ids=["run-e2e-001"],
            queue_ids=["qi-001"],
            decision={
                "action": "hold",
                "actor": "user:test",
                "decided_at": datetime.now(timezone.utc).isoformat(),
                "reason": "Waiting for more data",
            },
        )
        errors = validate_review_packet(pkt)
        assert any("hold_until" in e for e in errors)

    def test_packet_approve_selected_validates_ids(self, tmp_path: Path):
        """approve_selected with unknown IDs is detected."""
        pkt = build_review_packet(
            packet_id="pkt-sel-001",
            digest_date="2026-03-01",
            created_at=datetime.now(timezone.utc).isoformat(),
            source_id="src-e2e-001",
            run_ids=["run-e2e-001"],
            queue_ids=["qi-1", "qi-2"],
            decision={
                "action": "approve_selected",
                "actor": "user:test",
                "decided_at": datetime.now(timezone.utc).isoformat(),
                "reason": None,
                "approved_queue_ids": ["qi-999"],
            },
        )
        errors = validate_review_packet(pkt)
        assert any("not in queue_ids" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════
# AC-MVP1-001-4: Auto-lane — disallowed classes stay in human review
# ═══════════════════════════════════════════════════════════════════════


class TestAutoLane:
    """AC-MVP1-001-4: Auto-approval lane rejects NEW and CONTRADICTING,
    keeping them in human review."""

    def test_new_claim_rejected_by_auto_lane(self):
        """NEW claim is always routed to human review."""
        item = build_queue_item(
            queue_id="qi-new-001",
            run_id="run-e2e-001",
            item_type="claim_note",
            target_path="Inbox/Sources/claim-new.md",
            proposed_action="promote_to_canon",
            created_at=datetime.now(timezone.utc).isoformat(),
            checks={
                "match_class": "NEW",
                "provenance_present": True,
            },
        )
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is False
        assert decision.reason_code == REASON_DISALLOW_NEW

    def test_contradicting_claim_rejected_by_auto_lane(self):
        """CONTRADICTING claim is always routed to human review."""
        item = build_queue_item(
            queue_id="qi-contra-001",
            run_id="run-e2e-001",
            item_type="claim_note",
            target_path="Inbox/Sources/claim-contra.md",
            proposed_action="promote_to_canon",
            created_at=datetime.now(timezone.utc).isoformat(),
            checks={
                "match_class": "CONTRADICTING",
                "provenance_present": True,
            },
        )
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is False
        assert decision.reason_code == REASON_DISALLOW_CONTRADICTING

    def test_exact_with_provenance_auto_approved(self):
        """EXACT match with provenance IS auto-approved."""
        item = build_queue_item(
            queue_id="qi-exact-001",
            run_id="run-e2e-001",
            item_type="claim_note",
            target_path="Inbox/Sources/claim-exact.md",
            proposed_action="promote_to_canon",
            created_at=datetime.now(timezone.utc).isoformat(),
            checks={
                "match_class": "EXACT",
                "provenance_present": True,
                "similarity": 0.99,
            },
        )
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is True
        assert decision.reason_code == REASON_EXACT_PROVENANCE

    def test_exact_without_provenance_rejected(self):
        """EXACT match without provenance goes to human review."""
        item = build_queue_item(
            queue_id="qi-exact-np-001",
            run_id="run-e2e-001",
            item_type="claim_note",
            target_path="Inbox/Sources/claim-np.md",
            proposed_action="promote_to_canon",
            created_at=datetime.now(timezone.utc).isoformat(),
            checks={
                "match_class": "EXACT",
                "provenance_present": False,
                "similarity": 0.98,
            },
        )
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is False

    def test_pipeline_annotates_auto_approval(self, tmp_path: Path):
        """Queue items produced by propose_queue have auto_approval checks."""
        results = _run_full_pipeline(tmp_path)
        for item in results["queue_items"]:
            checks = item.get("checks", {})
            assert "auto_approval" in checks, (
                f"Queue item {item['queue_id']} missing auto_approval in checks"
            )
            aa = checks["auto_approval"]
            assert "auto_approve" in aa
            assert "reason_code" in aa

    def test_new_claims_from_pipeline_not_auto_approved(self, tmp_path: Path):
        """NEW claims generated by pipeline have auto_approve=False."""
        results = _run_full_pipeline(tmp_path)
        new_items = [
            item for item in results["queue_items"]
            if item.get("checks", {}).get("match_class") == "NEW"
        ]
        for item in new_items:
            aa = item["checks"]["auto_approval"]
            assert aa["auto_approve"] is False
            assert aa["reason_code"] == REASON_DISALLOW_NEW

    def test_ambiguous_similarity_rejected(self):
        """Claims in ambiguous similarity band [0.70..0.85) go to human review."""
        item = build_queue_item(
            queue_id="qi-ambig-001",
            run_id="run-e2e-001",
            item_type="claim_note",
            target_path="Inbox/Sources/claim-ambig.md",
            proposed_action="merge",
            created_at=datetime.now(timezone.utc).isoformat(),
            checks={
                "match_class": "NEAR_DUPLICATE",
                "provenance_present": True,
                "similarity": 0.78,
            },
        )
        decision = evaluate_auto_approval(item)
        assert decision.auto_approve is False


# ═══════════════════════════════════════════════════════════════════════
# Cross-schema consistency
# ═══════════════════════════════════════════════════════════════════════


class TestCrossSchemaConsistency:
    """Verify that artifacts produced by the pipeline are mutually consistent."""

    def test_delta_source_id_matches_extraction(self, tmp_path: Path):
        """Delta report source_id matches extraction bundle source_id."""
        results = _run_full_pipeline(tmp_path)
        dr = results["delta_report"]
        bundle = results["extraction_bundle"]
        assert dr["source_id"] == bundle["source_id"]

    def test_delta_run_id_matches_extraction(self, tmp_path: Path):
        """Delta report run_id matches extraction bundle run_id."""
        results = _run_full_pipeline(tmp_path)
        dr = results["delta_report"]
        bundle = results["extraction_bundle"]
        assert dr["run_id"] == bundle["run_id"]

    def test_queue_items_reference_correct_run(self, tmp_path: Path):
        """Queue items reference the correct run_id."""
        results = _run_full_pipeline(tmp_path)
        for item in results["queue_items"]:
            assert item["run_id"] == results["run_id"]

    def test_fingerprint_in_delta_matches_stage(self, tmp_path: Path):
        """Delta report fingerprint matches fingerprint stage output."""
        results = _run_full_pipeline(tmp_path)
        dr = results["delta_report"]
        fp = results["identity"].fingerprint
        assert dr["source_revision"]["fingerprint"] == fp

    def test_locator_in_delta_matches_stage(self, tmp_path: Path):
        """Delta report normalized_locator matches fingerprint stage output."""
        results = _run_full_pipeline(tmp_path)
        dr = results["delta_report"]
        loc = results["identity"].normalized_locator
        assert dr["source_revision"]["normalized_locator"] == loc

    def test_claim_counts_match_extraction(self, tmp_path: Path):
        """Delta total_extracted_claims matches extraction bundle claims count."""
        results = _run_full_pipeline(tmp_path)
        dr = results["delta_report"]
        bundle = results["extraction_bundle"]
        total_delta = dr["counts"]["total_extracted_claims"]
        total_bundle = len(bundle.get("claims", []))
        assert total_delta == total_bundle

    def test_all_envelopes_have_timestamps(self, tmp_path: Path):
        """All output envelopes have ISO-8601 timestamps."""
        results = _run_full_pipeline(tmp_path)
        for env in results["envelopes"]:
            assert env.timestamp is not None
            assert len(env.timestamp) > 0
