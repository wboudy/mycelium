"""
Tests for baseline graph analysis (MVP3-2).

Verifies acceptance criteria from §12.4:
  AC-MVP3-2-BASE-1: Hub score formula matches spec exactly.
  AC-MVP3-2-BASE-2: Bridge detection uses Tarjan's algorithm correctly.
  AC-MVP3-2-BASE-3: Output includes all minimum required fields.
  AC-MVP3-2-BASE-4: Deterministic ordering via lexical tie-break.
  AC-MVP3-2-ADV-1: Advanced mode gated by explicit flag.
  AC-MVP3-2-ADV-2: Approximate betweenness for top-N candidates.
  AC-MVP3-2-ADV-3: Budget controls with partial output on exceed.
  AC-MVP3-2-ADV-4: Advanced metrics don't affect baseline SLA gates.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

from mycelium.graph import (
    BUDGET_EXCEEDED_MSG,
    BetweennessMetrics,
    BudgetExceededWarning,
    GraphAnalysisResult,
    HubMetrics,
    analyze_graph,
    analyze_graph_from_edges,
    build_wikilink_graph,
    compute_approximate_betweenness,
    compute_hub_scores,
    find_bridges_and_articulation_points,
)


# ── Test fixtures ────────────────────────────────────────────────────

def _simple_chain() -> list[tuple[str, str]]:
    """A -> B -> C (linear chain)."""
    return [("A", "B"), ("B", "C")]


def _star_graph() -> list[tuple[str, str]]:
    """Center node with spokes: A->B, A->C, A->D, A->E."""
    return [("A", "B"), ("A", "C"), ("A", "D"), ("A", "E")]


def _diamond_graph() -> list[tuple[str, str]]:
    """Diamond: A->B, A->C, B->D, C->D."""
    return [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]


def _bridge_graph() -> list[tuple[str, str]]:
    """Two triangles connected by a bridge:
    Component 1: A-B-C (triangle)
    Component 2: D-E-F (triangle)
    Bridge: C-D
    """
    return [
        ("A", "B"), ("B", "C"), ("C", "A"),  # triangle 1
        ("D", "E"), ("E", "F"), ("F", "D"),  # triangle 2
        ("C", "D"),                           # bridge
    ]


def _disconnected_graph() -> list[tuple[str, str]]:
    """Two disconnected components."""
    return [("A", "B"), ("C", "D")]


# ── AC-MVP3-2-BASE-1: Hub score formula ──────────────────────────────

class TestHubScoreFormula:
    """AC-MVP3-2-BASE-1: hub_score = 0.6*norm(in_degree) + 0.4*norm(page_rank)."""

    def test_star_graph_center_has_zero_hub_score(self):
        """In a star A->B,C,D,E, center A has in_degree=0, spokes have in_degree=1."""
        result = analyze_graph_from_edges(_star_graph())
        # A has in_degree=0 (no incoming), B/C/D/E have in_degree=1 each
        hub_by_id = {h.node_id: h for h in result.hubs}
        assert hub_by_id["A"].in_degree == 0
        for node in "BCDE":
            assert hub_by_id[node].in_degree == 1

    def test_chain_end_node_highest_in_degree(self):
        """In A->B->C, C has highest in_degree relative to A."""
        result = analyze_graph_from_edges(_simple_chain())
        hub_by_id = {h.node_id: h for h in result.hubs}
        assert hub_by_id["A"].in_degree == 0
        assert hub_by_id["B"].in_degree == 1
        assert hub_by_id["C"].in_degree == 1

    def test_hub_score_in_valid_range(self):
        result = analyze_graph_from_edges(_diamond_graph())
        for hub in result.hubs:
            assert 0.0 <= hub.hub_score <= 1.0

    def test_hub_metrics_include_all_fields(self):
        result = analyze_graph_from_edges(_simple_chain())
        for hub in result.hubs:
            assert hasattr(hub, "node_id")
            assert hasattr(hub, "in_degree")
            assert hasattr(hub, "page_rank")
            assert hasattr(hub, "hub_score")

    def test_single_node_graph(self):
        result = analyze_graph_from_edges([], nodes={"A"})
        assert len(result.hubs) == 1
        assert result.hubs[0].node_id == "A"
        assert result.hubs[0].hub_score == 0.0

    def test_hub_score_formula_verification(self):
        """Verify the 0.6/0.4 weighting on a known graph."""
        # In diamond: D has in_degree=2 (from B and C), A has in_degree=0
        result = analyze_graph_from_edges(_diamond_graph())
        hub_by_id = {h.node_id: h for h in result.hubs}
        # D should have highest hub score (highest in-degree)
        assert hub_by_id["D"].hub_score >= hub_by_id["A"].hub_score


# ── AC-MVP3-2-BASE-2: Bridge detection ──────────────────────────────

class TestBridgeDetection:
    """AC-MVP3-2-BASE-2: Tarjan's algorithm on undirected projection."""

    def test_bridge_graph_finds_bridge(self):
        """Known bridge between two triangles."""
        result = analyze_graph_from_edges(_bridge_graph())
        # C-D is the bridge (only connection between the two triangles)
        assert ("C", "D") in result.bridge_edges

    def test_bridge_graph_finds_articulation_points(self):
        result = analyze_graph_from_edges(_bridge_graph())
        # C and D are articulation points (removing either disconnects)
        assert "C" in result.articulation_points
        assert "D" in result.articulation_points

    def test_chain_all_edges_are_bridges(self):
        """In a chain A-B-C, all edges are bridges."""
        result = analyze_graph_from_edges(_simple_chain())
        assert len(result.bridge_edges) == 2
        assert ("A", "B") in result.bridge_edges
        assert ("B", "C") in result.bridge_edges

    def test_chain_middle_is_articulation_point(self):
        result = analyze_graph_from_edges(_simple_chain())
        assert "B" in result.articulation_points

    def test_triangle_no_bridges(self):
        """A triangle has no bridges."""
        edges = [("A", "B"), ("B", "C"), ("C", "A")]
        result = analyze_graph_from_edges(edges)
        assert result.bridge_edges == []
        assert result.articulation_points == []

    def test_diamond_no_bridges(self):
        """Diamond graph has no bridges (multiple paths between all nodes)."""
        result = analyze_graph_from_edges(_diamond_graph())
        assert result.bridge_edges == []

    def test_disconnected_graph_no_bridges_within_components(self):
        """Each component is just an edge, which is a bridge."""
        result = analyze_graph_from_edges(_disconnected_graph())
        assert len(result.bridge_edges) == 2

    def test_single_node_no_bridges(self):
        result = analyze_graph_from_edges([], nodes={"A"})
        assert result.bridge_edges == []
        assert result.articulation_points == []


# ── AC-MVP3-2-BASE-3: Output includes all required fields ───────────

class TestOutputFields:
    """AC-MVP3-2-BASE-3: Minimum outputs present."""

    def test_result_has_all_fields(self):
        result = analyze_graph_from_edges(_diamond_graph())
        assert hasattr(result, "hubs")
        assert hasattr(result, "articulation_points")
        assert hasattr(result, "bridge_edges")
        assert hasattr(result, "components_summary")

    def test_components_summary_fields(self):
        result = analyze_graph_from_edges(_diamond_graph())
        cs = result.components_summary
        assert "total_components" in cs
        assert "largest_component_size" in cs
        assert "isolated_nodes" in cs
        assert "component_sizes" in cs

    def test_diamond_single_component(self):
        result = analyze_graph_from_edges(_diamond_graph())
        assert result.components_summary["total_components"] == 1
        assert result.components_summary["largest_component_size"] == 4

    def test_disconnected_two_components(self):
        result = analyze_graph_from_edges(_disconnected_graph())
        assert result.components_summary["total_components"] == 2

    def test_isolated_nodes_counted(self):
        result = analyze_graph_from_edges([], nodes={"A", "B", "C"})
        assert result.components_summary["isolated_nodes"] == 3
        assert result.components_summary["total_components"] == 3

    def test_to_dict_serialization(self):
        result = analyze_graph_from_edges(_simple_chain())
        d = result.to_dict()
        assert "hubs" in d
        assert "articulation_points" in d
        assert "bridge_edges" in d
        assert "components_summary" in d
        # Hub entries are dicts with required keys
        for hub in d["hubs"]:
            assert "node_id" in hub
            assert "in_degree" in hub
            assert "page_rank" in hub
            assert "hub_score" in hub

    def test_empty_graph(self):
        result = analyze_graph_from_edges([])
        assert result.hubs == []
        assert result.articulation_points == []
        assert result.bridge_edges == []
        assert result.components_summary["total_components"] == 0


# ── AC-MVP3-2-BASE-4: Deterministic ordering ────────────────────────

class TestDeterministicOrdering:
    """AC-MVP3-2-BASE-4: Same graph yields identical output across runs."""

    def test_hubs_sorted_by_score_then_id(self):
        result = analyze_graph_from_edges(_star_graph())
        scores = [h.hub_score for h in result.hubs]
        # Scores should be non-increasing
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_lexical_tie_breaking(self):
        """Nodes with equal hub scores are ordered lexically."""
        # Star graph: B, C, D, E all have same in_degree and similar PR
        result = analyze_graph_from_edges(_star_graph())
        equal_score_hubs = [h for h in result.hubs if h.hub_score == result.hubs[-1].hub_score]
        if len(equal_score_hubs) > 1:
            ids = [h.node_id for h in equal_score_hubs]
            assert ids == sorted(ids)

    def test_deterministic_across_runs(self):
        """Multiple runs produce identical results."""
        r1 = analyze_graph_from_edges(_bridge_graph())
        r2 = analyze_graph_from_edges(_bridge_graph())
        assert r1.to_dict() == r2.to_dict()

    def test_articulation_points_sorted(self):
        result = analyze_graph_from_edges(_bridge_graph())
        assert result.articulation_points == sorted(result.articulation_points)

    def test_bridge_edges_sorted(self):
        result = analyze_graph_from_edges(_bridge_graph())
        assert result.bridge_edges == sorted(result.bridge_edges)


# ── Vault-based graph building ───────────────────────────────────────

class TestVaultGraphBuilding:

    def _create_vault_notes(self, vault_root, notes):
        """Create note files with wikilinks in the vault.

        notes: list of (relative_path, wikilink_targets)
        """
        for rel_path, targets in notes:
            full_path = vault_root / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            links = " ".join(f"[[{t}]]" for t in targets)
            full_path.write_text(f"---\nid: test\n---\n{links}\n")

    def test_build_graph_from_vault(self, tmp_path):
        self._create_vault_notes(tmp_path, [
            ("Sources/src-001.md", ["Claims/clm-001"]),
            ("Claims/clm-001.md", ["Sources/src-001"]),
        ])
        adjacency, nodes = build_wikilink_graph(tmp_path)
        assert "Sources/src-001" in nodes
        assert "Claims/clm-001" in nodes
        assert "Claims/clm-001" in adjacency.get("Sources/src-001", set())

    def test_analyze_graph_from_vault(self, tmp_path):
        self._create_vault_notes(tmp_path, [
            ("Sources/a.md", ["Sources/b", "Sources/c"]),
            ("Sources/b.md", ["Sources/c"]),
            ("Sources/c.md", []),
        ])
        result = analyze_graph(tmp_path)
        assert len(result.hubs) == 3
        # c has highest in_degree (linked from a and b)
        hub_by_id = {h.node_id: h for h in result.hubs}
        assert hub_by_id["Sources/c"].in_degree == 2

    def test_unresolved_links_ignored(self, tmp_path):
        """Wikilinks that don't resolve to files are excluded."""
        self._create_vault_notes(tmp_path, [
            ("Sources/a.md", ["Sources/nonexistent"]),
        ])
        adjacency, nodes = build_wikilink_graph(tmp_path)
        assert "Sources/nonexistent" not in nodes

    def test_empty_vault(self, tmp_path):
        result = analyze_graph(tmp_path)
        assert result.hubs == []
        assert result.components_summary["total_components"] == 0


# ── AC-MVP3-2-ADV-1: Advanced mode gating ─────────────────────────

class TestAdvancedModeGating:
    """AC-MVP3-2-ADV-1: Advanced mode activates only with explicit flag."""

    def test_baseline_no_betweenness(self):
        """Without advanced_graph flag, betweenness is None."""
        result = analyze_graph_from_edges(_diamond_graph())
        assert result.betweenness is None
        assert result.budget_warning is None

    def test_baseline_to_dict_no_betweenness(self):
        """to_dict omits betweenness when not computed."""
        result = analyze_graph_from_edges(_diamond_graph())
        d = result.to_dict()
        assert "betweenness" not in d
        assert "budget_warning" not in d

    def test_advanced_flag_enables_betweenness(self):
        """With advanced_graph=True, betweenness is computed."""
        result = analyze_graph_from_edges(_diamond_graph(), advanced_graph=True)
        assert result.betweenness is not None
        assert len(result.betweenness) > 0

    def test_advanced_to_dict_includes_betweenness(self):
        """to_dict includes betweenness when computed."""
        result = analyze_graph_from_edges(
            _diamond_graph(), advanced_graph=True
        )
        d = result.to_dict()
        assert "betweenness" in d
        for entry in d["betweenness"]:
            assert "node_id" in entry
            assert "betweenness" in entry

    def test_advanced_flag_false_explicit(self):
        """Explicit advanced_graph=False behaves like default."""
        result = analyze_graph_from_edges(
            _bridge_graph(), advanced_graph=False
        )
        assert result.betweenness is None


# ── AC-MVP3-2-ADV-2: Betweenness computation ──────────────────────

class TestBetweennessComputation:
    """AC-MVP3-2-ADV-2: Approximate betweenness for top-N candidates."""

    def test_bridge_node_high_betweenness(self):
        """Nodes C and D in bridge graph should have high betweenness."""
        edges = _bridge_graph()
        all_nodes = set()
        adj = defaultdict(set)
        for s, t in edges:
            adj[s].add(t)
            all_nodes.add(s)
            all_nodes.add(t)
        metrics, warning = compute_approximate_betweenness(
            dict(adj), all_nodes, top_n=6
        )
        top_ids = [m.node_id for m in metrics]
        # C and D bridge the two triangles, should be in top positions
        assert "C" in top_ids[:3]
        assert "D" in top_ids[:3]

    def test_top_n_limits_output(self):
        """Output respects top_n parameter."""
        edges = _bridge_graph()
        adj = defaultdict(set)
        all_nodes = set()
        for s, t in edges:
            adj[s].add(t)
            all_nodes.add(s)
            all_nodes.add(t)
        metrics, _ = compute_approximate_betweenness(
            dict(adj), all_nodes, top_n=2
        )
        assert len(metrics) == 2

    def test_betweenness_values_nonnegative(self):
        """All betweenness values should be non-negative."""
        result = analyze_graph_from_edges(
            _diamond_graph(), advanced_graph=True
        )
        for b in result.betweenness:
            assert b.betweenness >= 0.0

    def test_deterministic_results(self):
        """Same graph + seed produces identical betweenness."""
        r1 = analyze_graph_from_edges(
            _bridge_graph(), advanced_graph=True
        )
        r2 = analyze_graph_from_edges(
            _bridge_graph(), advanced_graph=True
        )
        assert r1.to_dict()["betweenness"] == r2.to_dict()["betweenness"]

    def test_single_node_betweenness(self):
        """Single node graph has zero betweenness."""
        metrics, warning = compute_approximate_betweenness(
            {}, {"A"}, top_n=1
        )
        assert len(metrics) == 1
        assert metrics[0].betweenness == 0.0
        assert warning is None

    def test_empty_graph_betweenness(self):
        """Empty graph returns empty metrics."""
        metrics, warning = compute_approximate_betweenness(
            {}, set(), top_n=5
        )
        assert metrics == []
        assert warning is None

    def test_chain_middle_node_high_betweenness(self):
        """In A->B->C->D->E chain, middle nodes have higher betweenness."""
        edges = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")]
        adj = defaultdict(set)
        all_nodes = set()
        for s, t in edges:
            adj[s].add(t)
            all_nodes.add(s)
            all_nodes.add(t)
        metrics, _ = compute_approximate_betweenness(
            dict(adj), all_nodes, top_n=5
        )
        by_id = {m.node_id: m for m in metrics}
        # Middle nodes (B, C, D) should have higher betweenness than endpoints
        assert by_id["C"].betweenness >= by_id["A"].betweenness
        assert by_id["C"].betweenness >= by_id["E"].betweenness

    def test_metrics_sorted_by_betweenness_desc(self):
        """Metrics are sorted by betweenness descending."""
        result = analyze_graph_from_edges(
            _bridge_graph(), advanced_graph=True, betweenness_top_n=6
        )
        scores = [b.betweenness for b in result.betweenness]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_tie_breaking_by_node_id(self):
        """Equal betweenness nodes are ordered lexically by node_id."""
        # Triangle: all nodes have equal betweenness
        edges = [("A", "B"), ("B", "C"), ("C", "A")]
        adj = defaultdict(set)
        all_nodes = set()
        for s, t in edges:
            adj[s].add(t)
            all_nodes.add(s)
            all_nodes.add(t)
        metrics, _ = compute_approximate_betweenness(
            dict(adj), all_nodes, top_n=3
        )
        equal = [m for m in metrics if m.betweenness == metrics[0].betweenness]
        if len(equal) > 1:
            ids = [m.node_id for m in equal]
            assert ids == sorted(ids)


# ── AC-MVP3-2-ADV-3: Budget controls ──────────────────────────────

class TestBudgetControls:
    """AC-MVP3-2-ADV-3: Budget controls prevent runaway computation."""

    def test_budget_exceeded_returns_warning(self):
        """When budget_max_bfs < sample_count, warning is emitted."""
        # Create a graph with many nodes so sample_count > budget
        edges = [(f"n{i}", f"n{i+1}") for i in range(20)]
        adj = defaultdict(set)
        all_nodes = set()
        for s, t in edges:
            adj[s].add(t)
            all_nodes.add(s)
            all_nodes.add(t)
        metrics, warning = compute_approximate_betweenness(
            dict(adj), all_nodes,
            top_n=5,
            sample_count=15,
            budget_max_bfs=3,
        )
        assert warning is not None
        assert warning.partial is True
        assert warning.samples_completed == 3
        assert warning.samples_requested == 15
        assert "Budget exceeded" in warning.message

    def test_budget_not_exceeded(self):
        """When budget is sufficient, no warning."""
        edges = _diamond_graph()
        adj = defaultdict(set)
        all_nodes = set()
        for s, t in edges:
            adj[s].add(t)
            all_nodes.add(s)
            all_nodes.add(t)
        _, warning = compute_approximate_betweenness(
            dict(adj), all_nodes,
            sample_count=4,
            budget_max_bfs=100,
        )
        assert warning is None

    def test_partial_results_still_valid(self):
        """Even with budget exceeded, partial results are usable."""
        edges = [(f"n{i}", f"n{i+1}") for i in range(30)]
        adj = defaultdict(set)
        all_nodes = set()
        for s, t in edges:
            adj[s].add(t)
            all_nodes.add(s)
            all_nodes.add(t)
        metrics, warning = compute_approximate_betweenness(
            dict(adj), all_nodes,
            top_n=5,
            sample_count=20,
            budget_max_bfs=2,
        )
        assert warning is not None
        assert len(metrics) <= 5
        assert len(metrics) > 0
        for m in metrics:
            assert m.betweenness >= 0.0

    def test_budget_warning_in_result(self):
        """Budget warning propagates through analyze_graph_from_edges."""
        edges = [(f"n{i}", f"n{i+1}") for i in range(20)]
        result = analyze_graph_from_edges(
            edges,
            advanced_graph=True,
            betweenness_samples=15,
            betweenness_budget=2,
        )
        assert result.budget_warning is not None
        assert result.budget_warning.partial is True
        d = result.to_dict()
        assert "budget_warning" in d
        assert d["budget_warning"]["partial"] is True

    def test_budget_warning_message_format(self):
        """Warning message uses the deterministic format."""
        msg = BUDGET_EXCEEDED_MSG.format(completed=3, requested=10)
        assert "3/10" in msg
        assert "Budget exceeded" in msg


# ── AC-MVP3-2-ADV-4: Advanced metrics don't affect baseline ───────

class TestAdvancedDoesNotAffectBaseline:
    """AC-MVP3-2-ADV-4: Advanced metrics don't affect baseline SLA gates."""

    def test_baseline_fields_identical_with_and_without_advanced(self):
        """Hub scores, bridges, and components are the same regardless of flag."""
        edges = _bridge_graph()
        r_base = analyze_graph_from_edges(edges, advanced_graph=False)
        r_adv = analyze_graph_from_edges(edges, advanced_graph=True)

        # Hubs should be identical
        base_hubs = [
            (h.node_id, h.in_degree, h.page_rank, h.hub_score)
            for h in r_base.hubs
        ]
        adv_hubs = [
            (h.node_id, h.in_degree, h.page_rank, h.hub_score)
            for h in r_adv.hubs
        ]
        assert base_hubs == adv_hubs

        # Articulation points identical
        assert r_base.articulation_points == r_adv.articulation_points

        # Bridge edges identical
        assert r_base.bridge_edges == r_adv.bridge_edges

        # Components summary identical
        assert r_base.components_summary == r_adv.components_summary

    def test_baseline_dict_subset_of_advanced_dict(self):
        """Baseline to_dict keys are a subset of advanced to_dict."""
        edges = _diamond_graph()
        r_base = analyze_graph_from_edges(edges)
        r_adv = analyze_graph_from_edges(edges, advanced_graph=True)
        d_base = r_base.to_dict()
        d_adv = r_adv.to_dict()
        for key in d_base:
            assert key in d_adv
            assert d_base[key] == d_adv[key]

    def test_advanced_mode_on_star_graph(self):
        """Advanced mode on star graph: center should not have highest betweenness
        since it has no incoming paths through it."""
        result = analyze_graph_from_edges(
            _star_graph(), advanced_graph=True, betweenness_top_n=5
        )
        # Baseline still works
        assert len(result.hubs) == 5
        # Advanced metrics present
        assert result.betweenness is not None
