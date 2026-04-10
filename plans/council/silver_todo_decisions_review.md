# SilverDune Council Review: TODO-Q1..Q6 Decisions (APR Round 5)

## Scope and Method
- Scope followed the council override: `mycelium-apr-spec/docs/plans/mycelium_refactor_plan_apr_round5.md` as primary spec.
- Repository evidence was validated against current implementation/docs in `mycelium-apr-spec/src`, `mycelium-apr-spec/tests`, `mycelium-apr-spec/CURRENT_STATE.md`, and `mycelium-apr-spec/SPEC.round5.md`.
- This memo is planning/review only and proposes explicit product decisions for TODO-Q1..Q6.

## Key Repository Evidence (for implementation reality)
- Primary unresolved TODOs are explicitly listed in the round-5 refactor plan at `docs/plans/mycelium_refactor_plan_apr_round5.md:784-789`.
- MVP scope dependencies:
  - MVP1 requires ingest URL/PDF, dedupe, review proposals, provenance gate (`docs/plans/mycelium_refactor_plan_apr_round5.md:671-680`).
  - MVP2 requires review queue lifecycle + `graduate` + frontier (`docs/plans/mycelium_refactor_plan_apr_round5.md:683-690`).
- Current implementation is orchestration tooling, not vault ingestion:
  - CLI commands are `run/status/auto` only (`src/mycelium/cli.py:6-8`, command parser at `src/mycelium/cli.py:363-447`).
  - MCP/tools expose 7 workflow tools (`src/mycelium/tools.py:23-236`, `src/mycelium/mcp/server.py:5-11`, `tests/test_tools.py:37`).
  - No ingestion/delta/graduate/frontier implementation in `src` (keyword scan across `src`/`tests` shows no such symbols; current tests focus on orchestration + MCP tool behavior).
  - System baseline confirms this gap (`CURRENT_STATE.md:4`, `CURRENT_STATE.md:14-15`, `CURRENT_STATE.md:30`, `CURRENT_STATE.md:91`).

## Cross-Plan Conflict Resolution
1. **TODO numbering/content drift across docs**
- Conflict:
  - In the primary refactor plan, TODO-Q1 is **ID strategy** and TODO-Q3 is **confidence** (`docs/plans/mycelium_refactor_plan_apr_round5.md:784-786`).
  - In `SPEC.round5.md`, TODO-Q1 is **confidence** and TODO-Q2 is **ID strategy** (`SPEC.round5.md:527-529`).
- Decision:
  - Treat the primary refactor plan (`docs/plans/...round5.md`) as authoritative for TODO numbering and closure order.
- Rationale:
  - Council override explicitly selected this file as the primary spec.

2. **Egress defaults: previously suggested vs unresolved in primary plan**
- Conflict:
  - `SPEC.round5.md` already contains broad default allowlist/blocklist examples (`SPEC.round5.md:437-444`), while primary plan keeps policy unresolved under TODO-Q5 / TODO-Q-SEC-1 (`docs/plans/...round5.md:635`, `788`).
- Decision:
  - Promote the prior broad defaults into explicit, testable policy with stricter pattern-level controls (below under TODO-Q5), and use primary plan as decision authority.

3. **Novelty threshold location drift**
- Conflict:
  - Older `SPEC.round5.md` TODO-Q5 asks novelty threshold buckets (`SPEC.round5.md:531`), but primary TODO-Q5 is egress policy and novelty formula is already specified as DEL-002 in primary plan (`docs/plans/...round5.md:579-584`).
- Decision:
  - Keep novelty thresholds out of TODO-Q5 for this round; treat triage buckets as future work aligned with MVP3 TODOs (`docs/plans/...round5.md:693-696`).

## TODO Decisions

### TODO-Q1: Canonical ID Strategy for Notes
**Decision**
- Adopt **slug+hash hybrid as canonical** for machine-generated notes.
- Canonical ID format:
  - `id = <slug>--h-<12hex>` (12 hex chars from stable SHA-256 digest prefix).
- Human-authored/manual notes MAY remain slug-only initially, but all ingestion-generated `source`/`claim` notes MUST use hybrid IDs.

**Rationale**
- NAM-001 currently allows either slug or hash (`docs/plans/...round5.md:252`), but does not resolve collision policy.
- Obsidian readability and git-diff usability favor retaining semantic slugs.
- Dedupe/idempotency requirements need strong collision resistance for repeated/large-scale ingestion (`docs/plans/...round5.md:538-542`, `671-680`).

**Tradeoffs**
- Pros:
  - Human-readable wikilinks remain usable.
  - Deterministic collision resistance without opaque-only IDs.
  - Easier debugging than hash-only IDs.
- Cons:
  - Slightly longer filenames/links.
  - Requires deterministic slug normalization and hash-input contract governance.

**Implementation Complexity Impact**
- **Medium**.
- New work items:
  - Add ID generation utility and regex validator for hybrid format.
  - Add migration/compat support for existing slug-only notes.
  - Ensure deterministic mode (goldens) normalizes ID generation behavior (`docs/plans/...round5.md:742-746`).

**MVP Gate**
- **Must decide before MVP1**: **Yes**.
- Why: MVP1 requires ingest/idempotency artifacts and file naming consistency (`docs/plans/...round5.md:671-680`).

---

### TODO-Q2: Minimum Provenance Locator Granularity by Source Kind
**Decision**
- Make `provenance.locator` an object with required per-kind minimum fields:

| Source Kind | Required Locator Minimum |
|---|---|
| `url` | `{ url, section_heading?, paragraph_start, paragraph_end, quote_hash }` |
| `pdf` | `{ file_ref, page_start, page_end, block_index?, quote_hash }` |
| `doi`/`arxiv` | `{ identifier, section_heading?, paragraph_start?, page_start?, quote_hash }` |
| `highlights` | `{ source_ref, highlight_id, local_position, quote_hash }` |
| `book` | `{ title, edition?, chapter?, page_or_loc, quote_hash }` |
| `text_bundle` | `{ bundle_id, doc_id, chunk_id, char_start?, char_end?, quote_hash }` |

- `quote_hash` = deterministic hash of normalized excerpt text used as locator integrity anchor.
- If extractor cannot meet minimum granularity, ingestion must emit validation warning and block canon promotion for affected claims until human review confirms locator quality.

**Rationale**
- Provenance is required for claims (`docs/plans/...round5.md:161-172`, `81-82`).
- Current schema allows string-or-object locator but not minimum granularity by source kind.
- MVP1 scope is URL/PDF ingest (`docs/plans/...round5.md:671-676`), so URL/PDF locator quality must be concrete now.

**Tradeoffs**
- Pros:
  - Higher traceability and review trust.
  - Better repeatability for contradiction/verification workflows.
  - Improves promotion gate quality.
- Cons:
  - Added extraction complexity, especially for noisy HTML/PDF.
  - Some sources will require fallback/coarse locators + manual intervention.

**Implementation Complexity Impact**
- **High** for extraction adapters; **Medium** for validation.
- New work items:
  - Source-kind-specific locator builders in normalization/extraction stages.
  - Schema validator updates + queue checks (`provenance_present` is already required conceptually, `docs/plans/...round5.md:592`).

**MVP Gate**
- **Must decide before MVP1**: **Partially yes**.
- URL/PDF minima: **must be final before MVP1**.
- Non-MVP1 source kinds (`doi/arxiv/highlights/book/text_bundle`) can be detailed now but implemented by MVP2+.

---

### TODO-Q3: Confidence Calibration Rubric per Domain
**Decision**
- Introduce a deterministic confidence rubric:
  - Score range `[0.0..1.0]` remains schema-valid (`docs/plans/...round5.md:130,135`).
  - Confidence computed from weighted factors:
    - `evidence_quality` (quote fidelity + locator precision)
    - `source_reliability` (domain-specific source tier)
    - `corroboration` (supporting vs contradicting counts)
    - `recency_fit` (for time-sensitive domains)
- Domain profiles:
  - `scientific`, `engineering/docs`, `news/market`, `personal-notes` each have explicit weight vector.
- Promotion rule:
  - Confidence is advisory in MVP1.
  - In MVP2, low-confidence contradiction/new claims must be auto-flagged for review queue priority.

**Rationale**
- Confidence is currently optional and unconstrained beyond numeric range (`docs/plans/...round5.md:130,135`).
- Frontier/ranking quality degrades without calibration consistency; risk is already identified in prior spec lineage (`SPEC.round5.md:523`).
- Current codebase has no claim-confidence implementation, so rubric must be simple/deterministic first.

**Tradeoffs**
- Pros:
  - Better prioritization signal for review/frontier.
  - Deterministic and testable behavior.
- Cons:
  - Weight tuning risk and domain subjectivity.
  - Potential false precision early on.

**Implementation Complexity Impact**
- **Medium**.
- New work items:
  - Confidence computation module + domain config.
  - Unit tests with fixed fixtures for deterministic outputs.

**MVP Gate**
- **Must decide before MVP1**: **No** (advisory field only).
- **Must decide before MVP2**: **Yes**, because frontier quality and queue prioritization depend on calibration consistency.

---

### TODO-Q4: Authoritative Review UX for Promotion Decisions
**Decision**
- Authoritative approval path is **command/API level** (`graduate`), with optional UI clients.
- UX policy:
  - CLI/MCP `graduate` is the **source of truth** for transition execution.
  - Obsidian plugin is a client surface (MVP2/MVP3) that submits approvals into same command contract; it is not a separate authority.
- Approval recording contract:
  - Every approval/rejection persists to queue item state plus audit event including `actor`, `timestamp`, `queue_id`, `decision`, and `reason`.

**Rationale**
- Promotion semantics already defined at command level (`docs/plans/...round5.md:383-413`, `596-603`).
- Current product runtime is CLI + MCP tooling (`src/mycelium/cli.py`, `src/mycelium/mcp/server.py`, `pyproject.toml:20`) with no plugin implementation.
- This avoids dual authority and race conditions.

**Tradeoffs**
- Pros:
  - Single decision authority and deterministic audits.
  - Plugin can be added later without changing governance semantics.
- Cons:
  - Pure CLI may feel less ergonomic to non-terminal users until plugin matures.

**Implementation Complexity Impact**
- **Medium**.
- New work items:
  - Queue state transition layer and immutable decision log.
  - Actor identity plumbing for audit fields.

**MVP Gate**
- **Must decide before MVP1**: **Yes (authority model)**.
- **Full plugin UX can wait**: MVP2/MVP3.

---

### TODO-Q5: Default Egress Allowlist/Blocklist + Sanitization
**Decision**
- Adopt strict default-deny egress with explicit allowlist and structured redaction:

**Allowlist (default):**
- `Inbox/Sources/**`
- `Inbox/ReviewQueue/**`
- `Reports/Delta/**`
- Explicitly selected canonical files for a user-approved command invocation only.

**Blocklist (default):**
- `Logs/Audit/**`
- `Indexes/**`
- `Quarantine/**`
- `.git/**`, `.env*`, `**/*secret*`, `**/*token*`, `**/*.pem`, `**/*.key`, `**/id_rsa*`, credentials/config files by policy regex.
- Wildcard whole-vault egress unless elevated explicit approval.

**Sanitization levels:**
- `none` (explicit override only)
- `standard` (default): redact emails, phone numbers, API-key/token patterns, auth headers, obvious PII.
- `strict`: `standard` + redact local absolute paths and organization identifiers configured by policy.

**Audit requirements for every egress attempt:**
- decision (`blocked`/`sent`), destination, bytes, file list, payload digest, sanitization mode, redaction counts, reason/context.

**Rationale**
- SEC-001/SEC-002 explicitly require allow/block checks and outbound evidence (`docs/plans/...round5.md:623-633`).
- TODO-Q-SEC-1 leaves this undefined (`docs/plans/...round5.md:635`).
- Prior spec round contains broad defaults (`SPEC.round5.md:437-444`), but not complete pattern-level policy.

**Tradeoffs**
- Pros:
  - Strong leakage reduction for early releases.
  - Deterministic policy decisions for tests and audits.
- Cons:
  - More initial false blocks and operator friction.
  - Needs override workflow for valid exceptional cases.

**Implementation Complexity Impact**
- **Medium-High**.
- New work items:
  - Path policy engine + regex matcher + sanitization pipeline + audit enrichment.
  - Policy fixtures and integration tests for blocked/allowed/redacted cases.

**MVP Gate**
- **Must decide before MVP1**: **Yes** (external extraction/LLM interactions create immediate policy risk).

---

### TODO-Q6: Performance Targets + Measurement Strategy
**Decision**
- Define explicit initial SLO-style targets for MVP1/MVP2 on reference hardware (document exact machine profile in benchmark metadata):

**MVP1 targets (URL/PDF ingest + dedupe/delta):**
- `ingest(url_basic)` p95 ≤ **20s**, p99 ≤ **30s**.
- `ingest(pdf_basic<=10 pages)` p95 ≤ **35s**, p99 ≤ **50s**.
- `delta report generation` after extraction p95 ≤ **2s**.
- Peak RSS for single ingestion run ≤ **1.5 GB**.

**MVP2 retrieval targets:**
- `context(limit=20)` p95 ≤ **1.5s** on seeded fixture.
- `frontier(limit=20)` p95 ≤ **2.5s** on seeded contradiction/question fixture.

**Measurement policy:**
- Add deterministic benchmark harness using golden fixtures and fixed nondeterminism controls (`docs/plans/...round5.md:742-746`).
- Emit benchmark artifact JSON per run under `Reports/Benchmarks/<date>/<run_id>.json`.
- CI performance guardrail: fail if p95 regresses >20% against rolling baseline for same fixture class.

**Rationale**
- Primary plan requires numeric targets but currently leaves them undefined (`docs/plans/...round5.md:789`).
- Target vision says user should get useful outputs “within minutes” (`TARGET_VISION.md:83`), which needs concrete engineering bounds.
- Current codebase has no ingestion/retrieval engine, so benchmark expectations must be explicit from the start.

**Tradeoffs**
- Pros:
  - Clear go/no-go quality gates.
  - Makes performance regressions visible early.
- Cons:
  - Early thresholds may need recalibration once real extraction providers are integrated.
  - Requires fixture discipline to avoid noisy measurements.

**Implementation Complexity Impact**
- **Medium** for harness + CI integration; **High** if targets are enforced before architecture stabilizes.

**MVP Gate**
- **Must decide before MVP1**: **Yes for ingest/delta targets**.
- **Can defer retrieval threshold enforcement to MVP2**: yes, but thresholds should be predeclared now.

## MVP Gating Summary

| TODO | Decision Needed Before MVP1? | Can Wait to MVP2/MVP3? | Notes |
|---|---|---|---|
| Q1 ID strategy | **Yes** | Migration refinements can continue in MVP2 | Required for deterministic naming/idempotency |
| Q2 provenance granularity | **Yes (URL/PDF minimum)** | Other source kinds to MVP2+ | MVP1 ingest scope is URL/PDF |
| Q3 confidence rubric | No (advisory-only in MVP1) | **Yes, must finalize by MVP2** | Frontier/review prioritization quality depends on it |
| Q4 review UX authority | **Yes (single authority model)** | Plugin UX can wait to MVP2/MVP3 | Avoids dual-authority governance |
| Q5 egress policy | **Yes** | Policy tuning can continue | Security-critical from first external calls |
| Q6 performance targets | **Yes (ingest/delta)** | Retrieval enforcement to MVP2 | “Within minutes” needs measurable gates |

## Recommended Immediate Closure Order (Product)
1. Close Q1 + Q2(URL/PDF subset) together (shared schema + deterministic ID/provenance contract).
2. Close Q5 next (security-critical, blocks safe external integration).
3. Close Q4 authority model and audit decision record format (unblocks coherent `graduate` lifecycle work).
4. Close Q6 baseline ingest/delta targets and benchmark artifact schema.
5. Close Q3 before frontier prioritization in MVP2.

## Net Effect on Implementation Complexity
- Overall impact: **medium-high**, mainly because current codebase is orchestration-only and vault ingestion subsystems are still unimplemented.
- Complexity drivers:
  - New schema and deterministic identity/provenance engines.
  - New policy engines (egress + sanitization + audit evidence).
  - New benchmark/test infrastructure with deterministic fixture controls.
