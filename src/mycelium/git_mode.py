"""
Git Mode for per-packet commit granularity (REV-004).

When Git Mode is enabled via Config/review_policy.yaml (git_mode.enabled=true),
promotions applied from Review Packets create exactly one git commit per
Source packet apply batch.

Commit subject schema:
    graduate packet=<packet_id> source=<source_id> run_ids=<sorted_csv>

Commit body includes applied queue_id values in deterministic lexical order.

Atomicity: if commit or write fails, no partial canonical mutations persist.

Spec reference: §8.3.1 REV-004
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PacketPromotion:
    """A batch of promotions grouped by source packet."""

    packet_id: str
    source_id: str
    run_ids: list[str]
    queue_ids: list[str]
    promoted_paths: list[str]


class GitModeError(Exception):
    """Raised when a Git Mode operation fails."""

    def __init__(self, message: str, code: str = "ERR_GIT_MODE_FAILED") -> None:
        self.code = code
        super().__init__(message)


def build_commit_subject(
    packet_id: str,
    source_id: str,
    run_ids: list[str],
) -> str:
    """Build the commit subject per AC-REV-004-3.

    Schema: graduate packet=<packet_id> source=<source_id> run_ids=<sorted_csv>
    """
    sorted_runs = ",".join(sorted(run_ids))
    return f"graduate packet={packet_id} source={source_id} run_ids={sorted_runs}"


def build_commit_body(queue_ids: list[str]) -> str:
    """Build the commit body per AC-REV-004-4.

    Includes queue_ids in deterministic lexical order.
    """
    sorted_ids = sorted(queue_ids)
    lines = ["Applied queue items:"]
    for qid in sorted_ids:
        lines.append(f"  - {qid}")
    return "\n".join(lines)


def _run_git(vault_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command in the vault root."""
    return subprocess.run(
        ["git", *args],
        cwd=vault_root,
        capture_output=True,
        text=True,
        check=False,
    )


def commit_packet_promotion(
    vault_root: Path,
    promotion: PacketPromotion,
) -> str:
    """Create a single git commit for a source packet promotion batch.

    Stages promoted files, creates the commit with the spec-defined schema,
    and returns the commit hash.

    Args:
        vault_root: Absolute path to the vault (git repo) root.
        promotion: The packet promotion batch.

    Returns:
        The commit SHA hex string.

    Raises:
        GitModeError: If git add or git commit fails (AC-REV-004-5).
    """
    # Stage promoted files
    for path in promotion.promoted_paths:
        result = _run_git(vault_root, "add", path)
        if result.returncode != 0:
            raise GitModeError(
                f"git add failed for {path}: {result.stderr.strip()}"
            )

    # Build commit message
    subject = build_commit_subject(
        promotion.packet_id,
        promotion.source_id,
        promotion.run_ids,
    )
    body = build_commit_body(promotion.queue_ids)
    message = f"{subject}\n\n{body}"

    # Commit
    result = _run_git(vault_root, "commit", "-m", message)
    if result.returncode != 0:
        raise GitModeError(
            f"git commit failed: {result.stderr.strip()}"
        )

    # Get the commit hash
    hash_result = _run_git(vault_root, "rev-parse", "HEAD")
    if hash_result.returncode != 0:
        raise GitModeError(
            f"git rev-parse HEAD failed: {hash_result.stderr.strip()}"
        )

    return hash_result.stdout.strip()


def apply_git_mode_promotions(
    vault_root: Path,
    packets: list[PacketPromotion],
    *,
    write_fn: Any = None,
) -> list[dict[str, Any]]:
    """Apply promotions in Git Mode: one commit per source packet.

    Args:
        vault_root: Absolute path to the vault (git repo) root.
        packets: List of packet promotion batches.
        write_fn: Optional callable(vault_root, promotion) to write files
                  before committing. If None, files are assumed pre-written.

    Returns:
        List of dicts with {packet_id, commit_hash, queue_ids}.

    Raises:
        GitModeError: If any git operation fails (atomicity guarantee).
    """
    results: list[dict[str, Any]] = []

    for promotion in packets:
        if write_fn is not None:
            write_fn(vault_root, promotion)

        commit_hash = commit_packet_promotion(vault_root, promotion)
        results.append({
            "packet_id": promotion.packet_id,
            "commit_hash": commit_hash,
            "queue_ids": sorted(promotion.queue_ids),
        })

    return results
