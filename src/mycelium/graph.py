"""
Baseline graph analysis over canonical wikilink graph (MVP3-2).

Builds a directed graph from Obsidian wikilinks in Canonical Scope,
then computes:
  - Hub scores: hub_score = 0.6*norm(in_degree) + 0.4*norm(page_rank)
  - Bridge detection via Tarjan's algorithm on undirected projection
  - Components summary

Outputs are deterministic: same graph yields same output with lexical
tie-breaking by stable target id.

Spec reference: §12.4 TODO-Q-MVP3-2
"""

from __future__ import annotations

import random
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mycelium.vault_layout import CANONICAL_DIRS
from mycelium.wikilink import extract_wikilinks, resolve_wikilink


# ── Data model ────────────────────────────────────────────────────────

@dataclass
class HubMetrics:
    """Metrics for a single hub node."""

    node_id: str
    in_degree: int
    page_rank: float
    hub_score: float


@dataclass
class BetweennessMetrics:
    """Approximate betweenness centrality for a single node."""

    node_id: str
    betweenness: float


@dataclass
class BudgetExceededWarning:
    """Warning emitted when computation budget is exceeded."""

    message: str
    samples_completed: int
    samples_requested: int
    partial: bool


@dataclass
class GraphAnalysisResult:
    """Complete result of baseline graph analysis.

    Attributes:
        hubs: Hub nodes sorted by hub_score descending, then node_id.
        articulation_points: Nodes whose removal disconnects the graph.
        bridge_edges: Edges whose removal disconnects components.
        components_summary: Summary of connected components.
    """

    hubs: list[HubMetrics] = field(default_factory=list)
    articulation_points: list[str] = field(default_factory=list)
    bridge_edges: list[tuple[str, str]] = field(default_factory=list)
    components_summary: dict[str, Any] = field(default_factory=dict)
    betweenness: list[BetweennessMetrics] | None = None
    budget_warning: BudgetExceededWarning | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        d: dict[str, Any] = {
            "hubs": [
                {
                    "node_id": h.node_id,
                    "in_degree": h.in_degree,
                    "page_rank": h.page_rank,
                    "hub_score": h.hub_score,
                }
                for h in self.hubs
            ],
            "articulation_points": self.articulation_points,
            "bridge_edges": [list(e) for e in self.bridge_edges],
            "components_summary": self.components_summary,
        }
        if self.betweenness is not None:
            d["betweenness"] = [
                {"node_id": b.node_id, "betweenness": b.betweenness}
                for b in self.betweenness
            ]
        if self.budget_warning is not None:
            d["budget_warning"] = {
                "message": self.budget_warning.message,
                "samples_completed": self.budget_warning.samples_completed,
                "samples_requested": self.budget_warning.samples_requested,
                "partial": self.budget_warning.partial,
            }
        return d


# ── Graph building ───────────────────────────────────────────────────

def build_wikilink_graph(
    vault_root: Path,
) -> tuple[dict[str, set[str]], set[str]]:
    """Build a directed wikilink graph from Canonical Scope notes.

    Returns:
        Tuple of (adjacency_dict, all_nodes):
        - adjacency_dict maps source_id -> set of target_ids (outgoing edges).
        - all_nodes is the set of all known node ids.
    """
    adjacency: dict[str, set[str]] = defaultdict(set)
    all_nodes: set[str] = set()

    for scope_dir in CANONICAL_DIRS:
        scope_path = vault_root / scope_dir
        if not scope_path.exists():
            continue
        for md_file in sorted(scope_path.rglob("*.md")):
            # Node id is vault-relative path without extension
            rel = md_file.relative_to(vault_root)
            node_id = str(rel.with_suffix(""))
            all_nodes.add(node_id)

            content = md_file.read_text(encoding="utf-8")
            targets = extract_wikilinks(content)
            for target in targets:
                resolved = resolve_wikilink(target, vault_root)
                if resolved is not None:
                    target_rel = resolved.relative_to(vault_root)
                    target_id = str(target_rel.with_suffix(""))
                    adjacency[node_id].add(target_id)
                    all_nodes.add(target_id)

    return dict(adjacency), all_nodes


# ── PageRank ─────────────────────────────────────────────────────────

def _compute_page_rank(
    adjacency: dict[str, set[str]],
    all_nodes: set[str],
    *,
    damping: float = 0.85,
    iterations: int = 100,
    tolerance: float = 1e-8,
) -> dict[str, float]:
    """Compute PageRank scores for all nodes.

    Uses the standard power iteration method.
    """
    n = len(all_nodes)
    if n == 0:
        return {}

    node_list = sorted(all_nodes)  # deterministic ordering
    rank = {node: 1.0 / n for node in node_list}
    base = (1.0 - damping) / n

    # Build reverse adjacency for efficient computation
    reverse_adj: dict[str, list[str]] = defaultdict(list)
    out_degree: dict[str, int] = {}
    for node in node_list:
        targets = adjacency.get(node, set())
        out_degree[node] = len(targets)
        for target in targets:
            reverse_adj[target].append(node)

    for _ in range(iterations):
        new_rank: dict[str, float] = {}
        max_diff = 0.0

        for node in node_list:
            incoming_sum = sum(
                rank[src] / out_degree[src]
                for src in reverse_adj.get(node, [])
                if out_degree[src] > 0
            )
            new_rank[node] = base + damping * incoming_sum
            max_diff = max(max_diff, abs(new_rank[node] - rank[node]))

        rank = new_rank
        if max_diff < tolerance:
            break

    return rank


# ── Normalization ────────────────────────────────────────────────────

def _normalize(values: dict[str, float]) -> dict[str, float]:
    """Min-max normalize values to [0, 1]. Returns 0 for all if uniform."""
    if not values:
        return {}
    min_v = min(values.values())
    max_v = max(values.values())
    spread = max_v - min_v
    if spread == 0:
        return {k: 0.0 for k in values}
    return {k: (v - min_v) / spread for k, v in values.items()}


# ── Hub scoring ──────────────────────────────────────────────────────

def compute_hub_scores(
    adjacency: dict[str, set[str]],
    all_nodes: set[str],
) -> list[HubMetrics]:
    """Compute hub scores for all nodes.

    Formula: hub_score = 0.6*norm(in_degree) + 0.4*norm(page_rank)

    Returns list sorted by hub_score descending, then node_id ascending.
    """
    # Compute in-degrees
    in_degrees: dict[str, int] = {node: 0 for node in all_nodes}
    for source, targets in adjacency.items():
        for target in targets:
            if target in in_degrees:
                in_degrees[target] += 1

    # Compute PageRank
    page_ranks = _compute_page_rank(adjacency, all_nodes)

    # Normalize
    norm_in_deg = _normalize({k: float(v) for k, v in in_degrees.items()})
    norm_pr = _normalize(page_ranks)

    # Compute hub scores
    hubs: list[HubMetrics] = []
    for node in sorted(all_nodes):
        in_deg = in_degrees.get(node, 0)
        pr = page_ranks.get(node, 0.0)
        hub_score = 0.6 * norm_in_deg.get(node, 0.0) + 0.4 * norm_pr.get(node, 0.0)
        hubs.append(HubMetrics(
            node_id=node,
            in_degree=in_deg,
            page_rank=round(pr, 8),
            hub_score=round(hub_score, 8),
        ))

    # Sort by hub_score descending, then node_id ascending
    hubs.sort(key=lambda h: (-h.hub_score, h.node_id))
    return hubs


# ── Tarjan bridge detection ──────────────────────────────────────────

def find_bridges_and_articulation_points(
    adjacency: dict[str, set[str]],
    all_nodes: set[str],
) -> tuple[list[str], list[tuple[str, str]]]:
    """Find articulation points and bridge edges using Tarjan's algorithm.

    Operates on the undirected projection of the directed graph.

    Returns:
        Tuple of (articulation_points, bridge_edges), both sorted lexically.
    """
    # Build undirected adjacency
    undirected: dict[str, set[str]] = defaultdict(set)
    for source, targets in adjacency.items():
        for target in targets:
            undirected[source].add(target)
            undirected[target].add(source)
    # Include isolated nodes
    for node in all_nodes:
        if node not in undirected:
            undirected[node] = set()

    disc: dict[str, int] = {}
    low: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    ap_set: set[str] = set()
    bridges: list[tuple[str, str]] = []
    timer = [0]

    def _dfs(u: str) -> None:
        disc[u] = low[u] = timer[0]
        timer[0] += 1
        child_count = 0

        for v in sorted(undirected[u]):  # deterministic ordering
            if v not in disc:
                child_count += 1
                parent[v] = u
                _dfs(v)
                low[u] = min(low[u], low[v])

                # u is an articulation point if:
                # 1. u is root and has 2+ children
                # 2. u is not root and low[v] >= disc[u]
                if parent[u] is None and child_count > 1:
                    ap_set.add(u)
                if parent[u] is not None and low[v] >= disc[u]:
                    ap_set.add(u)

                # (u, v) is a bridge if low[v] > disc[u]
                if low[v] > disc[u]:
                    edge = tuple(sorted([u, v]))
                    bridges.append(edge)  # type: ignore[arg-type]
            elif v != parent.get(u):
                low[u] = min(low[u], disc[v])

    # Process all nodes (handles disconnected components)
    for node in sorted(all_nodes):
        if node not in disc:
            parent[node] = None
            _dfs(node)

    art_points = sorted(ap_set)
    bridge_edges = sorted(set(bridges))
    return art_points, bridge_edges


# ── Approximate betweenness centrality ─────────────────────────────

BUDGET_EXCEEDED_MSG = (
    "Budget exceeded: completed {completed}/{requested} samples. "
    "Returning partial results."
)


def compute_approximate_betweenness(
    adjacency: dict[str, set[str]],
    all_nodes: set[str],
    *,
    top_n: int = 10,
    sample_count: int = 100,
    budget_max_bfs: int = 200,
    seed: int = 42,
) -> tuple[list[BetweennessMetrics], BudgetExceededWarning | None]:
    """Compute approximate betweenness centrality via sampled shortest paths.

    Uses BFS from a random sample of source nodes on the undirected projection
    to estimate betweenness centrality. Returns top-N candidates sorted by
    betweenness descending, then node_id ascending.

    Budget controls: if the number of BFS traversals exceeds budget_max_bfs,
    computation stops and partial results are returned with a warning.

    Args:
        adjacency: Directed adjacency dict.
        all_nodes: Set of all node ids.
        top_n: Number of top candidates to return.
        sample_count: Number of source nodes to sample for BFS.
        budget_max_bfs: Maximum BFS traversals before budget cutoff.
        seed: Random seed for deterministic sampling.

    Returns:
        Tuple of (top_n_metrics, budget_warning_or_none).
    """
    if not all_nodes:
        return [], None

    # Build undirected adjacency
    undirected: dict[str, set[str]] = defaultdict(set)
    for source, targets in adjacency.items():
        for target in targets:
            undirected[source].add(target)
            undirected[target].add(source)
    for node in all_nodes:
        if node not in undirected:
            undirected[node] = set()

    node_list = sorted(all_nodes)
    n = len(node_list)

    # Determine sample sources
    rng = random.Random(seed)
    actual_samples = min(sample_count, n)
    sources = rng.sample(node_list, actual_samples)

    betweenness: dict[str, float] = {node: 0.0 for node in node_list}
    budget_warning: BudgetExceededWarning | None = None
    bfs_count = 0
    completed_samples = 0

    for source in sources:
        if bfs_count >= budget_max_bfs:
            budget_warning = BudgetExceededWarning(
                message=BUDGET_EXCEEDED_MSG.format(
                    completed=completed_samples,
                    requested=actual_samples,
                ),
                samples_completed=completed_samples,
                samples_requested=actual_samples,
                partial=True,
            )
            break

        # BFS from source to compute shortest paths and dependencies
        pred: dict[str, list[str]] = {node: [] for node in node_list}
        sigma: dict[str, int] = {node: 0 for node in node_list}
        sigma[source] = 1
        dist: dict[str, int] = {node: -1 for node in node_list}
        dist[source] = 0
        queue: deque[str] = deque([source])
        stack: list[str] = []

        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in sorted(undirected[v]):
                # First visit
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                # Shortest path via v
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)

        bfs_count += 1
        completed_samples += 1

        # Back-propagation of dependencies
        delta: dict[str, float] = {node: 0.0 for node in node_list}
        while stack:
            w = stack.pop()
            for v in pred[w]:
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != source:
                betweenness[w] += delta[w]

    # Normalize by number of completed samples (approximate scaling)
    if completed_samples > 0 and n > 2:
        scale = n / completed_samples
        for node in node_list:
            betweenness[node] *= scale

    # Sort by betweenness descending, then node_id ascending
    ranked = sorted(node_list, key=lambda x: (-betweenness[x], x))
    top = ranked[:top_n]

    metrics = [
        BetweennessMetrics(
            node_id=node,
            betweenness=round(betweenness[node], 8),
        )
        for node in top
    ]

    return metrics, budget_warning


# ── Connected components ─────────────────────────────────────────────

def _compute_components(
    adjacency: dict[str, set[str]],
    all_nodes: set[str],
) -> dict[str, Any]:
    """Compute connected components summary on undirected projection."""
    # Build undirected adjacency
    undirected: dict[str, set[str]] = defaultdict(set)
    for source, targets in adjacency.items():
        for target in targets:
            undirected[source].add(target)
            undirected[target].add(source)
    for node in all_nodes:
        if node not in undirected:
            undirected[node] = set()

    visited: set[str] = set()
    components: list[list[str]] = []

    for node in sorted(all_nodes):
        if node in visited:
            continue
        # BFS
        component: list[str] = []
        bfs_queue: deque[str] = deque([node])
        while bfs_queue:
            current = bfs_queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor in sorted(undirected[current]):
                if neighbor not in visited:
                    bfs_queue.append(neighbor)
        components.append(sorted(component))

    return {
        "total_components": len(components),
        "largest_component_size": max(len(c) for c in components) if components else 0,
        "isolated_nodes": sum(1 for c in components if len(c) == 1),
        "component_sizes": sorted([len(c) for c in components], reverse=True),
    }


# ── Main analysis entry point ────────────────────────────────────────

def analyze_graph(
    vault_root: Path,
    *,
    advanced_graph: bool = False,
    betweenness_top_n: int = 10,
    betweenness_samples: int = 100,
    betweenness_budget: int = 200,
) -> GraphAnalysisResult:
    """Run baseline graph analysis on the canonical wikilink graph.

    Builds the graph, computes hub scores, finds bridges and articulation
    points, and returns a deterministic result.

    Args:
        vault_root: Absolute path to the vault root.
        advanced_graph: If True, also compute approximate betweenness centrality.
        betweenness_top_n: Number of top betweenness candidates to return.
        betweenness_samples: Number of BFS source samples for betweenness.
        betweenness_budget: Maximum BFS traversals before budget cutoff.

    Returns:
        GraphAnalysisResult with all minimum required outputs.
    """
    adjacency, all_nodes = build_wikilink_graph(vault_root)
    hubs = compute_hub_scores(adjacency, all_nodes)
    art_points, bridges = find_bridges_and_articulation_points(adjacency, all_nodes)
    components = _compute_components(adjacency, all_nodes)

    betweenness = None
    budget_warning = None
    if advanced_graph:
        betweenness, budget_warning = compute_approximate_betweenness(
            adjacency, all_nodes,
            top_n=betweenness_top_n,
            sample_count=betweenness_samples,
            budget_max_bfs=betweenness_budget,
        )

    return GraphAnalysisResult(
        hubs=hubs,
        articulation_points=art_points,
        bridge_edges=bridges,
        components_summary=components,
        betweenness=betweenness,
        budget_warning=budget_warning,
    )


def analyze_graph_from_edges(
    edges: list[tuple[str, str]],
    nodes: set[str] | None = None,
    *,
    advanced_graph: bool = False,
    betweenness_top_n: int = 10,
    betweenness_samples: int = 100,
    betweenness_budget: int = 200,
) -> GraphAnalysisResult:
    """Run analysis on an explicit edge list (useful for testing).

    Args:
        edges: List of (source, target) directed edges.
        nodes: Optional explicit node set. If None, inferred from edges.
        advanced_graph: If True, also compute approximate betweenness centrality.
        betweenness_top_n: Number of top betweenness candidates to return.
        betweenness_samples: Number of BFS source samples for betweenness.
        betweenness_budget: Maximum BFS traversals before budget cutoff.

    Returns:
        GraphAnalysisResult.
    """
    adjacency: dict[str, set[str]] = defaultdict(set)
    all_nodes: set[str] = set()

    for source, target in edges:
        adjacency[source].add(target)
        all_nodes.add(source)
        all_nodes.add(target)

    if nodes is not None:
        all_nodes |= nodes

    adj_dict = dict(adjacency)
    hubs = compute_hub_scores(adj_dict, all_nodes)
    art_points, bridges = find_bridges_and_articulation_points(adj_dict, all_nodes)
    components = _compute_components(adj_dict, all_nodes)

    betweenness = None
    budget_warning = None
    if advanced_graph:
        betweenness, budget_warning = compute_approximate_betweenness(
            adj_dict, all_nodes,
            top_n=betweenness_top_n,
            sample_count=betweenness_samples,
            budget_max_bfs=betweenness_budget,
        )

    return GraphAnalysisResult(
        hubs=hubs,
        articulation_points=art_points,
        bridge_edges=bridges,
        components_summary=components,
        betweenness=betweenness,
        budget_warning=budget_warning,
    )
