"""Tests for baseline graph analysis (MVP3-2).

Verifies acceptance criteria:
  AC-MVP3-2-BASE-1: Hub score formula matches spec.
  AC-MVP3-2-BASE-2: Bridge detection uses Tarjan's on undirected projection.
  AC-MVP3-2-BASE-3: Output includes all minimum required fields.
  AC-MVP3-2-BASE-4: Deterministic ordering via lexical tie-break.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mycelium.graph_analysis import (
    analyze_graph,
    build_wikilink_graph,
    compute_hub_scores,
    compute_pagerank,
    find_bridges_and_articulation_points,
    find_connected_components,
)
from mycelium.wikilink import extract_wikilinks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_note(vault: Path, rel_path: str, content: str) -> None:
    full = vault / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _build_triangle(vault: Path) -> None:
    """Create a triangle graph: A -> B -> C -> A."""
    _write_note(vault, "Sources/a.md", "See [[Sources/b]].")
    _write_note(vault, "Sources/b.md", "See [[Sources/c]].")
    _write_note(vault, "Sources/c.md", "See [[Sources/a]].")


def _build_linear(vault: Path) -> None:
    """Create a linear graph: A -> B -> C (bridge between each)."""
    _write_note(vault, "Sources/a.md", "See [[Sources/b]].")
    _write_note(vault, "Sources/b.md", "See [[Sources/c]].")
    _write_note(vault, "Sources/c.md", "Content.")


def _build_star(vault: Path) -> None:
    """Create a star graph: center -> {a, b, c, d}."""
    _write_note(
        vault, "Sources/center.md",
        "See [[Sources/a]] [[Sources/b]] [[Sources/c]] [[Sources/d]].",
    )
    _write_note(vault, "Sources/a.md", "Content.")
    _write_note(vault, "Sources/b.md", "Content.")
    _write_note(vault, "Sources/c.md", "Content.")
    _write_note(vault, "Sources/d.md", "Content.")


# ─── Graph building ──────────────────────────────────────────────────────

class TestBuildWikilinkGraph:

    def test_empty_vault(self, tmp_path: Path):
        graph = build_wikilink_graph(tmp_path)
        assert graph["nodes"] == set()
        assert graph["edges"] == []

    def test_single_note_no_links(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/a.md", "No links.")
        graph = build_wikilink_graph(tmp_path)
        assert graph["nodes"] == {"Sources/a"}
        assert graph["edges"] == []

    def test_directed_edges(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/a.md", "See [[Sources/b]].")
        _write_note(tmp_path, "Sources/b.md", "Content.")
        graph = build_wikilink_graph(tmp_path)
        assert ("Sources/a", "Sources/b") in graph["edges"]
        assert graph["in_degree"]["Sources/b"] == 1
        assert graph["in_degree"].get("Sources/a", 0) == 0

    def test_self_links_excluded(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/a.md", "See [[Sources/a]].")
        graph = build_wikilink_graph(tmp_path)
        assert graph["edges"] == []

    def test_cross_scope_links(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/s-001.md", "See [[Claims/c-001]].")
        _write_note(tmp_path, "Claims/c-001.md", "Content.")
        graph = build_wikilink_graph(tmp_path)
        assert ("Sources/s-001", "Claims/c-001") in graph["edges"]

    def test_draft_scope_excluded(self, tmp_path: Path):
        _write_note(tmp_path, "Inbox/Sources/draft.md", "See [[Sources/a]].")
        _write_note(tmp_path, "Sources/a.md", "Content.")
        graph = build_wikilink_graph(tmp_path)
        # Draft notes should not be in the graph
        assert "Inbox/Sources/draft" not in graph["nodes"]

    def test_basename_resolution(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/s-001.md", "See [[c-001]].")
        _write_note(tmp_path, "Claims/c-001.md", "Content.")
        graph = build_wikilink_graph(tmp_path)
        assert ("Sources/s-001", "Claims/c-001") in graph["edges"]


# ─── PageRank ────────────────────────────────────────────────────────────

class TestPageRank:

    def test_empty_graph(self):
        result = compute_pagerank(set(), {})
        assert result == {}

    def test_single_node(self):
        result = compute_pagerank({"a"}, {})
        assert abs(result["a"] - 1.0) < 0.01

    def test_two_nodes_mutual(self):
        nodes = {"a", "b"}
        adj = {"a": ["b"], "b": ["a"]}
        result = compute_pagerank(nodes, adj)
        # Equal PageRank for symmetric graph
        assert abs(result["a"] - result["b"]) < 0.01

    def test_star_graph_center_higher(self):
        nodes = {"center", "a", "b", "c"}
        adj = {"a": ["center"], "b": ["center"], "c": ["center"]}
        result = compute_pagerank(nodes, adj)
        assert result["center"] > result["a"]


# ─── AC-MVP3-2-BASE-1: Hub score formula ─────────────────────────────────

class TestHubScores:

    def test_hub_score_formula(self):
        """AC-MVP3-2-BASE-1: hub_score = 0.6*norm(in_degree) + 0.4*norm(page_rank)."""
        nodes = {"a", "b"}
        in_degree = {"a": 10, "b": 5}
        pagerank = {"a": 0.8, "b": 0.4}

        hubs = compute_hub_scores(nodes, in_degree, pagerank)
        hub_a = next(h for h in hubs if h["node_id"] == "a")
        hub_b = next(h for h in hubs if h["node_id"] == "b")

        # norm(in_degree): a=1.0, b=0.5
        # norm(page_rank): a=1.0, b=0.5
        # hub_a = 0.6*1.0 + 0.4*1.0 = 1.0
        # hub_b = 0.6*0.5 + 0.4*0.5 = 0.5
        assert hub_a["hub_score"] == 1.0
        assert hub_b["hub_score"] == 0.5

    def test_hub_sorted_by_score_desc(self):
        nodes = {"a", "b", "c"}
        in_degree = {"a": 1, "b": 3, "c": 2}
        pagerank = {"a": 0.1, "b": 0.5, "c": 0.3}
        hubs = compute_hub_scores(nodes, in_degree, pagerank)
        scores = [h["hub_score"] for h in hubs]
        assert scores == sorted(scores, reverse=True)

    def test_hub_lexical_tiebreak(self):
        """AC-MVP3-2-BASE-4: Tie-break ordering is lexical by node_id."""
        nodes = {"a", "b", "c"}
        in_degree = {"a": 5, "b": 5, "c": 5}
        pagerank = {"a": 0.3, "b": 0.3, "c": 0.3}
        hubs = compute_hub_scores(nodes, in_degree, pagerank)
        ids = [h["node_id"] for h in hubs]
        assert ids == ["a", "b", "c"]

    def test_hub_includes_required_metrics(self):
        nodes = {"a"}
        in_degree = {"a": 3}
        pagerank = {"a": 0.5}
        hubs = compute_hub_scores(nodes, in_degree, pagerank)
        h = hubs[0]
        assert "in_degree" in h
        assert "page_rank" in h
        assert "hub_score" in h
        assert "node_id" in h

    def test_empty_graph(self):
        hubs = compute_hub_scores(set(), {}, {})
        assert hubs == []

    def test_zero_in_degree(self):
        nodes = {"a", "b"}
        in_degree = {"a": 0, "b": 0}
        pagerank = {"a": 0.5, "b": 0.5}
        hubs = compute_hub_scores(nodes, in_degree, pagerank)
        for h in hubs:
            # norm(in_degree) = 0/0 -> 0, norm(pr) = 1.0
            assert h["hub_score"] == round(0.4 * 1.0, 6)


# ─── AC-MVP3-2-BASE-2: Bridge detection via Tarjan ──────────────────────

class TestBridgeDetection:

    def test_triangle_no_bridges(self):
        """Triangle graph has no bridges or articulation points."""
        nodes = {"a", "b", "c"}
        edges = [("a", "b"), ("b", "c"), ("c", "a")]
        bridges, aps = find_bridges_and_articulation_points(nodes, edges)
        assert bridges == []
        assert aps == []

    def test_linear_chain_bridges(self):
        """Linear chain a-b-c has bridges a-b and b-c, articulation point b."""
        nodes = {"a", "b", "c"}
        edges = [("a", "b"), ("b", "c")]
        bridges, aps = find_bridges_and_articulation_points(nodes, edges)
        assert ("a", "b") in bridges
        assert ("b", "c") in bridges
        assert "b" in aps

    def test_bridge_edge_sorted(self):
        """Bridge edges are (u, v) with u < v lexically."""
        nodes = {"x", "a"}
        edges = [("x", "a")]
        bridges, _ = find_bridges_and_articulation_points(nodes, edges)
        assert bridges == [("a", "x")]

    def test_disconnected_components(self):
        """Disconnected nodes: no bridges, no articulation points."""
        nodes = {"a", "b", "c"}
        edges: list[tuple[str, str]] = []
        bridges, aps = find_bridges_and_articulation_points(nodes, edges)
        assert bridges == []
        assert aps == []

    def test_star_graph_center_is_articulation(self):
        """Star graph: center is articulation point, all edges are bridges."""
        nodes = {"center", "a", "b", "c"}
        edges = [("center", "a"), ("center", "b"), ("center", "c")]
        bridges, aps = find_bridges_and_articulation_points(nodes, edges)
        assert "center" in aps
        assert len(bridges) == 3

    def test_known_bridge_fixture(self):
        """AC-MVP3-2-BASE-2: Fixture with known bridges produces correct output.

        Graph: a-b-c-d with extra edge a-c (forming triangle a-b-c).
        Bridge: c-d. Articulation point: c.
        """
        nodes = {"a", "b", "c", "d"}
        edges = [("a", "b"), ("b", "c"), ("a", "c"), ("c", "d")]
        bridges, aps = find_bridges_and_articulation_points(nodes, edges)
        assert ("c", "d") in bridges
        assert len(bridges) == 1
        assert "c" in aps

    def test_empty_graph(self):
        bridges, aps = find_bridges_and_articulation_points(set(), [])
        assert bridges == []
        assert aps == []


# ─── Connected components ────────────────────────────────────────────────

class TestConnectedComponents:

    def test_single_component(self):
        nodes = {"a", "b", "c"}
        edges = [("a", "b"), ("b", "c")]
        result = find_connected_components(nodes, edges)
        assert result["count"] == 1
        assert result["sizes"] == [3]
        assert result["isolated_count"] == 0

    def test_two_components(self):
        nodes = {"a", "b", "c", "d"}
        edges = [("a", "b"), ("c", "d")]
        result = find_connected_components(nodes, edges)
        assert result["count"] == 2
        assert result["sizes"] == [2, 2]

    def test_isolated_nodes(self):
        nodes = {"a", "b", "c"}
        edges: list[tuple[str, str]] = []
        result = find_connected_components(nodes, edges)
        assert result["count"] == 3
        assert result["isolated_count"] == 3

    def test_empty(self):
        result = find_connected_components(set(), [])
        assert result["count"] == 0


# ─── AC-MVP3-2-BASE-3 / AC-MVP3-2-BASE-4: Full analysis ─────────────────

class TestAnalyzeGraph:

    def test_minimum_output_fields(self, tmp_path: Path):
        """AC-MVP3-2-BASE-3: Output includes hubs, articulation_points,
        bridge_edges, components_summary."""
        _build_triangle(tmp_path)
        result = analyze_graph(tmp_path)
        assert "hubs" in result
        assert "articulation_points" in result
        assert "bridge_edges" in result
        assert "components_summary" in result

    def test_deterministic_output(self, tmp_path: Path):
        """AC-MVP3-2-BASE-4: Same graph yields identical output across runs."""
        _build_triangle(tmp_path)
        r1 = analyze_graph(tmp_path)
        r2 = analyze_graph(tmp_path)
        assert r1 == r2

    def test_empty_vault(self, tmp_path: Path):
        result = analyze_graph(tmp_path)
        assert result["hubs"] == []
        assert result["articulation_points"] == []
        assert result["bridge_edges"] == []
        assert result["node_count"] == 0

    def test_star_graph_analysis(self, tmp_path: Path):
        _build_star(tmp_path)
        result = analyze_graph(tmp_path)

        # Center should have highest hub_score (most outbound -> most in_degree for targets)
        assert result["node_count"] == 5
        assert result["edge_count"] == 4
        assert "Sources/center" in result["articulation_points"]

    def test_linear_chain_analysis(self, tmp_path: Path):
        _build_linear(tmp_path)
        result = analyze_graph(tmp_path)

        assert len(result["bridge_edges"]) == 2
        assert "Sources/b" in result["articulation_points"]

    def test_hub_metrics_present(self, tmp_path: Path):
        _build_triangle(tmp_path)
        result = analyze_graph(tmp_path)
        for hub in result["hubs"]:
            assert "in_degree" in hub
            assert "page_rank" in hub
            assert "hub_score" in hub

    def test_components_summary_present(self, tmp_path: Path):
        _build_triangle(tmp_path)
        result = analyze_graph(tmp_path)
        cs = result["components_summary"]
        assert "count" in cs
        assert "sizes" in cs
        assert "isolated_count" in cs

    def test_cross_scope_graph(self, tmp_path: Path):
        _write_note(tmp_path, "Sources/s-001.md", "See [[Claims/c-001]].")
        _write_note(tmp_path, "Claims/c-001.md", "See [[Concepts/con-001]].")
        _write_note(tmp_path, "Concepts/con-001.md", "Content.")
        result = analyze_graph(tmp_path)
        assert result["node_count"] == 3
        assert result["edge_count"] == 2
