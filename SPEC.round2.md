# Mycelium Agentic Knowledge Vault Specification
Version: Round 2 (Interfaces and Schemas Lock-in)
Status: Draft

## 1. Glossary
| Term | Definition |
|---|---|
| Vault | Obsidian-compatible root directory containing canonical Markdown notes and machine-generated draft artifacts. |
| Canonical Note | Human-approved note with `status: canon`. |
| Draft Note | Agent-generated note pending review with `status: draft`. |
| Reviewed Note | Human-reviewed note eligible for promotion with `status: reviewed`. |
| Source Note | Note representing one external artifact (URL/PDF/DOI/arXiv/book/highlights bundle). |
| Claim | Atomic, falsifiable assertion with provenance. |
| Claim Note | Note whose primary payload is one atomic claim. |
| Concept Note | Note defining a term, entity, or idea with context and links. |
| Question Note | Note capturing an unresolved question or uncertainty. |
| MOC | Map of Content; curated navigation/index note. |
| Delta | Computed difference between ingested source knowledge and existing vault knowledge. |
| Delta Report | Structured artifact for one ingestion run: novelty, overlap, contradictions, links, and follow-up gaps. |
| Frontier | Topics with low clarity/support or unresolved conflicts relative to user interest. |
| Promotion | Explicit transition of note state to canonical. |
| Provenance | Trace metadata linking extracted claims to source references and locations. |
| Ingestion Job | End-to-end processing run for one source input. |
| Source Fingerprint | Deterministic identity value used for idempotency checks on ingest. |

## 2. Goals
- Preserve local-first Markdown canon and Obsidian interoperability.
- Convert raw sources into structured, linked, attributable knowledge.
- Compute source-level delta and novelty rather than only summaries.
- Enforce human-owned canon with draft-first agent output.
- Improve recall/synthesis/navigation via graph-aware retrieval.
- Surface the knowledge frontier and reading priorities.

## 3. Non-Goals
- Replacing user reasoning/voice.
- Uncurated full-vault RAG ingestion without structure.
- Public social network capabilities.
- Default autonomous canon writes.
- Mandatory cloud-only execution.

## 4. Scope
### 4.1 In Scope
- URL/PDF/DOI/arXiv/highlights/book-note ingestion.
- Extraction: gist, key bullets, atomic claims, definitions, named entities.
- Claim dedupe and Delta Report generation.
- Link/MOC recommendation updates.
- Review queue and promotion workflow.
- Frontier analysis and recommendation outputs.

### 4.2 Out of Scope (Initial)
- Meeting transcript/email ingestion.
- Multi-user collaboration and permissions model.
- Zero-review autonomous canon mutation.

## 5. Personas and Use Cases
| Persona | Outcome | Primary Workflows |
|---|---|---|
| Knowledge Owner | Capture and preserve high-value knowledge without quality drift | `/ingest`, `/delta`, `/graduate` |
| Research Explorer | Identify weak/conflicted areas and next best reading | `/frontier`, `/connect`, `/ideas` |
| Project Builder | Generate context packs and trace idea evolution | `/context`, `/trace` |

## 6. System Architecture (High-Level)
| Component | Responsibility | Inputs | Outputs |
|---|---|---|---|
| Ingestion Adapters | Capture source content and metadata by type | URL/PDF/DOI/arXiv/text bundle | Raw source payload |
| Normalizer | Convert payload to normalized markdown sections | Raw payload | Normalized content |
| Extractor | Produce structured extraction artifacts | Normalized content | Gist/bullets/claims/definitions/entities |
| Comparator | Match extracted claims against vault claims | Extracted claims + claim index | overlap/new/conflict candidates |
| Delta Engine | Score and summarize delta | Comparator output + graph state | Delta report |
| Linker | Propose wikilinks, MOC deltas, related notes | Extraction + delta + vault graph | Link/update proposals |
| Review Queue Manager | Stage draft changes for human review | Draft artifacts | Queue entries |
| Promotion Manager | Apply approved promotions to canon | Queue approvals | Canon updates + audit entries |
| Retrieval Engine | Build citation-backed query answers/context packs | Query + graph/index state | Ranked note/claim/source bundle |
| Frontier Analyzer | Surface low-support/high-interest gaps | Claim graph + question graph | Frontier report |
| Audit Logger | Persist operation trace and egress events | Pipeline events | Append-only logs |

## 7. Functional Requirements
| ID | Requirement | Acceptance Criteria |
|---|---|---|
| FR-001 | Vault Markdown MUST remain canonical source of truth. | AC-FR-001-1: Canonical content required for operation is present in Markdown files. AC-FR-001-2: Canonical files open correctly in Obsidian. |
| FR-002 | `/ingest` MUST create one source note per new source in inbox scope. | AC-FR-002-1: URL ingestion creates one source note in `/Inbox/Sources/`. AC-FR-002-2: PDF ingestion creates one source note in `/Inbox/Sources/`. |
| FR-003 | Ingestion MUST extract gist, key bullets, and atomic claims. | AC-FR-003-1: Each completed ingestion has all three artifacts. AC-FR-003-2: Missing artifact marks ingestion as partial failure. |
| FR-004 | Imported claims MUST include provenance. | AC-FR-004-1: Claim schema validation fails if provenance is absent. AC-FR-004-2: Promotion validator rejects provenance-missing claims. |
| FR-005 | Each ingestion MUST generate and persist a Delta Report. | AC-FR-005-1: Delta report file exists in `/Reports/Delta/` for every completed ingestion run. AC-FR-005-2: Report includes novelty/overlap/reinforcement/contradiction/link sections. |
| FR-006 | Dedupe MUST execute before claim creation. | AC-FR-006-1: Repeated ingestion of identical claims does not create new canonical claim notes. AC-FR-006-2: Dedupe decision is logged in delta report. |
| FR-007 | Agents MUST write draft artifacts by default. | AC-FR-007-1: Newly generated notes default to `status: draft`. AC-FR-007-2: Canonical paths are unchanged before `/graduate` approval. |
| FR-008 | `/graduate` MUST perform explicit promotion to canon. | AC-FR-008-1: Promotion changes status to `canon`. AC-FR-008-2: Promotion records actor, timestamp, and changed files in audit log. |
| FR-009 | `/delta <source>` MUST return structured claim-delta categories. | AC-FR-009-1: Output contains `new`, `overlap`, `reinforced`, `contradicted`. AC-FR-009-2: Output cites affected notes/sources. |
| FR-010 | `/frontier` MUST return weak-support/open-question outputs. | AC-FR-010-1: Output lists weakly supported beliefs and open questions. AC-FR-010-2: Output includes prioritized reading targets. |
| FR-011 | `/context` MUST build bounded context packs without full-vault load. | AC-FR-011-1: Retrieval trace indicates selective traversal from MOCs/indexes. AC-FR-011-2: Output includes citations for returned claims/sources. |
| FR-012 | `/trace`, `/connect`, and `/ideas` SHOULD return structured proposals grounded in linked notes/claims. | AC-FR-012-1: Each command returns machine-parseable sections. AC-FR-012-2: Each result includes supporting references. |

## 8. Non-Functional Requirements
| ID | Requirement | Acceptance Criteria |
|---|---|---|
| NFR-001 | System MUST be local-first. | AC-NFR-001-1: Canonical operations function offline. AC-NFR-001-2: Canon storage is local filesystem. |
| NFR-002 | System MUST enforce outbound content controls for external LLM calls. | AC-NFR-002-1: Allowlist policy blocks non-allowed paths. AC-NFR-002-2: Blocked send attempts are logged with reason. |
| NFR-003 | System MUST provide append-only audit logs for ingestion/promotion/egress events. | AC-NFR-003-1: Every event has timestamp, actor, op, targets. AC-NFR-003-2: Append-only behavior is test-verified. |
| NFR-004 | Ingestion SHOULD complete within interactive latency for single-source jobs. | AC-NFR-004-1: Median duration metrics are emitted. AC-NFR-004-2: Timeout/error states are explicit. |
| NFR-005 | Ingestion MUST be idempotent by source fingerprint and normalized locator. | AC-NFR-005-1: Re-running identical input reuses prior source note id. AC-NFR-005-2: Delta report marks duplicate/low-delta result. |
| NFR-006 | Changes MUST remain git-friendly and reversible. | AC-NFR-006-1: Canon changes are text diffs. AC-NFR-006-2: Last promotion revert restores previous canon content. |

## 9. Interface Contracts
### 9.1 Command Surface
| Command | Arguments | Output Contract | Side Effects | Error Contract |
|---|---|---|---|---|
| `/ingest` | `--url <url>` OR `--pdf <path>` OR `--id <doi\|arxiv>`; optional `--why`, `--tags` | Returns `run_id`, `source_id`, paths to source note, extraction bundle, delta report, review items | Writes draft artifacts to inbox/reports/review queue | `ERR_INVALID_INPUT`, `ERR_UNSUPPORTED_SOURCE`, `ERR_NORMALIZATION_FAILED`, `ERR_EXTRACTION_FAILED`, `ERR_SCHEMA_VALIDATION` |
| `/delta` | `<source_id\|source_path>` | Returns structured delta sections with counts and references | None | `ERR_SOURCE_NOT_FOUND`, `ERR_DELTA_NOT_FOUND` |
| `/frontier` | optional `--tag`, `--project`, `--limit` | Returns frontier topics, weak beliefs, open questions, reading targets | None | `ERR_NO_FRONTIER_DATA` |
| `/connect` | `<domainA> <domainB>` optional `--limit` | Returns bridge proposals, candidate links, candidate notes | MAY create draft bridge notes in inbox | `ERR_DOMAIN_NOT_FOUND`, `ERR_INSUFFICIENT_CONTEXT` |
| `/trace` | `<idea_or_note_id>` | Returns timeline of linked notes/claims/events | None | `ERR_TRACE_NOT_FOUND` |
| `/graduate` | optional `--queue-id`, `--all-reviewed`, `--dry-run` | Returns promoted item list and resulting canonical paths | Updates note statuses and canonical content | `ERR_QUEUE_ITEM_INVALID`, `ERR_PROVENANCE_MISSING`, `ERR_PROMOTION_CONFLICT` |
| `/context` | optional `--goal`, `--project`, `--limit` | Returns ranked context pack with citations and traversal trace | None | `ERR_CONTEXT_EMPTY` |
| `/ideas` | optional `--theme`, `--limit` | Returns structured idea candidates with linked support | MAY create draft idea notes | `ERR_INSUFFICIENT_SIGNAL` |

### 9.2 Command Output Envelope
Every command response MUST use:
- `ok: boolean`
- `command: string`
- `timestamp: ISO-8601 UTC`
- `data: object`
- `errors: array` (empty if none)

Acceptance Criteria:
- AC-IF-001-1: All command handlers return the envelope keys above.
- AC-IF-001-2: Erroring commands set `ok=false` and include at least one structured error item.

## 10. Vault File and Folder Layout
| Path | Type | Canonical or Derived | Purpose |
|---|---|---|---|
| `/Inbox/Sources/` | dir | Derived drafts | Source captures and extraction drafts |
| `/Inbox/ReviewQueue/` | dir | Derived drafts | Queue items pending human review |
| `/Sources/` | dir | Canonical | Promoted source notes |
| `/Claims/` | dir | Canonical | Canonical claim notes |
| `/Concepts/` | dir | Canonical | Canonical concept notes |
| `/Questions/` | dir | Canonical | Canonical question notes |
| `/Projects/` | dir | Canonical | Project state/decision notes |
| `/MOCs/` | dir | Canonical | Curated map-of-content notes |
| `/Reports/Delta/` | dir | Derived durable | Delta report history |
| `/Logs/Audit/` | dir | Derived durable | Audit/event logs |
| `/Indexes/` | dir | Derived | Optional machine indexes for retrieval/dedupe |

Acceptance Criteria:
- AC-LAY-001-1: Ingestion writes only to inbox/reports/logs before promotion.
- AC-LAY-001-2: Canonical content directories remain valid Markdown artifacts.

## 11. Canonical Schemas
### 11.1 Shared Frontmatter Contract
| Key | Type | Requirement | Constraint |
|---|---|---|---|
| `type` | enum | MUST | `source|claim|concept|question|project|moc` |
| `id` | string | MUST | lowercase kebab-case or hash-prefixed id |
| `created` | datetime | MUST | ISO-8601 UTC |
| `updated` | datetime | MUST | ISO-8601 UTC |
| `status` | enum | MUST | `draft|reviewed|canon` |
| `tags` | list[string] | SHOULD | lowercase, kebab-case tags |
| `confidence` | number | SHOULD | range `0.0..1.0` |
| `source_ref` | string | MUST for imported notes | URL/DOI/arXiv/book reference |

Acceptance Criteria:
- AC-SCH-001-1: Schema validator rejects missing required keys.
- AC-SCH-001-2: Date fields must parse as UTC ISO-8601.

### 11.2 Source Note Schema (with Example)
Required fields:
- `type`, `id`, `status`, `created`, `updated`, `source_ref`, `source_kind`, `captured_at`, `fingerprint`

Markdown example:
```markdown
---
type: source
id: src-20260225-transformers-paper
status: draft
created: 2026-02-25T02:00:00Z
updated: 2026-02-25T02:00:00Z
source_ref: https://arxiv.org/abs/1706.03762
source_kind: arxiv
captured_at: 2026-02-25T02:00:00Z
fingerprint: sha256:abc123...
tags: [ml, transformers]
why_saved: "potential relevance to agent memory indexing"
reading_status: unread
---
# Source: Attention Is All You Need
```

Acceptance Criteria:
- AC-SRC-001-1: `fingerprint` is stable across repeated ingestion of identical normalized content.
- AC-SRC-001-2: Duplicate ingest resolves to existing `id` unless override flag is explicitly set.

### 11.3 Claim Note Schema (with Example)
Required fields:
- `type`, `id`, `status`, `created`, `updated`, `claim_text`, `provenance`

Markdown example:
```markdown
---
type: claim
id: clm-transformer-self-attention-reduces-recurrence
status: draft
created: 2026-02-25T02:01:00Z
updated: 2026-02-25T02:01:00Z
claim_text: "Self-attention can replace recurrence for sequence transduction tasks at competitive quality."
confidence: 0.74
provenance:
  source_id: src-20260225-transformers-paper
  source_ref: https://arxiv.org/abs/1706.03762
  locator: section:abstract
tags: [ml, architecture]
---
# Claim
[[Sources/src-20260225-transformers-paper]]
```

Acceptance Criteria:
- AC-CLM-001-1: `provenance.source_id` and `provenance.source_ref` are both required.
- AC-CLM-001-2: Promotion fails if claim text is empty or provenance is missing.

### 11.4 Concept Note Schema (with Example)
Required fields:
- `type`, `id`, `status`, `created`, `updated`, `term`

Markdown example:
```markdown
---
type: concept
id: cpt-self-attention
status: reviewed
created: 2026-02-25T02:05:00Z
updated: 2026-02-25T02:05:00Z
term: "Self-attention"
definition_status: working
tags: [ml, sequence-modeling]
---
# Self-attention
Definition draft linked to [[Claims/clm-transformer-self-attention-reduces-recurrence]].
```

Acceptance Criteria:
- AC-CPT-001-1: Concept note includes `term` and at least one outbound wikilink before canon promotion.

### 11.5 Delta Report Schema (with Example)
Required fields:
- `run_id`, `source_id`, `created_at`, `novelty_score`, `new_claims`, `overlapping_claims`, `reinforced_claims`, `contradicted_claims`, `new_links`

YAML example:
```yaml
run_id: ing-20260225-020000-001
source_id: src-20260225-transformers-paper
created_at: 2026-02-25T02:04:30Z
novelty_score: 0.41
new_claims:
  - clm-transformer-self-attention-reduces-recurrence
overlapping_claims:
  - clm-sequence-models-need-positional-information
reinforced_claims: []
contradicted_claims: []
new_links:
  - from: clm-transformer-self-attention-reduces-recurrence
    to: cpt-self-attention
follow_up_questions:
  - "Under what data regimes does this claim degrade?"
```

Acceptance Criteria:
- AC-DEL-001-1: Delta report is persisted for every completed ingestion (success or partial).
- AC-DEL-001-2: Report lists empty arrays explicitly, not omitted keys.

### 11.6 Review Queue Item Schema (with Example)
Required fields:
- `queue_id`, `run_id`, `item_type`, `target_path`, `proposed_action`, `status`, `created_at`

YAML example:
```yaml
queue_id: rq-20260225-0007
run_id: ing-20260225-020000-001
item_type: claim_note
target_path: Inbox/Claims/clm-transformer-self-attention-reduces-recurrence.md
proposed_action: promote_to_canon
status: pending_review
created_at: 2026-02-25T02:05:10Z
checks:
  provenance_present: true
  links_present: true
  duplicate_risk: low
```

Acceptance Criteria:
- AC-RQ-001-1: `/graduate --dry-run` lists queue item validation results.
- AC-RQ-001-2: Non-pending items are immutable except explicit state transition operation.

## 12. Explicit Contracts
### 12.1 Ingestion Idempotency Rules
- Rule ID-1: The system MUST derive a `source_fingerprint` from normalized source payload.
- Rule ID-2: The system MUST maintain a source index mapping normalized locator + fingerprint -> `source_id`.
- Rule ID-3: Re-ingesting matching locator/fingerprint MUST reuse existing `source_id` and create a new run record only.
- Rule ID-4: Re-ingesting matching locator but changed fingerprint MUST create a new run and append source revision metadata.

Acceptance Criteria:
- AC-IDM-001-1: Duplicate ingest yields zero new canonical claim note files by default.
- AC-IDM-001-2: Changed-content ingest under same URL records revision lineage.

### 12.2 Naming Conventions
- Note id MUST be lowercase and kebab-case, with type prefix recommended (`src-`, `clm-`, `cpt-`, `qst-`, `prj-`, `moc-`).
- File names MUST match note `id` exactly plus `.md`.
- Tags SHOULD be lowercase kebab-case without spaces.

Acceptance Criteria:
- AC-NAM-001-1: Validator rejects note files where filename and `id` differ.
- AC-NAM-001-2: Validator flags non-conforming tags.

### 12.3 Link Conventions
- Internal links MUST use Obsidian wikilinks (`[[Path/NoteId]]`).
- Claim notes MUST link to at least one source note.
- Concept notes SHOULD link to supporting claims and related concepts.
- MOC notes MUST contain curated outbound links and optional grouping headers.

Acceptance Criteria:
- AC-LNK-001-1: Claim promotion fails without at least one source wikilink.
- AC-LNK-001-2: Link checker reports unresolved wikilinks and fails strict mode.

### 12.4 Frontmatter Key Conventions
- Required keys MUST appear in frontmatter top-level unless explicitly nested by schema.
- Unknown keys MAY exist but MUST NOT shadow required keys.

Acceptance Criteria:
- AC-FMT-001-1: Schema validation reports missing required keys with line-level diagnostics.
- AC-FMT-001-2: Duplicate required keys are rejected.

## 13. Governance
| Rule ID | Rule | Acceptance Criteria |
|---|---|---|
| GOV-001 | Human owner MUST remain final authority over canonical content. | AC-GOV-001-1: No canon write occurs without explicit promotion action. |
| GOV-002 | Agent output MUST default to inbox/draft artifacts. | AC-GOV-002-1: New agent outputs are created in inbox paths with `status: draft`. |
| GOV-003 | Imported claims MUST include provenance before canon eligibility. | AC-GOV-003-1: Promotion validator blocks provenance-missing claims. |
| GOV-004 | Audit trail MUST capture ingestion, promotion, and external-send events. | AC-GOV-004-1: Log includes actor, action, timestamp, and file targets. |

## 14. Risks and TODO Questions
### 14.1 Risks
- Claim granularity inconsistency may degrade dedupe and delta quality.
- Aggressive linking may create noisy navigation.
- Weak confidence calibration may distort frontier ranking.
- External egress misconfiguration may leak sensitive data.

### 14.2 TODO Questions
- TODO-Q1: What confidence calibration rubric is required per domain?
- TODO-Q2: Should IDs be slug-only, hash-only, or slug+hash hybrid for collision resistance?
- TODO-Q3: What minimum provenance is acceptable for offline book notes with no URL/DOI?
- TODO-Q4: Which review UX is authoritative for promotion decisions (CLI-only vs plugin-assisted)?
- TODO-Q5: What novelty thresholds should drive queue prioritization buckets?

## 15. Milestone Acceptance Criteria
### 15.1 MVP1
- URL/PDF ingest produces source note + extraction + delta report.
- Basic dedupe suppresses obvious duplicate claim creation.
- Link proposals include valid wikilink targets when matches exist.
- Imported claims include provenance fields.

### 15.2 MVP2
- Review queue + promotion workflow functions end-to-end.
- Canonical claim representation drives dedupe and delta.
- Frontier output includes open questions and weak-support beliefs.

### 15.3 MVP3
- `/connect`, `/trace`, `/ideas` return citation-backed structured outputs.
- Recommendation output includes prioritized reading targets.
- Triage scoring generates queue ordering and skip-list output.
