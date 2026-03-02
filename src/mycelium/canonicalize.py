"""
Deterministic claim canonicalization (DED-001).

Produces stable canonical forms and extracted_claim_key hashes from
raw claim text. The same input always yields the same output across runs.

Spec reference: mycelium_refactor_plan_apr_round5.md §7.1
"""

from __future__ import annotations

import hashlib
import re
import unicodedata


def canonicalize(text: str) -> str:
    """Produce a deterministic canonical form of a claim text.

    Transformations applied (in order):
    1. Unicode NFC normalization — ensures composed forms.
    2. Strip leading/trailing whitespace.
    3. Collapse all interior whitespace runs (spaces, tabs, newlines) to a
       single ASCII space.
    4. Normalize Unicode punctuation to ASCII equivalents (curly quotes,
       em/en dashes, ellipses, etc.).
    5. Lowercase.

    The result is a stable string suitable for hashing.

    Args:
        text: Raw claim text (may contain irregular whitespace, mixed
              Unicode forms, varied punctuation).

    Returns:
        Canonical form string.
    """
    # 1. NFC normalization
    s = unicodedata.normalize("NFC", text)

    # 2-3. Strip and collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()

    # 4. Normalize common Unicode punctuation to ASCII
    s = _normalize_punctuation(s)

    # 5. Lowercase
    s = s.lower()

    return s


def extracted_claim_key(text: str) -> str:
    """Compute the deterministic claim key for a given text.

    Formula (DED-001):
        extracted_claim_key = "h-" + first_12_hex(sha256(canonical_form_utf8_bytes))

    Args:
        text: Raw claim text.

    Returns:
        A string like ``"h-a1b2c3d4e5f6"`` (14 chars total).
    """
    canonical = canonicalize(text)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"h-{digest[:12]}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Map of Unicode code points to ASCII replacements.
_PUNCT_MAP = str.maketrans(
    {
        # Curly/smart quotes → straight
        "\u2018": "'",   # '
        "\u2019": "'",   # '
        "\u201c": '"',   # "
        "\u201d": '"',   # "
        # Dashes
        "\u2013": "-",   # en dash
        "\u2014": "-",   # em dash
        # Ellipsis
        "\u2026": "...",
        # Non-breaking space
        "\u00a0": " ",
    }
)


def _normalize_punctuation(s: str) -> str:
    """Replace common Unicode punctuation with ASCII equivalents."""
    return s.translate(_PUNCT_MAP)
