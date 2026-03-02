"""
Tests for future command stubs (CMD-FUT-001).

Acceptance Criteria:
- AC-CMD-FUT-001-1: Each command spec includes complete contract.
- AC-CMD-FUT-001-2: Contract tests validate envelope conformance.
"""

from __future__ import annotations

import pytest

from mycelium.commands.future_stubs import (
    CONNECT_CONTRACT,
    ERR_NOT_IMPLEMENTED,
    FUTURE_COMMAND_CONTRACTS,
    IDEAS_CONTRACT,
    TRACE_CONTRACT,
    connect,
    ideas,
    trace,
)
from mycelium.models import OutputEnvelope


# ---------------------------------------------------------------------------
# AC-CMD-FUT-001-1: Complete contracts
# ---------------------------------------------------------------------------

CONTRACT_REQUIRED_KEYS = {"command", "inputs", "outputs", "side_effects", "errors"}


class TestContractCompleteness:
    """Each command contract has inputs, outputs, side_effects, errors."""

    @pytest.mark.parametrize("name,contract", [
        ("connect", CONNECT_CONTRACT),
        ("trace", TRACE_CONTRACT),
        ("ideas", IDEAS_CONTRACT),
    ])
    def test_contract_has_required_keys(self, name: str, contract: dict):
        missing = CONTRACT_REQUIRED_KEYS - set(contract.keys())
        assert not missing, f"{name} contract missing keys: {missing}"

    def test_all_contracts_registered(self):
        assert set(FUTURE_COMMAND_CONTRACTS.keys()) == {"connect", "trace", "ideas"}


# ---------------------------------------------------------------------------
# AC-CMD-FUT-001-2: Envelope conformance
# ---------------------------------------------------------------------------

class TestEnvelopeConformance:
    """Stubs return valid OutputEnvelope with ERR_NOT_IMPLEMENTED."""

    def test_connect_returns_envelope(self):
        env = connect({})
        assert isinstance(env, OutputEnvelope)
        assert env.ok is False
        assert env.command == "connect"
        assert any(e.code == ERR_NOT_IMPLEMENTED for e in env.errors)

    def test_trace_returns_envelope(self):
        env = trace({})
        assert isinstance(env, OutputEnvelope)
        assert env.ok is False
        assert env.command == "trace"
        assert any(e.code == ERR_NOT_IMPLEMENTED for e in env.errors)

    def test_ideas_returns_envelope(self):
        env = ideas({})
        assert isinstance(env, OutputEnvelope)
        assert env.ok is False
        assert env.command == "ideas"
        assert any(e.code == ERR_NOT_IMPLEMENTED for e in env.errors)

    def test_envelope_has_timestamp(self):
        env = connect({})
        assert env.timestamp is not None

    def test_envelope_to_dict(self):
        env = trace({})
        d = env.to_dict()
        assert "ok" in d
        assert "command" in d
        assert "errors" in d
        assert d["ok"] is False
