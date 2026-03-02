"""
Tests for spec lint checks (§14).

Covers:
- LINT-001: Glossary term coverage
- LINT-002: MUST requirements have acceptance criteria
- LINT-003: Interface completeness
- LINT-004: Duplicate normative statements
- run_all_lints: Aggregated runner
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from mycelium.spec_lint import (
    LintFinding,
    LintResult,
    _extract_glossary_terms,
    _find_used_terms,
    lint_glossary_coverage,
    lint_must_has_ac,
    lint_interface_completeness,
    lint_duplicate_normatives,
    run_all_lints,
)


# ---------------------------------------------------------------------------
# LintFinding / LintResult
# ---------------------------------------------------------------------------

class TestLintFinding:

    def test_to_dict_minimal(self):
        f = LintFinding(rule="LINT-001", message="test")
        d = f.to_dict()
        assert d["rule"] == "LINT-001"
        assert d["message"] == "test"
        assert d["severity"] == "error"
        assert "line" not in d

    def test_to_dict_with_line(self):
        f = LintFinding(rule="LINT-002", message="msg", line=42, severity="warning")
        d = f.to_dict()
        assert d["line"] == 42
        assert d["severity"] == "warning"


class TestLintResult:

    def test_empty_passes(self):
        r = LintResult()
        assert r.passed is True
        assert r.error_count == 0

    def test_warning_only_passes(self):
        r = LintResult(findings=[LintFinding(rule="X", message="w", severity="warning")])
        assert r.passed is True
        assert r.error_count == 0

    def test_error_fails(self):
        r = LintResult(findings=[LintFinding(rule="X", message="e", severity="error")])
        assert r.passed is False
        assert r.error_count == 1

    def test_to_dict(self):
        r = LintResult(findings=[LintFinding(rule="X", message="m")])
        d = r.to_dict()
        assert "passed" in d
        assert "error_count" in d
        assert "findings" in d
        assert len(d["findings"]) == 1


# ---------------------------------------------------------------------------
# LINT-001: Glossary term coverage
# ---------------------------------------------------------------------------

GLOSSARY_SPEC = textwrap.dedent("""\
    # Spec Title

    ## 2. Glossary

    | Term | Definition |
    |------|------------|
    | Bead | A unit of work |
    | Claim | An extracted assertion |
    | Fingerprint | Content hash |

    ## 3. Architecture

    This section uses Bead and Claim concepts.

    ## 4. Details

    The Claim is verified via the pipeline.
""")


class TestExtractGlossaryTerms:

    def test_extracts_terms(self):
        lines = GLOSSARY_SPEC.splitlines()
        terms = _extract_glossary_terms(lines)
        assert terms == {"Bead", "Claim", "Fingerprint"}

    def test_empty_spec(self):
        terms = _extract_glossary_terms([])
        assert terms == set()

    def test_no_glossary_section(self):
        lines = ["# Title", "## 3. Architecture", "Some text"]
        terms = _extract_glossary_terms(lines)
        assert terms == set()


class TestFindUsedTerms:

    def test_finds_used_terms(self):
        lines = GLOSSARY_SPEC.splitlines()
        terms = {"Bead", "Claim", "Fingerprint"}
        used = _find_used_terms(lines, terms)
        assert "Bead" in used
        assert "Claim" in used
        assert "Fingerprint" not in used

    def test_no_terms_used(self):
        lines = ["## 3. Start", "nothing here"]
        used = _find_used_terms(lines, {"Alpha", "Beta"})
        assert used == {}


class TestLintGlossaryCoverage:

    def test_unused_term_warning(self):
        result = lint_glossary_coverage(GLOSSARY_SPEC)
        # Fingerprint is defined but never used after glossary
        warnings = [f for f in result.findings if f.severity == "warning"]
        unused_terms = [f.message for f in warnings]
        assert any("Fingerprint" in m for m in unused_terms)

    def test_all_used_no_warnings(self):
        spec = textwrap.dedent("""\
            ## 2. Glossary

            | Term | Definition |
            |------|------------|
            | Alpha | First |

            ## 3. Body

            Alpha is used here.
        """)
        result = lint_glossary_coverage(spec)
        assert result.passed is True
        assert len(result.findings) == 0

    def test_no_glossary_error(self):
        result = lint_glossary_coverage("## 3. No glossary here")
        assert result.passed is False
        errors = [f for f in result.findings if f.severity == "error"]
        assert len(errors) == 1
        assert "LINT-001" in errors[0].rule


# ---------------------------------------------------------------------------
# LINT-002: MUST requirements have acceptance criteria
# ---------------------------------------------------------------------------

class TestLintMustHasAC:

    def test_must_with_ac_passes(self):
        spec = textwrap.dedent("""\
            **Requirement REQ-001:** The system MUST do X.

            **Acceptance Criteria**
            - AC-1: X is done.
        """)
        result = lint_must_has_ac(spec)
        assert result.passed is True
        assert len(result.findings) == 0

    def test_must_without_ac_fails(self):
        spec = textwrap.dedent("""\
            **Requirement REQ-002:** The system MUST do Y.

            Some other text but no acceptance criteria.

            ## Next Section
        """)
        result = lint_must_has_ac(spec)
        assert result.passed is False
        assert any("REQ-002" in f.message for f in result.findings)

    def test_should_not_flagged(self):
        spec = textwrap.dedent("""\
            **Requirement REQ-003:** The system SHOULD do Z.

            No AC needed for SHOULD.
        """)
        result = lint_must_has_ac(spec)
        assert result.passed is True

    def test_ac_in_next_section_not_found(self):
        spec = textwrap.dedent("""\
            **Requirement REQ-004:** The system MUST validate.

            ### Next subsection

            Acceptance Criteria here but after section break.
        """)
        result = lint_must_has_ac(spec)
        assert result.passed is False


# ---------------------------------------------------------------------------
# LINT-003: Interface completeness
# ---------------------------------------------------------------------------

class TestLintInterfaceCompleteness:

    def test_complete_interface_passes(self):
        spec = textwrap.dedent("""\
            ### 6.1.1 Stage interfaces

            1) Capture

            **Input**: SourceInput
            **Output**: RawSourcePayload
            **Side effects**: Network I/O
            **Errors**: ERR_CAPTURE_FAILED

            ### Next section
        """)
        result = lint_interface_completeness(spec)
        assert result.passed is True

    def test_missing_component_fails(self):
        spec = textwrap.dedent("""\
            ### 6.1.1 Stage interfaces

            1) Capture

            **Input**: SourceInput
            **Output**: RawSourcePayload

            ### Next section
        """)
        result = lint_interface_completeness(spec)
        missing_msgs = [f.message for f in result.findings]
        assert any("Errors" in m for m in missing_msgs)
        assert any("Side effects" in m for m in missing_msgs)

    def test_no_stages_section(self):
        spec = "## 7. Something else\nNo stages here."
        result = lint_interface_completeness(spec)
        # No stages found, no findings
        assert result.passed is True


# ---------------------------------------------------------------------------
# LINT-004: Duplicate normative statements
# ---------------------------------------------------------------------------

class TestLintDuplicateNormatives:

    def test_no_duplicates_passes(self):
        spec = textwrap.dedent("""\
            The system MUST validate input.
            The system MUST log errors.
        """)
        result = lint_duplicate_normatives(spec)
        assert result.passed is True

    def test_duplicate_detected(self):
        spec = textwrap.dedent("""\
            The system MUST validate all input.
            Some other text.
            The system MUST validate all input.
        """)
        result = lint_duplicate_normatives(spec)
        warnings = [f for f in result.findings if f.severity == "warning"]
        assert len(warnings) >= 1
        assert "LINT-004" in warnings[0].rule

    def test_similar_but_different_passes(self):
        spec = textwrap.dedent("""\
            The system MUST validate input types.
            The system MUST validate input ranges.
        """)
        result = lint_duplicate_normatives(spec)
        assert len(result.findings) == 0


# ---------------------------------------------------------------------------
# run_all_lints
# ---------------------------------------------------------------------------

class TestRunAllLints:

    def test_runs_all_checks(self, tmp_path: Path):
        spec = textwrap.dedent("""\
            # Spec

            ## 2. Glossary

            | Term | Definition |
            |------|------------|
            | Widget | A component |

            ## 3. Body

            The Widget is used throughout.
        """)
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(spec, encoding="utf-8")

        results = run_all_lints(spec_file)
        assert "LINT-001" in results
        assert "LINT-002" in results
        assert "LINT-003" in results
        assert "LINT-004" in results

    def test_returns_lint_results(self, tmp_path: Path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("## 3. No glossary\n", encoding="utf-8")

        results = run_all_lints(spec_file)
        for v in results.values():
            assert isinstance(v, LintResult)
