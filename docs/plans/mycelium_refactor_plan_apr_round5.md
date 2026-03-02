# Mycelium Agentic Knowledge Vault Specification
Version: 1.1  
Status: Final (Hardened)

## 1. Overview
Mycelium is a local-first, Obsidian-compatible knowledge vault. Markdown notes and Obsidian wikilinks are the canonical knowledge substrate. Sources are ingested through a staged pipeline that extracts structured knowledge, computes deltas against the existing vault, proposes graph/link updates, and surfaces the user’s “knowledge frontier.” Human authorship remains authoritative: agents may draft, but canonical notes change only through explicit human promotion.

## 2. Glossary
| Term | Definition |
|---|---|
| Vault | The Obsidian-compatible root directory containing canonical Markdown notes plus derived artifacts. |
| Canonical Content | Markdown Notes in the Vault that represent the user-approved knowledge base. |
| Derived Artifact | Machine-generated files that are either rebuildable (e.g., indexes) or durable history (e.g., delta reports, audit logs). |
| Canonical Scope | The set of canonical directories in the default Vault layout (§4.1). |
| Draft Scope | The set of non-canonical directories used for drafts, derived artifacts, and diagnostics (§4.1). |
| Canonical Directory | A directory under Canonical Scope (e.g., `Claims/`). |
| Draft Directory | A directory under Draft Scope (e.g., `Inbox/Sources/`). |
| Obsidian Wikilink | An internal link in the form `[[Path/NoteId]]` understood by Obsidian. |
| Note | A Markdown file with YAML frontmatter at the top and a Markdown body. |
| Note Type | The `type` frontmatter value defining the schema: `source`, `claim`, `concept`, `question`, `project`, `moc`. |
| Note Status | The `status` frontmatter value: `draft`, `reviewed`, `canon`. |
| Canonical Note | A Note with `status: canon` located in Canonical Scope. |
| Draft Note | A Note with `status: draft` located in Draft Scope. |
| Reviewed Note | A Note with `status: reviewed` that is eligible for Promotion to `canon`. |
| Source | An external artifact (URL, PDF, DOI/arXiv reference, highlights bundle, book notes bundle, or other text bundle) being ingested. |
| Source Note | A Note representing one Source, including identity, fingerprint, and metadata. |
| Source Kind | The normalized class of a Source input: `url`, `pdf`, `doi`, `arxiv`, `highlights`, `book`, `text_bundle`. |
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
| Match Record | A structured record describing one extracted claim’s Match Class outcome (used in Delta Reports; §4.2.6). |
| Dedupe | The process of avoiding creation of duplicate claims by matching against existing claims. |
| Delta | The computed difference between extracted knowledge and the existing Vault knowledge. |
| Delta Report | A durable artifact summarizing delta categories, novelty scoring, match records, link proposals, and follow-ups for one Run ID. |
| Review Queue | A set of proposed actions requiring explicit human decision before canonical changes. |
| Review Queue Item | One proposed action (e.g., “promote this claim”, “merge provenance”, “create concept note”). |
| Review Digest | A reading-first artifact grouping Review Queue Items by Source into Review Packets (§4.2.9). |
| Review Packet | The per-Source unit within a Review Digest that supports packet-level decisions and optional claim-level drill-down. |
| Review Decision Record | A durable record of Review decisions applied by the `review` command (§4.2.10). |
| Hold Decision | A reviewer choice that defers apply without rejecting; queue items remain `pending_review` and are resurfaced later. |
| Auto-Approval Lane | A constrained policy that auto-approves only low-risk, non-semantic proposals while keeping semantic changes in human review. |
| Promotion | The explicit transition that applies approved changes and sets affected Notes to `status: canon` (implemented by `graduate`). |
| Frontier | A ranked view of unclear, weakly supported, conflicting, or prerequisite-gap topics. |
| Context Pack | A bounded, citation-backed bundle of notes/claims/sources assembled for a user goal. |
| Strict Mode | A validation mode in which schema errors and (when applicable) unresolved canonical-scope links are treated as command errors (§5.1.2). |
| Dry Run | A mode in which write-capable commands compute and validate planned writes but perform no filesystem mutations (§5.1.1). |
| Deterministic Test Mode | A test-only mode that removes nondeterminism (timestamps/IDs) for golden fixtures (§13.4). |
| Git Mode | An optional apply mode in which Promotions are applied via git commits (§8.3.1). |
| Egress | Any transmission of Vault-derived content to an external model/service. |
| Egress Policy | The allowlist/blocklist and sanitization rules governing Egress (§9.2). |
| Allowlist | A set of permitted vault-relative path patterns for Egress (glob semantics). |
| Blocklist | A set of prohibited vault-relative path patterns for Egress (glob semantics). |
| Sanitization | Redaction/transformation applied to outbound payloads before Egress. |
| Quarantine | An isolated location where invalid or partial artifacts are stored with diagnostics. |
| Stage | A named pipeline step with defined inputs, outputs, and error behavior (§6.1). |
| Stage Name | The canonical string identifier for a Stage used in errors and audit records (§6.1.2). |
| Idempotency | The property that repeating an operation with the same input does not create duplicate canonical outcomes. |
| Golden Fixture | A versioned, deterministic input+expected-output test artifact set used to prevent regressions. |
| Regression Test | A test that prevents previously-fixed bugs from returning (especially dedupe/idempotency). |

## 3. System Invariants
### INV-001: Canonical storage substrate
**Requirement INV-001:** Canonical Content MUST be stored as Obsidian-compatible Markdown Notes in the Vault filesystem.

**Acceptance Criteria**
- AC-INV-001-1: For a Vault containing Canonical Notes, Obsidian opens the Vault and renders (a) YAML frontmatter and (b) Markdown body for Notes in Canonical Scope, without requiring any non-Markdown store for readability.
- AC-INV-001-2: No canonical knowledge required for operation exists only in a non-Markdown store (e.g., DB-only). If indexes exist, deleting/rebuilding them does not delete Canonical Notes.

### INV-002: Human authority over canon
**Requirement INV-002:** Canonical Notes MUST NOT be created or modified without an explicit Promotion action (implemented by `graduate`; §5.2.5).

**Acceptance Criteria**
- AC-INV-002-1: Running ingestion and other commands without Promotion produces no diffs under Canonical Scope (§4.1) and does not change any Note with `status: canon`.
- AC-INV-002-2: Attempted writes targeting Canonical Scope without Promotion return a structured error with code `ERR_CANON_WRITE_FORBIDDEN` and produce no file mutation.

### INV-003: Draft-first agent outputs
**Requirement INV-003:** Agent-generated Notes and proposals MUST be written as Draft Notes into Draft Scope by default.

**Acceptance Criteria**
- AC-INV-003-1: For any ingestion run that generates Notes, all newly created Notes are `status: draft` and located in Draft Scope.
- AC-INV-003-2: Dry Run mode (§5.1.1) produces no filesystem writes and returns planned operations instead.

### INV-004: Provenance required for imported claims
**Requirement INV-004:** Imported Claims MUST include Provenance sufficient to trace back to a Source and Locator.

**Acceptance Criteria**
- AC-INV-004-1: Schema validation fails for any Claim Note missing required Provenance fields (§4.2.3).
- AC-INV-004-2: Promotion refuses any Claim Note missing required Provenance, returning `ERR_PROVENANCE_MISSING`, and does not mutate Canonical Scope.

### INV-005: Idempotent ingestion identity
**Requirement INV-005:** Ingestion MUST be idempotent with respect to `(Normalized Locator, Source Fingerprint)`.

**Acceptance Criteria**
- AC-INV-005-1: Re-ingesting the same Source (same locator+fingerprint) reuses the same `source_id` and creates no duplicate canonical Claim Notes.
- AC-INV-005-2: Re-ingesting a Source with the same locator but different fingerprint produces a new Run ID and records revision lineage in the Delta Report (§4.2.6), without overwriting prior Source Notes.

## 4. Vault Data Model
### 4.1 Default Vault Layout
The Vault uses vault-relative paths. The following layout is the default.

| Path | Classification | Purpose |
|---|---|---|
| `Inbox/Sources/` | Derived (draft scope) | Draft Source Notes and staged extraction artifacts. |
| `Inbox/ReviewQueue/` | Derived (draft scope) | Review Queue Items awaiting human decision. |
| `Inbox/ReviewDigest/` | Derived (draft scope) | Review Digests and per-Source Review Packets. |
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

**Requirement VLT-001:** The system MUST treat the directories above as the authoritative boundary between Draft Scope and Canonical Scope.

**Acceptance Criteria**
- AC-VLT-001-1: Without Promotion, the system writes only under Draft Scope directories: `Inbox/`, `Reports/`, `Logs/`, `Indexes/`, and `Quarantine/`.
- AC-VLT-001-2: Promotion applies approved changes by creating or modifying Notes only within Canonical Scope and updates `status` to `canon` (§8.3).

### 4.2 Note and Artifact Schemas
All Notes are Markdown with YAML frontmatter. Some Derived Artifacts are YAML (§4.2.6–§4.2.10).

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
| `last_reviewed_at` | datetime | No | ISO-8601 UTC; used by Frontier staleness/tie-breaks (§5.2.7) |

Notes MAY include additional frontmatter keys. Validators MUST ignore unknown keys unless a stricter schema version explicitly specifies otherwise (see MIG-002).

**Acceptance Criteria**
- AC-SCH-001-1: A schema validator rejects any Note missing a required shared key and reports which key is missing.
- AC-SCH-001-2: `created` and `updated` parse as UTC ISO-8601 and validator rejects invalid formats.
- AC-SCH-001-3: If `confidence` exists, validator rejects values outside `[0.0..1.0]`.
- AC-SCH-001-4: If `last_reviewed_at` exists, validator rejects invalid datetime formats.

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
- AC-SCH-002-1: For a given normalized payload, `fingerprint` remains identical across repeated ingestion runs (deterministic fixture mode; §13.4).
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
| `locator` | object | Yes |

`provenance.locator` minima (MVP1 decision):
- For `source_kind: url`, `locator` MUST include keys (values may be null where specified):
  - `url: string`
  - `section: string|null`
  - `paragraph_index: int|null`
  - `snippet_hash: string` (`sha256:<hex>`)
- For `source_kind: pdf`, `locator` MUST include keys:
  - `pdf_ref: string`
  - `page: int`
  - `section: string|null`
  - `snippet_hash: string` (`sha256:<hex>`)
- For other source kinds in MVP1 (`doi|arxiv|highlights|book|text_bundle`), `locator` MAY be a minimal object with `raw_locator: string`; stricter structured minima are deferred to MVP2.

**Acceptance Criteria**
- AC-SCH-003-1: Validator rejects Claim Notes with empty `claim_text` (after trimming whitespace).
- AC-SCH-003-2: Validator rejects Claim Notes missing `provenance.source_id`, `provenance.source_ref`, or `provenance.locator`.
- AC-SCH-003-3: Promotion to canon fails for any Claim Note that does not contain at least one outbound Obsidian Wikilink that resolves to a Source Note whose `id` equals `provenance.source_id`.
- AC-SCH-003-4: For URL/PDF sources, validator rejects `provenance.locator` missing required keys or invalid `snippet_hash` format.
- AC-SCH-003-5: For non-URL/PDF MVP1 source kinds, validator accepts `raw_locator` and emits a warning indicating deferred locator strictness.

#### 4.2.4 Concept Note Schema
**Requirement SCH-004:** A Concept Note MUST include `term: string` in addition to the shared schema.

**Acceptance Criteria**
- AC-SCH-004-1: Validator rejects Concept Notes missing `term`.
- AC-SCH-004-2: Promotion to canon fails for Concept Notes that have zero outbound Obsidian Wikilinks (at least one resolved wikilink is required).

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
- `created_at: datetime` (ISO-8601 UTC)
- `source_revision: object` (see below)
- `pipeline_status: enum` (`completed|failed_after_extraction|failed_before_extraction`)
- `counts: object` (see below)
- `novelty_score: number` (range `[0..1]`)
- `match_groups: object` with arrays for each Match Class (see below)
- `conflicts: array[object]` (empty allowed; explicit key required)
- `warnings: array[object]` (empty allowed; explicit key required)
- `failures: array[object]` (empty allowed; explicit key required)
- `new_links: array` (empty allowed; explicit key required)
- `follow_up_questions: array` (empty allowed; explicit key required)

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

`match_groups.*` entry schema (Match Record):
- Required keys:
  - `extracted_claim_key: string` (deterministic per claim; see §7.1)
  - `match_class: enum` (must equal the containing group key)
  - `similarity: number` (range `[0..1]`)
  - `existing_claim_id: string|null` (null permitted for `NEW`)
- Optional keys:
  - `draft_claim_note_path: string|null` (used when a Draft Claim Note is created in Draft Scope)
  - `notes: string|null` (human-readable rationale)

`conflicts` entry schema (Conflict Record):
- Required keys:
  - `new_extracted_claim_key: string`
  - `existing_claim_id: string`
  - `evidence: object` (implementation-defined; must be JSON/YAML-serializable)
- Optional keys:
  - `draft_claim_note_path: string|null`

`warnings` entry schema:
- Required keys: `code: string`, `message: string`
- Optional: `details: object`

`failures` entry schema:
- Required keys: `code: string`, `message: string`, `stage: string|null`, `retryable: boolean`
- Optional: `details: object`

**Acceptance Criteria**
- AC-SCH-006-1: After any ingestion attempt that begins extraction and produces a schema-valid Extraction Bundle (§4.2.8), a Delta Report exists for the Run ID even if later stages fail (with `pipeline_status` and `failures` populated as applicable).
- AC-SCH-006-2: Delta Report YAML always includes the required top-level keys and includes empty arrays explicitly (keys are present even if arrays are empty).
- AC-SCH-006-3: Validator rejects Delta Reports with `novelty_score` outside `[0..1]`.
- AC-SCH-006-4: Each Match Record in `match_groups.*` includes required keys and `match_class` equals its containing group key.
- AC-SCH-006-5: `pipeline_status` is `completed` on successful runs, `failed_after_extraction` when failure occurs after extraction begins, and `failed_before_extraction` otherwise.

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
- `created_at: datetime` (ISO-8601 UTC)
- `checks: object` (arbitrary keys allowed; used for validation results)

**Acceptance Criteria**
- AC-SCH-007-1: The system refuses to mutate a non-`pending_review` queue item except via explicit state transition operations (§8.2), returning `ERR_QUEUE_IMMUTABLE`.
- AC-SCH-007-2: `graduate` in Dry Run mode lists validation results for each queue item without changing any files.

#### 4.2.8 Extraction Bundle Schema
Extraction Bundles are staged artifacts written under `Inbox/Sources/`.

**Requirement SCH-008:** Each Ingestion Job that completes the Extract stage (§6.1.1) MUST persist at least one Extraction Bundle artifact in YAML that conforms to the schema below.

Format: YAML

Required keys:
- `run_id: string`
- `source_id: string`
- `created_at: datetime` (ISO-8601 UTC)
- `gist: string`
- `bullets: array[string]` (may be empty; explicit key required)
- `claims: array[object]` (may be empty; explicit key required)
- `entities: array` (empty allowed; explicit key required)
- `definitions: array` (empty allowed; explicit key required)
- `warnings: array[object]` (empty allowed; explicit key required)

`claims` entry minima:
- Required keys:
  - `extracted_claim_key: string` (deterministic; see §7.1)
  - `claim_text: string` (non-empty)
  - `claim_type: enum` (same values as SCH-003)
  - `polarity: enum` (same values as SCH-003)
  - `provenance: object` (same minima as SCH-003, including locator minima by source_kind)
- Optional keys:
  - `suggested_note_id: string|null` (id to use if this claim becomes a Note; must conform to NAM-001 if present)
  - `notes: string|null`

`warnings` entry schema:
- Required keys: `code: string`, `message: string`
- Optional: `details: object`

**Acceptance Criteria**
- AC-SCH-008-1: For a successful extraction, an Extraction Bundle YAML file exists under `Inbox/Sources/` and validates against this schema.
- AC-SCH-008-2: Validator rejects Extraction Bundles that omit any required top-level key or that contain any claim with empty `claim_text`.
- AC-SCH-008-3: If `claims` is empty, `warnings` contains an entry with code `WARN_NO_CLAIMS_EXTRACTED`.

#### 4.2.9 Review Digest and Packet Schema
Review Digests and per-Source Review Packets are written under `Inbox/ReviewDigest/`.

**Requirement SCH-009:** `review_digest` MUST persist Review Packets as YAML that conform to the schema below, one packet per Source included in the digest.

Format: YAML

Required keys:
- `packet_id: string`
- `digest_date: string` (YYYY-MM-DD)
- `created_at: datetime` (ISO-8601 UTC)
- `source_id: string`
- `run_ids: array[string]` (non-empty)
- `queue_ids: array[string]` (non-empty)
- `decision: object|null` (null permitted until a decision is recorded)

`decision` object (when non-null) required keys:
- `action: enum` (`approve_all|approve_selected|hold|reject`)
- `actor: string`
- `decided_at: datetime` (ISO-8601 UTC)
- `reason: string|null`

Additional keys by action:
- if `action=approve_selected`: `approved_queue_ids: array[string]` (non-empty)
- if `action=hold`: `hold_until: string` (YYYY-MM-DD)

**Acceptance Criteria**
- AC-SCH-009-1: For a digest with N Sources, exactly N packet YAML files are created and each validates against this schema.
- AC-SCH-009-2: In deterministic test mode, packet ordering and packet contents are stable for the same Vault snapshot (excluding explicitly nondeterministic fields normalized per §13.4).
- AC-SCH-009-3: Validator rejects packet files with `action=approve_selected` that omit `approved_queue_ids` or include ids not present in `queue_ids`.

#### 4.2.10 Review Decision Record Schema
Review Decision Records are durable artifacts written under `Inbox/ReviewDigest/`.

**Requirement SCH-010:** Each invocation of `review` MUST persist exactly one Review Decision Record in YAML using the schema below.

Format: YAML

Required keys:
- `decision_id: string`
- `created_at: datetime` (ISO-8601 UTC)
- `mode: enum` (`direct|digest`)
- `actor: string`
- `reason: string|null`
- `results: array[object]` (explicit key required; empty allowed)

`results` entry schema:
- Required keys:
  - `queue_id: string`
  - `old_status: enum` (`pending_review|approved|rejected`)
  - `new_status: enum` (`pending_review|approved|rejected`)
- Optional keys:
  - `hold_until: string|null` (YYYY-MM-DD)
  - `details: object|null`

**Acceptance Criteria**
- AC-SCH-010-1: After any successful `review` invocation (`ok=true`), the returned `decision_record_path` exists and validates against this schema.
- AC-SCH-010-2: For hold decisions, `new_status` equals `pending_review` and `hold_until` is present.

### 4.3 Naming and Link Rules
#### 4.3.1 Note ID and filename alignment
**Requirement NAM-001:** `id` MUST match exactly one of the following patterns, and the Markdown filename MUST equal `<id>.md`:
- slug-only: `^[a-z0-9]+(?:-[a-z0-9]+)*$`
- hash-only: `^h-[0-9a-f]{12,64}$`
- hybrid machine form: `^[a-z0-9]+(?:-[a-z0-9]+)*--h-[0-9a-f]{12}$`

**Acceptance Criteria**
- AC-NAM-001-1: Validator rejects Notes where filename and `id` differ.
- AC-NAM-001-2: Validator rejects `id` strings outside the allowed patterns.
- AC-NAM-001-3: Machine-generated notes default to the hybrid `<slug>--h-<12hex>` pattern unless an explicit migration compatibility mode is enabled.

**Resolution (TODO-Q-NAM-1):** Migration compatibility mode is explicit and disabled by default.
- Config key: `naming.compat_mode` with values `strict` (default) or `legacy_slug_generation`.
- In `strict`, machine-generated notes MUST use hybrid `<slug>--h-<12hex>`.
- In `legacy_slug_generation`, machine-generated notes MAY emit slug-only ids only when no filename/id collision exists; on collision they MUST fall back to hybrid form.
- This mode does not relax NAM-001 validation or filename/id equality rules.

#### 4.3.2 Wikilink resolution
**Requirement LNK-001:** In Strict Mode, all Obsidian Wikilinks in Canonical Scope MUST resolve to an existing Note path.

**Acceptance Criteria**
- AC-LNK-001-1: A link-check helper reports unresolved links; Strict Mode fails if unresolved count > 0.
- AC-LNK-001-2: In non-Strict Mode, unresolved links are reported as warnings and, when the operation is associated with an ingestion Run ID, recorded in the Delta Report `warnings` array (§4.2.6).

## 5. External Interfaces
### 5.1 Command API (transport-agnostic)
Commands are user-invoked operations. They may be implemented via CLI, MCP tools, or an Obsidian plugin, but their logical contract is identical.

**Requirement IF-001:** Every command response MUST return the Output Envelope below.

Output Envelope (JSON object):
- `ok: boolean`
- `command: string`
- `timestamp: string` (ISO-8601 UTC)
- `data: object` (command-specific; MAY include partial results on failure)
- `errors: array[ErrorObject]` (empty if `ok=true`)
- `warnings: array[WarningObject]` (empty allowed)
- `trace: object|null` (optional, for debug/diagnostics)

ErrorObject:
- `code: string`
- `message: string`
- `details: object` (optional)
- `stage: string|null` (optional Stage Name; §6.1.2)
- `retryable: boolean`

WarningObject:
- `code: string`
- `message: string`
- `details: object` (optional)

**Acceptance Criteria**
- AC-IF-001-1: All commands return the envelope keys exactly as specified.
- AC-IF-001-2: If a command fails, `ok=false` and `errors.length>=1`.
- AC-IF-001-3: Error objects always include `code`, `message`, and `retryable`.
- AC-IF-001-4: `timestamp` parses as ISO-8601 UTC and `command` equals the invoked command name.

#### 5.1.1 Common flags: Dry Run
**Requirement IF-002:** Commands that can write files MUST support a Dry Run mode.

Dry Run planned operation schema (returned as `data.planned_writes` when `dry_run=true`):
- `op: enum` (`write|move|copy|mkdir|delete`)
- `path: string` (vault-relative target path)
- `from_path: string|null` (required when `op` is `move|copy|delete`)
- `reason: string|null` (human-readable rationale)

**Acceptance Criteria**
- AC-IF-002-1: Dry Run returns planned file operations in `data.planned_writes` and produces no filesystem diffs.
- AC-IF-002-2: Dry Run still performs schema validation of planned outputs and reports validation errors.

#### 5.1.2 Common flags: Strict Mode
**Requirement IF-003:** Commands that accept `strict: boolean` MUST apply Strict Mode semantics as follows:
- If `strict=true`: schema validation errors (and, where applicable, Canonical Scope unresolved-link errors) produce `ok=false`.
- If `strict=false`: schema validation errors and unresolved links MAY be downgraded to warnings only for read-only commands, and MUST be recorded in `warnings` (and in the Delta Report `warnings` array when the operation is associated with a Run ID).

**Acceptance Criteria**
- AC-IF-003-1: A fixture with an invalid Note schema causes `ok=false` when `strict=true` and produces a warning (not an error) when `strict=false` for a read-only command.
- AC-IF-003-2: For ingestion-associated warnings, the Delta Report includes corresponding warning entries (§4.2.6).

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
  - `strict: boolean` (Strict Mode; §5.1.2)
  - `dry_run: boolean` (Dry Run; §5.1.1)

Output `data`:
- `run_id: string`
- `source_id: string`
- `source_note_path: string`
- `delta_report_path: string`
- `review_queue_item_paths: array[string]`
- `artifact_paths: array[string]` (Extraction Bundle and related artifact paths)
- `idempotency: object` with:
  - `normalized_locator: string`
  - `fingerprint: string`
  - `reused_source_id: boolean`
  - `prior_fingerprint: string|null`

Side effects (when not Dry Run):
- Writes Draft Scope artifacts under `Inbox/`.
- Writes durable outputs under `Reports/Delta/` and `Logs/Audit/`.
- Writes rebuildable indexes under `Indexes/` as needed.

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
- AC-CMD-ING-001-3: After `ingest` succeeds, `artifact_paths` is non-empty and includes at least one Extraction Bundle artifact that validates against SCH-008.

**Requirement CMD-ING-002:** `ingest` MUST return a self-consistent idempotency record that matches the persisted Source Note and Delta Report.

**Acceptance Criteria**
- AC-CMD-ING-002-1: `data.idempotency.normalized_locator` equals the Source Note `normalized_locator` and Delta Report `source_revision.normalized_locator`.
- AC-CMD-ING-002-2: `data.idempotency.fingerprint` equals the Source Note `fingerprint` and Delta Report `source_revision.fingerprint`.
- AC-CMD-ING-002-3: If `prior_fingerprint` is non-null, it equals Delta Report `source_revision.prior_fingerprint`.

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
- `conflicts: array` (from Delta Report)
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

#### 5.2.3 `review`
Input:
- One of:
  - `queue_id: string`
  - `queue_item_paths: array[string]`
  - `digest_path: string`
- Decision mode:
  - direct mode (`queue_id`/`queue_item_paths`): `decision: enum` (`approve|reject|hold`)
  - digest mode (`digest_path`): decisions loaded from packet records (§4.2.9)
- Optional:
  - `reason: string`
  - `actor: string`

Output `data`:
- `updated: array[{queue_id, old_status, new_status}]`
- `held: array[{queue_id, hold_until}]`
- `decision_record_path: string`

Side effects:
- Applies explicit state transitions for queue items (§8.2).
- Writes Review Decision Records under `Inbox/ReviewDigest/` (§4.2.10).

Errors:
- `ERR_QUEUE_ITEM_INVALID`
- `ERR_QUEUE_IMMUTABLE`
- `ERR_REVIEW_DECISION_INVALID`

**Requirement CMD-REV-001:** `review` MUST be the authoritative state transition operation for queue decisions.

**Acceptance Criteria**
- AC-CMD-REV-001-1: Legal transitions are limited to `pending_review -> approved` and `pending_review -> rejected`; any mutation attempt on non-pending items returns `ERR_QUEUE_IMMUTABLE`.
- AC-CMD-REV-001-2: `decision=hold` does not mutate queue `status`; it records deferred review metadata and keeps the item pending.
- AC-CMD-REV-001-3: For digest mode, every packet decision maps deterministically to queue item outcomes (approved/rejected/held) using packet `queue_ids`.

#### 5.2.4 `review_digest`
Input:
- Optional:
  - `date: string` (YYYY-MM-DD; default=today)
  - `run_ids: array[string]`
  - `limit_sources: int`
  - `include_claim_cards: boolean` (default=true)

Output `data`:
- `digest_path: string`
- `packet_paths: array[string]`
- `source_count: int`
- `pending_item_count: int`

Side effects:
- Writes a digest under `Inbox/ReviewDigest/`.
- Writes per-Source packet records (SCH-009).

Errors:
- `ERR_REVIEW_DIGEST_EMPTY`
- `ERR_SCHEMA_VALIDATION`

**Requirement CMD-RDG-001:** `review_digest` MUST produce a reading-first artifact grouped by Source, with per-Source Review Packets that support deterministic downstream decision application.

**Acceptance Criteria**
- AC-CMD-RDG-001-1: A digest with pending items includes one Review Packet per Source and each packet includes `queue_ids` and `run_ids` (SCH-009).
- AC-CMD-RDG-001-2: Packet decisions support exactly `approve_all`, `approve_selected`, `hold`, and `reject` (SCH-009).
- AC-CMD-RDG-001-3: Digest generation is deterministic for the same snapshot in Deterministic Test Mode (§13.4).

**Resolution (TODO-Q-RDG-1):**
- The authoritative invocation surface is the `review_digest` command/API contract itself.
- Invocation may be performed manually, by external scheduler, or via client integration, but all paths MUST call the same command semantics and emit the same artifact schemas.
- A built-in scheduler is not required by this spec.
- Invocations MUST record actor provenance; recommended actor format is `user:<id>`, `scheduler:<id>`, or `client:<id>`.

#### 5.2.5 `graduate`
Input:
- One of:
  - `queue_id: string`
  - `queue_item_paths: array[string]`
  - `all_approved: boolean`
  - `from_digest: string` (apply packet decisions from digest path)
- Optional:
  - `dry_run: boolean`
  - `strict: boolean`

Output `data`:
- `promoted: array[{queue_id, from_path, to_path}]`
- `rejected: array[{queue_id, reason}]`
- `skipped: array[{queue_id, reason}]`
- `audit_event_ids: array[string]`

Side effects:
- Applies approved Promotions, moving artifacts into Canonical Scope and updating statuses.
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
- AC-CMD-GRD-001-2: On success, each promoted Note has `status: canon` and resides in a Canonical Directory.
- AC-CMD-GRD-001-3: Any `graduate` invocation with `dry_run=false` rejects `strict=false` with `ERR_SCHEMA_VALIDATION` (non-Strict is only permitted when `dry_run=true`).
- AC-CMD-GRD-001-4: `from_digest` applies only items explicitly approved by packet decisions; held items remain pending.

#### 5.2.6 `context`
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

#### 5.2.7 `frontier`
Input:
- Optional:
  - `project: string`
  - `tags: array[string]`
  - `limit: int`

Output `data`:
- `conflicts: array[...]`
- `weak_support: array[...]`
- `open_questions: array[...]`
- `reading_targets: array[{target, score, rationale, citations, factors}]` (ranked)
- `explanations: object` (ranking factors)

Side effects: none.

Errors:
- `ERR_NO_FRONTIER_DATA`

**Requirement CMD-FRN-001:** `frontier` MUST surface conflicts, weak support, and open questions when present in seeded data.

**Acceptance Criteria**
- AC-CMD-FRN-001-1: In a seeded Vault fixture containing at least one contradiction and one question, `conflicts.length>=1` and `open_questions.length>=1`.
- AC-CMD-FRN-001-2: `reading_targets` is sorted by an explicit numeric rank/score field included per target.

**Requirement CMD-FRN-002:** `frontier` scoring MUST be deterministic and use the weighted formula below:  
`score = 100 * (0.35*conflict_factor + 0.25*support_gap + 0.20*goal_relevance + 0.10*novelty + 0.10*staleness)`

Factor constraints:
- each factor is in `[0..1]`
- score is clamped to `[0..100]`
- ties are resolved by `(higher conflict_factor, older last_reviewed_at, lexical target id)`

For tie-breaking, `last_reviewed_at` is sourced from Note frontmatter when present; if absent for a target, the system uses `updated` as the fallback tie-break timestamp.

**Acceptance Criteria**
- AC-CMD-FRN-002-1: For a deterministic fixture, repeated frontier runs return byte-identical `reading_targets` ordering and scores.
- AC-CMD-FRN-002-2: Each reading target includes `factors` with all five factor components and values in `[0..1]`.
- AC-CMD-FRN-002-3: If two targets have equal score, tie-break ordering follows the defined deterministic order and fallback behavior.

**Resolution (TODO-Q-FRN-1):** Frontier factor derivations are deterministic and use the **Option B** council choice (hardened deterministic factors).

Let:
- `ref_ts` = command reference timestamp (fixed in Deterministic Test Mode).
- `review_ts(T)` = `last_reviewed_at` when present, otherwise `updated`.
- `contradict_count(T)` = number of contradiction/conflict records citing `T`.
- `support_count(T)` = number of distinct supporting `source_id` values linked to `T`.
- `linked_delta_novelty_30d(T)` = `novelty_score` values from Delta Reports linked to `T` with `created_at >= ref_ts - 30 days`.
- `p75(x)` = deterministic nearest-rank 75th percentile over sorted values `x`; if `x` is empty, `0.0`.

Derivations:
- `conflict_factor(T) = clamp01(contradict_count(T) / max(1, contradict_count(T) + support_count(T)))`
- `support_gap(T) = 1.0 - clamp01(support_count(T) / 3.0)`
- `goal_relevance(T)`:
  - If both `project` and `tags` inputs are omitted: `0.5`
  - Otherwise:
    - `project_match = 1.0` if `project` provided and `T.project == project`; `0.0` if `project` provided and not equal; `0.5` if `project` omitted or `T.project` absent
    - `tag_overlap = |T.tags ∩ input.tags| / max(1, |input.tags|)`; if `input.tags` omitted, `tag_overlap = 0.5`
    - `goal_relevance(T) = clamp01(0.6*project_match + 0.4*tag_overlap)`
- `novelty(T) = clamp01(p75(linked_delta_novelty_30d(T)))`
- `staleness(T) = clamp01(days_between(ref_ts, review_ts(T)) / 45.0)`

#### 5.2.8 `connect`, `trace`, `ideas`
These commands are part of later milestones and may be implemented after MVP2.

**Requirement CMD-FUT-001:** If implemented, each of `connect`, `trace`, and `ideas` MUST conform to IF-001 Output Envelope and define inputs/outputs/side effects/errors in this section before being considered complete.

**Acceptance Criteria**
- AC-CMD-FUT-001-1: For each implemented command, the spec section includes a complete contract: inputs, outputs, side effects, and errors.
- AC-CMD-FUT-001-2: Contract tests validate envelope conformance and schema correctness for each command.

## 6. Ingestion Pipeline
### 6.1 Pipeline Stages and Interfaces
Stages are executed in order. Each stage has a defined interface and error behavior.

**Requirement PIPE-001:** The pipeline MUST be stage-scoped: failures must identify the Stage Name and must not silently proceed with invalid inputs.

Clarification: After a stage failure, the system MAY perform failure-finalization steps (e.g., writing audit events, quarantining artifacts, and writing a Delta Report with `pipeline_status` reflecting failure) as long as those steps do not rely on invalid downstream inputs.

**Acceptance Criteria**
- AC-PIPE-001-1: When a stage fails, the command returns an error with `stage` set to the failing Stage Name (§6.1.2) and an appropriate error code.
- AC-PIPE-001-2: No downstream semantic stage runs using outputs that failed validation (e.g., Compare does not run if Extract fails schema validation).

#### 6.1.1 Stage interfaces (logical; transport/implementation unspecified)
1) Capture  
Input: Source input (`url` / `pdf_path` / `id` / `text_bundle`)  
Output: `RawSourcePayload { bytes|text, media_type, source_ref, source_kind }`  
Side effects: May create transient capture cache entries in Draft Scope only.  
Errors: `ERR_CAPTURE_FAILED`, `ERR_UNSUPPORTED_SOURCE`

2) Normalize  
Input: RawSourcePayload  
Output: `NormalizedSource { normalized_text, normalized_locator, source_kind, source_ref, extracted_metadata }`  
Side effects: None (pure transform).  
Errors: `ERR_NORMALIZATION_FAILED`

3) Fingerprint  
Input: NormalizedSource  
Output: `SourceIdentity { normalized_locator, fingerprint }`  
Side effects: Reads/writes source identity index under `Indexes/`.  
Errors: `ERR_NORMALIZATION_FAILED`

4) Extract  
Input: NormalizedSource  
Output: `ExtractionBundle` artifact (SCH-008)  
Side effects: Writes Extraction Bundle artifacts under `Inbox/Sources/`.  
Errors: `ERR_EXTRACTION_FAILED`, `ERR_SCHEMA_VALIDATION`

5) Compare (Dedupe)  
Input: extracted claims (from Extraction Bundle) + claim index/snapshot  
Output: `MatchResults[]` (Match Records grouped in Delta Report; SCH-006)  
Side effects: Reads claim index snapshot; no Canonical Scope writes.  
Errors: `ERR_INDEX_UNAVAILABLE`, `ERR_SCHEMA_VALIDATION`

6) Delta  
Input: MatchResults (or failure-finalization context)  
Output: Delta Report (SCH-006)  
Side effects: Writes one Delta Report under `Reports/Delta/`; appends audit metadata.  
Errors: `ERR_SCHEMA_VALIDATION`

7) Propose + Queue  
Input: Extraction Bundle + MatchResults + vault snapshot  
Output: Review Queue Items (SCH-007)  
Side effects: Writes queue items under `Inbox/ReviewQueue/`.  
Errors: `ERR_SCHEMA_VALIDATION`

#### 6.1.2 Stage Names
**Requirement PIPE-003:** Errors and audit records that reference a Stage MUST use one of the canonical Stage Names below:
- `capture`
- `normalize`
- `fingerprint`
- `extract`
- `compare`
- `delta`
- `propose_queue`

**Acceptance Criteria**
- AC-PIPE-003-1: For induced failures in each stage, the returned error includes `stage` equal to one of the canonical Stage Names above.
- AC-PIPE-003-2: Audit events that include a `stage` field use only the canonical Stage Names.

### 6.2 Minimum extraction outputs
**Requirement EXT-001:** Extraction MUST produce, at minimum: `gist`, `bullets`, and either (a) at least one claim or (b) an explicit warning explaining why zero claims were produced.

**Acceptance Criteria**
- AC-EXT-001-1: For a golden fixture Source known to contain extractable assertions, `claims.length>=1` in the Extraction Bundle (SCH-008).
- AC-EXT-001-2: For a fixture designed to yield zero claims, the Extraction Bundle includes a warning with code `WARN_NO_CLAIMS_EXTRACTED`.

### 6.3 Artifact staging and atomicity
**Requirement PIPE-002:** The system MUST stage ingestion outputs in Draft Scope and MUST NOT leave partially written Canonical Scope files on failure.

**Acceptance Criteria**
- AC-PIPE-002-1: Inducing a failure after Extract but before Propose+Queue results in quarantined partial Draft Scope artifacts with diagnostics (§10.2), and any Delta Report written reflects failure via `pipeline_status` and `failures` (SCH-006).
- AC-PIPE-002-2: No files in Canonical Scope are created or modified in any failure scenario without Promotion (INV-002).

### 6.4 Idempotency resolution
**Requirement IDM-001:** The system MUST maintain a Source index mapping `(normalized_locator, fingerprint) -> source_id`.

**Acceptance Criteria**
- AC-IDM-001-1: Ingesting an identical fixture twice returns the same `source_id` and sets `data.idempotency.reused_source_id=true` on the second run.
- AC-IDM-001-2: Ingesting a changed-content fixture with the same normalized locator returns a different fingerprint and records `prior_fingerprint` in the Delta Report `source_revision`.

### 6.5 Delta Report generation
**Requirement DEL-001:** Delta Report generation MUST be part of ingestion completion and MUST record match group membership for every extracted claim.

**Acceptance Criteria**
- AC-DEL-001-1: For any successful ingestion, `counts.total_extracted_claims == sum(len(match_groups[...]))`.
- AC-DEL-001-2: Delta Report includes non-empty `match_groups.NEW` for a fixture with novel claims, and non-empty `match_groups.EXACT` or `match_groups.NEAR_DUPLICATE` for an overlap-only fixture.

## 7. Dedupe and Delta Engine
### 7.1 Claim canonicalization
**Requirement DED-001:** Claim canonicalization MUST be deterministic: the same input claim text produces the same canonical form across runs.

Canonicalization output MUST define `extracted_claim_key` deterministically as:  
`extracted_claim_key = "h-" + first_12_hex(sha256( canonical_form_utf8_bytes ))`

**Acceptance Criteria**
- AC-DED-001-1: A unit test runs canonicalization twice on the same text and asserts byte-identical canonical output.
- AC-DED-001-2: Canonicalization collapses whitespace and normalizes Unicode such that cosmetic formatting differences in a golden pair produce identical canonical outputs.
- AC-DED-001-3: For a golden claim pair with identical canonical form, computed `extracted_claim_key` matches exactly.

### 7.2 Match class assignment
**Requirement DED-002:** The comparator MUST assign exactly one Match Class to each extracted claim.

**Acceptance Criteria**
- AC-DED-002-1: For any extraction run, the number of Match Records across all `match_groups.*` equals `counts.total_extracted_claims`.
- AC-DED-002-2: Each Match Record includes `match_class` ∈ {`EXACT`,`NEAR_DUPLICATE`,`SUPPORTING`,`CONTRADICTING`,`NEW`} and a numeric `similarity` in `[0..1]`.

### 7.3 Merge rules
**Requirement DED-003:** Merge rules MUST follow:
- `EXACT` and `NEAR_DUPLICATE`: do not create a new canonical Claim Note by default.
- `SUPPORTING`: attach provenance/support metadata to the existing claim (as a proposal requiring review if it changes canonical content).
- `CONTRADICTING`: preserve both claims and emit an explicit Conflict Record in the Delta Report.
- `NEW`: create a Draft Claim Note linked to its Source.

Similarity thresholds (decision record):
- `EXACT`: similarity `>= 0.97`
- `NEAR_DUPLICATE`: similarity `>= 0.85` and `< 0.97`
- `NEW` candidate default: max similarity `< 0.70`
- Similarity in `[0.70..0.85)` requires reviewer decision between `merge` and `create` paths.

Canonical update policy from match class:
- `EXACT`: update existing canonical claim provenance/support only (no new claim file).
- `NEAR_DUPLICATE`: default to update existing claim; creating a new claim file requires explicit review approval.
- `SUPPORTING`: update existing claim support/provenance fields; no new claim file by default.
- `CONTRADICTING`: create a new draft claim and a conflict link proposal; do not overwrite existing canonical claim text.
- `NEW`: create new draft claim and queue for Promotion.

**Acceptance Criteria**
- AC-DED-003-1: Re-ingesting an overlap-only fixture yields `match_groups.NEW.length==0` and does not increase canonical claim note count.
- AC-DED-003-2: A contradiction fixture yields `match_groups.CONTRADICTING.length>=1` and the Delta Report includes a Conflict Record where `existing_claim_id` and `new_extracted_claim_key` are both present.
- AC-DED-003-3: A novel fixture yields `match_groups.NEW.length>=1` and creates Draft Claim Notes (in Draft Scope) for those new claims.
- AC-DED-003-4: For claims with similarity in `[0.70..0.85)`, generated queue items include a reviewer-visible merge/create recommendation and do not auto-approve.

### 7.4 Novelty scoring
**Requirement DEL-002:** The system MUST compute `novelty_score` deterministically using only Delta Report counts and MUST define it as:  
`novelty_score = (new_count + contradicting_count) / max(1, total_extracted_claims)`

**Acceptance Criteria**
- AC-DEL-002-1: For any Delta Report, recomputing the formula from `counts` matches stored `novelty_score` exactly (within floating-point tolerance of 1e-9).
- AC-DEL-002-2: `novelty_score` equals `0` when `total_extracted_claims==0`.

### 7.5 Confidence rubric (MVP1 advisory)
**Requirement CONF-001:** MVP1 MUST apply a deterministic advisory confidence rubric for extracted claims.

Rubric (advisory; does not auto-promote):
- `confidence = clamp(0,1, 0.40*provenance_quality + 0.30*extract_consistency + 0.20*dedupe_support + 0.10*source_reliability)`
- all factor values are deterministic and in `[0..1]`
- confidence guides review ordering and frontier factors but is not itself a Promotion decision

MVP1 deterministic factor definitions (to ensure testability without external reputation systems):
- `provenance_quality`:
  - `1.0` if Provenance meets the structured minima for `url` or `pdf` (SCH-003) OR includes `raw_locator` for other MVP1 kinds
  - `0.0` if any required provenance field is missing (SCH-003)
- `extract_consistency`:
  - `1.0` for extraction outputs that pass SCH-008 validation
  - `0.0` for claims that fail SCH-008 validation (they are not eligible claims and must not be emitted as claims)
- `dedupe_support`:
  - `1.0` for `EXACT`
  - `0.8` for `NEAR_DUPLICATE`
  - `0.6` for `SUPPORTING`
  - `0.4` for `NEW`
  - `0.2` for `CONTRADICTING`
- `source_reliability`:
  - `0.5` constant in MVP1 (domain calibration deferred)

**Acceptance Criteria**
- AC-CONF-001-1: Re-running confidence calculation for the same fixture yields identical values.
- AC-CONF-001-2: Claims missing required provenance fields are not emitted as valid claims in the Extraction Bundle; if present in intermediate data, their computed confidence is `<= 0.4` and they remain routed to human review paths (not auto-approved).

**Resolution (TODO-Q-CONF-1):** MVP2 calibration for `source_reliability` is defined and user-configurable.
- Optional config file: `Config/source_reliability.yaml`
- Schema: map of domain/publisher key -> numeric reliability in `[0..1]`, plus optional `"default"` key.
- Lookup order: exact key match, parent-domain fallback, then `"default"`.
- If config is absent, `"default"` is `0.5`.
- Values are clamped to `[0..1]`; invalid values fail Strict Mode with `ERR_SCHEMA_VALIDATION` and are warnings in non-Strict mode.

## 8. Review Queue and Promotion
### 8.1 Review queue generation
**Requirement REV-001:** Ingestion MUST generate Review Queue Items for all proposed canonical-impacting actions, including at minimum: promoting new claims and creating new source notes.

**Acceptance Criteria**
- AC-REV-001-1: For a fixture producing at least one new claim, ingestion produces at least one queue item with `item_type: claim_note` and `proposed_action: promote_to_canon` (or a `create` + later promotion path).
- AC-REV-001-2: Queue items include `checks` that at least capture `provenance_present` for claim-related items.

### 8.1.1 Nightly reading-first review workflow
**Requirement REV-001A:** Review MUST support a reading-first workflow that groups queue items by Source into Review Packets.

Workflow requirements (packet semantics):
- Default review unit is a Source packet, with optional claim-level drill-down.
- Packet actions are exactly: `approve_all`, `approve_selected`, `hold`, `reject` (SCH-009).
- `hold` keeps queue items in `pending_review` and records `hold_until` metadata.
- `CONTRADICTING` proposals remain human-review only and are never auto-approved (see REV-001B).

**Acceptance Criteria**
- AC-REV-001A-1: A generated digest includes packet summaries, claim cards (when enabled), citations, and canonical-impact descriptions for each Source packet.
- AC-REV-001A-2: Applying packet actions through `review` and `graduate --from_digest` yields deterministic queue and promotion outcomes for a deterministic fixture.
- AC-REV-001A-3: Hold decisions resurface after the configured hold TTL (decision: 14 days).

**Resolution (TODO-Q-REV-1):**
- Hold policy is stored in `Config/review_policy.yaml` under `hold_ttl_days` (default `14`).
- Every `hold` decision MUST write explicit `hold_until` into both packet decision data (SCH-009) and review decision results (SCH-010).
- Resurfacing is deterministic at `review_digest` generation time: a held queue item is re-included only when `hold_until <= digest_date`.
- No built-in scheduler is required; resurfacing happens whenever digest generation runs.

### 8.1.2 Auto-approval lane policy
**Requirement REV-001B:** The Auto-Approval Lane MUST be constrained to low-risk, non-semantic updates.

Allowed auto-approval classes:
- `EXACT` matches that only attach provenance/support metadata.
- metadata-only Source/Claim note field updates that do not alter claim meaning.
- non-semantic formatting normalization (whitespace/frontmatter ordering/link formatting) with no claim-text change.

Disallowed auto-approval classes:
- any `NEW` claim proposal.
- any `CONTRADICTING` proposal.
- any proposal with missing/weak provenance checks.
- any merge/create ambiguity in similarity band `[0.70..0.85)`.

**Acceptance Criteria**
- AC-REV-001B-1: Auto-approved items include policy reason codes in audit details.
- AC-REV-001B-2: Disallowed classes are routed to human-review packets and remain `pending_review` until explicit review action.

### 8.2 Review state transitions
**Requirement REV-002:** Queue state transitions MUST be explicit and mediated by `review` command semantics.

Transition rules:
- legal transitions: `pending_review -> approved` and `pending_review -> rejected`
- illegal transitions: any mutation of `approved`/`rejected` status without explicit migration tooling
- `hold` is a review decision artifact, not a queue status mutation

**Acceptance Criteria**
- AC-REV-002-1: Integration tests enforce that illegal transitions return `ERR_QUEUE_IMMUTABLE`.
- AC-REV-002-2: `review` writes Review Decision Records and actor/reason metadata for every transition (SCH-010).

### 8.3 Promotion semantics
**Requirement REV-003:** Promotion (via `graduate`) MUST:
1) Validate schemas (SCH-001..SCH-010) in Strict Mode for promoted items.  
2) Update promoted Notes to `status: canon`.  
3) Write promoted Notes into Canonical Scope.  
4) Append audit entries for all affected files (§9.1).

**Acceptance Criteria**
- AC-REV-003-1: After a successful Promotion, every promoted Note validates and has `status: canon`.
- AC-REV-003-2: Audit log contains an entry that lists the promoted paths and the actor identifier.
- AC-REV-003-3: A `graduate` attempt that would mutate Canonical Scope while `strict=false` fails with `ERR_SCHEMA_VALIDATION`.

#### 8.3.1 Git Mode (apply commit granularity)
**Requirement REV-004:** When Git Mode is enabled, Promotions applied from Review Packets MUST create exactly one git commit per Source packet apply batch.

**Acceptance Criteria**
- AC-REV-004-1: In a fixture applying Promotions for two different Source packets in a single run, the resulting git history includes exactly two new commits.
- AC-REV-004-2: In a fixture applying Promotions for one Source packet, the resulting git history includes exactly one new commit whose diff contains only changes attributable to that packet’s promoted items.

**Resolution (TODO-Q-REV-2):**
- Git Mode configuration is stored in `Config/review_policy.yaml` at `git_mode.enabled` (default `false`).
- When enabled, `graduate --from_digest` MUST produce exactly one commit per Source packet apply batch (REV-004).
- Minimum commit subject schema:
  - `graduate packet=<packet_id> source=<source_id> run_ids=<sorted_csv_run_ids>`
- Commit body MUST include applied `queue_id` values in deterministic lexical order.
- If Git Mode is enabled and commit/write fails, promotion apply MUST fail atomically with no partial canonical mutations.

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
- AC-AUD-001-2: Audit logs are append-only: a test verifies that a new run only appends and does not rewrite prior entries.

**Requirement AUD-002:** Audit logs MUST be stored as newline-delimited JSON (JSONL) under `Logs/Audit/`, with one audit event per line.

**Acceptance Criteria**
- AC-AUD-002-1: A parser can read each line as a JSON object and validate the minimum fields in AUD-001.
- AC-AUD-002-2: Appending new events does not change the byte content of previous lines in the same file.

### 9.2 Egress policy
**Requirement SEC-001:** If external Egress is performed, it MUST be governed by an Egress Policy that includes allowlist and blocklist checks and optional sanitization.

**Acceptance Criteria**
- AC-SEC-001-1: Attempting to egress a blocklisted path fails with `ERR_EGRESS_POLICY_BLOCK` and emits an `egress_blocked` audit event.
- AC-SEC-001-2: Egressing an allowlisted test payload emits an `egress_completed` audit event including `bytes_sent` and destination identifier.

**Requirement SEC-002:** The system MUST log what content was sent externally (or its cryptographic digest) and why.

**Acceptance Criteria**
- AC-SEC-002-1: Egress audit events include either (a) a locally stored outbound payload reference, or (b) a payload digest plus the list of source file paths included.
- AC-SEC-002-2: Egress audit events include a reason field (e.g., command name and user request context).

Default policy decision (Q5): staged `report_only (14 days) -> enforce default-deny allowlist` with fail-closed redaction.

Default allowlist patterns (post-burn-in):
- `Sources/**`
- `Claims/**`
- `Concepts/**`
- `Questions/**`
- `Projects/**`
- `MOCs/**`
- `Inbox/ReviewDigest/**`
- `Reports/Delta/**`

Default blocklist patterns:
- `Logs/Audit/**`
- `Indexes/**`
- `Quarantine/**`
- `**/.git/**`
- `**/*.key`
- `**/*.pem`
- `**/*secret*`

Default sanitization policy (when enabled):
- fail closed on redact/parse failures
- redact API keys/tokens, email addresses, phone numbers, and local absolute paths unless explicitly required by command
- include `redaction_summary` in audit `details`

**Requirement SEC-003:** Egress mode transitions MUST be explicit (`report_only` -> `enforce`) and auditable.

**Acceptance Criteria**
- AC-SEC-003-1: In `report_only`, blocked content is logged as `egress_blocked` simulation events but send path remains allowed.
- AC-SEC-003-2: In `enforce`, blocklisted payloads are rejected with `ERR_EGRESS_POLICY_BLOCK` and no outbound bytes are sent.
- AC-SEC-003-3: Mode transitions append an audit event including actor, timestamp, and reason.

**Requirement SEC-004:** When Sanitization is enabled for an Egress attempt, the system MUST apply redaction rules and MUST record a `redaction_summary` in the audit event details.

**Acceptance Criteria**
- AC-SEC-004-1: A fixture payload containing an API key-like token and an email address results in an `egress_attempted`/`egress_completed` audit event that includes `redaction_summary` indicating at least those two redaction categories were applied.
- AC-SEC-004-2: If the sanitization step fails to parse or redact (induced failure fixture), the Egress attempt is blocked and recorded as `egress_blocked` with a failure reason.

**Resolution (TODO-Q-SEC-1):**
- Egress policy state is stored in `Config/egress_policy.yaml` with keys:
  - `mode: report_only|enforce`
  - `burn_in_started_at: ISO-8601 UTC`
  - `last_transition_at: ISO-8601 UTC|null`
  - `transitioned_by: string|null`
  - `transition_reason: string|null`
- Burn-in elapsed days are computed from `burn_in_started_at` at evaluation time; no scheduler is required.
- Transition `report_only -> enforce` is explicit only (command or config change), and MUST emit an audit event per SEC-003.
- Passing 14 days does not auto-flip mode; explicit transition remains required.

## 10. Failure Modes and Recovery
### 10.1 Explicit failures and recoverability
**Requirement ERR-001:** Pipeline failures MUST be explicit, stage-scoped, and recoverable without manual deletion of Canonical Scope files.

**Acceptance Criteria**
- AC-ERR-001-1: For induced failures in each Stage, the returned error includes `stage` and a deterministic `code`.
- AC-ERR-001-2: Retrying the same ingestion after a transient failure produces a successful run without requiring manual cleanup of Canonical Scope.

### 10.2 Quarantine behavior
**Requirement ERR-002:** Invalid or partial artifacts MUST be placed in `Quarantine/` with a diagnostic sidecar.

**Acceptance Criteria**
- AC-ERR-002-1: A corrupted frontmatter fixture results in a quarantined copy and a diagnostic file containing the parse error and the affected original path.
- AC-ERR-002-2: The original corrupted canonical file (if any) is not overwritten.

## 11. Compatibility and Migration
### 11.1 Obsidian and git friendliness
**Requirement MIG-001:** All Canonical Notes MUST remain human-readable and git-diff friendly.

**Acceptance Criteria**
- AC-MIG-001-1: Canonical Notes contain only YAML frontmatter + Markdown body; no binary blobs.
- AC-MIG-001-2: Schema changes that add fields do not require rewriting unchanged canonical notes.

### 11.2 Schema evolution
**Requirement MIG-002:** Any breaking schema or layout change MUST include a migration and rollback procedure.

**Acceptance Criteria**
- AC-MIG-002-1: A migration test applies the migration to a fixture Vault and validates that all Notes still pass schema checks.
- AC-MIG-002-2: A rollback test restores the pre-migration fixture state byte-for-byte for Canonical Notes.

## 12. Milestones
Milestones define required capability bundles.

### 12.1 MVP1
**Requirement MVP1-001:** MVP1 MUST include:
- Ingest URL and PDF into Draft Scope (`Inbox/Sources/`).
- Generate Source Note, Extraction Bundle, and Delta Report.
- Perform basic dedupe/match classification.
- Propose best-effort links (as Review Queue Items).
- Generate Review Digest packets grouped by Source.
- Support packet actions: `approve_all`, `approve_selected`, `hold`, `reject`.
- Support deterministic apply from digest decisions (`graduate --from_digest`).
- Enforce constrained Auto-Approval Lane policy for non-semantic updates only.
- Enforce provenance and Promotion gate.

**Acceptance Criteria**
- AC-MVP1-001-1: End-to-end tests cover URL and PDF ingest and verify artifacts and schemas (SCH-002, SCH-006, SCH-008, SCH-007).
- AC-MVP1-001-2: Idempotency test demonstrates Source ID reuse and no canonical duplication on repeat ingest.
- AC-MVP1-001-3: Digest test verifies packet generation (SCH-009) and deterministic decision apply behavior.
- AC-MVP1-001-4: Auto-lane test verifies disallowed classes (`NEW`, `CONTRADICTING`) remain in human review.

### 12.2 MVP2
**Requirement MVP2-001:** MVP2 MUST include:
- Review Queue lifecycle enforcement and `graduate`.
- Promotion updates Canonical Scope with audit records.
- Frontier output for seeded contradictions and questions using deterministic scoring formula.
- Stable context/frontier retrieval behavior over canonical wikilink graph.

**Acceptance Criteria**
- AC-MVP2-001-1: Integration test enforces invalid queue transitions fail with `ERR_QUEUE_IMMUTABLE`.
- AC-MVP2-001-2: Frontier seeded fixture yields non-empty `conflicts` and `open_questions`.
- AC-MVP2-001-3: Frontier fixture yields deterministic scores and ordering across repeated runs.

### 12.3 Performance targets (decision Q6)
**Requirement PERF-001:** MVP1/MVP2 MUST enforce numeric p95 latency targets on benchmark fixtures.

Targets:
- `ingest(url_basic)` p95 <= 60s
- `ingest(pdf_basic)` p95 <= 120s
- `delta` by `delta_report_path` p95 <= 5s
- `frontier` on seeded medium fixture p95 <= 8s

**Acceptance Criteria**
- AC-PERF-001-1: Bench suite reports p95 for all four targets and fails gate on threshold breach.
- AC-PERF-001-2: Benchmark results include fixture id, run count, and hardware profile metadata.

### 12.4 MVP3 (future)
MVP3 may include advanced triage (“watery vs dense”), `/connect`, `/trace`, `/ideas`, and ranking improvements.

**Resolution (TODO-Q-MVP3-1):** MVP3 triage/skip policy uses the **Option C** council choice (governed deterministic lifecycle with hysteresis).
- `triage_score = clamp01(0.45*conflict_factor + 0.25*support_gap + 0.20*novelty + 0.10*staleness)`
- Buckets:
  - `dense` if `triage_score >= 0.67`
  - `mixed` if `0.34 <= triage_score < 0.67`
  - `watery` if `triage_score < 0.34`
- Hysteresis:
  - `dense -> mixed` only after 2 consecutive evaluations with `triage_score < 0.62`
  - `watery -> mixed` on first evaluation with `triage_score >= 0.42`
- Skip-list entry requires all:
  - 3 consecutive `watery` evaluations
  - `conflict_factor == 0`
  - zero open-question references
  - target not manually pinned
  - target age `>= 14 days`
- Skip-list metadata per target:
  - `skip_since`, `skip_reason`, `next_review_at`
  - default `next_review_at = skip_since + 30 days`
- Skip-list removal on first of:
  - any new conflict reference
  - any new open-question reference
  - manual unskip
  - `next_review_at` reached (auto-resurface and re-evaluate)
- Safety cap: skip-list may include at most 20% of active targets in a snapshot.
- Skipped targets remain retrievable with `include_skip=true`.

**Resolution (TODO-Q-MVP3-2):** MVP3 graph analysis uses the **Option C** council choice (two-tier model with stronger hub quality + dual-size perf envelopes).
- Graph substrate:
  - canonical wikilink graph over Canonical Scope notes
  - directed edges for traversal; undirected projection for articulation/bridge analysis
- Core algorithms (required baseline):
  - Hub score: `hub_score = 0.6*norm(in_degree) + 0.4*norm(page_rank)`
  - Bridges: Tarjan articulation points + bridge edges on undirected projection (`O(V+E)`)
  - Tie-break ordering: lexical by stable target id
- Optional advanced mode (`--advanced-graph`):
  - approximate betweenness for top-N candidates
  - advanced-mode metrics are non-blocking for baseline SLA gates unless explicitly enabled
- Minimum outputs:
  - `hubs`, `articulation_points`, `bridge_edges`, `components_summary`
  - hub metrics include `in_degree`, `page_rank`, `hub_score`
- Performance targets:
  - Medium fixture (`~5k` nodes / `~20k` edges):
    - graph build p95 `<= 2.5s`
    - core analysis p95 `<= 4.0s`
    - end-to-end command p95 `<= 6.0s`
  - Large fixture (`~10k` nodes / `~50k` edges):
    - graph build p95 `<= 6.0s`
    - core analysis p95 `<= 9.0s`
    - end-to-end command p95 `<= 14.0s`

## 13. Test Plan
This section specifies required testing layers and fixture strategy.

### 13.1 Unit Tests
**Requirement TST-U-001:** Unit tests MUST cover deterministic canonicalization, schema validation, match classification, and novelty scoring.

**Acceptance Criteria**
- AC-TST-U-001-1: Canonicalization determinism tests pass (AC-DED-001-1/2/3).
- AC-TST-U-001-2: Schema validators reject each invalid fixture with the expected error code.
- AC-TST-U-001-3: Novelty scoring recomputation matches stored value (AC-DEL-002-1).

### 13.2 Integration Tests
**Requirement TST-I-001:** Integration tests MUST cover the pipeline stage chain and enforce Draft/Cannon boundaries.

**Acceptance Criteria**
- AC-TST-I-001-1: A full pipeline run from capture→delta→queue completes for each supported source kind fixture.
- AC-TST-I-001-2: A boundary test verifies no writes occur under Canonical Scope without Promotion (AC-INV-002-1).
- AC-TST-I-001-3: `review` transition tests enforce legal transitions and immutable-state failures.
- AC-TST-I-001-4: `review_digest` tests verify Source packet grouping and packet schema (SCH-009).

### 13.3 End-to-End Tests
**Requirement TST-E2E-001:** End-to-end tests MUST validate user workflows: first ingest, repeat ingest, contradiction ingest, review, promotion, and context/frontier outputs.

**Acceptance Criteria**
- AC-TST-E2E-001-1: First ingest fixture produces Source Note (draft), Extraction Bundle, Delta Report, and Queue Items.
- AC-TST-E2E-001-2: Repeat ingest fixture produces identical `source_id` and `match_groups.NEW.length==0` for an overlap-only fixture.
- AC-TST-E2E-001-3: Contradiction fixture yields `CONTRADICTING` matches and the Delta Report includes at least one Conflict Record.
- AC-TST-E2E-001-4: Review + Promotion fixture updates statuses to `canon`, moves files into Canonical Scope, and appends audit events.
- AC-TST-E2E-001-5: Review Digest workflow fixture validates `approve_all`, `approve_selected`, `hold`, and `reject` semantics end-to-end.
- AC-TST-E2E-001-6: Hold TTL fixture resurfaces held items after 14 days.

### 13.4 Golden Fixtures
Golden fixtures are versioned, deterministic test inputs with expected outputs.

**Requirement TST-G-001:** The test suite MUST include golden fixture sets for ingestion and Delta Reports.

Minimum fixture categories:
- `url_basic`: a stable HTML/text URL capture representation (offline fixture) producing at least one `NEW` claim.
- `pdf_basic`: a small PDF fixture producing at least one `NEW` claim.
- `delta_overlap_only`: produces only `EXACT`/`NEAR_DUPLICATE` matches.
- `delta_new_and_contradict`: produces at least one `NEW` and one `CONTRADICTING`.
- `corrupted_frontmatter`: triggers Quarantine behavior.
- `idempotency_changed_content`: same locator, different fingerprint.

**Acceptance Criteria**
- AC-TST-G-001-1: Golden expected Delta Report content is stable under Deterministic Test Mode (TST-G-002), with dynamic fields either fixed or normalized consistently.
- AC-TST-G-001-2: Updating a golden fixture requires a changelog entry describing why outputs changed (e.g., schema version bump or algorithm change).

**Requirement TST-G-002:** The system MUST support Deterministic Test Mode for golden testing via either:
- fixed clock and stable ID generation, or
- a documented normalization step that removes nondeterminism before comparison.

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

### 13.6 Performance Bench Tests
**Requirement TST-P-001:** Bench tests MUST enforce PERF-001 thresholds and produce reproducible p95 reports.

**Acceptance Criteria**
- AC-TST-P-001-1: Bench suite runs in CI (or scheduled local gate) and records p50/p95/p99 plus pass/fail per target.
- AC-TST-P-001-2: Any p95 threshold breach blocks release unless explicitly waived with a changelog rationale.

## 14. Spec Lint Checklist
**Requirement LINT-001:** Specialized terms used in the spec MUST appear in the Glossary.

**Acceptance Criteria**
- AC-LINT-001-1: A spec-lint pass flags any Term used as a defined concept (e.g., capitalized Term or explicitly referenced Term) that is not present in the Glossary table and fails lint.

**Requirement LINT-002:** Every `MUST` requirement in this spec MUST have explicit Acceptance Criteria in the same section.

**Acceptance Criteria**
- AC-LINT-002-1: A spec-lint pass flags any `MUST` requirement without a nearby “Acceptance Criteria” block and fails lint.

**Requirement LINT-003:** Every interface described as required MUST specify inputs, outputs, side effects, and errors.

**Acceptance Criteria**
- AC-LINT-003-1: A spec-lint pass flags any required command or Stage interface missing any of the four components.

**Requirement LINT-004:** Repetition MUST be minimized by defining invariants once and referencing them.

**Acceptance Criteria**
- AC-LINT-004-1: A spec-lint pass flags duplicate normative statements that restate the same invariant without referencing its ID.

## 15. Decision Record (Resolved for v1.1)
- Q1 (Note ID strategy): Use hybrid `<slug>--h-<12hex>` for machine-generated notes; migration compatibility may allow manual slug-only notes.
- Q2 (provenance locator granularity): URL/PDF require structured locator + `snippet_hash`; other source kinds use `raw_locator` in MVP1.
- Q3 (confidence rubric): deterministic advisory rubric enabled in MVP1 (see CONF-001); MVP2 adds optional user-configurable `source_reliability` calibration.
- Q4 (authoritative review UX): command/API is authoritative; CLI and Obsidian plugin are client surfaces.
- Q5 (egress policy): staged `report_only (14 days) -> enforce default-deny allowlist` with fail-closed redaction.
- Q6 (performance targets): fixed numeric p95 thresholds defined in PERF-001.
- Q7 (nightly review unit): Source-level Review Packets with optional claim drill-down.
- Q8 (review actions): `approve_all`, `approve_selected`, `hold`, `reject`.
- Q9 (auto-approval lane): constrained to low-risk, non-semantic updates; semantic changes remain human-review.
- Q10 (apply commit granularity): one commit per Source packet apply batch.
- Q11 (hold aging policy): hold TTL is 14 days, then item resurfaces in nightly digest.
- Q12 (contradictions): always require human review with side-by-side evidence; never auto-approved.
- Q13 (frontier scoring): deterministic weighted formula in CMD-FRN-002 with Option B derivations (ratio-based conflict/support, p75 novelty over 30d lookback, 45d staleness normalization).
- Q14 (create-vs-update threshold): similarity thresholds and merge/create ambiguity band defined in DED-003.
- Q15 (MVP3 triage): Option C chosen with governed skip-list lifecycle, hysteresis, and skip-cap safety controls.
- Q16 (MVP3 graph analysis): Option C chosen with two-tier analytics (hybrid hub score + Tarjan core, optional advanced mode) and dual-size performance targets.
