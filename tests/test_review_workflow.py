"""
Tests for the reading-first review digest workflow (REV-001A).

Verifies:
  AC-REV-001A-1: Digest includes packet summaries, claim cards, citations,
                  and canonical-impact descriptions.
  AC-REV-001A-2: Applying packet actions yields deterministic outcomes.
  AC-REV-001A-3: Hold decisions resurface after configured hold TTL.
"""

from __future__ import annotations

from datetime import date

import pytest

from mycelium.review_policy import ReviewPolicy
from mycelium.review_workflow import (
    CONTRADICTING_CLASS,
    ActionResult,
    DigestResult,
    PacketSummary,
    QueueItem,
    apply_hold,
    apply_packet_action,
    build_packet_summary,
    filter_for_digest,
    generate_digest,
    group_by_source,
    should_resurface,
)


def _item(
    queue_id: str = "q-1",
    source_id: str = "src-1",
    run_id: str = "run-1",
    **kwargs,
) -> QueueItem:
    return QueueItem(queue_id=queue_id, source_id=source_id, run_id=run_id, **kwargs)


# ─── Grouping ────────────────────────────────────────────────────────────

class TestGroupBySource:

    def test_single_source(self):
        items = [_item(queue_id="q-1"), _item(queue_id="q-2")]
        groups = group_by_source(items)
        assert len(groups) == 1
        assert len(groups["src-1"]) == 2

    def test_multiple_sources(self):
        items = [
            _item(queue_id="q-1", source_id="s-a"),
            _item(queue_id="q-2", source_id="s-b"),
            _item(queue_id="q-3", source_id="s-a"),
        ]
        groups = group_by_source(items)
        assert len(groups) == 2
        assert len(groups["s-a"]) == 2
        assert len(groups["s-b"]) == 1

    def test_empty(self):
        assert group_by_source([]) == {}


# ─── Resurfacing ─────────────────────────────────────────────────────────

class TestResurfacing:
    """AC-REV-001A-3: Held items resurface after hold TTL."""

    def test_no_hold_always_resurfaces(self):
        item = _item()
        assert should_resurface(item, date(2026, 3, 1)) is True

    def test_hold_before_date_does_not_resurface(self):
        item = _item(hold_until="2026-03-15")
        assert should_resurface(item, date(2026, 3, 1)) is False

    def test_hold_on_date_resurfaces(self):
        item = _item(hold_until="2026-03-01")
        assert should_resurface(item, date(2026, 3, 1)) is True

    def test_hold_after_date_resurfaces(self):
        item = _item(hold_until="2026-02-15")
        assert should_resurface(item, date(2026, 3, 1)) is True

    def test_non_pending_not_resurfaced(self):
        item = _item(status="approved")
        assert should_resurface(item, date(2026, 3, 1)) is False

    def test_14_day_hold_resurfaces(self):
        """Default 14-day hold TTL: held on Mar 1, resurfaces on Mar 15."""
        policy = ReviewPolicy(hold_ttl_days=14)
        item = _item()
        apply_hold(item, policy, from_date=date(2026, 3, 1))
        assert item.hold_until == "2026-03-15"
        assert should_resurface(item, date(2026, 3, 14)) is False
        assert should_resurface(item, date(2026, 3, 15)) is True


class TestFilterForDigest:

    def test_filters_held_items(self):
        items = [
            _item(queue_id="q-1"),
            _item(queue_id="q-2", hold_until="2026-04-01"),
        ]
        result = filter_for_digest(items, date(2026, 3, 1))
        assert len(result) == 1
        assert result[0].queue_id == "q-1"

    def test_includes_resurfaced_items(self):
        items = [
            _item(queue_id="q-1", hold_until="2026-02-15"),
        ]
        result = filter_for_digest(items, date(2026, 3, 1))
        assert len(result) == 1

    def test_excludes_non_pending(self):
        items = [
            _item(queue_id="q-1", status="approved"),
            _item(queue_id="q-2", status="pending_review"),
        ]
        result = filter_for_digest(items, date(2026, 3, 1))
        assert len(result) == 1
        assert result[0].queue_id == "q-2"


# ─── AC-REV-001A-1: Packet summaries ────────────────────────────────────

class TestPacketSummary:
    """AC-REV-001A-1: Digest includes summaries, claim cards, citations, impact."""

    def test_includes_queue_ids_and_run_ids(self):
        items = [
            _item(queue_id="q-1", run_id="r-1"),
            _item(queue_id="q-2", run_id="r-2"),
        ]
        ps = build_packet_summary("src-1", items)
        assert sorted(ps.queue_ids) == ["q-1", "q-2"]
        assert sorted(ps.run_ids) == ["r-1", "r-2"]

    def test_includes_citations(self):
        items = [_item()]
        ps = build_packet_summary("src-1", items)
        assert len(ps.citations) >= 1

    def test_includes_canonical_impact(self):
        items = [_item()]
        ps = build_packet_summary("src-1", items)
        assert ps.canonical_impact != ""

    def test_claim_cards_when_enabled(self):
        items = [_item(claim_text="test claim", match_class="EXACT")]
        ps = build_packet_summary("src-1", items, include_claim_cards=True)
        assert len(ps.claim_cards) == 1
        assert ps.claim_cards[0]["claim_text"] == "test claim"

    def test_no_claim_cards_when_disabled(self):
        items = [_item(claim_text="test claim")]
        ps = build_packet_summary("src-1", items, include_claim_cards=False)
        assert ps.claim_cards == []

    def test_contradicting_flagged(self):
        items = [_item(match_class=CONTRADICTING_CLASS)]
        ps = build_packet_summary("src-1", items)
        assert ps.has_contradicting is True
        assert "contradicting" in ps.canonical_impact.lower()

    def test_non_contradicting_not_flagged(self):
        items = [_item(match_class="EXACT")]
        ps = build_packet_summary("src-1", items)
        assert ps.has_contradicting is False

    def test_to_dict_structure(self):
        items = [_item()]
        ps = build_packet_summary("src-1", items)
        d = ps.to_dict()
        assert "source_id" in d
        assert "queue_ids" in d
        assert "run_ids" in d
        assert "claim_count" in d
        assert "has_contradicting" in d
        assert "canonical_impact" in d
        assert "citations" in d
        assert "claim_cards" in d


# ─── Digest generation ──────────────────────────────────────────────────

class TestGenerateDigest:

    def test_basic_digest(self):
        items = [
            _item(queue_id="q-1", source_id="s-1"),
            _item(queue_id="q-2", source_id="s-2"),
        ]
        result = generate_digest(items, date(2026, 3, 1))
        assert result.source_count == 2
        assert result.pending_item_count == 2

    def test_held_items_excluded(self):
        items = [
            _item(queue_id="q-1"),
            _item(queue_id="q-2", hold_until="2026-04-01"),
        ]
        result = generate_digest(items, date(2026, 3, 1))
        assert result.pending_item_count == 1
        assert result.held_item_count == 1

    def test_limit_sources(self):
        items = [
            _item(queue_id="q-1", source_id="s-a"),
            _item(queue_id="q-2", source_id="s-b"),
            _item(queue_id="q-3", source_id="s-c"),
        ]
        result = generate_digest(items, date(2026, 3, 1), limit_sources=2)
        assert result.source_count == 2

    def test_digest_to_dict(self):
        items = [_item()]
        result = generate_digest(items, date(2026, 3, 1))
        d = result.to_dict()
        assert "digest_date" in d
        assert "packets" in d
        assert "source_count" in d
        assert "pending_item_count" in d
        assert "held_item_count" in d


# ─── AC-REV-001A-2: Deterministic action outcomes ───────────────────────

class TestApproveAll:

    def test_approves_non_contradicting(self):
        items = [
            _item(queue_id="q-1", match_class="EXACT"),
            _item(queue_id="q-2", match_class="NEW"),
        ]
        result = apply_packet_action("approve_all", items)
        assert sorted(result.approved) == ["q-1", "q-2"]
        assert result.skipped == []

    def test_skips_contradicting(self):
        items = [
            _item(queue_id="q-1", match_class="EXACT"),
            _item(queue_id="q-2", match_class=CONTRADICTING_CLASS),
        ]
        result = apply_packet_action("approve_all", items)
        assert result.approved == ["q-1"]
        assert result.skipped == ["q-2"]

    def test_items_status_updated(self):
        items = [_item(match_class="EXACT")]
        apply_packet_action("approve_all", items)
        assert items[0].status == "approved"


class TestApproveSelected:

    def test_approves_only_selected(self):
        items = [
            _item(queue_id="q-1", match_class="EXACT"),
            _item(queue_id="q-2", match_class="NEW"),
        ]
        result = apply_packet_action(
            "approve_selected", items, approved_queue_ids=["q-1"]
        )
        assert result.approved == ["q-1"]
        assert items[0].status == "approved"
        assert items[1].status == "pending_review"

    def test_skips_contradicting_even_if_selected(self):
        items = [_item(queue_id="q-1", match_class=CONTRADICTING_CLASS)]
        result = apply_packet_action(
            "approve_selected", items, approved_queue_ids=["q-1"]
        )
        assert result.skipped == ["q-1"]
        assert result.approved == []


class TestHoldAction:

    def test_hold_all(self):
        items = [
            _item(queue_id="q-1"),
            _item(queue_id="q-2"),
        ]
        policy = ReviewPolicy(hold_ttl_days=14)
        result = apply_packet_action(
            "hold", items, policy=policy, from_date=date(2026, 3, 1)
        )
        assert sorted(result.held) == ["q-1", "q-2"]
        assert items[0].hold_until == "2026-03-15"
        assert items[0].status == "pending_review"

    def test_hold_with_custom_ttl(self):
        items = [_item()]
        policy = ReviewPolicy(hold_ttl_days=7)
        apply_packet_action(
            "hold", items, policy=policy, from_date=date(2026, 3, 1)
        )
        assert items[0].hold_until == "2026-03-08"


class TestRejectAction:

    def test_rejects_all(self):
        items = [
            _item(queue_id="q-1"),
            _item(queue_id="q-2"),
        ]
        result = apply_packet_action("reject", items)
        assert sorted(result.rejected) == ["q-1", "q-2"]
        assert items[0].status == "rejected"
        assert items[1].status == "rejected"


# ─── Determinism ────────────────────────────────────────────────────────

class TestDeterminism:
    """AC-REV-001A-2: Deterministic outcomes for same fixtures."""

    def _fixture(self) -> list[QueueItem]:
        return [
            QueueItem("q-1", "s-1", "r-1", match_class="EXACT"),
            QueueItem("q-2", "s-1", "r-1", match_class=CONTRADICTING_CLASS),
            QueueItem("q-3", "s-2", "r-2", match_class="NEW"),
        ]

    def test_approve_all_deterministic(self):
        r1 = apply_packet_action("approve_all", self._fixture())
        r2 = apply_packet_action("approve_all", self._fixture())
        assert r1.approved == r2.approved
        assert r1.skipped == r2.skipped

    def test_digest_deterministic(self):
        d1 = generate_digest(self._fixture(), date(2026, 3, 1))
        d2 = generate_digest(self._fixture(), date(2026, 3, 1))
        assert d1.source_count == d2.source_count
        assert d1.pending_item_count == d2.pending_item_count
        assert len(d1.packets) == len(d2.packets)
        for p1, p2 in zip(d1.packets, d2.packets):
            assert p1.source_id == p2.source_id
            assert p1.queue_ids == p2.queue_ids


# ─── ActionResult serialization ─────────────────────────────────────────

class TestActionResult:

    def test_to_dict(self):
        r = ActionResult(
            approved=["q-1"],
            rejected=["q-2"],
            held=["q-3"],
            skipped=["q-4"],
        )
        d = r.to_dict()
        assert d == {
            "approved": ["q-1"],
            "rejected": ["q-2"],
            "held": ["q-3"],
            "skipped": ["q-4"],
        }
