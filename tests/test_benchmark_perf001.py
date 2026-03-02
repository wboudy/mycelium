"""
Benchmark suite for MVP1/MVP2 p95 latency targets (PERF-001).

Verifies:
  AC-PERF-001-1: Bench suite reports p95 for all four targets and fails
                  gate on threshold breach.
  AC-PERF-001-2: Benchmark results include fixture id, run count, and
                  hardware profile metadata.

Targets and thresholds:
  - ingest(url_basic) p95 <= 60s
  - ingest(pdf_basic) p95 <= 120s
  - delta by delta_report_path p95 <= 5s
  - frontier on seeded medium fixture p95 <= 8s
"""

from __future__ import annotations

import math
import platform
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from mycelium.commands.frontier import (
    TargetData,
    compute_factors,
    compute_score,
    rank_targets,
)
from mycelium.delta_report import build_delta_report, save_delta_report, load_delta_report
from mycelium.stages.capture import SourceInput, capture
from mycelium.stages.compare import ClaimIndex, compare
from mycelium.stages.delta import delta
from mycelium.stages.extract import extract
from mycelium.stages.fingerprint import fingerprint
from mycelium.stages.normalize import normalize


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# PERF-001 p95 thresholds (seconds)
THRESHOLDS = {
    "ingest_url_basic": 60.0,
    "ingest_pdf_basic": 120.0,
    "delta_report_path": 5.0,
    "frontier_medium": 8.0,
}

# Number of benchmark runs per target
BENCH_RUNS = 5  # Enough for p95 calculation


# ---------------------------------------------------------------------------
# Hardware profile
# ---------------------------------------------------------------------------

def get_hardware_profile() -> dict[str, str]:
    """Collect basic hardware/platform metadata."""
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "processor": platform.processor() or "unknown",
        "machine": platform.machine(),
    }


# ---------------------------------------------------------------------------
# Benchmark result model
# ---------------------------------------------------------------------------

@dataclass
class BenchResult:
    """Result of a benchmark run for a single target."""
    fixture_id: str
    run_count: int
    latencies: list[float] = field(default_factory=list)
    hardware_profile: dict[str, str] = field(default_factory=dict)
    threshold_seconds: float = 0.0

    @property
    def p50(self) -> float:
        return _percentile(self.latencies, 0.50)

    @property
    def p95(self) -> float:
        return _percentile(self.latencies, 0.95)

    @property
    def p99(self) -> float:
        return _percentile(self.latencies, 0.99)

    @property
    def passed(self) -> bool:
        return self.p95 <= self.threshold_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "run_count": self.run_count,
            "p50_seconds": round(self.p50, 6),
            "p95_seconds": round(self.p95, 6),
            "p99_seconds": round(self.p99, 6),
            "threshold_seconds": self.threshold_seconds,
            "passed": self.passed,
            "hardware_profile": self.hardware_profile,
        }


def _percentile(values: list[float], pct: float) -> float:
    """Compute percentile using nearest-rank method."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    rank = math.ceil(pct * n) - 1
    return sorted_vals[max(0, rank)]


# ---------------------------------------------------------------------------
# Fixture texts
# ---------------------------------------------------------------------------

URL_BASIC_TEXT = (
    "Recent studies show that deep learning models achieve state-of-the-art "
    "results on protein folding prediction tasks. AlphaFold2 demonstrates "
    "that attention-based architectures can predict 3D protein structures "
    "with atomic accuracy. The transformer architecture has been shown to "
    "generalize across multiple domains including vision, language, and "
    "biological sequence analysis."
)

PDF_BASIC_TEXT = (
    "Quantum computing threatens current cryptographic standards. "
    "Post-quantum cryptography algorithms based on lattice problems "
    "are being standardized by NIST. The transition timeline is "
    "estimated at 10-15 years for critical infrastructure. "
    "Key exchange protocols using lattice-based schemes have been "
    "demonstrated to be resistant to known quantum attacks."
)


def _build_medium_frontier_fixture() -> list[TargetData]:
    """Seeded medium frontier fixture (~20 targets)."""
    ref_ts = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    targets = []
    for i in range(20):
        targets.append(TargetData(
            target_id=f"t-{i:03d}",
            contradict_count=i % 5,
            support_count=(i * 2) % 7,
            project="proj-a" if i % 3 == 0 else "proj-b",
            tags=[f"tag-{i % 4}", f"tag-{i % 6}"],
            linked_delta_novelty_scores=[0.1 * (i % 10), 0.05 * (i % 8)],
            last_reviewed_at=datetime(
                2026, 2, max(1, i), tzinfo=timezone.utc,
            ),
        ))
    return targets


# ---------------------------------------------------------------------------
# Pipeline runner for ingest benchmarks
# ---------------------------------------------------------------------------

def _run_ingest_pipeline(
    vault: Path,
    text: str,
    source_id: str,
    run_id: str,
) -> None:
    """Run full ingest pipeline: capture→normalize→fingerprint→extract→compare→delta."""
    si = SourceInput(text_bundle=text, source_id=source_id)
    payload, _ = capture(si)
    norm, _ = normalize(payload)
    ident, _ = fingerprint(norm)
    bundle, _ = extract(norm, vault_root=vault, run_id=run_id, source_id=source_id)
    idx = ClaimIndex(claims=[])
    compare_result, _ = compare(bundle.get("claims", []), claim_index=idx)
    delta(
        run_id=run_id,
        source_id=source_id,
        normalized_locator=ident.normalized_locator,
        fingerprint=ident.fingerprint,
        compare_result=compare_result,
        vault_root=vault,
    )


# ═══════════════════════════════════════════════════════════════════════
# AC-PERF-001-1: p95 benchmarks for all four targets
# ═══════════════════════════════════════════════════════════════════════


class TestIngestURLBasicBench:
    """ingest(url_basic) p95 <= 60s."""

    def test_p95_within_threshold(self, tmp_path: Path):
        latencies = []
        for i in range(BENCH_RUNS):
            run_vault = tmp_path / f"run-url-{i}"
            run_vault.mkdir()
            start = time.perf_counter()
            _run_ingest_pipeline(
                run_vault, URL_BASIC_TEXT, f"src-url-{i}", f"run-url-{i}",
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        result = BenchResult(
            fixture_id="ingest_url_basic",
            run_count=BENCH_RUNS,
            latencies=latencies,
            hardware_profile=get_hardware_profile(),
            threshold_seconds=THRESHOLDS["ingest_url_basic"],
        )
        assert result.passed, (
            f"ingest(url_basic) p95={result.p95:.3f}s "
            f"exceeds threshold {result.threshold_seconds}s"
        )


class TestIngestPDFBasicBench:
    """ingest(pdf_basic) p95 <= 120s."""

    def test_p95_within_threshold(self, tmp_path: Path):
        latencies = []
        for i in range(BENCH_RUNS):
            run_vault = tmp_path / f"run-pdf-{i}"
            run_vault.mkdir()
            start = time.perf_counter()
            _run_ingest_pipeline(
                run_vault, PDF_BASIC_TEXT, f"src-pdf-{i}", f"run-pdf-{i}",
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        result = BenchResult(
            fixture_id="ingest_pdf_basic",
            run_count=BENCH_RUNS,
            latencies=latencies,
            hardware_profile=get_hardware_profile(),
            threshold_seconds=THRESHOLDS["ingest_pdf_basic"],
        )
        assert result.passed, (
            f"ingest(pdf_basic) p95={result.p95:.3f}s "
            f"exceeds threshold {result.threshold_seconds}s"
        )


class TestDeltaReportBench:
    """delta by delta_report_path p95 <= 5s."""

    def test_p95_within_threshold(self, tmp_path: Path):
        # Pre-build a delta report on disk
        report = build_delta_report(
            run_id="bench-delta-001",
            source_id="src-bench-001",
            normalized_locator="text_bundle:bench-delta",
            fingerprint="sha256:" + "a" * 64,
        )
        report_path = save_delta_report(tmp_path, report)

        latencies = []
        for _ in range(BENCH_RUNS):
            start = time.perf_counter()
            loaded = load_delta_report(report_path)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)
            assert loaded["run_id"] == "bench-delta-001"

        result = BenchResult(
            fixture_id="delta_report_path",
            run_count=BENCH_RUNS,
            latencies=latencies,
            hardware_profile=get_hardware_profile(),
            threshold_seconds=THRESHOLDS["delta_report_path"],
        )
        assert result.passed, (
            f"delta p95={result.p95:.3f}s "
            f"exceeds threshold {result.threshold_seconds}s"
        )


class TestFrontierMediumBench:
    """frontier on seeded medium fixture p95 <= 8s."""

    def test_p95_within_threshold(self):
        targets = _build_medium_frontier_fixture()
        ref_ts = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

        latencies = []
        for _ in range(BENCH_RUNS):
            start = time.perf_counter()
            ranked = rank_targets(
                targets, ref_ts,
                input_project="proj-a",
                input_tags=["tag-0", "tag-2"],
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)
            assert len(ranked) == 20

        result = BenchResult(
            fixture_id="frontier_medium",
            run_count=BENCH_RUNS,
            latencies=latencies,
            hardware_profile=get_hardware_profile(),
            threshold_seconds=THRESHOLDS["frontier_medium"],
        )
        assert result.passed, (
            f"frontier p95={result.p95:.3f}s "
            f"exceeds threshold {result.threshold_seconds}s"
        )


# ═══════════════════════════════════════════════════════════════════════
# AC-PERF-001-2: Results include fixture id, run count, hardware profile
# ═══════════════════════════════════════════════════════════════════════


class TestBenchResultMetadata:
    """AC-PERF-001-2: Benchmark results include required metadata."""

    def test_result_has_fixture_id(self):
        result = BenchResult(
            fixture_id="ingest_url_basic",
            run_count=5,
            latencies=[0.1, 0.2, 0.3, 0.4, 0.5],
            hardware_profile=get_hardware_profile(),
            threshold_seconds=60.0,
        )
        d = result.to_dict()
        assert "fixture_id" in d
        assert d["fixture_id"] == "ingest_url_basic"

    def test_result_has_run_count(self):
        result = BenchResult(
            fixture_id="test",
            run_count=10,
            latencies=[0.1] * 10,
            threshold_seconds=1.0,
        )
        d = result.to_dict()
        assert "run_count" in d
        assert d["run_count"] == 10

    def test_result_has_hardware_profile(self):
        profile = get_hardware_profile()
        result = BenchResult(
            fixture_id="test",
            run_count=5,
            latencies=[0.1] * 5,
            hardware_profile=profile,
            threshold_seconds=1.0,
        )
        d = result.to_dict()
        assert "hardware_profile" in d
        assert "platform" in d["hardware_profile"]
        assert "python_version" in d["hardware_profile"]
        assert "processor" in d["hardware_profile"]
        assert "machine" in d["hardware_profile"]

    def test_result_has_percentiles(self):
        result = BenchResult(
            fixture_id="test",
            run_count=5,
            latencies=[0.1, 0.2, 0.3, 0.4, 0.5],
            threshold_seconds=1.0,
        )
        d = result.to_dict()
        assert "p50_seconds" in d
        assert "p95_seconds" in d
        assert "p99_seconds" in d

    def test_result_pass_fail_flag(self):
        result = BenchResult(
            fixture_id="test",
            run_count=5,
            latencies=[0.1] * 5,
            threshold_seconds=1.0,
        )
        assert result.passed is True
        d = result.to_dict()
        assert d["passed"] is True

    def test_result_fails_on_breach(self):
        result = BenchResult(
            fixture_id="test",
            run_count=5,
            latencies=[10.0] * 5,
            threshold_seconds=1.0,
        )
        assert result.passed is False
        d = result.to_dict()
        assert d["passed"] is False


# ═══════════════════════════════════════════════════════════════════════
# Percentile calculation correctness
# ═══════════════════════════════════════════════════════════════════════


class TestPercentileCalculation:
    """Verify percentile computation correctness."""

    def test_p50_of_five(self):
        assert _percentile([1, 2, 3, 4, 5], 0.50) == 3

    def test_p95_of_five(self):
        assert _percentile([1, 2, 3, 4, 5], 0.95) == 5

    def test_p95_of_twenty(self):
        vals = list(range(1, 21))
        assert _percentile(vals, 0.95) == 19

    def test_p99_of_hundred(self):
        vals = list(range(1, 101))
        assert _percentile(vals, 0.99) == 99

    def test_empty_list(self):
        assert _percentile([], 0.95) == 0.0

    def test_single_value(self):
        assert _percentile([42.0], 0.95) == 42.0


# ═══════════════════════════════════════════════════════════════════════
# Gate check
# ═══════════════════════════════════════════════════════════════════════


class TestGateCheck:
    """Verify the gate check mechanism works correctly."""

    def test_all_thresholds_defined(self):
        """All four PERF-001 targets have defined thresholds."""
        assert "ingest_url_basic" in THRESHOLDS
        assert "ingest_pdf_basic" in THRESHOLDS
        assert "delta_report_path" in THRESHOLDS
        assert "frontier_medium" in THRESHOLDS

    def test_thresholds_match_spec(self):
        """Thresholds match PERF-001 spec values."""
        assert THRESHOLDS["ingest_url_basic"] == 60.0
        assert THRESHOLDS["ingest_pdf_basic"] == 120.0
        assert THRESHOLDS["delta_report_path"] == 5.0
        assert THRESHOLDS["frontier_medium"] == 8.0

    def test_bench_result_gate_pass(self):
        """Result with p95 below threshold passes gate."""
        result = BenchResult(
            fixture_id="ingest_url_basic",
            run_count=5,
            latencies=[0.5, 0.6, 0.7, 0.8, 0.9],
            threshold_seconds=60.0,
        )
        assert result.passed is True

    def test_bench_result_gate_fail(self):
        """Result with p95 above threshold fails gate."""
        result = BenchResult(
            fixture_id="ingest_url_basic",
            run_count=5,
            latencies=[65.0, 70.0, 80.0, 55.0, 60.0],
            threshold_seconds=60.0,
        )
        assert result.passed is False
