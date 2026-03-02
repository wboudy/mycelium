"""Quarantine with diagnostic sidecar for invalid artifacts (ERR-002).

Invalid or partial artifacts MUST be placed in `Quarantine/` with a
diagnostic sidecar file. The original corrupted canonical file (if any)
is never overwritten.

The sidecar is a YAML file alongside the quarantined copy, containing:
- The parse/validation error that triggered quarantine
- The original vault-relative path of the affected file
- A timestamp of when the quarantine occurred
- The stage (if applicable) where the error was detected

Spec reference: mycelium_refactor_plan_apr_round5.md §10.2 (ERR-002)
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


@dataclass
class QuarantineRecord:
    """Metadata for a quarantined artifact.

    Attributes:
        original_path: Vault-relative path of the source file.
        error_code: Deterministic error code (e.g., ERR_CORRUPTED_NOTE).
        error_message: Human-readable description of the error.
        quarantined_at: ISO-8601 UTC timestamp of quarantine.
        stage: Pipeline stage where the error was detected, if applicable.
        details: Optional additional context about the error.
    """

    original_path: str
    error_code: str
    error_message: str
    quarantined_at: str = ""
    stage: str | None = None
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.quarantined_at:
            self.quarantined_at = (
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "original_path": self.original_path,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "quarantined_at": self.quarantined_at,
        }
        if self.stage is not None:
            d["stage"] = self.stage
        if self.details is not None:
            d["details"] = self.details
        return d


@dataclass
class QuarantineResult:
    """Result of a quarantine operation.

    Attributes:
        quarantined_path: Vault-relative path of the quarantined copy.
        sidecar_path: Vault-relative path of the diagnostic sidecar.
        record: The quarantine metadata record.
        original_preserved: True if the original file was left untouched.
    """

    quarantined_path: str
    sidecar_path: str
    record: QuarantineRecord
    original_preserved: bool = True


def _quarantine_filename(original_path: str) -> str:
    """Derive the quarantine filename from the original vault-relative path.

    Replaces path separators with double-underscore to create a flat
    filename that preserves the original path info.
    E.g., "Sources/my-note.md" → "Sources__my-note.md"
    """
    return original_path.replace("/", "__").replace("\\", "__")


def _sidecar_filename(quarantined_name: str) -> str:
    """Derive the sidecar filename from the quarantined filename.

    E.g., "Sources__my-note.md" → "Sources__my-note.md.diagnostic.yaml"
    Uses the full filename (not stem) to avoid collisions between files
    with different extensions (e.g. note.md vs note.yaml).
    """
    return f"{quarantined_name}.diagnostic.yaml"


def quarantine_file(
    vault_root: Path,
    vault_relative_path: str,
    *,
    error_code: str,
    error_message: str,
    stage: str | None = None,
    details: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> QuarantineResult:
    """Move an invalid artifact to Quarantine/ with a diagnostic sidecar.

    AC-ERR-002-1: A corrupted frontmatter fixture results in a quarantined
    copy and a diagnostic file containing the parse error and the affected
    original path.

    AC-ERR-002-2: The original corrupted canonical file (if any) is not
    overwritten. We COPY (not move) to quarantine, preserving the original.

    Args:
        vault_root: Absolute path to the vault root directory.
        vault_relative_path: Vault-relative path of the file to quarantine.
        error_code: Deterministic error code.
        error_message: Human-readable description of the error.
        stage: Pipeline stage where the error was detected.
        details: Optional additional context.
        timestamp: Optional explicit timestamp (for deterministic testing).

    Returns:
        QuarantineResult with paths and metadata.

    Raises:
        FileNotFoundError: If the source file does not exist.
    """
    from mycelium.vault_layout import PathTraversalError, safe_vault_path

    try:
        source = safe_vault_path(vault_root, vault_relative_path)
    except PathTraversalError:
        raise FileNotFoundError(
            f"Invalid vault path (traversal detected): {vault_relative_path}"
        )
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {vault_relative_path}")

    # Create Quarantine directory if it doesn't exist
    quarantine_dir = vault_root / "Quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    # Derive filenames
    q_name = _quarantine_filename(vault_relative_path)
    s_name = _sidecar_filename(q_name)

    q_path = quarantine_dir / q_name
    s_path = quarantine_dir / s_name

    # Build the record
    record = QuarantineRecord(
        original_path=vault_relative_path,
        error_code=error_code,
        error_message=error_message,
        quarantined_at=timestamp or "",
        stage=stage,
        details=details,
    )

    # Copy the file to quarantine (AC-ERR-002-2: original not overwritten)
    shutil.copy2(str(source), str(q_path))

    # Write the diagnostic sidecar (atomic write for consistency)
    from mycelium.atomic_write import atomic_write_text

    yaml_content = yaml.dump(record.to_dict(), default_flow_style=False, allow_unicode=True)
    atomic_write_text(s_path, yaml_content, mkdir=False)

    # Return vault-relative paths
    q_rel = f"Quarantine/{q_name}"
    s_rel = f"Quarantine/{s_name}"

    return QuarantineResult(
        quarantined_path=q_rel,
        sidecar_path=s_rel,
        record=record,
        original_preserved=True,
    )
