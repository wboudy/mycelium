"""Baseline graph analysis: hub scoring and bridge detection (MVP3-2).

Builds a canonical wikilink graph over Canonical Scope notes, computes
hub scores, and detects articulation points and bridges using Tarjan's
algorithm.

Spec reference: §12.4 TODO-Q-MVP3-2 Resolution (Option C)
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from mycelium.vault_layout import CANONICAL_DIRS
from mycelium.wikilink import extract_wikilinks


# ---------------------------------------------------------------------------
# Graph building
# ---------------------------------------------------------------------------

def build_wikilink_graph(vault_root: Path) -> dict[str, Any]:
    """Build a directed wikilink graph over Canonical Scope notes.

    Scans all Markdown files in Canonical Scope directories, extracts
    wikilinks, and resolves them to note IDs.

    Returns:
        A graph dict with:
        - ``nodes``: set of note IDs (vault-relative paths without .md).
        - ``edges``: list of (source, target) directed edges.
        - ``adjacency``: dict mapping node -> list of outbound targets.
        - ``in_degree``: dict mapping node -> inbound edge count.
    """
    nodes: set[str] = set()
    edges: list[tuple[str, str]] = []
    adjacency: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = defaultdict(int)

    # Index all canonical notes by basename (without .md) for resolution
    note_index: dict[str, str] = {}  # basename -> vault-relative id
    for scope_dir in CANONICAL_DIRS:
        scope_path = vault_root / scope_dir
        if not scope_path.exists():
            continue
        for md_file in scope_path.rglob("*.md"):
            rel = str(md_file.relative_to(vault_root))
            node_id = rel[:-3]  # strip .md
            nodes.add(node_id)
            in_degree.setdefault(node_id, 0)
            basename = md_file.stem
            note_index[basename] = node_id
            # Also index by full path without extension
            note_index[node_id] = node_id

    # Extract edges
    for scope_dir in CANONICAL_DIRS:
        scope_path = vault_root / scope_dir
        if not scope_path.exists():
            continue
        for md_file in scope_path.rglob("*.md"):
            rel = str(md_file.relative_to(vault_root))
            source_id = rel[:-3]
            content = md_file.read_text(encoding="utf-8")
            targets = extract_wikilinks(content)
            for target in targets:
                # Resolve target to a known node
                resolved = _resolve_to_node(target, note_index)
                if resolved is not None and resolved != source_id:
                    edges.append((source_id, resolved))
                    adjacency[source_id].append(resolved)
                    in_degree[resolved] = in_degree.get(resolved, 0) + 1

    return {
        "nodes": nodes,
        "edges": edges,
        "adjacency": dict(adjacency),
        "in_degree": dict(in_degree),
    }


def _resolve_to_node(
    target: str,
    note_index: dict[str, str],
) -> str | None:
    """Resolve a wikilink target to a graph node ID."""
    # Try direct match (e.g., "Sources/s-001")
    if target in note_index:
        return note_index[target]

    # Try basename match (e.g., "s-001")
    basename = target.rsplit("/", 1)[-1]
    if basename in note_index:
        return note_index[basename]

    return None


# ---------------------------------------------------------------------------
# PageRank (simplified power iteration)
# ---------------------------------------------------------------------------

def compute_pagerank(
    nodes: set[str],
    adjacency: dict[str, list[str]],
    *,
    damping: float = 0.85,
    iterations: int = 20,
) -> dict[str, float]:
    """Compute PageRank scores using power iteration.

    Args:
        nodes: Set of all node IDs.
        adjacency: Directed adjacency list (outbound edges).
        damping: Damping factor (default 0.85).
        iterations: Number of power iterations (default 20).

    Returns:
        Dict mapping node ID to PageRank score.
    """
    n = len(nodes)
    if n == 0:
        return {}

    rank: dict[str, float] = {node: 1.0 / n for node in nodes}
    base = (1.0 - damping) / n

    for _ in range(iterations):
        new_rank: dict[str, float] = {node: base for node in nodes}
        for node in nodes:
            out_links = adjacency.get(node, [])
            if not out_links:
                # Dangling node: distribute evenly
                share = damping * rank[node] / n
                for other in nodes:
                    new_rank[other] += share
            else:
                share = damping * rank[node] / len(out_links)
                for target in out_links:
                    if target in new_rank:
                        new_rank[target] += share
        rank = new_rank

    return rank


# ---------------------------------------------------------------------------
# Hub scoring
# ---------------------------------------------------------------------------

def _normalize_values(values: dict[str, float]) -> dict[str, float]:
    """Normalize values to [0, 1] range using max-normalization (v / max)."""
    if not values:
        return {}
    max_val = max(values.values())
    if max_val == 0:
        return {k: 0.0 for k in values}
    return {k: v / max_val for k, v in values.items()}


def compute_hub_scores(
    nodes: set[str],
    in_degree: dict[str, int],
    pagerank: dict[str, float],
) -> list[dict[str, Any]]:
    """Compute hub scores per spec formula.

    Formula: hub_score = 0.6 * norm(in_degree) + 0.4 * norm(page_rank)

    Args:
        nodes: Set of all node IDs.
        in_degree: Dict mapping node -> inbound edge count.
        pagerank: Dict mapping node -> PageRank score.

    Returns:
        List of hub records sorted by hub_score descending, then
        lexically by node ID (tie-break).
    """
    # Normalize
    in_deg_float = {n: float(in_degree.get(n, 0)) for n in nodes}
    norm_in_deg = _normalize_values(in_deg_float)
    norm_pr = _normalize_values(pagerank)

    hubs: list[dict[str, Any]] = []
    for node in nodes:
        hub_score = round(
            0.6 * norm_in_deg.get(node, 0.0) + 0.4 * norm_pr.get(node, 0.0),
            6,
        )
        hubs.append({
            "node_id": node,
            "in_degree": in_degree.get(node, 0),
            "page_rank": round(pagerank.get(node, 0.0), 6),
            "hub_score": hub_score,
        })

    # Sort by hub_score descending, then lexically by node_id
    hubs.sort(key=lambda h: (-h["hub_score"], h["node_id"]))
    return hubs


# ---------------------------------------------------------------------------
# Tarjan bridge/articulation point detection
# ---------------------------------------------------------------------------

def find_bridges_and_articulation_points(
    nodes: set[str],
    edges: list[tuple[str, str]],
) -> tuple[list[tuple[str, str]], list[str]]:
    """Find bridges and articulation points using Tarjan's algorithm.

    Operates on the undirected projection of the directed graph.

    Args:
        nodes: Set of all node IDs.
        edges: Directed edges (converted to undirected internally).

    Returns:
        Tuple of (bridge_edges, articulation_points):
        - bridge_edges: list of (u, v) pairs where u < v lexically.
        - articulation_points: sorted list of node IDs.
    """
    # Build undirected adjacency
    adj: dict[str, set[str]] = defaultdict(set)
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)

    disc: dict[str, int] = {}
    low: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    bridges: list[tuple[str, str]] = []
    aps: set[str] = set()
    timer = [0]

    def dfs(u: str) -> None:
        disc[u] = low[u] = timer[0]
        timer[0] += 1
        child_count = 0

        for v in sorted(adj.get(u, set())):
            if v not in disc:
                child_count += 1
                parent[v] = u
                dfs(v)
                low[u] = min(low[u], low[v])

                # Bridge check
                if low[v] > disc[u]:
                    bridge = tuple(sorted([u, v]))
                    bridges.append(bridge)  # type: ignore[arg-type]

                # Articulation point check
                if parent[u] is None and child_count > 1:
                    aps.add(u)
                if parent[u] is not None and low[v] >= disc[u]:
                    aps.add(u)
            elif v != parent.get(u):
                low[u] = min(low[u], disc[v])

    # Run DFS from each unvisited node (handles disconnected components)
    for node in sorted(nodes):
        if node not in disc:
            parent[node] = None
            dfs(node)

    # Sort outputs for determinism
    bridges.sort()
    return bridges, sorted(aps)


# ---------------------------------------------------------------------------
# Connected components
# ---------------------------------------------------------------------------

def find_connected_components(
    nodes: set[str],
    edges: list[tuple[str, str]],
) -> dict[str, Any]:
    """Find connected components in the undirected projection.

    Returns:
        Dict with:
        - ``count``: number of connected components.
        - ``sizes``: sorted list of component sizes (descending).
        - ``isolated_count``: number of single-node components.
    """
    adj: dict[str, set[str]] = defaultdict(set)
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)

    visited: set[str] = set()
    sizes: list[int] = []

    for node in sorted(nodes):
        if node in visited:
            continue
        # DFS (stack-based traversal)
        component: list[str] = []
        queue = [node]
        while queue:
            current = queue.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor in adj.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        sizes.append(len(component))

    sizes.sort(reverse=True)
    return {
        "count": len(sizes),
        "sizes": sizes,
        "isolated_count": sum(1 for s in sizes if s == 1),
    }


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

def analyze_graph(vault_root: Path) -> dict[str, Any]:
    """Run full baseline graph analysis over the canonical wikilink graph.

    Returns:
        Dict with minimum required outputs:
        - ``hubs``: list of hub records with in_degree, page_rank, hub_score.
        - ``articulation_points``: list of node IDs.
        - ``bridge_edges``: list of (u, v) edge pairs.
        - ``components_summary``: connected component statistics.
    """
    graph = build_wikilink_graph(vault_root)
    nodes = graph["nodes"]
    edges = graph["edges"]
    adjacency = graph["adjacency"]
    in_degree = graph["in_degree"]

    pagerank = compute_pagerank(nodes, adjacency)
    hubs = compute_hub_scores(nodes, in_degree, pagerank)
    bridge_edges, articulation_points = find_bridges_and_articulation_points(
        nodes, edges,
    )
    components_summary = find_connected_components(nodes, edges)

    return {
        "hubs": hubs,
        "articulation_points": articulation_points,
        "bridge_edges": bridge_edges,
        "components_summary": components_summary,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }
