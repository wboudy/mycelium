# Mycelium Agentic Knowledge Vault Specification
Version: 1.0  
Status: Final

## 1. Overview
Mycelium is a local-first, Obsidian-compatible knowledge vault. Markdown notes and Obsidian wikilinks are the canonical knowledge substrate. Sources are ingested through a staged pipeline that extracts structured knowledge, computes deltas against the existing vault, proposes graph/link updates, and surfaces the user’s “knowledge frontier.” Human authorship remains authoritative: agents may draft, but canonical notes change only through explicit human promotion.

## 2. Glossary
| Term | Definition |
|---|---|
| Vault | The Obsidian-compatible root directory containing canonical Markdown notes plus derived artifacts. |
| Canonical Content | Markdown notes in the Vault that represent the user-approved knowledge base. |
| Derived Artifact | Machine-generated files that can be rebuilt (e.g., indexes) or are durable outputs (e.g., delta reports, audit logs). |
| Obsidian Wikilink | An internal link in the form `[[Path/NoteId]]` understood by Obsidian. |
| Note | A Markdown file with YAML frontmatter at the top and a Markdown body. |
| Note Type | The `type` frontmatter value defining the schema: `source`, `claim`, `concept`, `question`, `project`, `moc`. |
| Note Status | The `status` frontmatter value: `draft`, `reviewed`, `canon`. |
| Canonical Note | A Note with `status: canon` located in canonical directories. |
| Draft Note | A Note with `status: draft` located in draft/inbox directories. |
| Reviewed Note | A Note with `status: reviewed` that is eligible for promotion to `canon`. |
| Source | An external artifact (URL, PDF, DOI/arXiv reference, highlights bundle, book notes bundle, or other text bundle) being ingested. |
| Source Note | A Note representing one Source, including identity, fingerprint, and metadata. |
| Source Kind | The normalized class of a Source input, e.g., `url`, `pdf`, `doi`, `arxiv`, `highlights`, `book`, `text_bundle`. |
| Normalized Locator | A deterministic identifier for where the Source came from (e.g., canonicalized URL string, PDF path digest, DOI string). |
| Source Fingerprint | A deterministic hash derived from the normalized Source payload used for idempotency. |
| Ingestion Job | One end-to-end pipeline execution for one Source input. |
| Run ID | A unique identifier for an Ingestion Job execution. |
| Source ID | A stable identifier for a Source Note, reused across idempotent re-ingestion of identical normalized payloads. |
| Extraction Bundle | The structured outputs produced by extraction (e.g., gist, bullets, claims, entities). |
| Claim | An atomic, falsifiable assertion extracted from a Source and tracked in the Vault. |
| Claim Note | A Note whose primary payload is a single Claim with provenance. |
| Provenance | Metadata linking extracted knowledge to its Source and a locator within that Source. |
| Locator | A structured pointer into a Source (e.g., section name, paragraph index, page number). |
| Claim Canonicalization | Deterministic normalization of claim text to support matching/deduplication. |
| Match Class | The classification of an extracted claim against existing claims: `EXACT`, `NEAR_DUPLICATE`, `SUPPORTING`, `CONTRADICTING`, `NEW`. |
| Dedupe | The process of avoiding creation of duplicate claims by matching against existing claims. |
| Delta | The computed difference between extracted knowledge and the existing Vault knowledge. |
| Delta Report | A durable artifact summarizing delta categories, novelty scoring, link proposals, and follow-ups for one Run ID. |
| Review Queue | A set of proposed actions requiring explicit human decision before canonical changes. |
| Review Queue Item | One proposed action (e.g., “promote this claim”, “merge provenance”, “create concept note”). |
| Promotion | The explicit transition that applies approved changes and sets affected notes to `status: canon`. |
| Frontier | A ranked view of unclear, weakly supported, conflicting, or prerequisite-gap topics. |
| Context Pack | A bounded, citation-backed bundle of notes/claims/sources assembled for a user goal. |
| Egress | Any transmission of Vault-derived content to an external model/service. |
| Egress Policy | The allowlist/blocklist and sanitization rules governing egress. |
| Allowlist | The set of permitted file/path scopes allowed for egress. |
| Blocklist | The set of prohibited file/path scopes that must not be sent via egress. |
| Sanitization | Redaction/transformation applied to outbound payloads before egress. |
| Quarantine | An isolated location where invalid or partial artifacts are stored with diagnostics. |
| Stage | A named pipeline step with defined inputs, outputs, and error behavior. |
| Idempotency | The property that repeating an operation with the same input does not create duplicate canonical outcomes. |
| Golden Fixture | A versioned, deterministic input+expected-output test artifact set used to prevent regressions. |
| Regression Test | A test that prevents previously-fixed bugs from returning (especially dedupe/idempotency). |

## 3. System Invariants
### INV-001: Canonical storage substrate
**Requirement:** Canonical Content MUST be stored as Obsidian-compatible Markdown Notes in the Vault filesystem.

**Acceptance Criteria**
- AC-INV-001-1: For a Vault containing canonical notes, opening the Vault in Obsidian preserves readability of Notes (frontmatter + body) and resolution of Obsidian Wikilinks.
- AC-INV-001-2: No canonical knowledge required for operation exists only in a non-Markdown store (e.g., DB-only). If indexes exist, deleting/rebuilding them does not delete canonical knowledge.

### INV-002: Human authority over canon
**Requirement:** Canonical Notes MUST NOT be created or modified without an explicit Promotion action.

**Acceptance Criteria**
- AC-INV-002-1: Running ingestion and other commands without Promotion produces no diffs under canonical directories (see §4.1) and does not change any Note with `status: canon`.
- AC-INV-002-2: Attempted writes targeting canonical directories without Promotion result in a structured error with code `ERR_CANON_WRITE_FORBIDDEN` and no file mutation.

### INV-003: Draft-first agent outputs
**Requirement:** Agent-generated notes and proposals MUST be written as Draft Notes into draft/inbox directories by default.

**Acceptance Criteria**
- AC-INV-003-1: For any ingestion run that generates notes, all newly created Notes are `status: draft` and located in draft/inbox directories.
- AC-INV-003-2: A “dry run” mode (see §5.1) produces no filesystem writes and returns planned paths instead.

### INV-004: Provenance required for imported claims
**Requirement:** Imported Claims MUST include Provenance sufficient to trace back to a Source and Locator.

**Acceptance Criteria**
- AC-INV-004-1: Schema validation fails for any Claim Note missing required provenance fields (see §4.2.3).
- AC-INV-004-2: Promotion refuses any Claim Note missing required provenance, returning `ERR_PROVENANCE_MISSING`, and does not mutate canonical directories.

### INV-005: Idempotent ingestion identity
**Requirement:** Ingestion MUST be idempotent with respect to (Normalized Locator, Source Fingerprint).

**Acceptance Criteria**
- AC-INV-005-1: Re-ingesting the same Source (same locator+fingerprint) reuses the same `source_id` and creates no duplicate canonical claim notes.
- AC-INV-005-2: Re-ingesting a Source with the same locator but different fingerprint produces a new Run ID and records a revision link in the Delta Report (see §6.4), without overwriting prior Source Notes.

## 4. Vault Data Model
### 4.1 Default Vault Layout
The Vault uses vault-relative paths. The following layout is the default.

| Path | Classification | Purpose |
|---|---|---|
| `Inbox/Sources/` | Derived (draft scope) | Draft Source Notes and staged extraction artifacts. |
| `Inbox/ReviewQueue/` | Derived (draft scope) | Review Queue Items awaiting human decision. |
| `Sources/` | Canonical | Canonical Source Notes. |
| `Claims/` | Canonical | Canonical Claim Notes. |
| `Concepts/` | Canonical | Canonical Concept Notes. |
| `Questions/` | Canonical | Canonical Question Notes. |
| `Projects/` | Canonical | Canonical Project Notes. |
| `MOCs/` | Canonical | Canonical map-of-content Notes. |
| `Reports/Delta/` | Derived (durable) | Delta Reports (durable history). |
| `Logs/Audit/` | Derived (durable) | Append-only audit/event logs. |
| `Indexes/` | Derived (rebuildable) | Optional indexes/caches for retrieval/dedupe. |
| `Quarantine/` | Derived (durable) | Invalid/partial artifacts with diagnostics. |

**Requirement VLT-001:** The system MUST treat the directories above as the authoritative boundary between draft scope and canonical scope.

**Acceptance Criteria**
- AC-VLT-001-1: Without Promotion, the system writes only under `Inbox/`, `Reports/`, `Logs/`, `Indexes/`, and `Quarantine/`.
- AC-VLT-001-2: Promotion moves or copies approved artifacts into canonical directories and updates `status` to `canon` (see §8).

### 4.2 Note Schemas
All Notes are Markdown with YAML frontmatter.

#### 4.2.1 Shared Frontmatter Schema
**Requirement SCH-001:** Every Note MUST include the shared frontmatter keys below.

| Key | Type | Required | Notes |
|---|---:|:---:|---|
| `type` | enum | Yes | `source \| claim \| concept \| question \| project \| moc` |
| `id` | string | Yes | Stable identifier; format constraints in §4.3 |
| `status` | enum | Yes | `draft \| reviewed \| canon` |
| `created` | datetime | Yes | ISO-8601 UTC |
| `updated` | datetime | Yes | ISO-8601 UTC |
| `tags` | list[string] | No | Lowercase kebab-case recommended |
| `confidence` | number | No | Range `[0.0..1.0]` if present |

**Acceptance Criteria**
- AC-SCH-001-1: A schema validator rejects any Note missing a required shared key and reports which key is missing.
- AC-SCH-001-2: `created` and `updated` parse as UTC ISO-8601 and validator rejects non-UTC or invalid formats.
- AC-SCH-001-3: If `confidence` exists, validator rejects values outside `[0.0..1.0]`.

#### 4.2.2 Source Note Schema
**Requirement SCH-002:** A Source Note MUST include the fields below in addition to the shared schema.

| Key | Type | Required | Notes |
|---|---:|:---:|---|
| `source_ref` | string | Yes | Original reference (URL/DOI/arXiv/book identifier/etc.) |
| `source_kind` | enum | Yes | `url \| pdf \| doi \| arxiv \| highlights \| book \| text_bundle` |
| `normalized_locator` | string | Yes | Deterministic locator string |
| `fingerprint` | string | Yes | Format `sha256:<hex>` |
| `captured_at` | datetime | Yes | ISO-8601 UTC |

**Acceptance Criteria**
- AC-SCH-002-1: For a given normalized payload, `fingerprint` remains identical across repeated ingestion runs.
- AC-SCH-002-2: Validator rejects `fingerprint` not matching `sha256:<64-hex>`.
- AC-SCH-002-3: Validator rejects Source Notes missing any required Source Note key.

#### 4.2.3 Claim Note Schema
**Requirement SCH-003:** A Claim Note MUST include the fields below in addition to the shared schema.

| Key | Type | Required | Notes |
|---|---:|:---:|---|
| `claim_text` | string | Yes | Non-empty |
| `claim_type` | enum | Yes | `empirical \| definition \| causal \| normative \| procedural` |
| `polarity` | enum | Yes | `supports \| opposes \| neutral` |
| `provenance` | object | Yes | Defined below |

`provenance` object:
| Field | Type | Required |
|---|---:|:---:|
| `source_id` | string | Yes |
| `source_ref` | string | Yes |
| `locator` | string or object | Yes |

**Acceptance Criteria**
- AC-SCH-003-1: Validator rejects Claim Notes with empty `claim_text` (after trimming whitespace).
- AC-SCH-003-2: Validator rejects Claim Notes missing `provenance.source_id`, `provenance.source_ref`, or `provenance.locator`.
- AC-SCH-003-3: Claim Notes promoted to canon (via Promotion) always have at least one outbound Obsidian Wikilink to a Source Note.

#### 4.2.4 Concept Note Schema
**Requirement SCH-004:** A Concept Note MUST include `term: string` in addition to the shared schema.

**Acceptance Criteria**
- AC-SCH-004-1: Validator rejects Concept Notes missing `term`.
- AC-SCH-004-2: Promotion to canon fails for Concept Notes that have zero outbound wikilinks (at least one link required).

#### 4.2.5 Question Note Schema
**Requirement SCH-005:** A Question Note MUST include `question_text: string` in addition to the shared schema.

**Acceptance Criteria**
- AC-SCH-005-1: Validator rejects Question Notes missing `question_text` or with empty `question_text` after trimming.

#### 4.2.6 Delta Report Schema
Delta Reports are durable artifacts written under `Reports/Delta/`.

**Requirement SCH-006:** Each Ingestion Job MUST persist exactly one Delta Report per Run ID using the schema below.

Format: YAML

Required keys:
- `run_id: string`
- `source_id: string`
- `created_at: datetime (ISO-8601 UTC)`
- `source_revision: object` (see below)
- `counts: object` (see below)
- `novelty_score: number` (range `[0..1]`)
- `match_groups: object` with arrays for each Match Class (see below)
- `new_links: array`
- `follow_up_questions: array`

`source_revision` required fields:
- `normalized_locator: string`
- `fingerprint: string`
- `prior_fingerprint: string|null`

`counts` required fields:
- `total_extracted_claims: int`
- `exact_count: int`
- `near_duplicate_count: int`
- `supporting_count: int`
- `contradicting_count: int`
- `new_count: int`

`match_groups` required keys (arrays; empty arrays allowed and must be present):
- `EXACT`
- `NEAR_DUPLICATE`
- `SUPPORTING`
- `CONTRADICTING`
- `NEW`

**Acceptance Criteria**
- AC-SCH-006-1: After any ingestion attempt that reaches extraction, a Delta Report exists for the Run ID even if later stages fail (with failures recorded; see §10).
- AC-SCH-006-2: Delta Report YAML always includes the required keys and includes empty arrays explicitly (keys are present even if arrays are empty).
- AC-SCH-006-3: Validator rejects Delta Reports with `novelty_score` outside `[0..1]`.

#### 4.2.7 Review Queue Item Schema
Review Queue Items are written under `Inbox/ReviewQueue/`.

**Requirement SCH-007:** Each Review Queue Item MUST be persisted as YAML with the keys below.

Required keys:
- `queue_id: string`
- `run_id: string`
- `item_type: enum` (`source_note \| claim_note \| concept_note \| question_note \| link_proposal \| merge_proposal`)
- `target_path: string` (vault-relative)
- `proposed_action: enum` (`create \| promote_to_canon \| merge \| link \| reject`)
- `status: enum` (`pending_review \| approved \| rejected`)
- `created_at: datetime (ISO-8601 UTC)`
- `checks: object` (arbitrary keys allowed; used for validation results)

**Acceptance Criteria**
- AC-SCH-007-1: The system refuses to mutate a non-`pending_review` queue item except via explicit state transition operations (see §8.2), returning `ERR_QUEUE_IMMUTABLE`.
- AC-SCH-007-2: `graduate` in dry-run mode lists validation results for each queue item without changing any files.

### 4.3 Naming and Link Rules
#### 4.3.1 Note ID and filename alignment
**Requirement NAM-001:** `id` MUST be lowercase kebab-case OR a hash identifier prefixed with `h-` (e.g., `h-<hex>`). The Markdown filename MUST equal `<id>.md`.

**Acceptance Criteria**
- AC-NAM-001-1: Validator rejects Notes where filename and `id` differ.
- AC-NAM-001-2: Validator rejects `id` strings outside allowed patterns.

#### 4.3.2 Wikilink resolution
**Requirement LNK-001:** In strict mode, all Obsidian Wikilinks in canonical directories MUST resolve to an existing Note path.

**Acceptance Criteria**
- AC-LNK-001-1: A link-check command (or test helper) reports unresolved links; strict mode fails if count > 0.
- AC-LNK-001-2: In non-strict mode, unresolved links are reported as warnings and recorded in the Delta Report warnings list (see §6.5).

## 5. External Interfaces
### 5.1 Command API (transport-agnostic)
Commands are user-invoked operations. They may be implemented via CLI, MCP tools, or an Obsidian plugin, but their logical contract is identical.

**Requirement IF-001:** Every command response MUST return the Output Envelope below.

Output Envelope (JSON object):
- `ok: boolean`
- `command: string`
- `timestamp: string` (ISO-8601 UTC)
- `data: object` (command-specific)
- `errors: array[ErrorObject]` (empty if `ok=true`)
- `warnings: array[WarningObject]` (empty allowed)
- `trace: object|null` (optional, for debug/diagnostics)

ErrorObject:
- `code: string`
- `message: string`
- `details: object` (optional)
- `stage: string|null` (optional pipeline stage name)
- `retryable: boolean`

WarningObject:
- `code: string`
- `message: string`
- `details: object` (optional)

**Acceptance Criteria**
- AC-IF-001-1: All commands return the envelope keys exactly as specified.
- AC-IF-001-2: If a command fails, `ok=false` and `errors.length>=1`.
- AC-IF-001-3: Error objects always include `code`, `message`, and `retryable`.

#### 5.1.1 Common flags
**Requirement IF-002:** Commands that can write files MUST support a dry-run mode.

**Acceptance Criteria**
- AC-IF-002-1: Dry-run mode returns planned file operations in `data.planned_writes` and produces no filesystem diffs.
- AC-IF-002-2: Dry-run mode still performs schema validation of planned outputs and reports validation errors.

### 5.2 Command Contracts
This section defines inputs, outputs, side effects, and errors for each command.

#### 5.2.1 `ingest`
Input:
- One of:
  - `url: string`
  - `pdf_path: string` (vault-relative or absolute)
  - `id: string` (DOI or arXiv identifier)
  - `text_bundle: object` (for highlights/book notes)
- Optional:
  - `why_saved: string`
  - `tags: array[string]`
  - `strict: boolean` (enables strict schema/link checking)
  - `dry_run: boolean`

Output `data`:
- `run_id: string`
- `source_id: string`
- `source_note_path: string`
- `delta_report_path: string`
- `review_queue_item_paths: array[string]`
- `artifact_paths: array[string]` (extraction bundle paths)
- `idempotency: object` with:
  - `normalized_locator: string`
  - `fingerprint: string`
  - `reused_source_id: boolean`
  - `prior_fingerprint: string|null`

Side effects:
- Writes draft artifacts under `Inbox/` and durable outputs under `Reports/Delta/` and `Logs/Audit/`.
- Must not write canonical directories without Promotion (INV-002).

Errors (non-exhaustive):
- `ERR_INVALID_INPUT`
- `ERR_UNSUPPORTED_SOURCE`
- `ERR_CAPTURE_FAILED`
- `ERR_NORMALIZATION_FAILED`
- `ERR_EXTRACTION_FAILED`
- `ERR_SCHEMA_VALIDATION`
- `ERR_CORRUPTED_NOTE`
- `ERR_CANON_WRITE_FORBIDDEN`

**Requirement CMD-ING-001:** `ingest` MUST create a Source Note, an Extraction Bundle, and a Delta Report for each successful ingestion run.

**Acceptance Criteria**
- AC-CMD-ING-001-1: After `ingest` succeeds (`ok=true`), the returned `source_note_path` exists and validates against SCH-002.
- AC-CMD-ING-001-2: After `ingest` succeeds, the returned `delta_report_path` exists and validates against SCH-006.
- AC-CMD-ING-001-3: After `ingest` succeeds, `artifact_paths` is non-empty and every referenced file exists.

#### 5.2.2 `delta`
Input:
- One of:
  - `source_id: string`
  - `delta_report_path: string`
- Optional: `strict: boolean`

Output `data`:
- `run_id: string`
- `source_id: string`
- `counts: object` (from Delta Report)
- `match_groups: object` (from Delta Report)
- `new_links: array`
- `follow_up_questions: array`
- `citations: array` (paths/ids referenced)

Side effects: none.

Errors:
- `ERR_SOURCE_NOT_FOUND`
- `ERR_DELTA_NOT_FOUND`
- `ERR_SCHEMA_VALIDATION`

**Requirement CMD-DEL-001:** `delta` MUST return match group arrays for all Match Classes and include counts.

**Acceptance Criteria**
- AC-CMD-DEL-001-1: `data.match_groups` includes keys `EXACT`, `NEAR_DUPLICATE`, `SUPPORTING`, `CONTRADICTING`, `NEW`.
- AC-CMD-DEL-001-2: `data.counts.total_extracted_claims` equals the sum of the five match class counts in the Delta Report.

#### 5.2.3 `graduate`
Input:
- One of:
  - `queue_id: string`
  - `queue_item_paths: array[string]`
  - `all_reviewed: boolean`
- Optional:
  - `dry_run: boolean`
  - `strict: boolean`

Output `data`:
- `promoted: array[{queue_id, from_path, to_path}]`
- `rejected: array[{queue_id, reason}]`
- `audit_event_ids: array[string]`

Side effects:
- Applies approved Promotions, moving artifacts into canonical directories and updating statuses.
- Appends audit events.

Errors:
- `ERR_QUEUE_ITEM_INVALID`
- `ERR_QUEUE_IMMUTABLE`
- `ERR_PROVENANCE_MISSING`
- `ERR_PROMOTION_CONFLICT`
- `ERR_SCHEMA_VALIDATION`

**Requirement CMD-GRD-001:** `graduate` MUST apply Promotions only for approved queue items and MUST be atomic per queue item.

**Acceptance Criteria**
- AC-CMD-GRD-001-1: If a queue item fails validation, that item results in no canonical changes while other valid items may still be promoted (per-item atomicity).
- AC-CMD-GRD-001-2: On success, each promoted Note has `status: canon` and resides in a canonical directory.

#### 5.2.4 `context`
Input:
- Optional:
  - `goal: string`
  - `project: string`
  - `tags: array[string]`
  - `limit: int`
  - `strict: boolean`

Output `data`:
- `items: array[{path, type, title, rationale, citations}]`
- `traversal_trace: object` (bounded traversal record)
- `limits_applied: object` (e.g., `limit`, max depth)

Side effects: none.

Errors:
- `ERR_CONTEXT_EMPTY`
- `ERR_SCHEMA_VALIDATION`

**Requirement CMD-CTX-001:** `context` MUST produce bounded output and include citations to supporting Notes/Sources.

**Acceptance Criteria**
- AC-CMD-CTX-001-1: Returned `items.length` is `<= limit` when `limit` is provided.
- AC-CMD-CTX-001-2: Every returned item includes at least one citation that resolves to an existing Note path.

#### 5.2.5 `frontier`
Input:
- Optional:
  - `project: string`
  - `tags: array[string]`
  - `limit: int`

Output `data`:
- `conflicts: array[...]`
- `weak_support: array[...]`
- `open_questions: array[...]`
- `reading_targets: array[...]` (ranked)
- `explanations: object` (ranking factors)

Side effects: none.

Errors:
- `ERR_NO_FRONTIER_DATA`

**Requirement CMD-FRN-001:** `frontier` MUST surface conflicts, weak support, and open questions when present in seeded data.

**Acceptance Criteria**
- AC-CMD-FRN-001-1: In a seeded Vault fixture containing at least one contradiction and one question, `conflicts.length>=1` and `open_questions.length>=1`.
- AC-CMD-FRN-001-2: `reading_targets` is sorted by an explicit numeric rank/score field included per target.

#### 5.2.6 `connect`, `trace`, `ideas`
These commands are part of later milestones and may be implemented after MVP2.

**Requirement CMD-FUT-001:** If implemented, each of `connect`, `trace`, and `ideas` MUST conform to IF-001 Output Envelope and define inputs/outputs/errors in this section before being considered complete.

**Acceptance Criteria**
- AC-CMD-FUT-001-1: For each implemented command, the spec section includes a complete contract: inputs, outputs, side effects, and errors.
- AC-CMD-FUT-001-2: Contract tests validate envelope conformance and schema correctness for each command.

## 6. Ingestion Pipeline
### 6.1 Pipeline Stages and Interfaces
Stages are executed in order. Each stage has a defined interface and error behavior.

**Requirement PIPE-001:** The pipeline MUST be stage-scoped: failures must identify the stage and must not silently continue with invalid inputs.

**Acceptance Criteria**
- AC-PIPE-001-1: When a stage fails, the command returns an error with `stage` set to the failing stage name and an appropriate error code.
- AC-PIPE-001-2: No downstream stage runs using outputs that failed validation.

#### 6.1.1 Stage interfaces
The following internal interfaces are required (implementation language/library is unspecified).

1) Capture  
Input: Source input (`url` / `pdf_path` / `id` / `text_bundle`)  
Output: `RawSourcePayload { bytes|text, media_type, source_ref, source_kind }`  
Errors: `ERR_CAPTURE_FAILED`, `ERR_UNSUPPORTED_SOURCE`

2) Normalize  
Input: RawSourcePayload  
Output: `NormalizedSource { normalized_text, normalized_locator, source_kind, source_ref, extracted_metadata }`  
Errors: `ERR_NORMALIZATION_FAILED`

3) Fingerprint  
Input: NormalizedSource  
Output: `SourceIdentity { normalized_locator, fingerprint }`  
Errors: `ERR_NORMALIZATION_FAILED`

4) Extract  
Input: NormalizedSource  
Output: `ExtractionBundle { gist, bullets, claims[], entities[], definitions[] }`  
Errors: `ERR_EXTRACTION_FAILED`, `ERR_SCHEMA_VALIDATION`

5) Compare (Dedupe)  
Input: `claims[]`, current claim index/snapshot  
Output: `MatchResults[]` with Match Class per claim  
Errors: `ERR_INDEX_UNAVAILABLE` (if index read fails), `ERR_SCHEMA_VALIDATION`

6) Delta  
Input: MatchResults + link proposals  
Output: Delta Report object (SCH-006)  
Errors: `ERR_SCHEMA_VALIDATION`

7) Propose + Queue  
Input: ExtractionBundle + MatchResults + vault snapshot  
Output: Review Queue Items (SCH-007)  
Errors: `ERR_SCHEMA_VALIDATION`

### 6.2 Minimum extraction outputs
**Requirement EXT-001:** Extraction MUST produce, at minimum: `gist`, `bullets`, and at least one `claim` OR an explicit `warnings` entry explaining why zero claims were produced.

**Acceptance Criteria**
- AC-EXT-001-1: For a golden fixture Source known to contain extractable assertions, `claims.length>=1`.
- AC-EXT-001-2: For a fixture designed to yield zero claims, the extraction output includes `warnings` with code `WARN_NO_CLAIMS_EXTRACTED`.

### 6.3 Artifact staging and atomicity
**Requirement PIPE-002:** The system MUST stage ingestion outputs in draft scope and MUST NOT leave partially written canonical files on failure.

**Acceptance Criteria**
- AC-PIPE-002-1: Inducing a failure after extraction but before queue writing results in either (a) no new files, or (b) all new files placed under `Quarantine/` with diagnostics.
- AC-PIPE-002-2: No files in canonical directories are created or modified in any failure scenario without Promotion.

### 6.4 Idempotency resolution
**Requirement IDM-001:** The system MUST maintain a Source index mapping `(normalized_locator, fingerprint) -> source_id`.

**Acceptance Criteria**
- AC-IDM-001-1: Ingesting an identical fixture twice returns the same `source_id` and sets `data.idempotency.reused_source_id=true` on the second run.
- AC-IDM-001-2: Ingesting a changed-content fixture with the same normalized locator returns a different fingerprint and records `prior_fingerprint` in the Delta Report.

### 6.5 Delta Report generation
**Requirement DEL-001:** Delta Report generation MUST be part of ingestion completion and MUST record match group membership for every extracted claim.

**Acceptance Criteria**
- AC-DEL-001-1: For any successful ingestion, `counts.total_extracted_claims == sum(len(match_groups[...]))`.
- AC-DEL-001-2: Delta Report includes non-empty `match_groups.NEW` for a fixture with novel claims, and non-empty `match_groups.EXACT` or `match_groups.NEAR_DUPLICATE` for an overlap-only fixture.

## 7. Dedupe and Delta Engine
### 7.1 Claim canonicalization
**Requirement DED-001:** Claim canonicalization MUST be deterministic: the same input claim text produces the same canonical form across runs.

**Acceptance Criteria**
- AC-DED-001-1: A unit test runs canonicalization twice on the same text and asserts byte-identical output.
- AC-DED-001-2: Canonicalization collapses whitespace and normalizes Unicode such that cosmetic formatting differences in a golden pair produce identical canonical outputs.

### 7.2 Match class assignment
**Requirement DED-002:** The comparator MUST assign exactly one Match Class to each extracted claim.

**Acceptance Criteria**
- AC-DED-002-1: For any extraction run, the number of MatchResults equals `counts.total_extracted_claims`.
- AC-DED-002-2: Each MatchResult includes `class` ∈ {`EXACT`,`NEAR_DUPLICATE`,`SUPPORTING`,`CONTRADICTING`,`NEW`} and a numeric `similarity` in `[0..1]`.

### 7.3 Merge rules
**Requirement DED-003:** Merge rules MUST follow:
- `EXACT` and `NEAR_DUPLICATE`: do not create a new canonical Claim Note by default.
- `SUPPORTING`: attach provenance/support metadata to the existing claim (as a proposal requiring review if it changes canonical content).
- `CONTRADICTING`: preserve both claims and emit an explicit conflict record in the Delta Report.
- `NEW`: create a Draft Claim Note linked to its Source.

**Acceptance Criteria**
- AC-DED-003-1: Re-ingesting an overlap-only fixture yields `match_groups.NEW.length==0` and does not increase canonical claim note count.
- AC-DED-003-2: A contradiction fixture yields `match_groups.CONTRADICTING.length>=1` and includes both involved claim identifiers in the Delta Report conflict records.
- AC-DED-003-3: A novel fixture yields `match_groups.NEW.length>=1` and creates Draft Claim Notes for those new claims.

### 7.4 Novelty scoring
**Requirement DEL-002:** The system MUST compute `novelty_score` deterministically using only Delta Report counts and MUST define it as:
`novelty_score = (new_count + contradicting_count) / max(1, total_extracted_claims)`

**Acceptance Criteria**
- AC-DEL-002-1: For any Delta Report, recomputing the formula from `counts` matches stored `novelty_score` exactly (within floating-point tolerance of 1e-9).
- AC-DEL-002-2: `novelty_score` equals `0` when `total_extracted_claims==0`.

## 8. Review Queue and Promotion
### 8.1 Review queue generation
**Requirement REV-001:** Ingestion MUST generate Review Queue Items for all proposed canonical-impacting actions, including at minimum: promoting new claims and creating new source notes.

**Acceptance Criteria**
- AC-REV-001-1: For a fixture producing at least one new claim, ingestion produces at least one queue item with `item_type: claim_note` and `proposed_action: promote_to_canon` (or `create` + later promotion path).
- AC-REV-001-2: Queue items include `checks` that at least capture `provenance_present` for claim-related items.

### 8.2 Promotion semantics
**Requirement REV-002:** Promotion MUST:
1) Validate schemas (SCH-001..SCH-007) in strict mode for promoted items.  
2) Update promoted Notes to `status: canon`.  
3) Write promoted Notes into canonical directories.  
4) Append audit entries for all affected files (see §9.1).

**Acceptance Criteria**
- AC-REV-002-1: After a successful Promotion, every promoted Note validates and has `status: canon`.
- AC-REV-002-2: Audit log contains an entry that lists the promoted paths and the actor identifier.

## 9. Security, Privacy, and Audit
### 9.1 Audit logging
**Requirement AUD-001:** The system MUST write append-only audit logs for ingestion runs and promotions.

Audit event minimum fields:
- `event_id: string`
- `timestamp: ISO-8601 UTC`
- `actor: string` (use `"unknown"` if not determinable)
- `event_type: enum` (`ingest_started`, `ingest_completed`, `ingest_failed`, `promotion_applied`, `egress_attempted`, `egress_blocked`, `egress_completed`)
- `run_id: string|null`
- `targets: array[string]` (affected file paths, if any)
- `details: object`

**Acceptance Criteria**
- AC-AUD-001-1: Each `ingest` emits `ingest_started` and exactly one terminal event (`ingest_completed` or `ingest_failed`).
- AC-AUD-001-2: Audit logs are append-only: a test verifies that a new run only appends and does not rewrite prior lines/entries.

### 9.2 Egress policy
**Requirement SEC-001:** If external egress is performed, it MUST be governed by an Egress Policy that includes allowlist and blocklist checks and optional sanitization.

**Acceptance Criteria**
- AC-SEC-001-1: Attempting to egress a blocklisted path fails with `ERR_EGRESS_POLICY_BLOCK` and emits an `egress_blocked` audit event.
- AC-SEC-001-2: Egressing an allowlisted test payload emits an `egress_completed` audit event including `bytes_sent` and destination identifier.

**Requirement SEC-002:** The system MUST log what content was sent externally (or its cryptographic digest) and why.

**Acceptance Criteria**
- AC-SEC-002-1: Egress audit events include either (a) the full outbound payload content stored locally, or (b) a payload digest plus the list of source file paths included.
- AC-SEC-002-2: Egress audit events include a reason field (e.g., command name and user request context).

**TODO-Q-SEC-1:** Define the default allowlist and blocklist patterns (beyond the directory-level boundaries in §4.1) and the sanitization/redaction policy.

## 10. Failure Modes and Recovery
### 10.1 Explicit failures and recoverability
**Requirement ERR-001:** Pipeline failures MUST be explicit, stage-scoped, and recoverable without manual deletion of canonical files.

**Acceptance Criteria**
- AC-ERR-001-1: For induced failures in each stage, the returned error includes `stage` and a deterministic `code`.
- AC-ERR-001-2: Retrying the same ingestion after a transient failure produces a successful run without requiring manual cleanup of canonical directories.

### 10.2 Quarantine behavior
**Requirement ERR-002:** Invalid or partial artifacts MUST be placed in `Quarantine/` with a diagnostic sidecar.

**Acceptance Criteria**
- AC-ERR-002-1: A corrupted frontmatter fixture results in a quarantined copy and a diagnostic file containing the parse error and the affected original path.
- AC-ERR-002-2: The original corrupted canonical file (if any) is not overwritten.

## 11. Compatibility and Migration
### 11.1 Obsidian and git friendliness
**Requirement MIG-001:** All canonical Notes MUST remain human-readable and git-diff friendly.

**Acceptance Criteria**
- AC-MIG-001-1: Canonical Notes contain only YAML frontmatter + Markdown body; no binary blobs.
- AC-MIG-001-2: Schema changes that add fields do not require rewriting unchanged canonical notes.

### 11.2 Schema evolution
**Requirement MIG-002:** Any breaking schema or layout change MUST include a migration and rollback procedure.

**Acceptance Criteria**
- AC-MIG-002-1: A migration test applies the migration to a fixture Vault and validates that all Notes still pass schema checks.
- AC-MIG-002-2: A rollback test restores the pre-migration fixture state byte-for-byte for canonical Notes.

## 12. Milestones
Milestones define required capability bundles.

### 12.1 MVP1
**Requirement MVP1-001:** MVP1 MUST include:
- Ingest URL and PDF into draft scope (`Inbox/Sources/`).
- Generate Source Note, Extraction Bundle, and Delta Report.
- Perform basic dedupe/match classification.
- Propose best-effort links (as Review Queue Items).
- Enforce provenance and Promotion gate.

**Acceptance Criteria**
- AC-MVP1-001-1: End-to-end tests cover URL and PDF ingest and verify artifacts and schemas.
- AC-MVP1-001-2: Idempotency test demonstrates source_id reuse and no canonical duplication on repeat ingest.

### 12.2 MVP2
**Requirement MVP2-001:** MVP2 MUST include:
- Review Queue lifecycle enforcement and `graduate`.
- Promotion updates canonical directories with audit records.
- Frontier output for seeded contradictions and questions.

**Acceptance Criteria**
- AC-MVP2-001-1: Integration test enforces invalid queue transitions fail with `ERR_QUEUE_IMMUTABLE`.
- AC-MVP2-001-2: Frontier seeded fixture yields non-empty `conflicts` and `open_questions`.

### 12.3 MVP3 (future)
MVP3 may include advanced triage (“watery vs dense”), `/connect`, `/trace`, `/ideas`, and ranking improvements.

**TODO-Q-MVP3-1:** Define the triage scoring model and bucket thresholds for watery vs dense and skip-list behavior.  
**TODO-Q-MVP3-2:** Define the minimum viable graph algorithms for hub/bridge detection and their performance targets.

## 13. Test Plan
This section specifies required testing layers and fixture strategy.

### 13.1 Unit Tests
**Requirement TST-U-001:** Unit tests MUST cover deterministic canonicalization, schema validation, match classification, and novelty scoring.

**Acceptance Criteria**
- AC-TST-U-001-1: Canonicalization determinism tests pass (AC-DED-001-1/2).
- AC-TST-U-001-2: Schema validators reject each invalid fixture with the expected error code.
- AC-TST-U-001-3: Novelty scoring recomputation matches stored value (AC-DEL-002-1).

### 13.2 Integration Tests
**Requirement TST-I-001:** Integration tests MUST cover the pipeline stage chain and enforce draft/canon boundaries.

**Acceptance Criteria**
- AC-TST-I-001-1: A full pipeline run from capture→delta→queue completes for each supported source kind fixture.
- AC-TST-I-001-2: A boundary test verifies no writes occur under canonical directories without Promotion (AC-INV-002-1).

### 13.3 End-to-End Tests
**Requirement TST-E2E-001:** End-to-end tests MUST validate user workflows: first ingest, repeat ingest, contradiction ingest, promotion, and context/frontier outputs.

**Acceptance Criteria**
- AC-TST-E2E-001-1: First ingest fixture produces Source Note, Claim Notes (draft), Delta Report, and Queue Items.
- AC-TST-E2E-001-2: Repeat ingest fixture produces identical `source_id` and zero new canonical claim notes.
- AC-TST-E2E-001-3: Contradiction fixture yields `CONTRADICTING` matches and `frontier.conflicts.length>=1` in seeded data.
- AC-TST-E2E-001-4: Promotion fixture updates statuses to `canon`, moves files into canonical directories, and appends audit events.

### 13.4 Golden Fixtures
Golden fixtures are versioned, deterministic test inputs with expected outputs.

**Requirement TST-G-001:** The test suite MUST include golden fixture sets for ingestion and delta reports.

Minimum fixture categories:
- `url_basic`: a stable HTML/text URL capture representation (offline fixture) producing at least one NEW claim.
- `pdf_basic`: a small PDF fixture producing at least one NEW claim.
- `delta_overlap_only`: produces only `EXACT`/`NEAR_DUPLICATE` matches.
- `delta_new_and_contradict`: produces at least one `NEW` and one `CONTRADICTING`.
- `corrupted_frontmatter`: triggers quarantine behavior.
- `idempotency_changed_content`: same locator, different fingerprint.

**Acceptance Criteria**
- AC-TST-G-001-1: Golden expected Delta Report content is stable under deterministic test mode (see TST-G-002), with dynamic fields either fixed or normalized consistently.
- AC-TST-G-001-2: Updating a golden fixture requires a changelog entry describing why outputs changed (e.g., schema version bump or algorithm change).

**Requirement TST-G-002:** The system MUST support deterministic test mode for golden testing (fixed clock and stable ID generation, or a documented normalization step that removes nondeterminism before comparison).

**Acceptance Criteria**
- AC-TST-G-002-1: Running the same fixture twice yields byte-identical normalized outputs for golden comparison.
- AC-TST-G-002-2: Deterministic mode affects only nondeterministic fields (timestamps/IDs) and does not change semantic classifications (match classes).

### 13.5 Regression Tests (Dedupe + Idempotency)
**Requirement TST-R-001:** A regression suite MUST include targeted cases for dedupe false positives/negatives and idempotency edge cases.

Minimum regression cases:
- Semantically identical but differently formatted claims (should match as `EXACT` or `NEAR_DUPLICATE`).
- Semantically different claims with high lexical overlap (must not be incorrectly deduped).
- Same normalized locator with unchanged fingerprint (must reuse source_id).
- Same normalized locator with changed fingerprint (must record revision lineage).
- Re-running Promotion on already-promoted items (must be no-op or return deterministic conflict error).

**Acceptance Criteria**
- AC-TST-R-001-1: Any regression failure fails CI/release gating for the vault subsystem.
- AC-TST-R-001-2: Regression cases remain stable across refactors (only updated when intended behavior changes, with changelog note).

## 14. Spec Lint Checklist
**Requirement LINT-001:** Specialized terms used in the spec MUST appear in the Glossary.

**Acceptance Criteria**
- AC-LINT-001-1: A spec-lint pass flags any capitalized Term not present in the Glossary table and fails lint.

**Requirement LINT-002:** Every `MUST` requirement in this spec MUST have explicit Acceptance Criteria in the same section.

**Acceptance Criteria**
- AC-LINT-002-1: A spec-lint pass flags any `MUST` without a nearby “Acceptance Criteria” block and fails lint.

**Requirement LINT-003:** Every interface described as required MUST specify inputs, outputs, side effects, and errors.

**Acceptance Criteria**
- AC-LINT-003-1: A spec-lint pass flags any required command or stage missing any of the four components.

**Requirement LINT-004:** Repetition MUST be minimized by defining invariants once and referencing them.

**Acceptance Criteria**
- AC-LINT-004-1: A spec-lint pass flags duplicate normative statements that restate the same invariant without referencing its ID.

## 15. TODO Questions
- TODO-Q1: Choose canonical ID strategy for Notes: slug-only, hash-only, or slug+hash hybrid (impacts NAM-001 and dedupe collision handling).
- TODO-Q2: Define minimum provenance locator granularity per source kind (e.g., URL paragraph index vs PDF page/section).
- TODO-Q3: Define confidence calibration rubric per domain (how `confidence` is assigned and validated).
- TODO-Q4: Define the authoritative review UX for Promotion decisions (CLI-only vs Obsidian plugin vs both) and how approvals are recorded.
- TODO-Q5: Define default egress allowlist/blocklist patterns and sanitization policies (TODO-Q-SEC-1).
- TODO-Q6: Define performance targets for ingestion and retrieval (numeric thresholds) and how they are measured in tests/benchmarks.
