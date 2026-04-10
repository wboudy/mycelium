# TARGET_VISION

## 1. System Summary
Mycelium MUST become a local-first, Obsidian-native agentic knowledge vault where Markdown notes and wikilinks are the canonical knowledge substrate. The system MUST continuously ingest sources, extract structured knowledge, compute novelty/delta against existing vault knowledge, update graph connectivity, and surface the user’s knowledge frontier. Human authorship MUST remain authoritative: agents MAY propose and draft changes, but canonical notes MUST be explicitly reviewed and promoted by the human.

## 2. Core Goals
- Preserve Markdown files in an Obsidian vault as canonical source of truth (durable, local-first, no lock-in).
- Represent knowledge as a navigable graph using `[[wikilinks]]`, typed notes, frontmatter metadata, and curated MOCs.
- Ingest URLs, PDFs, DOI/arXiv citations, highlights/read-it-later items, and book notes.
- Execute a structured ingestion pipeline: capture, normalize, extract, deduplicate, delta analysis, graph linking, review/promotion.
- Produce a Delta Report per source including novelty score, new claims, reinforced/contradicted claims, new links, and follow-up questions.
- Minimize duplication by enriching existing notes/claims when overlap is high.
- Expose the “border of understanding” via frontier views: high-interest/low-clarity topics, weakly supported beliefs, conflicts, and prerequisite gaps.
- Provide command workflows over vault state: `/ingest`, `/delta`, `/frontier`, `/connect`, `/trace`, `/context`, `/ideas`, `/graduate`.
- Maintain strict provenance/attribution for imported claims.
- Improve retrieval quality so queries return linked claims/notes/sources with citations and optional deep dives.
- Include source triage (“watery vs dense”) to prioritize expected high-delta reading and skip low-value sources.

## 3. Non-Goals
- Full automation of personal thinking or replacement of the user’s voice.
- Blind “RAG over everything” without curation and structure.
- Unbounded dumping of private repositories/history into external model context windows.
- Building a public social network as the primary product.
- Silent agent writes directly to canonical notes by default.

## 4. Architectural Direction
- Architecture SHOULD be modular and pipeline-oriented with explicit stage boundaries.
- Storage boundary MUST keep canonical content as Obsidian-compatible Markdown files.
- Agent-write boundary MUST default to draft/inbox outputs; canonical mutation MUST require explicit approval/promotion.
- Provenance boundary MUST attach source identifiers (URL/DOI/book metadata) to imported claims.
- Delta engine boundary MUST compare extracted atomic claims to existing claim graph and output overlap/newness/contradictions.
- Graph update boundary MUST produce explicit link/index/MOC recommendations rather than opaque implicit changes.
- Retrieval boundary SHOULD use progressive disclosure (MOCs/indexes first, drill down selectively).
- Security boundary MUST control external LLM egress with file/folder allowlists and sanitization options.
- Audit boundary MUST preserve change logs and support git-friendly reversion.

## 5. Required Properties
### Performance
- Ingestion of a single URL/PDF SHOULD complete in minutes, not hours.
- Delta report generation MUST be included in ingestion completion.
- Retrieval commands SHOULD return actionable results in interactive latency.

### Reliability
- Ingestion MUST be idempotent for repeated identical sources.
- Pipeline failures MUST be explicit, stage-scoped, and recoverable.
- Canonical notes MUST NOT be overwritten silently.

### Security & Privacy
- System MUST be local-first by default.
- External LLM calls MUST be controllable by allowlist and sanitization policy.
- System MUST log what content is sent externally (audit trail).
- Local model mode MAY be added later.

### Scalability
- Vault growth over years MUST remain operable for ingest, dedupe, frontier analysis, and retrieval.
- Source connectors SHOULD be extensible via adapter-style ingestion inputs.

## 6. Compatibility / Migration Constraints
- Existing Markdown notes and wikilinks MUST remain readable/editable in Obsidian.
- Frontmatter conventions MUST remain human-readable and git-diff friendly.
- Schema evolution MAY add fields, but breaking metadata changes MUST include migration and rollback steps.
- Existing notes without full metadata SHOULD remain processable with explicit degraded behavior.
- Internal caches/indexes MAY be rebuilt or changed without breaking canonical Markdown compatibility.

## 7. Definition of Done
### MVP1
- Ingest URL/PDF into `/Inbox/Sources`.
- Generate source metadata, multi-resolution summary, and atomic claims.
- Perform basic dedupe against existing knowledge.
- Propose best-effort links to existing notes.
- Produce Delta Report per ingested source.

### MVP2
- Introduce stronger canonical claim representation and dedupe behavior.
- Add review queue and explicit promotion workflow (`draft -> reviewed -> canon`).
- Provide initial frontier dashboard/views.

### MVP3
- Add ranked recommendations, hub/bridge detection, and richer command workflows (`/connect`, `/trace`, `/ideas`).
- Add watery-vs-dense source triage with prioritized reading queue and skip list.

### Overall Success
- User can send a source and within minutes retrieve structured extracted knowledge, explicit delta, graph updates, and traceable provenance.
- Over time, retrieval and generation MUST reflect user-specific evolving beliefs/projects more than generic responses.

## 8. Spec Quality Requirements (No-Slop Rules)
The implementation spec MUST:
- Use explicit section hierarchy and defined terminology.
- Define invariants once and reference them; avoid repetition.
- State all requirements with normative language (`MUST`, `SHOULD`, `MAY`).
- Provide testable acceptance criteria for each `MUST` requirement.
- Define concrete interface contracts (inputs, outputs, side effects, errors).
- Define data models and schemas with required/optional fields.
- Enumerate failure modes and recovery expectations.
- Include migration strategy for any breaking schema or folder layout change.
- Include test strategy (unit, integration, end-to-end, regression, golden fixtures).
- Include explicit TODO questions where context is missing; no handwaving.
