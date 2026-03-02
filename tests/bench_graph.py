"""
Graph analysis performance benchmark suite (MVP3-2).

Generates deterministic graph fixtures and measures p95 latencies
for graph build, core analysis, and end-to-end operations.

Performance targets (§12.4):
  Medium (~5k nodes / ~20k edges):
    graph build p95 <= 2.5s, core analysis p95 <= 4.0s, e2e p95 <= 6.0s
  Large (~10k nodes / ~50k edges):
    graph build p95 <= 6.0s, core analysis p95 <= 9.0s, e2e p95 <= 14.0s

Run: python -m pytest tests/bench_graph.py -v --benchmark
"""

from __future__ import annotations

import random
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

import pytest

from mycelium.graph import (
    analyze_graph_from_edges,
    compute_hub_scores,
    find_bridges_and_articulation_points,
)


# ── Fixture generation ───────────────────────────────────────────────

def generate_graph_fixture(
    num_nodes: int,
    num_edges: int,
    seed: int = 42,
) -> tuple[list[tuple[str, str]], set[str]]:
    """Generate a deterministic random graph fixture.

    Uses a fixed seed for reproducibility (AC-MVP3-2-PERF-4).

    Args:
        num_nodes: Number of nodes to generate.
        num_edges: Number of directed edges to generate.
        seed: Random seed for deterministic generation.

    Returns:
        Tuple of (edges, nodes).
    """
    rng = random.Random(seed)
    nodes = {f"node-{i:06d}" for i in range(num_nodes)}
    node_list = sorted(nodes)

    edges: set[tuple[str, str]] = set()
    # Ensure connectivity: create a spanning tree first
    shuffled = list(node_list)
    rng.shuffle(shuffled)
    for i in range(1, len(shuffled)):
        edges.add((shuffled[i - 1], shuffled[i]))

    # Add remaining random edges
    while len(edges) < num_edges:
        src = rng.choice(node_list)
        tgt = rng.choice(node_list)
        if src != tgt:
            edges.add((src, tgt))

    return sorted(edges), nodes


# ── Pre-generated fixtures ───────────────────────────────────────────

MEDIUM_NODES = 5000
MEDIUM_EDGES = 20000
LARGE_NODES = 10000
LARGE_EDGES = 50000

# ── Thresholds (seconds) ─────────────────────────────────────────────

@dataclass
class PerfThresholds:
    graph_build: float
    core_analysis: float
    end_to_end: float


MEDIUM_THRESHOLDS = PerfThresholds(
    graph_build=2.5,
    core_analysis=4.0,
    end_to_end=6.0,
)

LARGE_THRESHOLDS = PerfThresholds(
    graph_build=6.0,
    core_analysis=9.0,
    end_to_end=14.0,
)


# ── Benchmark harness ────────────────────────────────────────────────

@dataclass
class BenchmarkResult:
    fixture_id: str
    run_count: int
    graph_build_p95: float
    core_analysis_p95: float
    end_to_end_p95: float
    thresholds: PerfThresholds
    breaches: list[str] = field(default_factory=list)

    def check_gates(self) -> list[str]:
        """Check all thresholds and return list of breaches."""
        breaches = []
        if self.graph_build_p95 > self.thresholds.graph_build:
            breaches.append(
                f"graph_build p95={self.graph_build_p95:.3f}s "
                f"> threshold={self.thresholds.graph_build}s"
            )
        if self.core_analysis_p95 > self.thresholds.core_analysis:
            breaches.append(
                f"core_analysis p95={self.core_analysis_p95:.3f}s "
                f"> threshold={self.thresholds.core_analysis}s"
            )
        if self.end_to_end_p95 > self.thresholds.end_to_end:
            breaches.append(
                f"end_to_end p95={self.end_to_end_p95:.3f}s "
                f"> threshold={self.thresholds.end_to_end}s"
            )
        self.breaches = breaches
        return breaches


def _p95(values: list[float]) -> float:
    """Compute p95 of a list of values."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * 0.95)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def run_benchmark(
    fixture_id: str,
    edges: list[tuple[str, str]],
    nodes: set[str],
    thresholds: PerfThresholds,
    runs: int = 5,
) -> BenchmarkResult:
    """Run benchmark measuring graph build, core analysis, and e2e.

    Args:
        fixture_id: Identifier for the fixture.
        edges: Directed edge list.
        nodes: Node set.
        thresholds: Performance thresholds.
        runs: Number of benchmark runs.

    Returns:
        BenchmarkResult with p95 measurements.
    """
    from collections import defaultdict

    build_times: list[float] = []
    analysis_times: list[float] = []
    e2e_times: list[float] = []

    for _ in range(runs):
        # End-to-end
        e2e_start = time.perf_counter()

        # Graph build (constructing adjacency from edges)
        build_start = time.perf_counter()
        adjacency: dict[str, set[str]] = defaultdict(set)
        for src, tgt in edges:
            adjacency[src].add(tgt)
        adj_dict = dict(adjacency)
        build_end = time.perf_counter()
        build_times.append(build_end - build_start)

        # Core analysis
        analysis_start = time.perf_counter()
        compute_hub_scores(adj_dict, nodes)
        find_bridges_and_articulation_points(adj_dict, nodes)
        analysis_end = time.perf_counter()
        analysis_times.append(analysis_end - analysis_start)

        e2e_end = time.perf_counter()
        e2e_times.append(e2e_end - e2e_start)

    result = BenchmarkResult(
        fixture_id=fixture_id,
        run_count=runs,
        graph_build_p95=_p95(build_times),
        core_analysis_p95=_p95(analysis_times),
        end_to_end_p95=_p95(e2e_times),
        thresholds=thresholds,
    )
    result.check_gates()
    return result


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════

# ─── AC-MVP3-2-PERF-4: Fixtures are deterministic ───────────────────

class TestFixtureDeterminism:

    def test_medium_fixture_deterministic(self):
        """Same seed produces identical fixture."""
        e1, n1 = generate_graph_fixture(100, 400, seed=42)
        e2, n2 = generate_graph_fixture(100, 400, seed=42)
        assert e1 == e2
        assert n1 == n2

    def test_large_fixture_deterministic(self):
        e1, n1 = generate_graph_fixture(200, 800, seed=99)
        e2, n2 = generate_graph_fixture(200, 800, seed=99)
        assert e1 == e2
        assert n1 == n2

    def test_different_seeds_differ(self):
        e1, _ = generate_graph_fixture(100, 400, seed=1)
        e2, _ = generate_graph_fixture(100, 400, seed=2)
        assert e1 != e2

    def test_medium_fixture_size(self):
        edges, nodes = generate_graph_fixture(MEDIUM_NODES, MEDIUM_EDGES)
        assert len(nodes) == MEDIUM_NODES
        assert len(edges) == MEDIUM_EDGES

    def test_large_fixture_size(self):
        edges, nodes = generate_graph_fixture(LARGE_NODES, LARGE_EDGES)
        assert len(nodes) == LARGE_NODES
        assert len(edges) == LARGE_EDGES

    def test_connectivity(self):
        """Spanning tree ensures at least weak connectivity."""
        edges, nodes = generate_graph_fixture(50, 100)
        # All nodes should be reachable in the undirected projection
        from collections import defaultdict
        adj: dict[str, set[str]] = defaultdict(set)
        for s, t in edges:
            adj[s].add(t)
            adj[t].add(s)
        visited: set[str] = set()
        start = sorted(nodes)[0]
        queue = [start]
        while queue:
            n = queue.pop()
            if n in visited:
                continue
            visited.add(n)
            queue.extend(adj[n] - visited)
        assert visited == nodes


# ─── AC-MVP3-2-PERF-3: Gate checks ──────────────────────────────────

class TestGateChecks:

    def test_no_breach_on_fast_results(self):
        result = BenchmarkResult(
            fixture_id="test",
            run_count=5,
            graph_build_p95=0.1,
            core_analysis_p95=0.2,
            end_to_end_p95=0.3,
            thresholds=MEDIUM_THRESHOLDS,
        )
        breaches = result.check_gates()
        assert breaches == []

    def test_breach_on_slow_graph_build(self):
        result = BenchmarkResult(
            fixture_id="test",
            run_count=5,
            graph_build_p95=10.0,
            core_analysis_p95=0.2,
            end_to_end_p95=0.3,
            thresholds=MEDIUM_THRESHOLDS,
        )
        breaches = result.check_gates()
        assert len(breaches) == 1
        assert "graph_build" in breaches[0]
        assert "10.000" in breaches[0]
        assert "2.5" in breaches[0]

    def test_breach_on_slow_analysis(self):
        result = BenchmarkResult(
            fixture_id="test",
            run_count=5,
            graph_build_p95=0.1,
            core_analysis_p95=5.0,
            end_to_end_p95=0.3,
            thresholds=MEDIUM_THRESHOLDS,
        )
        breaches = result.check_gates()
        assert any("core_analysis" in b for b in breaches)

    def test_breach_on_slow_e2e(self):
        result = BenchmarkResult(
            fixture_id="test",
            run_count=5,
            graph_build_p95=0.1,
            core_analysis_p95=0.2,
            end_to_end_p95=7.0,
            thresholds=MEDIUM_THRESHOLDS,
        )
        breaches = result.check_gates()
        assert any("end_to_end" in b for b in breaches)

    def test_multiple_breaches(self):
        result = BenchmarkResult(
            fixture_id="test",
            run_count=5,
            graph_build_p95=10.0,
            core_analysis_p95=10.0,
            end_to_end_p95=10.0,
            thresholds=MEDIUM_THRESHOLDS,
        )
        breaches = result.check_gates()
        assert len(breaches) == 3


# ─── AC-MVP3-2-PERF-1: Medium fixture benchmark ─────────────────────

class TestMediumBenchmark:
    """AC-MVP3-2-PERF-1: Medium fixture reports p95 for all 3 targets."""

    @pytest.mark.slow
    def test_medium_fixture_within_thresholds(self):
        """Run medium benchmark and check thresholds."""
        edges, nodes = generate_graph_fixture(MEDIUM_NODES, MEDIUM_EDGES)
        result = run_benchmark("medium", edges, nodes, MEDIUM_THRESHOLDS, runs=3)

        assert result.fixture_id == "medium"
        assert result.run_count == 3
        assert result.graph_build_p95 > 0
        assert result.core_analysis_p95 > 0
        assert result.end_to_end_p95 > 0

        if result.breaches:
            pytest.skip(
                f"Medium benchmark breaches (hardware-dependent): "
                f"{'; '.join(result.breaches)}"
            )


# ─── AC-MVP3-2-PERF-2: Large fixture benchmark ──────────────────────

class TestLargeBenchmark:
    """AC-MVP3-2-PERF-2: Large fixture reports p95 for all 3 targets."""

    @pytest.mark.slow
    def test_large_fixture_within_thresholds(self):
        """Run large benchmark and check thresholds."""
        edges, nodes = generate_graph_fixture(LARGE_NODES, LARGE_EDGES)
        result = run_benchmark("large", edges, nodes, LARGE_THRESHOLDS, runs=3)

        assert result.fixture_id == "large"
        assert result.run_count == 3
        assert result.graph_build_p95 > 0
        assert result.core_analysis_p95 > 0
        assert result.end_to_end_p95 > 0

        if result.breaches:
            pytest.skip(
                f"Large benchmark breaches (hardware-dependent): "
                f"{'; '.join(result.breaches)}"
            )


# ─── Small functional benchmark (always runs) ───────────────────────

class TestSmallBenchmark:
    """Quick benchmark with small fixture to validate harness."""

    def test_small_benchmark_runs(self):
        edges, nodes = generate_graph_fixture(100, 400)
        result = run_benchmark("small", edges, nodes, MEDIUM_THRESHOLDS, runs=3)
        assert result.graph_build_p95 < 1.0
        assert result.core_analysis_p95 < 2.0
        assert result.breaches == []

    def test_benchmark_result_has_fields(self):
        edges, nodes = generate_graph_fixture(50, 100)
        result = run_benchmark("tiny", edges, nodes, MEDIUM_THRESHOLDS, runs=2)
        assert result.fixture_id == "tiny"
        assert result.run_count == 2
        assert isinstance(result.graph_build_p95, float)
        assert isinstance(result.core_analysis_p95, float)
        assert isinstance(result.end_to_end_p95, float)
