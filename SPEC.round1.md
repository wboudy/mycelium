# Mycelium Agentic Knowledge Vault Specification
Version: Round 1 Canonical Draft
Status: Draft

## 1. Glossary
| Term | Definition |
|---|---|
| Vault | The Obsidian-compatible directory containing canonical Markdown notes and supporting metadata. |
| Canonical Note | A human-approved durable note with `status: canon`. |
| Draft Note | Agent-generated or provisional note pending review (`status: draft`). |
| Reviewed Note | Human-reviewed note approved for promotion (`status: reviewed`). |
| Source Note | Note representing an external artifact (URL, PDF, DOI/arXiv, book/highlight bundle). |
| Claim | Atomic, falsifiable assertion extracted from sources or authored by the user. |
| Claim Note | Note whose primary content is one atomic claim and its provenance/support/links. |
| Concept Note | Note defining a concept, term, or entity with contextual links. |
| Question Note | Note capturing an open problem, uncertainty, or research question. |
| MOC | Map of Content; curated index note linking related concepts/claims/sources. |
| Delta | Difference between newly ingested knowledge and current vault knowledge. |
| Delta Report | Structured artifact describing novelty, overlap, reinforcement, contradiction, and graph changes for one ingestion event. |
| Frontier | Areas of high interest with low clarity/support or unresolved conflicts. |
| Promotion | Controlled transition from draft/reviewed artifacts into canonical notes. |
| Provenance | Trace metadata linking a claim/note to source identifiers (URL/DOI/book metadata/etc.). |
| Ingestion Job | End-to-end processing unit for one source input. |

## 2. Goals
- Build a local-first, durable, no-lock-in personal knowledge system based on Obsidian Markdown.
- Convert raw sources into structured, linked, attributable knowledge rather than static summaries.
- Make novelty explicit through per-source delta accounting.
- Keep human authorship authoritative and prevent agent-generated canon drift.
- Improve retrieval, synthesis, and idea generation using graph structure and provenance.
- Expose understanding gaps via frontier views and prioritized next-reading suggestions.

## 3. Non-Goals
- Autonomous replacement of user reasoning or writing voice.
- Uncurated full-vault RAG that ignores structure and provenance.
- Public social networking functionality.
- Mandatory cloud-first processing.
- Direct default agent writes to canonical notes.

## 4. Scope
### 4.1 In Scope
- Source ingestion for URL/PDF/DOI/arXiv and highlight/book-note style text bundles.
- Structured extraction: gist, bullets, atomic claims, definitions, entities.
- Claim dedupe and delta reporting.
- Link and MOC recommendation updates.
- Review queue and promotion workflow.
- Frontier views and high-level recommendation output.

### 4.2 Out of Scope for Initial Delivery
- Email/meeting transcript ingestion.
- Multi-user collaboration and social publishing.
- Full automated canon mutation without review.

## 5. Personas and Primary Use Cases
| Persona | Primary Need | Key Commands/Flows |
|---|---|---|
| Knowledge Owner (primary user) | Rapidly ingest important sources while preserving quality and voice | `/ingest`, `/delta`, `/graduate`, `/frontier` |
| Research Explorer | Find what is new, uncertain, and high leverage to read next | `/frontier`, `/connect`, `/ideas` |
| Project Builder | Pull accurate context and trace decisions over time | `/context`, `/trace` |

### 5.1 Mandatory Use Cases
- Ingest source and obtain structured notes plus delta report.
- Navigate from a question to relevant claims, concepts, and sources with citations.
- Identify frontier areas with weak support/conflicts/open questions.
- Promote high-quality drafts into canonical notes with explicit human approval.

## 6. System Architecture (High-Level)
| Component | Responsibility | Inputs | Outputs |
|---|---|---|---|
| Ingestion Adapter Layer | Capture source content and metadata by input type | URL/PDF/DOI/text bundle | Normalized source payload |
| Normalizer | Convert content into clean Markdown-ready representation | Raw payload | Normalized sections |
| Extractor | Produce gist, key points, atomic claims, definitions, entities | Normalized sections | Structured extraction artifacts |
| Claim Comparator | Compare extracted claims to vault claims for overlap/novelty/conflict | Extracted claims + claim index | Match sets + conflict flags |
| Delta Engine | Compute novelty, reinforcement, contradiction, and graph changes | Comparator output + vault state | Delta report |
| Linker/Graph Updater | Propose wikilinks, MOC updates, related-note recommendations | Extraction + delta + existing graph | Link/update proposals |
| Review Queue Manager | Stage artifacts for human approval and promotion | Draft outputs | Review queue items |
| Promotion Manager | Apply approved transitions to canonical notes | Approved queue items | Canon updates + audit entries |
| Retrieval/Context Builder | Provide question-driven, citation-backed context packs | Query + vault state | Ranked note/claim/source bundle |
| Frontier Analyzer | Surface weak/conflicted/shallow areas and high-leverage targets | Claim/support graph + questions | Frontier views |
| Audit Logger | Record ingestion actions, changes, and external-send events | Pipeline events | Append-only logs |

## 7. Functional Requirements
### 7.1 Requirement Table
| ID | Requirement | Acceptance Criteria |
|---|---|---|
| FR-001 | The system MUST treat vault Markdown files as canonical source of truth. | AC-FR-001-1: No canonical data required for core operation is stored only in opaque binary stores. AC-FR-001-2: Canonical note content remains readable in Obsidian without proprietary tooling. |
| FR-002 | The system MUST ingest URL and PDF sources into `/Inbox/Sources`. | AC-FR-002-1: Given a valid URL input, one source note is created in `/Inbox/Sources`. AC-FR-002-2: Given a valid PDF input, one source note is created in `/Inbox/Sources`. |
| FR-003 | The system MUST capture source metadata including identifier, title (if available), capture timestamp, and source type. | AC-FR-003-1: Each source note frontmatter includes required metadata keys. AC-FR-003-2: Missing title is explicitly marked as unknown, not silently omitted. |
| FR-004 | The system MUST generate multi-resolution extraction artifacts for each ingested source. | AC-FR-004-1: Output includes a one-paragraph gist. AC-FR-004-2: Output includes key bullet points. AC-FR-004-3: Output includes atomic claims list. |
| FR-005 | The system MUST assign provenance to each imported claim. | AC-FR-005-1: Every extracted claim record contains a source reference. AC-FR-005-2: Validation fails if imported claim lacks provenance. |
| FR-006 | The system MUST compute and persist a Delta Report per ingestion job. | AC-FR-006-1: Delta report file exists for each completed ingestion. AC-FR-006-2: Report includes novelty summary, overlap summary, and connection changes. |
| FR-007 | The system MUST perform deduplication against existing claims before creating new claim notes. | AC-FR-007-1: Re-ingesting a source with identical claims does not create duplicate canonical claim notes. AC-FR-007-2: Dedupe decision is recorded in delta report. |
| FR-008 | The system MUST propose wikilink and MOC updates after ingestion. | AC-FR-008-1: At least one link proposal list is generated per ingestion when matches exist. AC-FR-008-2: MOC recommendations are generated for affected domains. |
| FR-009 | The system MUST enforce review-before-canon by default. | AC-FR-009-1: Agent-created notes default to `status: draft`. AC-FR-009-2: Canonical note updates require explicit promotion action. |
| FR-010 | The system MUST support a `/graduate` workflow that promotes approved drafts to canonical notes. | AC-FR-010-1: Promotion changes note status from `draft/reviewed` to `canon`. AC-FR-010-2: Promotion event is logged with timestamp and changed files. |
| FR-011 | The system MUST provide `/delta <source>` output showing new, overlapping, reinforced, and contradicted claims. | AC-FR-011-1: Command returns sections for new/overlap/reinforced/contradicted. AC-FR-011-2: Output references source identifiers and note links. |
| FR-012 | The system MUST provide `/frontier` output identifying low-clarity/high-interest areas. | AC-FR-012-1: Output includes open questions and weakly supported beliefs. AC-FR-012-2: Output includes prioritized reading targets. |
| FR-013 | The system MUST provide `/context` output that compiles a context pack from selected vault references without loading the entire vault. | AC-FR-013-1: Output includes ranked references and citations. AC-FR-013-2: Retrieval trace indicates which indexes/MOCs were traversed first. |
| FR-014 | The system SHOULD provide `/trace`, `/connect`, and `/ideas` workflows based on graph structure and deltas. | AC-FR-014-1: Each command returns at least one structured proposal/result block. AC-FR-014-2: Results include citation links to supporting notes/sources. |
| FR-015 | The system SHOULD include source triage scoring for signal density, credibility, redundancy, and watery-vs-dense heuristics. | AC-FR-015-1: Triage output includes per-source score breakdown. AC-FR-015-2: Output includes prioritized queue and skip list. |

## 8. Non-Functional Requirements
| ID | Requirement | Acceptance Criteria |
|---|---|---|
| NFR-001 | The system MUST be local-first, with canonical storage on local filesystem. | AC-NFR-001-1: Canonical notes remain available offline. AC-NFR-001-2: Core read/navigation functions run without network. |
| NFR-002 | The system MUST provide explicit controls over what content can be sent to external LLM providers. | AC-NFR-002-1: Configurable allowlist is enforced before send. AC-NFR-002-2: Blocked paths are rejected with explicit error. |
| NFR-003 | The system MUST produce an audit trail for ingestion, promotion, and external-send events. | AC-NFR-003-1: Each event includes timestamp, actor, operation, and affected files. AC-NFR-003-2: Log entries are append-only. |
| NFR-004 | Ingestion SHOULD complete in interactive time for single-source jobs. | AC-NFR-004-1: URL/PDF ingest median duration is measurable and reported. AC-NFR-004-2: Timeouts are surfaced with retry guidance. |
| NFR-005 | The system MUST be idempotent for repeated identical ingestion input. | AC-NFR-005-1: Re-run with same source identifier does not create duplicate source notes. AC-NFR-005-2: Delta report marks run as duplicate/low-delta. |
| NFR-006 | The system MUST remain git-friendly and reversible. | AC-NFR-006-1: All canonical changes are text diffs in repository files. AC-NFR-006-2: Reverting last promotion restores previous canonical state. |
| NFR-007 | The system SHOULD scale to long-lived vault growth without full-vault loading for each query. | AC-NFR-007-1: Retrieval path logs show selective traversal. AC-NFR-007-2: Query execution remains bounded by configured limits. |

## 9. Data Model (Initial)
### 9.1 Note Types
| Type | Purpose | Required Fields |
|---|---|---|
| `source` | External artifact record | `type`, `id`, `source_ref`, `captured_at`, `status` |
| `claim` | Atomic assertion | `type`, `id`, `claim_text`, `provenance`, `confidence`, `status` |
| `concept` | Definition/context node | `type`, `id`, `term`, `status` |
| `question` | Open issue/frontier item | `type`, `id`, `question`, `status` |
| `project` | Work context and decisions | `type`, `id`, `project_name`, `status` |
| `moc` | Navigation hub | `type`, `id`, `scope`, `status` |

### 9.2 Shared Frontmatter Keys
| Key | Type | Requirement | Notes |
|---|---|---|---|
| `type` | enum | MUST | `source|claim|concept|question|project|moc` |
| `id` | string | MUST | Stable unique identifier |
| `created` | datetime | MUST | ISO-8601 UTC |
| `updated` | datetime | MUST | ISO-8601 UTC |
| `status` | enum | MUST | `draft|reviewed|canon` |
| `tags` | list[string] | SHOULD | User/domain tags |
| `source_ref` | string | MUST for imported content | URL/DOI/arXiv/book reference |
| `confidence` | number | SHOULD | 0.0-1.0 scale |

### 9.3 Delta Report (Initial Fields)
| Field | Requirement | Description |
|---|---|---|
| `source_id` | MUST | Ingested source identifier |
| `run_id` | MUST | Ingestion job id |
| `novelty_summary` | MUST | Human-readable novelty synopsis |
| `novelty_score` | MUST | Quantified newness score |
| `new_claims` | MUST | Claims not represented previously |
| `overlapping_claims` | MUST | Claims matching existing knowledge |
| `reinforced_claims` | MUST | Existing claims with added support |
| `contradicted_claims` | MUST | Existing claims with opposing evidence |
| `new_links` | MUST | Proposed new graph edges |
| `follow_up_questions` | SHOULD | Suggested inquiry gaps |

## 10. Interfaces (Initial)
### 10.1 Command Surface
| Command | Input | Output | Side Effects |
|---|---|---|---|
| `/ingest <url\|pdf\|id>` | Source locator | Source note + extraction + delta report + link proposals | Writes to inbox/draft locations |
| `/delta <source>` | Source id/path | Delta report view | None |
| `/frontier` | Optional filters | Frontier topics + weak beliefs + reading targets | None |
| `/context` | Optional scope/goal | Ranked context pack with citations | None |
| `/graduate` | Optional queue selection | Promotion result summary | Updates statuses and canonical notes |
| `/trace <idea>` | Idea/topic id | Evolution timeline with linked notes | None |
| `/connect <domainA> <domainB>` | Two domain/topic refs | Bridge-note/link proposals | Draft proposal creation |
| `/ideas` | Optional focus | Idea candidates grounded in vault clusters/deltas | Draft idea outputs |

### 10.2 File Layout (Initial)
| Path | Purpose |
|---|---|
| `/Inbox/Sources/` | New source captures and extraction drafts |
| `/Inbox/ReviewQueue/` | Pending review/promotion items |
| `/Claims/` | Claim notes |
| `/Concepts/` | Concept notes |
| `/Questions/` | Question notes |
| `/Projects/` | Project notes |
| `/MOCs/` | Curated map-of-content notes |
| `/Reports/Delta/` | Delta report history |
| `/Logs/Audit/` | Audit logs |

## 11. Governance and Control Model
| Rule ID | Rule | Acceptance Criteria |
|---|---|---|
| GOV-001 | Human owner MUST remain final authority over canonical content. | AC-GOV-001-1: No automatic canonical write occurs without explicit promotion action. |
| GOV-002 | Agents MUST write to drafts/inbox by default. | AC-GOV-002-1: New agent-created artifacts default to `status: draft` and inbox path. |
| GOV-003 | Imported claims MUST include provenance before canon eligibility. | AC-GOV-003-1: Promotion validator rejects claims lacking provenance metadata. |
| GOV-004 | Change history MUST be auditable and reversible. | AC-GOV-004-1: Ingestion/promotion logs are persisted and reference changed files. |

## 12. Risks and Explicit TODO Questions
### 12.1 Risks
- Claim granularity inconsistency may reduce dedupe quality.
- Over-linking may produce noisy graph navigation.
- Under-specified confidence scoring may produce misleading frontier signals.
- External LLM egress may leak sensitive content without strict guards.

### 12.2 TODO Questions (Blocking Clarifications)
- TODO-Q1: What is the required default confidence scale and calibration policy for claims?
- TODO-Q2: What unique-id strategy should be canonical for notes and claims (slug, hash, hybrid)?
- TODO-Q3: What minimum metadata is required for book/highlight imports when source identifiers are incomplete?
- TODO-Q4: What user interaction model is preferred for review queue approvals (CLI prompts, file-based checklist, UI plugin)?
- TODO-Q5: What threshold defines “high novelty” versus “low novelty” for triage and queue ordering?

## 13. Initial Acceptance Criteria by Milestone
### 13.1 MVP1 Acceptance Criteria
- URL/PDF ingestion produces source note, extraction artifacts, and delta report.
- Basic dedupe prevents obvious duplicate claims.
- Link proposals reference existing notes when relevant.
- All imported claims include provenance references.

### 13.2 MVP2 Acceptance Criteria
- Review queue supports explicit promotion to canonical notes.
- Canonical claim representation is used in dedupe and delta reporting.
- Frontier output lists open questions and weakly supported beliefs.

### 13.3 MVP3 Acceptance Criteria
- Recommendations include ranked reading targets and bridge/hub-style connections.
- `/connect`, `/trace`, and `/ideas` return citation-backed outputs.
- Source triage produces prioritized queue and skip list with score breakdown.
