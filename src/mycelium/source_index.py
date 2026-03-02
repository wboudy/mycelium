"""Source identity index for idempotent ingestion (IDM-001).

Maintains a persistent mapping of ``(normalized_locator, fingerprint)`` to
``source_id`` under ``Indexes/`` in the vault. Supports O(1) lookups via
an in-memory dict backed by a JSON file.

Spec reference: §6.4 IDM-001, §3 INV-005
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mycelium.invariants import IngestionOutcome, SourceIdentity

# Default index file path relative to vault root
INDEX_FILENAME = "Indexes/source_identity_index.json"


class SourceIndex:
    """Persistent source identity index for idempotent ingestion.

    The index maps ``normalized_locator`` to a list of
    ``{source_id, fingerprint}`` records. This allows O(1) locator lookup
    and O(k) fingerprint comparison where k is the number of revisions
    for a single locator (typically 1-2).

    The index is persisted as JSON under ``Indexes/`` and survives process
    restart (AC-4). It is rebuildable from Source Notes if deleted (per INV-001).
    """

    def __init__(self, vault_dir: Path) -> None:
        self._vault_dir = vault_dir
        self._index_path = vault_dir / INDEX_FILENAME
        self._data: dict[str, list[dict[str, str]]] = {}
        self._load()

    def _load(self) -> None:
        """Load index from disk if it exists."""
        if self._index_path.exists():
            raw = self._index_path.read_text(encoding="utf-8")
            self._data = json.loads(raw) if raw.strip() else {}
        else:
            self._data = {}

    def _save(self) -> None:
        """Persist index to disk."""
        from mycelium.atomic_write import atomic_write_text

        content = json.dumps(self._data, indent=2, sort_keys=True)
        atomic_write_text(self._index_path, content, mkdir=True)

    def lookup(
        self, normalized_locator: str, fingerprint: str
    ) -> tuple[str, SourceIdentity | None]:
        """Look up a source by locator and fingerprint.

        Returns:
            A tuple of (outcome, matched_source) per INV-005 semantics:
            - SAME_CONTENT: exact match on locator+fingerprint.
            - REVISED_CONTENT: locator matches but fingerprint differs.
            - NEW_SOURCE: no matching locator.
        """
        records = self._data.get(normalized_locator)
        if records is None:
            return IngestionOutcome.NEW_SOURCE, None

        for rec in records:
            if rec["fingerprint"] == fingerprint:
                return IngestionOutcome.SAME_CONTENT, SourceIdentity(
                    source_id=rec["source_id"],
                    normalized_locator=normalized_locator,
                    fingerprint=fingerprint,
                )

        # Locator exists but fingerprint is new — revision
        latest = records[-1]
        return IngestionOutcome.REVISED_CONTENT, SourceIdentity(
            source_id=latest["source_id"],
            normalized_locator=normalized_locator,
            fingerprint=latest["fingerprint"],
        )

    def register(
        self, normalized_locator: str, fingerprint: str, source_id: str
    ) -> None:
        """Register a new source identity in the index.

        Args:
            normalized_locator: The deterministic locator string.
            fingerprint: The content fingerprint (sha256:<hex>).
            source_id: The assigned source_id.
        """
        if normalized_locator not in self._data:
            self._data[normalized_locator] = []

        # Avoid duplicate entries
        for rec in self._data[normalized_locator]:
            if rec["fingerprint"] == fingerprint:
                return

        self._data[normalized_locator].append({
            "source_id": source_id,
            "fingerprint": fingerprint,
        })
        self._save()

    def get_source_id(self, normalized_locator: str) -> str | None:
        """Get the source_id for a locator (latest revision)."""
        records = self._data.get(normalized_locator)
        if not records:
            return None
        return records[-1]["source_id"]

    def get_prior_fingerprint(
        self, normalized_locator: str, current_fingerprint: str
    ) -> str | None:
        """Get the fingerprint of the most recent prior revision.

        Returns None if this is the first ingestion of this locator or
        if the current fingerprint matches the latest.
        """
        records = self._data.get(normalized_locator)
        if not records:
            return None

        # Find the latest record that isn't the current fingerprint
        for rec in reversed(records):
            if rec["fingerprint"] != current_fingerprint:
                return rec["fingerprint"]

        return None

    @property
    def size(self) -> int:
        """Total number of source identity records."""
        return sum(len(records) for records in self._data.values())
