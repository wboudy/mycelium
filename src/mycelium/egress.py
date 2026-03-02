"""
Egress policy enforcement (SEC-001, SEC-002, SEC-003).

Governs external egress through allowlist/blocklist pattern matching.
Blocklisted paths fail with ERR_EGRESS_POLICY_BLOCK and emit an
egress_blocked audit event. Allowed payloads emit egress_completed.

SEC-002 adds content logging: egress audit events include either a
locally stored payload reference or a payload digest plus source file
paths, and a reason field.

SEC-003 adds mode-aware evaluation: in ``report_only`` mode, blocked
content is logged as simulation but the send path remains allowed;
in ``enforce`` mode, blocklisted payloads are rejected.

Spec reference: §9.2 SEC-001, SEC-002, SEC-003
"""

from __future__ import annotations

import hashlib
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from mycelium.audit import EventType, emit_event


# ── Default patterns (§9.2) ─────────────────────────────────────────────

DEFAULT_ALLOWLIST: tuple[str, ...] = (
    "Sources/**",
    "Claims/**",
    "Concepts/**",
    "Questions/**",
    "Projects/**",
    "MOCs/**",
    "Inbox/ReviewDigest/**",
    "Reports/Delta/**",
)

DEFAULT_BLOCKLIST: tuple[str, ...] = (
    "Logs/Audit/**",
    "Indexes/**",
    "Quarantine/**",
    "**/.git/**",
    "**/*.key",
    "**/*.pem",
    "**/*secret*",
)


class EgressPolicyError(Exception):
    """Raised when egress is blocked by policy."""

    def __init__(self, path: str, matched_pattern: str) -> None:
        self.code = "ERR_EGRESS_POLICY_BLOCK"
        self.path = path
        self.matched_pattern = matched_pattern
        super().__init__(
            f"{self.code}: path {path!r} blocked by pattern {matched_pattern!r}"
        )


def _matches_any(path: str, patterns: tuple[str, ...] | list[str]) -> str | None:
    """Check if a vault-relative path matches any glob pattern.

    Returns the first matching pattern, or None.
    """
    for pattern in patterns:
        if fnmatch(path, pattern):
            return pattern
    return None


def check_egress_policy(
    path: str,
    allowlist: tuple[str, ...] | list[str] = DEFAULT_ALLOWLIST,
    blocklist: tuple[str, ...] | list[str] = DEFAULT_BLOCKLIST,
) -> tuple[bool, str | None]:
    """Check whether a vault-relative path is allowed for egress.

    Blocklist is checked first (deny takes priority).

    Returns:
        Tuple of (allowed: bool, matched_pattern: str | None).
        If blocked, matched_pattern is the blocklist pattern.
        If allowed, matched_pattern is the allowlist pattern.
        If neither matches, returns (False, None) — default deny.
    """
    # Check blocklist first (deny wins)
    blocked_by = _matches_any(path, blocklist)
    if blocked_by:
        return False, blocked_by

    # Check allowlist
    allowed_by = _matches_any(path, allowlist)
    if allowed_by:
        return True, allowed_by

    # Default deny
    return False, None


def compute_payload_digest(payload: bytes) -> str:
    """Compute a SHA-256 digest of the payload.

    Returns:
        Hex-encoded SHA-256 digest prefixed with ``sha256:``.
    """
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def egress(
    vault_root: Path,
    path: str,
    payload_bytes: int,
    destination: str,
    *,
    actor: str = "unknown",
    reason: str | None = None,
    payload_ref: str | None = None,
    payload_digest: str | None = None,
    source_paths: list[str] | None = None,
    allowlist: tuple[str, ...] | list[str] = DEFAULT_ALLOWLIST,
    blocklist: tuple[str, ...] | list[str] = DEFAULT_BLOCKLIST,
) -> dict[str, Any]:
    """Attempt to egress a vault-relative path.

    Checks the path against blocklist/allowlist. If blocked, emits
    egress_blocked audit event and raises EgressPolicyError. If allowed,
    emits egress_completed audit event.

    SEC-002 content logging: callers should supply either ``payload_ref``
    (a locally stored outbound payload reference) or ``payload_digest``
    plus ``source_paths``. A ``reason`` field documents why the egress
    was performed.

    Args:
        vault_root: Absolute path to the vault root.
        path: Vault-relative path to egress.
        payload_bytes: Size of the payload in bytes.
        destination: Destination identifier (e.g. API endpoint, email).
        actor: Who/what is performing the egress.
        reason: Why the egress is being performed (AC-SEC-002-2).
        payload_ref: Locally stored outbound payload reference (AC-SEC-002-1a).
        payload_digest: Cryptographic digest of payload (AC-SEC-002-1b).
        source_paths: Source file paths included in payload (AC-SEC-002-1b).
        allowlist: Allowlist glob patterns.
        blocklist: Blocklist glob patterns.

    Returns:
        Dict with egress result details on success.

    Raises:
        EgressPolicyError: If the path is blocked by policy (AC-SEC-001-1).
    """
    allowed, matched = check_egress_policy(path, allowlist, blocklist)

    if not allowed:
        # AC-SEC-001-1: emit egress_blocked audit event
        blocked_details: dict[str, Any] = {
            "reason": "ERR_EGRESS_POLICY_BLOCK",
            "blocked_pattern": matched,
            "destination": destination,
        }
        if reason is not None:
            blocked_details["egress_reason"] = reason
        emit_event(
            vault_root,
            EventType.EGRESS_BLOCKED,
            actor=actor,
            targets=[path],
            details=blocked_details,
        )
        raise EgressPolicyError(path, matched or "default_deny")

    # AC-SEC-001-2 + AC-SEC-002: emit egress_completed audit event
    completed_details: dict[str, Any] = {
        "bytes_sent": payload_bytes,
        "destination": destination,
        "allowed_pattern": matched,
    }

    # AC-SEC-002-2: reason field
    if reason is not None:
        completed_details["reason"] = reason

    # AC-SEC-002-1: content reference — either (a) or (b)
    if payload_ref is not None:
        completed_details["payload_ref"] = payload_ref
    if payload_digest is not None:
        completed_details["payload_digest"] = payload_digest
    if source_paths is not None:
        completed_details["source_paths"] = source_paths

    emit_event(
        vault_root,
        EventType.EGRESS_COMPLETED,
        actor=actor,
        targets=[path],
        details=completed_details,
    )

    result: dict[str, Any] = {
        "path": path,
        "allowed": True,
        "bytes_sent": payload_bytes,
        "destination": destination,
        "matched_pattern": matched,
    }
    if reason is not None:
        result["reason"] = reason
    if payload_ref is not None:
        result["payload_ref"] = payload_ref
    if payload_digest is not None:
        result["payload_digest"] = payload_digest
    if source_paths is not None:
        result["source_paths"] = source_paths

    return result


def egress_with_policy(
    vault_root: Path,
    path: str,
    payload_bytes: int,
    destination: str,
    *,
    mode: str = "enforce",
    actor: str = "unknown",
    reason: str | None = None,
    payload_ref: str | None = None,
    payload_digest: str | None = None,
    source_paths: list[str] | None = None,
    allowlist: tuple[str, ...] | list[str] = DEFAULT_ALLOWLIST,
    blocklist: tuple[str, ...] | list[str] = DEFAULT_BLOCKLIST,
) -> dict[str, Any]:
    """Mode-aware egress evaluation (SEC-003).

    In ``enforce`` mode (AC-SEC-003-2), behaves identically to ``egress()``:
    blocklisted payloads raise EgressPolicyError.

    In ``report_only`` mode (AC-SEC-003-1), blocked content is logged as
    a simulation ``egress_blocked`` event but the send path is allowed —
    no exception is raised and the result is returned with
    ``simulated_block=True``.

    Args:
        vault_root: Absolute path to the vault root.
        path: Vault-relative path to egress.
        payload_bytes: Size of the payload in bytes.
        destination: Destination identifier.
        mode: Egress mode (``report_only`` or ``enforce``).
        actor: Who/what is performing the egress.
        reason: Why the egress is being performed.
        payload_ref: Locally stored outbound payload reference.
        payload_digest: Cryptographic digest of payload.
        source_paths: Source file paths included in payload.
        allowlist: Allowlist glob patterns.
        blocklist: Blocklist glob patterns.

    Returns:
        Dict with egress result details.

    Raises:
        EgressPolicyError: In ``enforce`` mode only, if blocked by policy.
    """
    if mode not in ("enforce", "report_only"):
        raise ValueError(
            f"Invalid egress mode {mode!r}: must be 'enforce' or 'report_only'"
        )

    if mode == "enforce":
        return egress(
            vault_root,
            path,
            payload_bytes,
            destination,
            actor=actor,
            reason=reason,
            payload_ref=payload_ref,
            payload_digest=payload_digest,
            source_paths=source_paths,
            allowlist=allowlist,
            blocklist=blocklist,
        )

    # report_only mode: check policy but don't block
    allowed, matched = check_egress_policy(path, allowlist, blocklist)

    if not allowed:
        # AC-SEC-003-1: log simulation egress_blocked but allow send
        sim_details: dict[str, Any] = {
            "reason": "ERR_EGRESS_POLICY_BLOCK",
            "blocked_pattern": matched,
            "destination": destination,
            "simulation": True,
        }
        if reason is not None:
            sim_details["egress_reason"] = reason
        emit_event(
            vault_root,
            EventType.EGRESS_BLOCKED,
            actor=actor,
            targets=[path],
            details=sim_details,
        )

        # Return success with simulation flag — send path remains allowed
        result: dict[str, Any] = {
            "path": path,
            "allowed": True,
            "simulated_block": True,
            "would_block_pattern": matched,
            "bytes_sent": payload_bytes,
            "destination": destination,
        }
        if reason is not None:
            result["reason"] = reason
        # SEC-002: include content logging fields in simulation results
        if payload_ref is not None:
            result["payload_ref"] = payload_ref
        if payload_digest is not None:
            result["payload_digest"] = payload_digest
        if source_paths is not None:
            result["source_paths"] = source_paths
        return result

    # Path is allowed — proceed normally
    return egress(
        vault_root,
        path,
        payload_bytes,
        destination,
        actor=actor,
        reason=reason,
        payload_ref=payload_ref,
        payload_digest=payload_digest,
        source_paths=source_paths,
        allowlist=allowlist,
        blocklist=blocklist,
    )
