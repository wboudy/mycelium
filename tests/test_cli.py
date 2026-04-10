"""Tests for Mycelium CLI helpers."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

from mycelium.cli import _resolve_auto_config


def _auto_args(
    *,
    max_iterations: int | None = None,
    max_cost: float | None = None,
    max_failures: int | None = None,
    approve: bool = False,
) -> Namespace:
    """Build argparse namespace used by _resolve_auto_config tests."""
    return Namespace(
        max_iterations=max_iterations,
        max_cost=max_cost,
        max_failures=max_failures,
        approve=approve,
    )


class TestResolveAutoConfig:
    """Tests for auto-loop configuration resolution."""

    def test_invalid_env_values_fall_back_to_defaults(self):
        """Malformed env values should not crash and should use defaults."""
        env = {
            "MYCELIUM_MAX_ITERATIONS": "abc",
            "MYCELIUM_MAX_COST": "nope",
            "MYCELIUM_MAX_FAILURES": "-2",
            "MYCELIUM_AUTO_APPROVE": "yes",
        }
        with patch.dict("os.environ", env, clear=True):
            max_iterations, max_cost, max_failures, auto_approve = _resolve_auto_config(
                _auto_args()
            )

        assert max_iterations == 10
        assert max_cost == 1.0
        assert max_failures == 3
        assert auto_approve is True

    def test_explicit_cli_values_are_sanitized_and_override_env(self):
        """CLI numeric args should win over env and clamp invalid bounds."""
        env = {
            "MYCELIUM_MAX_ITERATIONS": "50",
            "MYCELIUM_MAX_COST": "2.5",
            "MYCELIUM_MAX_FAILURES": "8",
            "MYCELIUM_AUTO_APPROVE": "false",
        }
        with patch.dict("os.environ", env, clear=True):
            max_iterations, max_cost, max_failures, auto_approve = _resolve_auto_config(
                _auto_args(max_iterations=0, max_cost=-3.0, max_failures=0, approve=False)
            )

        assert max_iterations == 1
        assert max_cost == 0.0
        assert max_failures == 1
        assert auto_approve is False

    def test_cli_approve_flag_takes_precedence(self):
        """Explicit --approve should enable auto-approve regardless of env."""
        with patch.dict("os.environ", {"MYCELIUM_AUTO_APPROVE": "0"}, clear=True):
            _, _, _, auto_approve = _resolve_auto_config(_auto_args(approve=True))

        assert auto_approve is True
