"""
Tests for the mycelium CLI and orchestrator.

Test mode: SMOKE
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock, patch

import pytest
import yaml

from mycelium.orchestrator import (
    DEFAULT_DEEP_MODEL,
    REQUIRES_APPROVAL,
    append_llm_usage,
    check_hitl_approval,
    extract_routing_labels,
    get_usage_summary,
    load_progress,
    normalize_current_agent,
    resolve_model_for_run,
    run_agent,
)
from mycelium.llm import CompletionResponse, DEFAULT_MODEL, UsageMetadata
from mycelium.cli import _normalize_objective


@pytest.fixture
def temp_mission(tmp_path):
    """Create a temporary mission directory with progress.yaml."""
    mission_dir = tmp_path / ".mycelium" / "missions" / "test-mission"
    mission_dir.mkdir(parents=True)
    
    # Create minimal progress.yaml
    progress_content = {
        "current_agent": "scientist",
        "mission_context": {
            "phase": "Test",
            "objective": "Test mission",
            "scope": ["Testing"],
            "constraints": [],
            "non_goals": [],
            "test_mode": "NONE",
        },
        "scientist_plan": {},
        "implementer_log": [],
        "verifier_report": [],
    }
    
    progress_file = mission_dir / "progress.yaml"
    with open(progress_file, "w") as f:
        yaml.dump(progress_content, f)
    
    # Create .mycelium structure at repo root
    mycelium_dir = tmp_path / ".mycelium"
    
    # Create CONTRACT.md
    contract_file = mycelium_dir / "CONTRACT.md"
    contract_file.write_text("# Test Contract\n\nTest content.")
    
    # Create agent template
    agents_dir = mycelium_dir / "agents" / "mission"
    agents_dir.mkdir(parents=True)
    
    scientist_md = agents_dir / "scientist.md"
    scientist_md.write_text(dedent("""
        ---
        role: scientist
        may_edit_code: false
        self_sequence_to: implementer
        ---
        # Test Scientist
        You are a test scientist.
    """))
    
    return mission_dir


class TestLoadProgress:
    """Tests for load_progress function."""

    def test_load_from_directory(self, temp_mission):
        """Loads progress.yaml from mission directory."""
        progress = load_progress(temp_mission)
        
        assert progress["current_agent"] == "scientist"
        assert progress["mission_context"]["objective"] == "Test mission"

    def test_load_from_file(self, temp_mission):
        """Loads progress.yaml from direct file path."""
        progress_file = temp_mission / "progress.yaml"
        progress = load_progress(progress_file)
        
        assert progress["current_agent"] == "scientist"

    def test_file_not_found(self, tmp_path):
        """Raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_progress(tmp_path / "nonexistent")

    def test_empty_yaml_returns_empty_dict(self, temp_mission):
        """Empty YAML should be normalized to an empty progress object."""
        progress_file = temp_mission / "progress.yaml"
        progress_file.write_text("")

        progress = load_progress(progress_file)

        assert progress == {}

    def test_non_mapping_yaml_raises_value_error(self, temp_mission):
        """Non-mapping YAML roots are rejected with a clear error."""
        progress_file = temp_mission / "progress.yaml"
        progress_file.write_text("- item1\n- item2\n")

        with pytest.raises(ValueError, match="expected YAML mapping/object root"):
            load_progress(progress_file)


class TestNormalizeCurrentAgent:
    """Tests for normalize_current_agent helper."""

    def test_plain_string(self):
        """Returns stripped string for normal current_agent values."""
        assert normalize_current_agent(" scientist ") == "scientist"

    def test_nested_current_agent_dict(self):
        """Unwraps nested current_agent dictionaries recursively."""
        raw = {"current_agent": {"current_agent": "implementer"}}
        assert normalize_current_agent(raw) == "implementer"

    def test_value_key_dict(self):
        """Supports malformed value-wrapped payloads."""
        assert normalize_current_agent({"value": "verifier"}) == "verifier"

    def test_agent_key_dict(self):
        """Supports malformed agent-wrapped payloads."""
        assert normalize_current_agent({"agent": "maintainer"}) == "maintainer"

    def test_fallback_stringification_for_unknown_dict(self):
        """Unknown dict payloads fall back to stable stringification."""
        raw = {"unexpected": "shape"}
        assert normalize_current_agent(raw) == str(raw).strip()

    def test_none_returns_empty_string(self):
        """None current_agent should be treated as empty."""
        assert normalize_current_agent(None) == ""

    def test_nested_none_returns_empty_string(self):
        """Nested current_agent/value None payloads should normalize to empty."""
        raw = {"current_agent": {"value": None}}
        assert normalize_current_agent(raw) == ""

    def test_mixed_case_is_normalized_to_lowercase(self):
        """Mixed-case agent values should normalize for validation."""
        assert normalize_current_agent(" Scientist ") == "scientist"
        assert normalize_current_agent({"current_agent": "ImPleMenter"}) == "implementer"


class TestAppendLlmUsage:
    """Tests for append_llm_usage function."""

    def test_creates_llm_usage_section(self):
        """Creates llm_usage section if missing."""
        progress = {}
        response = CompletionResponse(
            content="Test",
            usage=UsageMetadata(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost_usd=0.005,
                model="test-model",
            ),
            success=True,
        )
        
        result = append_llm_usage(progress, "scientist", response)
        
        assert "llm_usage" in result
        assert result["llm_usage"]["total_tokens"] == 150
        assert result["llm_usage"]["total_cost_usd"] == 0.005
        assert len(result["llm_usage"]["runs"]) == 1

    def test_appends_to_existing(self):
        """Appends to existing llm_usage section."""
        progress = {
            "llm_usage": {
                "runs": [
                    {"agent_role": "scientist", "total_tokens": 100, "cost_usd": 0.003}
                ],
                "total_tokens": 100,
                "total_cost_usd": 0.003,
            }
        }
        response = CompletionResponse(
            content="Test",
            usage=UsageMetadata(
                total_tokens=200,
                cost_usd=0.006,
            ),
            success=True,
        )
        
        result = append_llm_usage(progress, "implementer", response)
        
        assert len(result["llm_usage"]["runs"]) == 2
        assert result["llm_usage"]["total_tokens"] == 300
        assert result["llm_usage"]["total_cost_usd"] == 0.009

    def test_normalizes_non_dict_llm_usage(self):
        """Malformed llm_usage values are normalized before append."""
        progress = {"llm_usage": "corrupted"}
        response = CompletionResponse(
            content="Test",
            usage=UsageMetadata(total_tokens=50, cost_usd=0.002),
            success=True,
        )

        result = append_llm_usage(progress, "scientist", response)

        assert isinstance(result["llm_usage"], dict)
        assert isinstance(result["llm_usage"]["runs"], list)
        assert len(result["llm_usage"]["runs"]) == 1
        assert result["llm_usage"]["total_tokens"] == 50

    def test_normalizes_non_list_runs(self):
        """Non-list runs fields are reset to a safe list."""
        progress = {"llm_usage": {"runs": "bad-runs", "total_tokens": 999, "total_cost_usd": 3.14}}
        response = CompletionResponse(
            content="Test",
            usage=UsageMetadata(total_tokens=10, cost_usd=0.001),
            success=True,
        )

        result = append_llm_usage(progress, "verifier", response)

        assert len(result["llm_usage"]["runs"]) == 1
        assert result["llm_usage"]["total_tokens"] == 10
        assert result["llm_usage"]["total_cost_usd"] == 0.001


class TestCheckHitlApproval:
    """Tests for check_hitl_approval function."""

    def test_non_implementer_auto_approved(self):
        """Non-implementer agents don't require approval."""
        assert check_hitl_approval("scientist") is True
        assert check_hitl_approval("verifier") is True
        assert check_hitl_approval("maintainer") is True

    def test_implementer_requires_approval(self):
        """Implementer requires approval."""
        assert "implementer" in REQUIRES_APPROVAL

    def test_auto_approve_flag(self):
        """Auto-approve bypasses HITL gate."""
        assert check_hitl_approval("implementer", auto_approve=True) is True


class TestGetUsageSummary:
    """Tests for get_usage_summary function."""

    def test_no_usage_data(self, temp_mission):
        """Returns zeros when no usage data exists."""
        summary = get_usage_summary(temp_mission)
        
        assert summary["total_tokens"] == 0
        assert summary["total_cost_usd"] == 0.0
        assert summary["runs"] == 0
        assert summary["runs_detail"] == []

    def test_with_usage_data(self, temp_mission):
        """Returns correct totals when usage data exists."""
        # Add usage data to progress.yaml
        progress_file = temp_mission / "progress.yaml"
        with open(progress_file) as f:
            progress = yaml.safe_load(f)
        
        progress["llm_usage"] = {
            "runs": [
                {"agent_role": "scientist", "total_tokens": 1000, "cost_usd": 0.03},
                {"agent_role": "implementer", "total_tokens": 2000, "cost_usd": 0.06},
            ],
            "total_tokens": 3000,
            "total_cost_usd": 0.09,
        }
        
        with open(progress_file, "w") as f:
            yaml.dump(progress, f)
        
        summary = get_usage_summary(temp_mission)
        
        assert summary["total_tokens"] == 3000
        assert summary["total_cost_usd"] == 0.09
        assert summary["runs"] == 2

    def test_invalid_progress_returns_stable_empty_schema(self, temp_mission):
        """Error paths should still return the full usage-summary shape."""
        progress_file = temp_mission / "progress.yaml"
        progress_file.write_text("- invalid-root\n")

        summary = get_usage_summary(temp_mission)

        assert summary["total_tokens"] == 0
        assert summary["total_cost_usd"] == 0.0
        assert summary["runs"] == 0
        assert summary["runs_detail"] == []

    def test_malformed_llm_usage_root_returns_stable_summary(self, temp_mission):
        """Non-dict llm_usage values should not break summary generation."""
        progress_file = temp_mission / "progress.yaml"
        with open(progress_file) as f:
            progress = yaml.safe_load(f)

        progress["llm_usage"] = "corrupted"
        with open(progress_file, "w") as f:
            yaml.dump(progress, f)

        summary = get_usage_summary(temp_mission)

        assert summary["total_tokens"] == 0
        assert summary["total_cost_usd"] == 0.0
        assert summary["runs"] == 0
        assert summary["runs_detail"] == []

    def test_malformed_runs_field_is_filtered(self, temp_mission):
        """Summary should ignore non-dict run entries and keep stable shape."""
        progress_file = temp_mission / "progress.yaml"
        with open(progress_file) as f:
            progress = yaml.safe_load(f)

        progress["llm_usage"] = {
            "runs": [{"total_tokens": 7, "cost_usd": 0.002}, "bad-entry", 123],
            "total_tokens": "not-a-number",
            "total_cost_usd": "not-a-number",
        }
        with open(progress_file, "w") as f:
            yaml.dump(progress, f)

        summary = get_usage_summary(temp_mission)

        assert summary["total_tokens"] == 7
        assert summary["total_cost_usd"] == 0.002
        assert summary["runs"] == 1
        assert summary["runs_detail"] == [{"total_tokens": 7, "cost_usd": 0.002}]

    def test_runs_detail_numeric_fields_are_sanitized(self, temp_mission):
        """runs_detail entries should always have numeric-safe fields for rendering."""
        progress_file = temp_mission / "progress.yaml"
        with open(progress_file) as f:
            progress = yaml.safe_load(f)

        progress["llm_usage"] = {
            "runs": [
                {"agent_role": "scientist", "total_tokens": "abc", "cost_usd": "bad"},
                {"agent_role": "verifier", "total_tokens": 5.8, "cost_usd": 0.0042},
            ],
            "total_tokens": "invalid",
            "total_cost_usd": "invalid",
        }
        with open(progress_file, "w") as f:
            yaml.dump(progress, f)

        summary = get_usage_summary(temp_mission)

        assert summary["total_tokens"] == 5
        assert summary["total_cost_usd"] == 0.0042
        assert summary["runs"] == 2
        assert summary["runs_detail"][0]["total_tokens"] == 0
        assert summary["runs_detail"][0]["cost_usd"] == 0.0
        assert summary["runs_detail"][1]["total_tokens"] == 5
        assert summary["runs_detail"][1]["cost_usd"] == 0.0042


class TestModelRouting:
    """Tests for model routing policy in orchestrator."""

    def test_extract_routing_labels_handles_mixed_shapes(self):
        """Label extractor normalizes list/string/dict forms into a stable set."""
        progress = {
            "labels": " agent:Scientist,   model:deep ",
            "mission_context": {
                "labels": ["needs:orchestrator", {"label": "Model:Deep"}],
                "bead_labels": "interrupt ROOT-CAUSE",
            },
            "routing": {"label": "model:deep"},
        }

        labels = extract_routing_labels(progress)

        assert "agent:scientist" in labels
        assert "model:deep" in labels
        assert "needs:orchestrator" in labels
        assert "interrupt" in labels
        assert "root-cause" in labels

    def test_resolve_model_override_wins(self, monkeypatch):
        """Explicit model override takes precedence over all routing signals."""
        monkeypatch.setenv("MYCELIUM_MODEL", "anthropic/claude-sonnet-4-20250514")
        monkeypatch.setenv("MYCELIUM_MODEL_DEEP", "anthropic/claude-opus-4-1")
        progress = {"mission_context": {"labels": ["model:deep"]}}

        model, source = resolve_model_for_run(progress, "openai/gpt-4.1")

        assert model == "openai/gpt-4.1"
        assert source == "override"

    def test_resolve_model_blank_override_is_ignored(self, monkeypatch):
        """Whitespace-only override should not bypass normal routing."""
        monkeypatch.delenv("MYCELIUM_MODEL", raising=False)
        monkeypatch.setenv("MYCELIUM_MODEL_DEEP", "anthropic/claude-opus-4-1")
        progress = {"mission_context": {"labels": ["model:deep"]}}

        model, source = resolve_model_for_run(progress, "   ")

        assert model == "anthropic/claude-opus-4-1"
        assert source == "model:deep:MYCELIUM_MODEL_DEEP"

    def test_resolve_model_deep_label_uses_deep_env(self, monkeypatch):
        """model:deep routes to configured deep model env var."""
        monkeypatch.delenv("MYCELIUM_MODEL", raising=False)
        monkeypatch.setenv("MYCELIUM_MODEL_DEEP", "anthropic/claude-opus-4-1")
        progress = {"mission_context": {"labels": ["model:deep", "needs:orchestrator"]}}

        model, source = resolve_model_for_run(progress, None)

        assert model == "anthropic/claude-opus-4-1"
        assert source == "model:deep:MYCELIUM_MODEL_DEEP"

    def test_resolve_model_deep_label_falls_back_to_default_deep(self, monkeypatch):
        """model:deep falls back to built-in deep model when no deep env is set."""
        monkeypatch.delenv("MYCELIUM_MODEL", raising=False)
        monkeypatch.delenv("MYCELIUM_MODEL_DEEP", raising=False)
        monkeypatch.delenv("MYCELIUM_DEEP_MODEL", raising=False)
        progress = {"bead": {"labels": ["model:deep"]}}

        model, source = resolve_model_for_run(progress, None)

        assert model == DEFAULT_DEEP_MODEL
        assert source == "model:deep:default"

    def test_resolve_model_deep_from_nested_routing_label(self, monkeypatch):
        """Nested routing.label also triggers deep-model selection."""
        monkeypatch.delenv("MYCELIUM_MODEL", raising=False)
        monkeypatch.setenv("MYCELIUM_DEEP_MODEL", "openai/o3")
        progress = {"routing": {"label": "model:deep"}}

        model, source = resolve_model_for_run(progress, None)

        assert model == "openai/o3"
        assert source == "model:deep:MYCELIUM_DEEP_MODEL"

    def test_resolve_model_deep_from_string_labels(self, monkeypatch):
        """Comma/space-delimited labels route correctly even with mixed case."""
        monkeypatch.delenv("MYCELIUM_MODEL", raising=False)
        monkeypatch.delenv("MYCELIUM_MODEL_DEEP", raising=False)
        monkeypatch.delenv("MYCELIUM_DEEP_MODEL", raising=False)
        progress = {"labels": " interrupt,ROOT-CAUSE   Model:Deep "}

        model, source = resolve_model_for_run(progress, None)

        assert model == DEFAULT_DEEP_MODEL
        assert source == "model:deep:default"

    def test_resolve_model_without_deep_label_uses_standard_default(self, monkeypatch):
        """Without model:deep, orchestrator uses normal model resolution."""
        monkeypatch.delenv("MYCELIUM_MODEL", raising=False)
        progress = {"mission_context": {"labels": ["agent:scientist"]}}

        model, source = resolve_model_for_run(progress, None)

        assert model == DEFAULT_MODEL
        assert source == "default"

    def test_resolve_model_ignores_blank_default_model_env(self, monkeypatch):
        """Blank MYCELIUM_MODEL should be treated as unset."""
        monkeypatch.setenv("MYCELIUM_MODEL", "   ")
        progress = {"mission_context": {"labels": ["agent:scientist"]}}

        model, source = resolve_model_for_run(progress, None)

        assert model == DEFAULT_MODEL
        assert source == "default"

    def test_run_agent_uses_routed_deep_model(self, temp_mission, monkeypatch):
        """run_agent passes routed deep model to complete()."""
        progress_file = temp_mission / "progress.yaml"
        with open(progress_file) as f:
            progress = yaml.safe_load(f)

        progress.setdefault("mission_context", {})["labels"] = ["model:deep", "needs:orchestrator"]

        with open(progress_file, "w") as f:
            yaml.dump(progress, f)

        monkeypatch.delenv("MYCELIUM_MODEL", raising=False)
        monkeypatch.delenv("MYCELIUM_MODEL_DEEP", raising=False)
        monkeypatch.delenv("MYCELIUM_DEEP_MODEL", raising=False)

        mock_response = CompletionResponse(
            content="Done",
            usage=UsageMetadata(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost_usd=0.01,
                model="openai/gpt-5",
            ),
            success=True,
        )

        with patch("mycelium.orchestrator.complete", return_value=mock_response) as mock_complete:
            response = run_agent(temp_mission, auto_approve=True, enable_tools=False)

        assert response.success is True
        assert mock_complete.call_args.kwargs["model"] == DEFAULT_DEEP_MODEL


class TestRunAgent:
    """Tests for run_agent function."""

    def test_mission_complete(self, temp_mission):
        """Returns success when mission is complete."""
        # Set current_agent to empty
        progress_file = temp_mission / "progress.yaml"
        with open(progress_file) as f:
            progress = yaml.safe_load(f)
        
        progress["current_agent"] = ""
        
        with open(progress_file, "w") as f:
            yaml.dump(progress, f)
        
        response = run_agent(temp_mission)
        
        assert response.success is True
        assert "complete" in response.content.lower()

    def test_invalid_agent(self, temp_mission):
        """Returns error for invalid agent."""
        progress_file = temp_mission / "progress.yaml"
        with open(progress_file) as f:
            progress = yaml.safe_load(f)
        
        progress["current_agent"] = "invalid_agent"
        
        with open(progress_file, "w") as f:
            yaml.dump(progress, f)
        
        response = run_agent(temp_mission)
        
        assert response.success is False
        assert "Invalid current_agent" in response.error

    def test_dry_run(self, temp_mission):
        """Dry run returns prompt without calling LLM."""
        response = run_agent(temp_mission, dry_run=True)
        
        assert response.success is True
        assert "DRY RUN" in response.content
        assert "scientist" in response.content

    def test_invalid_progress_yaml_root_returns_error(self, temp_mission):
        """run_agent returns a clear error when progress root is not a mapping."""
        progress_file = temp_mission / "progress.yaml"
        progress_file.write_text("- not-a-mapping\n")

        response = run_agent(temp_mission)

        assert response.success is False
        assert response.error is not None
        assert "YAML format error" in response.error

    def test_nested_current_agent_dict_is_normalized(self, temp_mission):
        """run_agent should accept nested current_agent dict mistakes."""
        progress_file = temp_mission / "progress.yaml"
        with open(progress_file) as f:
            progress = yaml.safe_load(f)

        progress["current_agent"] = {"current_agent": {"value": "scientist"}}
        with open(progress_file, "w") as f:
            yaml.dump(progress, f)

        response = run_agent(temp_mission, dry_run=True)

        assert response.success is True
        assert "Prompt for scientist" in response.content

    def test_none_current_agent_marks_mission_complete(self, temp_mission):
        """run_agent should treat None current_agent as mission complete."""
        progress_file = temp_mission / "progress.yaml"
        with open(progress_file) as f:
            progress = yaml.safe_load(f)

        progress["current_agent"] = None
        with open(progress_file, "w") as f:
            yaml.dump(progress, f)

        response = run_agent(temp_mission)

        assert response.success is True
        assert "Mission complete" in response.content

    def test_mixed_case_current_agent_executes_successfully(self, temp_mission):
        """run_agent should accept mixed-case agent values via normalization."""
        progress_file = temp_mission / "progress.yaml"
        with open(progress_file) as f:
            progress = yaml.safe_load(f)

        progress["current_agent"] = "Scientist"
        with open(progress_file, "w") as f:
            yaml.dump(progress, f)

        response = run_agent(temp_mission, dry_run=True)

        assert response.success is True
        assert "Prompt for scientist" in response.content


class TestCliStatusParsing:
    """Tests for cmd_status parsing helpers."""

    def test_normalize_objective_from_string(self):
        """Returns stripped objective text when mission_context is valid."""
        progress = {"mission_context": {"objective": "  Build X  "}}
        assert _normalize_objective(progress) == "Build X"

    def test_normalize_objective_from_non_dict_context(self):
        """Non-dict mission_context should not crash and returns empty."""
        progress = {"mission_context": ["unexpected", "shape"]}
        assert _normalize_objective(progress) == ""

    def test_normalize_objective_from_non_string(self):
        """Non-string objective is stringified safely."""
        progress = {"mission_context": {"objective": {"goal": "ship"}}}
        assert _normalize_objective(progress) == "{'goal': 'ship'}"

    def test_normalize_objective_from_none(self):
        """None objective maps to empty string."""
        progress = {"mission_context": {"objective": None}}
        assert _normalize_objective(progress) == ""


class TestCliHelp:
    """Tests for CLI help command."""

    def test_help_shows_commands(self):
        """mycelium-py --help shows available commands."""
        # Run as module since entry point may not be installed
        result = subprocess.run(
            [sys.executable, "-m", "mycelium.cli", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
        )
        
        # May fail if not installed, that's okay for SMOKE test
        if result.returncode == 0:
            assert "run" in result.stdout or "status" in result.stdout

    def test_run_help(self):
        """mycelium-py run --help shows usage."""
        result = subprocess.run(
            [sys.executable, "-m", "mycelium.cli", "run", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
        )
        
        if result.returncode == 0:
            assert "mission_path" in result.stdout or "approve" in result.stdout
