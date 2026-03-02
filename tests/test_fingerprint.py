"""
Tests for Fingerprint stage (stage 3/7, §6.1.1).

Acceptance Criteria:
- AC-1: NormalizedSource → deterministic SourceIdentity with stable fingerprint.
- AC-2: Identical content → identical fingerprints across runs.
- AC-3: Changed content with same locator → different fingerprint.
- AC-4: Source identity index updated (tested at integration level).
- AC-5: On failure, error with stage="fingerprint".
"""

from __future__ import annotations

import pytest

from mycelium.stages.fingerprint import (
    ERR_FINGERPRINT_FAILED,
    STAGE_NAME,
    SourceIdentity,
    compute_fingerprint,
    fingerprint,
)
from mycelium.stages.normalize import NormalizedSource


def _make_source(text: str = "test content", locator: str = "https://example.com") -> NormalizedSource:
    return NormalizedSource(
        normalized_text=text,
        normalized_locator=locator,
        source_kind="url",
        source_ref="https://example.com",
    )


# ---------------------------------------------------------------------------
# AC-1: Deterministic fingerprint
# ---------------------------------------------------------------------------

class TestDeterministicFingerprint:
    """AC-1: produces deterministic SourceIdentity."""

    def test_produces_identity(self):
        source = _make_source()
        identity, env = fingerprint(source)
        assert identity is not None
        assert env.ok is True
        assert identity.normalized_locator == "https://example.com"
        assert identity.fingerprint.startswith("sha256:")

    def test_fingerprint_format(self):
        fp = compute_fingerprint("hello")
        assert fp.startswith("sha256:")
        hex_part = fp.split(":")[1]
        assert len(hex_part) == 64
        assert all(c in "0123456789abcdef" for c in hex_part)


# ---------------------------------------------------------------------------
# AC-2: Identical content → identical fingerprints
# ---------------------------------------------------------------------------

class TestIdenticalContent:
    """AC-2: same content always produces same fingerprint."""

    def test_same_text_same_fingerprint(self):
        fp1 = compute_fingerprint("identical content")
        fp2 = compute_fingerprint("identical content")
        assert fp1 == fp2

    def test_repeated_calls(self):
        fps = [compute_fingerprint("stable") for _ in range(10)]
        assert len(set(fps)) == 1

    def test_full_pipeline_determinism(self):
        source = _make_source("deterministic test")
        id1, _ = fingerprint(source)
        id2, _ = fingerprint(source)
        assert id1.fingerprint == id2.fingerprint


# ---------------------------------------------------------------------------
# AC-3: Changed content → different fingerprint
# ---------------------------------------------------------------------------

class TestChangedContent:
    """AC-3: different content → different fingerprint."""

    def test_different_text_different_fp(self):
        fp1 = compute_fingerprint("version 1")
        fp2 = compute_fingerprint("version 2")
        assert fp1 != fp2

    def test_same_locator_different_content(self):
        s1 = _make_source(text="original", locator="https://example.com")
        s2 = _make_source(text="updated", locator="https://example.com")
        id1, _ = fingerprint(s1)
        id2, _ = fingerprint(s2)
        assert id1.normalized_locator == id2.normalized_locator
        assert id1.fingerprint != id2.fingerprint


# ---------------------------------------------------------------------------
# AC-5: Failure → error with stage="fingerprint"
# ---------------------------------------------------------------------------

class TestFailure:
    """AC-5: failure returns error with stage='fingerprint'."""

    def test_empty_source(self):
        source = NormalizedSource(
            normalized_text="",
            normalized_locator="",
            source_kind="url",
            source_ref="",
        )
        identity, env = fingerprint(source)
        assert identity is None
        assert env.ok is False
        assert env.errors[0].code == ERR_FINGERPRINT_FAILED
        assert env.errors[0].stage == STAGE_NAME


# ---------------------------------------------------------------------------
# SourceIdentity
# ---------------------------------------------------------------------------

class TestSourceIdentity:

    def test_to_dict(self):
        si = SourceIdentity(
            normalized_locator="https://example.com",
            fingerprint="sha256:abc123",
        )
        d = si.to_dict()
        assert d["normalized_locator"] == "https://example.com"
        assert d["fingerprint"] == "sha256:abc123"

    def test_envelope_data(self):
        source = _make_source()
        identity, env = fingerprint(source)
        d = env.to_dict()
        assert d["data"]["fingerprint"].startswith("sha256:")
        assert d["data"]["normalized_locator"] == "https://example.com"
