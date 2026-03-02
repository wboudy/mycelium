"""
Golden fixture infrastructure for Mycelium (TST-G-001).

Provides versioned, deterministic test inputs with expected outputs
for ingestion and Delta Report testing. Each fixture category has:

- Input data: the source material that would be ingested.
- Expected output: the Delta Report structure that should result.

All expected outputs use the deterministic mode (TST-G-002) sentinels
for nondeterministic fields (timestamps/IDs), ensuring byte-identical
comparison across runs.

Fixture categories (per spec §13.4):
- url_basic: stable HTML/text URL capture → at least one NEW claim
- pdf_basic: small PDF fixture → at least one NEW claim
- delta_overlap_only: produces only EXACT/NEAR_DUPLICATE matches
- delta_new_and_contradict: at least one NEW and one CONTRADICTING
- corrupted_frontmatter: triggers Quarantine behavior
- idempotency_changed_content: same locator, different fingerprint
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from mycelium.deterministic import normalize_output

FIXTURES_DIR = Path(__file__).parent


def load_fixture(name: str) -> dict[str, Any]:
    """Load a golden fixture by name.

    Args:
        name: Fixture category name (e.g., "url_basic").

    Returns:
        Dict with keys "input" and "expected_output".

    Raises:
        FileNotFoundError: If fixture file doesn't exist.
    """
    fixture_path = FIXTURES_DIR / f"{name}.yaml"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Golden fixture not found: {fixture_path}")
    with open(fixture_path) as f:
        return yaml.safe_load(f)


def list_fixtures() -> list[str]:
    """List all available golden fixture names."""
    return sorted(
        p.stem for p in FIXTURES_DIR.glob("*.yaml")
        if p.stem not in ("changelog",)
    )


REQUIRED_FIXTURE_CATEGORIES = frozenset({
    "url_basic",
    "pdf_basic",
    "delta_overlap_only",
    "delta_new_and_contradict",
    "corrupted_frontmatter",
    "idempotency_changed_content",
})
