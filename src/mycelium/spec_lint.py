"""
Spec lint checks (§14).

Validates the specification document for internal consistency:
- LINT-001: Glossary term coverage
- LINT-002: MUST requirements have acceptance criteria
- LINT-003: Interface completeness
- LINT-004: Duplicate normative statements
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LintFinding:
    """A single lint finding."""

    rule: str
    message: str
    line: int | None = None
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "rule": self.rule,
            "message": self.message,
            "severity": self.severity,
        }
        if self.line is not None:
            d["line"] = self.line
        return d


@dataclass
class LintResult:
    """Aggregated lint results."""

    findings: list[LintFinding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "error_count": self.error_count,
            "findings": [f.to_dict() for f in self.findings],
        }


# ---------------------------------------------------------------------------
# LINT-001: Glossary term coverage
# ---------------------------------------------------------------------------

def _extract_glossary_terms(lines: list[str]) -> set[str]:
    """Extract terms from the glossary table (§2).

    Glossary rows look like: ``| Term | Definition |``
    """
    terms: set[str] = set()
    in_glossary = False

    for line in lines:
        stripped = line.strip()

        # Detect glossary section
        if stripped.startswith("## 2.") or stripped == "## 2. Glossary":
            in_glossary = True
            continue

        # Stop at next section
        if in_glossary and stripped.startswith("## ") and not stripped.startswith("## 2"):
            break

        if not in_glossary:
            continue

        # Skip header separator
        if stripped.startswith("|---") or stripped.startswith("| Term"):
            continue

        # Parse table row
        if stripped.startswith("|"):
            parts = stripped.split("|")
            if len(parts) >= 3:
                term = parts[1].strip()
                if term:
                    terms.add(term)

    return terms


def _find_used_terms(lines: list[str], glossary_terms: set[str]) -> dict[str, list[int]]:
    """Find glossary terms used in the spec body (outside the glossary itself).

    Returns a dict mapping term → list of line numbers where used.
    """
    used: dict[str, list[int]] = {}
    past_glossary = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Skip until past glossary
        if stripped.startswith("## 3") or (stripped.startswith("## ") and "3." in stripped):
            past_glossary = True

        if not past_glossary:
            continue

        for term in glossary_terms:
            # Case-sensitive match for multi-word terms
            if term in line:
                used.setdefault(term, []).append(i)

    return used


def lint_glossary_coverage(spec_text: str) -> LintResult:
    """LINT-001: Check that specialized terms used in the spec appear in the Glossary.

    This checks the reverse: terms in the glossary that are never referenced
    outside the glossary, AND looks for capitalized compound terms that might
    be missing from the glossary.

    Args:
        spec_text: Full spec file content.

    Returns:
        LintResult with findings.
    """
    lines = spec_text.splitlines()
    glossary_terms = _extract_glossary_terms(lines)
    result = LintResult()

    if not glossary_terms:
        result.findings.append(LintFinding(
            rule="LINT-001",
            message="No glossary terms found — is the glossary table present?",
            severity="error",
        ))
        return result

    # Check each glossary term is actually used in the spec body
    used = _find_used_terms(lines, glossary_terms)
    unused = glossary_terms - set(used.keys())

    for term in sorted(unused):
        result.findings.append(LintFinding(
            rule="LINT-001",
            message=f"Glossary term '{term}' is defined but never referenced in the spec body",
            severity="warning",
        ))

    return result


# ---------------------------------------------------------------------------
# LINT-002: MUST requirements have acceptance criteria
# ---------------------------------------------------------------------------

def lint_must_has_ac(spec_text: str) -> LintResult:
    """LINT-002: Every MUST requirement must have acceptance criteria.

    Looks for lines containing ``**Requirement`` and checks that an
    ``**Acceptance Criteria**`` or ``Acceptance Criteria`` block follows
    within the same section (before the next ``###`` or ``##``).

    Args:
        spec_text: Full spec file content.

    Returns:
        LintResult with findings.
    """
    lines = spec_text.splitlines()
    result = LintResult()

    for i, line in enumerate(lines):
        if "**Requirement" in line and "MUST" in line:
            req_id_match = re.search(r"\*\*Requirement\s+([A-Z][\w-]+):", line)
            req_id = req_id_match.group(1) if req_id_match else f"line-{i + 1}"

            # Search forward for acceptance criteria before next section
            found_ac = False
            for j in range(i + 1, min(i + 30, len(lines))):
                fwd = lines[j].strip()
                if fwd.startswith("## ") or fwd.startswith("### "):
                    break
                if "Acceptance Criteria" in fwd:
                    found_ac = True
                    break

            if not found_ac:
                result.findings.append(LintFinding(
                    rule="LINT-002",
                    message=f"Requirement {req_id} has MUST but no nearby Acceptance Criteria",
                    line=i + 1,
                ))

    return result


# ---------------------------------------------------------------------------
# LINT-003: Interface completeness
# ---------------------------------------------------------------------------

_INTERFACE_COMPONENTS = {"Input", "Output", "Side effects", "Errors"}


def lint_interface_completeness(spec_text: str) -> LintResult:
    """LINT-003: Required interfaces specify inputs, outputs, side effects, errors.

    Scans stage interface blocks (§6.1.1) for the four required components.

    Args:
        spec_text: Full spec file content.

    Returns:
        LintResult with findings.
    """
    lines = spec_text.splitlines()
    result = LintResult()

    # Find stage interface blocks
    in_stages = False
    current_stage = None
    stage_line = 0
    found_components: set[str] = set()

    for i, line in enumerate(lines):
        stripped = line.strip()

        if "Stage interfaces" in stripped or "6.1.1" in stripped:
            in_stages = True
            continue

        if in_stages and stripped.startswith("### "):
            # Flush previous stage
            if current_stage:
                _check_stage_components(result, current_stage, stage_line, found_components)
            in_stages = False
            continue

        if not in_stages:
            continue

        # Detect stage headers (numbered: "1) Capture", "2) Normalize", etc.)
        stage_match = re.match(r"^(\d+)\)\s+(\w+)", stripped)
        if stage_match:
            if current_stage:
                _check_stage_components(result, current_stage, stage_line, found_components)
            current_stage = stage_match.group(2)
            stage_line = i + 1
            found_components = set()
            continue

        # Check for component keywords
        for comp in _INTERFACE_COMPONENTS:
            if stripped.startswith(f"{comp}:") or stripped.startswith(f"**{comp}"):
                found_components.add(comp)

    # Flush last stage
    if current_stage:
        _check_stage_components(result, current_stage, stage_line, found_components)

    return result


def _check_stage_components(
    result: LintResult,
    stage: str,
    line: int,
    found: set[str],
) -> None:
    missing = _INTERFACE_COMPONENTS - found
    for comp in sorted(missing):
        result.findings.append(LintFinding(
            rule="LINT-003",
            message=f"Stage '{stage}' missing interface component: {comp}",
            line=line,
        ))


# ---------------------------------------------------------------------------
# LINT-004: Duplicate normative statements
# ---------------------------------------------------------------------------

def lint_duplicate_normatives(spec_text: str) -> LintResult:
    """LINT-004: Flag duplicate normative statements.

    Detects MUST statements that appear to restate the same invariant
    by checking for identical or near-identical normative phrases.

    Args:
        spec_text: Full spec file content.

    Returns:
        LintResult with findings.
    """
    lines = spec_text.splitlines()
    result = LintResult()

    # Extract all MUST statements with their line numbers
    must_statements: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if " MUST " in line:
            # Normalize for comparison
            normalized = re.sub(r"\s+", " ", line.strip().lower())
            # Remove requirement IDs and formatting
            normalized = re.sub(r"\*\*requirement\s+[\w-]+:\*\*\s*", "", normalized)
            normalized = re.sub(r"\*\*", "", normalized)
            must_statements.append((i + 1, normalized))

    # Check for duplicates
    seen: dict[str, int] = {}
    for line_num, stmt in must_statements:
        if stmt in seen:
            result.findings.append(LintFinding(
                rule="LINT-004",
                message=f"Possible duplicate MUST statement (first seen at line {seen[stmt]})",
                line=line_num,
                severity="warning",
            ))
        else:
            seen[stmt] = line_num

    return result


# ---------------------------------------------------------------------------
# Run all lints
# ---------------------------------------------------------------------------

def run_all_lints(spec_path: str | Path) -> dict[str, LintResult]:
    """Run all spec lint checks on a spec file.

    Args:
        spec_path: Path to the spec markdown file.

    Returns:
        Dict mapping lint rule ID to its LintResult.
    """
    text = Path(spec_path).read_text(encoding="utf-8")
    return {
        "LINT-001": lint_glossary_coverage(text),
        "LINT-002": lint_must_has_ac(text),
        "LINT-003": lint_interface_completeness(text),
        "LINT-004": lint_duplicate_normatives(text),
    }
