"""Atomic file write utility (PIPE-002, AC-5).

Implements the temp-file-plus-rename pattern to prevent partially written
files from being visible to other processes or pipeline stages.

Spec reference: §6.3 PIPE-002
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(
    path: Path,
    content: str,
    *,
    encoding: str = "utf-8",
    mkdir: bool = True,
) -> None:
    """Write content to a file atomically using temp file + rename.

    Creates a temporary file in the same directory as the target, writes
    the content, flushes, then renames to the target path. On POSIX
    systems, rename is atomic within the same filesystem.

    Args:
        path: Target file path.
        content: Text content to write.
        encoding: Text encoding (default utf-8).
        mkdir: If True, create parent directories as needed.

    Raises:
        OSError: If the write or rename fails.
    """
    if mkdir:
        path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except BaseException:
        # Clean up temp file on any failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_bytes(
    path: Path,
    content: bytes,
    *,
    mkdir: bool = True,
) -> None:
    """Write bytes to a file atomically using temp file + rename.

    Args:
        path: Target file path.
        content: Bytes content to write.
        mkdir: If True, create parent directories as needed.

    Raises:
        OSError: If the write or rename fails.
    """
    if mkdir:
        path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
