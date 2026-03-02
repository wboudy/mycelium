"""
Extract stage — stage 4/7 of the ingestion pipeline (§6.1.1).

Input:  NormalizedSource
Output: ExtractionBundle artifact (SCH-008 compliant)
Side effects: Writes Extraction Bundle artifacts under Inbox/Sources/.
Errors: ERR_EXTRACTION_FAILED, ERR_SCHEMA_VALIDATION

Spec reference: mycelium_refactor_plan_apr_round5.md §6.1.1, §6.2 EXT-001, §4.2.8 SCH-008
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from mycelium.canonicalize import extracted_claim_key
from mycelium.models import (
    ErrorObject,
    OutputEnvelope,
    WarningObject,
    make_envelope,
)
from mycelium.schema import (
    CLAIM_TYPES,
    POLARITIES,
    validate_extraction_bundle,
)
from mycelium.stages.normalize import NormalizedSource

STAGE_NAME = "extract"

# Error codes (§10.1)
ERR_EXTRACTION_FAILED = "ERR_EXTRACTION_FAILED"
ERR_SCHEMA_VALIDATION = "ERR_SCHEMA_VALIDATION"

# Warning codes (§6.2 EXT-001)
WARN_NO_CLAIMS_EXTRACTED = "WARN_NO_CLAIMS_EXTRACTED"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Claim:
    """A single extracted claim from a source."""

    claim_text: str
    claim_type: str = "empirical"
    polarity: str = "supports"
    provenance: dict[str, Any] = field(default_factory=dict)
    suggested_note_id: str | None = None
    notes: str | None = None

    def to_dict(self, source_id: str, source_ref: str, source_kind: str) -> dict[str, Any]:
        """Convert to SCH-008 compliant claim dict."""
        d: dict[str, Any] = {
            "extracted_claim_key": extracted_claim_key(self.claim_text),
            "claim_text": self.claim_text,
            "claim_type": self.claim_type,
            "polarity": self.polarity,
            "provenance": self.provenance or _make_provenance(
                source_id, source_ref, source_kind, self.claim_text,
            ),
        }
        if self.suggested_note_id is not None:
            d["suggested_note_id"] = self.suggested_note_id
        if self.notes is not None:
            d["notes"] = self.notes
        return d


@dataclass
class ExtractionResult:
    """Internal result of the extraction process."""

    gist: str
    bullets: list[str] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    entities: list[Any] = field(default_factory=list)
    definitions: list[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Provenance construction
# ---------------------------------------------------------------------------

def _snippet_hash(text: str) -> str:
    """Compute sha256:<hex> hash for a snippet."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _make_provenance(
    source_id: str,
    source_ref: str,
    source_kind: str,
    claim_text: str,
    *,
    section: str | None = None,
    paragraph_index: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """Build a provenance object conforming to SCH-003 locator minima."""
    prov: dict[str, Any] = {
        "source_id": source_id,
        "source_ref": source_ref,
        "locator": _make_locator(
            source_kind, source_ref, claim_text,
            section=section,
            paragraph_index=paragraph_index,
            page=page,
        ),
    }
    return prov


def _make_locator(
    source_kind: str,
    source_ref: str,
    claim_text: str,
    *,
    section: str | None = None,
    paragraph_index: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """Build a locator dict based on source_kind per §4.2.3."""
    sh = _snippet_hash(claim_text)

    if source_kind == "url":
        return {
            "url": source_ref,
            "section": section,
            "paragraph_index": paragraph_index,
            "snippet_hash": sh,
        }
    elif source_kind == "pdf":
        return {
            "pdf_ref": source_ref,
            "page": page or 1,
            "section": section,
            "snippet_hash": sh,
        }
    else:
        # MVP1 fallback for other source kinds
        return {"raw_locator": source_ref}


# ---------------------------------------------------------------------------
# Text extraction (rule-based MVP1 implementation)
# ---------------------------------------------------------------------------

def _extract_gist(text: str) -> str:
    """Extract a one-line gist from the text."""
    lines = text.strip().split("\n")
    # Use first non-empty line, truncated
    for line in lines:
        stripped = line.strip()
        if stripped:
            if len(stripped) > 200:
                return stripped[:197] + "..."
            return stripped
    return "(empty document)"


def _extract_bullets(text: str) -> list[str]:
    """Extract key bullet points from the text."""
    bullets: list[str] = []
    lines = text.strip().split("\n")

    for line in lines:
        stripped = line.strip()
        # Detect existing bullet/numbered list items
        if re.match(r"^[-*•]\s+", stripped):
            bullet_text = re.sub(r"^[-*•]\s+", "", stripped).strip()
            if bullet_text:
                bullets.append(bullet_text)
        elif re.match(r"^\d+[.)]\s+", stripped):
            bullet_text = re.sub(r"^\d+[.)]\s+", "", stripped).strip()
            if bullet_text:
                bullets.append(bullet_text)

    # If no bullets found, use first few non-empty, non-heading lines
    if not bullets:
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                bullets.append(stripped)
                if len(bullets) >= 3:
                    break

    return bullets


def _extract_claims(text: str) -> list[Claim]:
    """Extract claims from text using rule-based heuristics.

    MVP1 approach: treat sentences with assertive patterns as claims.
    """
    claims: list[Claim] = []
    sentences = _split_sentences(text)

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 10:
            continue

        claim_type = _classify_claim_type(sentence)
        if claim_type is not None:
            polarity = _classify_polarity(sentence)
            claims.append(Claim(
                claim_text=sentence,
                claim_type=claim_type,
                polarity=polarity,
            ))

    return claims


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # First strip heading lines so they don't contaminate sentence splitting
    lines = text.split("\n")
    clean_lines = [line for line in lines if not line.strip().startswith("#")]
    clean_text = "\n".join(clean_lines)

    # Simple sentence splitting on period/question/exclamation followed by space or end
    sentences = re.split(r'(?<=[.!?])\s+', clean_text)
    result = []
    for s in sentences:
        s = s.strip()
        if s and len(s) > 5:
            result.append(s)
    return result


def _classify_claim_type(sentence: str) -> str | None:
    """Classify a sentence as a claim type or None if not a claim.

    Returns one of the CLAIM_TYPES or None.
    """
    lower = sentence.lower()

    # Definition patterns (avoid overly broad '\bis a\b' which matches most English sentences)
    if re.search(r'\bis defined as\b|\bmeans\b|\brefers to\b', lower):
        return "definition"

    # Causal patterns
    if re.search(r'\bcauses?\b|\bleads? to\b|\bresults? in\b|\bbecause\b|\btherefore\b', lower):
        return "causal"

    # Normative patterns (should/must/ought)
    if re.search(r'\bshould\b|\bmust\b|\bought to\b|\brequired?\b|\bshall\b', lower):
        return "normative"

    # Procedural patterns
    if re.search(r'\bsteps?\b|\bprocess\b|\bprocedure\b|\bfirst\b.*\bthen\b|\bhow to\b', lower):
        return "procedural"

    # Empirical patterns (factual assertions)
    if re.search(
        r'\bstud(?:y|ies)\b|\bresearch\b|\bdata\b|\bfound\b|\bshow(?:s|ed|n)?\b'
        r'|\bevidence\b|\bobserved?\b|\bmeasured?\b|\bincreases?\b|\bdecreases?\b',
        lower,
    ):
        return "empirical"

    # General assertions that look like claims
    if re.search(r'\bis\b|\bare\b|\bwas\b|\bwere\b|\bhas\b|\bhave\b', lower):
        if len(sentence) > 30:
            return "empirical"

    return None


def _classify_polarity(sentence: str) -> str:
    """Classify the polarity of a claim sentence."""
    lower = sentence.lower()
    if re.search(r'\bnot\b|\bnever\b|\bno\b|\bfails?\b|\bcannot\b|\bdoes not\b|\bdon\'t\b', lower):
        return "opposes"
    if re.search(r'\bhowever\b|\bbut\b|\balthough\b|\bdespite\b|\bcontrary\b', lower):
        return "neutral"
    return "supports"


# ---------------------------------------------------------------------------
# Bundle construction
# ---------------------------------------------------------------------------

def _build_bundle(
    source: NormalizedSource,
    result: ExtractionResult,
    *,
    run_id: str | None = None,
    source_id: str | None = None,
) -> dict[str, Any]:
    """Build a SCH-008 compliant ExtractionBundle dict."""
    rid = run_id or str(uuid.uuid4())
    sid = source_id or source.extracted_metadata.get("source_id", source.source_ref)

    bundle_warnings: list[dict[str, Any]] = []

    # AC-SCH-008-3: If no claims, add WARN_NO_CLAIMS_EXTRACTED
    if not result.claims:
        bundle_warnings.append({
            "code": WARN_NO_CLAIMS_EXTRACTED,
            "message": "No claims were extracted from this source",
        })

    claims_dicts = [
        c.to_dict(sid, source.source_ref, source.source_kind)
        for c in result.claims
    ]

    return {
        "run_id": rid,
        "source_id": sid,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "gist": result.gist,
        "bullets": result.bullets,
        "claims": claims_dicts,
        "entities": result.entities,
        "definitions": result.definitions,
        "warnings": bundle_warnings,
    }


# ---------------------------------------------------------------------------
# Main extract function
# ---------------------------------------------------------------------------

def extract(
    source: NormalizedSource,
    *,
    vault_root: Path | None = None,
    run_id: str | None = None,
    source_id: str | None = None,
) -> tuple[dict[str, Any] | None, OutputEnvelope]:
    """Execute the extract stage.

    Extracts claims, gist, and bullets from a NormalizedSource, producing
    an ExtractionBundle (SCH-008). Optionally writes the bundle to disk.

    Args:
        source: A NormalizedSource from the normalize stage.
        vault_root: If provided, writes the bundle YAML to Inbox/Sources/.
        run_id: Optional run ID (auto-generated if omitted).
        source_id: Optional source ID override.

    Returns:
        Tuple of (bundle_dict_or_none, envelope).
        On success, bundle_dict is SCH-008 compliant and envelope.ok is True.
        On failure, bundle_dict is None and envelope contains the error.
    """
    if not source.normalized_text:
        return None, make_envelope(
            STAGE_NAME,
            errors=[ErrorObject(
                code=ERR_EXTRACTION_FAILED,
                message="NormalizedSource has empty normalized_text",
                retryable=False,
                stage=STAGE_NAME,
            )],
        )

    # Run extraction
    try:
        extraction = ExtractionResult(
            gist=_extract_gist(source.normalized_text),
            bullets=_extract_bullets(source.normalized_text),
            claims=_extract_claims(source.normalized_text),
        )
    except Exception as e:
        return None, make_envelope(
            STAGE_NAME,
            errors=[ErrorObject(
                code=ERR_EXTRACTION_FAILED,
                message=f"Extraction failed: {e}",
                retryable=True,
                stage=STAGE_NAME,
                details={"source_ref": source.source_ref},
            )],
        )

    # Build bundle dict
    bundle = _build_bundle(
        source, extraction, run_id=run_id, source_id=source_id,
    )

    # Validate against SCH-008
    schema_errors = validate_extraction_bundle(bundle)
    if schema_errors:
        return None, make_envelope(
            STAGE_NAME,
            errors=[ErrorObject(
                code=ERR_SCHEMA_VALIDATION,
                message=f"ExtractionBundle failed schema validation: {'; '.join(schema_errors)}",
                retryable=False,
                stage=STAGE_NAME,
                details={"schema_errors": schema_errors},
            )],
        )

    # Write to disk if vault_root provided
    artifact_path: str | None = None
    if vault_root is not None:
        try:
            artifact_path = _write_bundle(vault_root, bundle)
        except Exception as e:
            return None, make_envelope(
                STAGE_NAME,
                errors=[ErrorObject(
                    code=ERR_EXTRACTION_FAILED,
                    message=f"Failed to write ExtractionBundle: {e}",
                    retryable=True,
                    stage=STAGE_NAME,
                    details={"vault_root": str(vault_root)},
                )],
            )

    # Build envelope data
    envelope_data: dict[str, Any] = {
        "run_id": bundle["run_id"],
        "source_id": bundle["source_id"],
        "gist": bundle["gist"],
        "claims_count": len(bundle["claims"]),
        "bullets_count": len(bundle["bullets"]),
    }
    if artifact_path:
        envelope_data["artifact_path"] = artifact_path

    # Forward bundle warnings as envelope warnings
    envelope_warnings = [
        WarningObject(code=w["code"], message=w["message"])
        for w in bundle.get("warnings", [])
    ]

    return bundle, make_envelope(
        STAGE_NAME,
        data=envelope_data,
        warnings=envelope_warnings or None,
    )


def _write_bundle(vault_root: Path, bundle: dict[str, Any]) -> str:
    """Write an ExtractionBundle to Inbox/Sources/ as YAML.

    Returns the vault-relative path of the written file.
    """
    inbox = vault_root / "Inbox" / "Sources"
    inbox.mkdir(parents=True, exist_ok=True)

    # Filename: <run_id>_extraction.yaml — sanitize run_id to prevent path traversal
    run_id = bundle["run_id"]
    safe_run_id = run_id.replace("/", "_").replace("\\", "_").replace("..", "_")
    filename = f"{safe_run_id}_extraction.yaml"
    filepath = inbox / filename
    # Verify the resolved path is still under inbox
    if not filepath.resolve().is_relative_to(inbox.resolve()):
        raise ValueError(f"run_id {run_id!r} would escape Inbox/Sources/")

    from mycelium.atomic_write import atomic_write_text

    yaml_content = yaml.safe_dump(
        bundle,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    atomic_write_text(filepath, yaml_content, mkdir=False)

    return f"Inbox/Sources/{filename}"
