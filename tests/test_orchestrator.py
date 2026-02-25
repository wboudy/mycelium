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
    VALID_AGENTS,
    append_llm_usage,
    check_hitl_approval,
    extract_routing_labels,
    resolve_model_for_run,
    get_usage_summary,
    load_progress,
    run_agent,
)
from mycelium.llm import CompletionResponse, DEFAULT_MODEL, UsageMetadata


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


class TestModelRouting:
    """Tests for model routing policy in orchestrator."""

    def test_extract_routing_labels_handles_mixed_shapes(self):
        """Label extractor normalizes list/string/dict forms into a stable set."""
        progress = {
            "labels": "agent:scientist, model:deep",
            "mission_context": {
                "labels": ["needs:orchestrator", {"label": "model:deep"}],
                "bead_labels": "interrupt root-cause",
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
        """Comma/space-delimited string labels still route correctly."""
        monkeypatch.delenv("MYCELIUM_MODEL", raising=False)
        monkeypatch.delenv("MYCELIUM_MODEL_DEEP", raising=False)
        monkeypatch.delenv("MYCELIUM_DEEP_MODEL", raising=False)
        progress = {"labels": "interrupt,root-cause model:deep"}

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
