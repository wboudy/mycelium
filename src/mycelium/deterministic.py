"""
Deterministic Test Mode for Mycelium (TST-G-002).

Provides two complementary mechanisms for golden fixture testing:

1. **Normalization** (``normalize_output``): strips or replaces
   nondeterministic fields (timestamps, UUIDs) from output dicts
   before comparison. This is the primary mechanism for golden tests.

2. **Fixed clock** (``fixed_clock``): a context manager that patches
   ``datetime.now`` and ``time.time`` to return a constant epoch,
   useful when tests need stable values *during* execution rather
   than post-hoc normalization.

Neither mechanism alters semantic fields (match classes, scores,
content, error codes, etc.), satisfying AC-TST-G-002-2.

Spec reference: §13.4 TST-G-002
"""

from __future__ import annotations

import copy
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Sentinel value used to replace all timestamps during normalization.
NORMALIZED_TIMESTAMP = "2000-01-01T00:00:00.000000Z"

#: Sentinel value used to replace all UUIDs during normalization.
NORMALIZED_UUID = "00000000-0000-0000-0000-000000000000"

#: Default epoch used by ``fixed_clock``.
FIXED_EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)

# Patterns for detecting nondeterministic values in strings.
_ISO8601_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"  # core datetime
    r"(?:\.\d+)?"                              # optional fractional seconds
    r"(?:Z|[+-]\d{2}:\d{2})?"                  # optional timezone
)

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# Keys whose values are always treated as nondeterministic.
_TIMESTAMP_KEYS = frozenset({
    "timestamp",
    "created_at",
    "updated_at",
    "ingested_at",
    "promoted_at",
    "reviewed_at",
    "expires_at",
})

_ID_KEYS = frozenset({
    "id",
    "uuid",
    "trace_id",
    "request_id",
    "run_id",
})


# ---------------------------------------------------------------------------
# Normalization (primary mechanism)
# ---------------------------------------------------------------------------

def normalize_output(data: dict[str, Any] | list | str) -> dict[str, Any] | list | str:
    """Replace nondeterministic fields in *data* with stable sentinels.

    Operates on a deep copy — the original data is never mutated.

    Rules:
    - Dict keys in ``_TIMESTAMP_KEYS`` → ``NORMALIZED_TIMESTAMP``
    - Dict keys in ``_ID_KEYS`` → ``NORMALIZED_UUID``
    - String values matching ISO-8601 patterns → ``NORMALIZED_TIMESTAMP``
    - String values matching UUID patterns → ``NORMALIZED_UUID``
    - All other values (including match classes, scores, content) are
      passed through unchanged (AC-TST-G-002-2).

    Args:
        data: The output structure to normalize.  Accepts dicts, lists,
              or bare strings.

    Returns:
        A deep-copied, normalized version of *data*.
    """
    data = copy.deepcopy(data)
    return _normalize(data)


def _normalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _normalize_value(k, v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize(item) for item in obj]
    if isinstance(obj, str):
        return _normalize_string(obj)
    return obj


def _normalize_value(key: str, value: Any) -> Any:
    """Normalize a single dict value, considering key semantics."""
    key_lower = key.lower()
    if key_lower in _TIMESTAMP_KEYS:
        return NORMALIZED_TIMESTAMP
    if key_lower in _ID_KEYS:
        return NORMALIZED_UUID
    return _normalize(value)


def _normalize_string(s: str) -> str:
    """Replace inline ISO-8601 timestamps and UUIDs in a string."""
    s = _UUID_RE.sub(NORMALIZED_UUID, s)
    s = _ISO8601_RE.sub(NORMALIZED_TIMESTAMP, s)
    return s


# ---------------------------------------------------------------------------
# Fixed clock (secondary mechanism)
# ---------------------------------------------------------------------------

@contextmanager
def fixed_clock(epoch: datetime | None = None):
    """Context manager that freezes ``datetime.now`` and ``time.time``.

    Inside the context, ``datetime.now()`` returns *epoch* (defaulting
    to ``FIXED_EPOCH``), and ``time.time()`` returns the corresponding
    POSIX timestamp.  All other ``datetime`` methods work normally.

    This is useful for tests that need deterministic timestamps *during*
    execution rather than normalizing after the fact.

    Args:
        epoch: The fixed point in time to return.  Defaults to
               ``FIXED_EPOCH`` (2000-01-01T00:00:00Z).

    Yields:
        The *epoch* datetime for convenience.

    Example::

        with fixed_clock() as now:
            envelope = make_envelope("test_cmd", data={"key": "val"})
            assert envelope.timestamp == "2000-01-01T00:00:00.000000Z"
    """
    epoch = epoch or FIXED_EPOCH
    epoch_posix = epoch.timestamp()

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return epoch.astimezone(tz)
            return epoch.replace(tzinfo=None)

        @classmethod
        def utcnow(cls):
            return epoch.replace(tzinfo=None)

    with patch("mycelium.models.datetime", _FrozenDatetime), \
         patch("mycelium.orchestrator.datetime", _FrozenDatetime), \
         patch("time.time", return_value=epoch_posix):
        yield epoch
