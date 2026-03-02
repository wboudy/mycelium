# CopperHawk Deep-Read Decomposition Readiness Brief (v1)

ROLE_ACK: WORKER

Date: 2026-03-02
Spec baseline: `docs/plans/mycelium_refactor_plan_apr_round5.md` (v1.1)

## Plan: Round5 Vault Refactor Decomposition Readiness

### Context
- Prior art search (required): `cass search "mycelium refactor round5 decomposition readiness execution sequencing testability CI gates" --limit 5`
- Prior art result: none found (`No results found.`)
- Repositories/files read in full for grounding:
  - `docs/plans/mycelium_refactor_plan_apr_round5.md`
  - `AGENTS.md`
  - `README.md`
  - `ROADMAP.md`
  - `src/mycelium/*.py`
  - `src/mycelium/mcp/*.py`
  - `tests/*.py`
- Constraint snapshot from repo:
  - Runtime: Python `>=3.10` (`pyproject.toml`)
  - Active dependencies: `pyyaml`, `fastmcp`, `litellm`
  - Current implemented product surface is mission orchestration (`run/status/auto`) and 7 generic MCP tools, not vault command contracts from round5 spec.

### Architecture

#### State Machine (Vault Workflow)
States: `[source_received, extracted, compared, delta_persisted, queued_pending_review, approved, rejected, held_pending_review, promoted_canon, failed_quarantined]`
Transitions:
  `source_received` → `extracted`: `ingest` capture+extract succeeds
  `extracted` → `compared`: compare/dedupe stage succeeds
  `compared` → `delta_persisted`: delta report written (SCH-006)
  `delta_persisted` → `queued_pending_review`: queue items written (SCH-007)
  `queued_pending_review` → `approved`: `review` approve transition
  `queued_pending_review` → `rejected`: `review` reject transition
  `queued_pending_review` → `held_pending_review`: `review` hold decision metadata written
  `approved` → `promoted_canon`: `graduate` applies promotion atomically per item
  `source_received` → `failed_quarantined`: pre-extract failure
  `extracted` → `failed_quarantined`: post-extract failure with quarantine + failure-coded delta
  `held_pending_review` → `queued_pending_review`: hold TTL resurfacing path (14-day policy)
Initial: `source_received`
Terminal: `[promoted_canon, rejected, failed_quarantined]`

#### Data Flow
1. Entry: command API (`ingest`, `review`, `review_digest`, `graduate`, `context`, `frontier`).
2. Transform: normalize source -> extract bundle (SCH-008) -> compare/dedupe -> delta report (SCH-006) -> queue items (SCH-007) -> review decision records (SCH-010).
3. Exit:
   - Canonical writes only via `graduate` into Canonical Scope.
   - Durable artifacts in Draft/Derived scopes (`Inbox/`, `Reports/Delta/`, `Logs/Audit/`, `Quarantine/`).
   - Read-only retrieval outputs (`context`, `frontier`) with citations.

#### Component Boundaries
- `command_api`: envelope, flags, dispatch, error codes.
- `schema_layer`: SCH-001..SCH-010 validation and deterministic ID/time normalization hooks.
- `pipeline_core`: stage execution (`capture_extract`, `compare`, `delta_report`, `propose_queue`) with stage-scoped failures.
- `review_engine`: queue transitions, digest packets, decision records, hold TTL metadata.
- `promotion_engine`: strict validation, canonical boundary enforcement, per-item atomic promotion.
- `retrieval_engine`: context assembly and frontier scoring over canonical wikilink graph.
- `audit_security`: JSONL append-only audit and egress policy.
- `test_harness`: unit/integration/e2e/golden/perf suites + CI gates.

## Requirement Coverage Map (Spec -> Evidence -> Status -> Gap)

| Requirement / Area | Spec Evidence | Repository Evidence | Status | Gap to Close |
|---|---|---|---|---|
| Command surface must include `ingest`, `delta`, `review`, `review_digest`, `graduate`, `context`, `frontier` | `mycelium_refactor_plan_apr_round5.md` §5.2 | `src/mycelium/cli.py` only registers `run`, `status`, `auto` (`add_parser` at lines ~293/318/334) | missing | Add vault command layer and transport adapters in CLI + MCP. |
| `review` authoritative transitions (CMD-REV-001) | §5.2.3, §8.2 | No `review` implementation or error constants found (`rg` over `src/` and `tests/` returns no matches for `def review`, `ERR_QUEUE_IMMUTABLE`) | missing | Implement explicit transition engine and immutable-state guard. |
| `review_digest` packet generation (CMD-RDG-001, SCH-009) | §5.2.4, §4.2.9 | No digest packet model or command in code/tests | missing | Add digest packet model, writer, deterministic ordering mode, tests. |
| `graduate` promotion + strict/atomic semantics (CMD-GRD-001, REV-003) | §5.2.5, §8.3 | No `graduate` implementation; no canonical mutation engine | missing | Add promotion engine with per-item transactions and strict-mode gating. |
| Frontier deterministic scoring (CMD-FRN-001/002) | §5.2.7 | No `frontier` command or scoring function in `src/` or `tests/` | missing | Implement frontier index + deterministic scorer + fixture tests. |
| Context bounded retrieval with citations (CMD-CTX-001) | §5.2.6 | No `context` command in implementation/tests | missing | Implement citation-first traversal with bounded outputs. |
| Schema validators SCH-001..SCH-010 | §4.2 | Current YAML logic only reads/updates mission `progress.yaml` (`src/mycelium/mcp/server.py` `_read_progress`, `_update_progress`) | missing | Add dedicated vault schema validation module + strict/non-strict behavior. |
| Extraction bundle persistence (SCH-008) | §4.2.8 | No extraction bundle model/output path logic in code | missing | Add extract stage outputs under `Inbox/Sources/` and schema tests. |
| Delta report semantics (SCH-006, DEL-002) | §4.2.6, §7.4 | No delta report builder/validator in code/tests | missing | Implement deterministic delta report generator and novelty score checks. |
| Queue item schema/lifecycle (SCH-007, REV-001/002) | §4.2.7, §8.1/8.2 | No queue item files/state machine implementation | missing | Add queue item persistence + transition constraints + immutability checks. |
| Review decision record schema (SCH-010) | §4.2.10 | No decision record writer | missing | Add decision record persistence and validation hook in `review`. |
| Stage-scoped pipeline errors (PIPE-001/003) | §6.1 | No stage-named pipeline implementation; no stage-coded failures | missing | Add stage orchestrator with canonical stage names and error envelope. |
| Audit JSONL append-only logs (AUD-001/002) | §9.1 | No append-only audit subsystem in `src/`; tests do not cover append-only JSONL | missing | Implement audit writer with append-only validation tests. |
| Egress allow/block policy + audit (SEC-001/002) | §9.2 | No egress policy module or enforcement points | missing | Add policy config + enforcement + audit emissions. |
| Deterministic test mode + golden fixtures (TST-G-001/002) | §13.4 | No fixture harness for round5 vault outputs; current tests are smoke/unit for orchestrator+MCP | missing | Add fixture corpus, normalization strategy, deterministic mode controls. |
| Regression/perf CI gates (TST-R-001, TST-P-001, PERF-001) | §12.3, §13.5/13.6 | No benchmark suite or CI gate for p95 thresholds | missing | Add perf harness and threshold-enforced CI stage. |
| Human gate before write actions | INV-002 intent, review/promotion guardrails | Existing HITL checks for implementer writes/commands in mission tooling (`orchestrator.py` `REQUIRES_APPROVAL`, `check_hitl_approval`; `mcp/server.py` `_requires_approval`) | partial | Reuse HITL pattern but bind to vault promotion gate and queue transitions, not only role-based implementer write checks. |
| Dry-run support | IF dry-run semantics §5.1.1 | `run_agent(..., dry_run=True)` exists for prompt preview in mission orchestrator (`orchestrator.py`) | partial | Implement dry-run semantics for all write-capable vault commands with planned write manifests. |
| Strict mode behavior | IF strict semantics §5.1.2 | No strict flag semantics for vault schemas/commands | missing | Add strict toggle behavior and enforce `graduate` strict-only writes. |
| Existing tests provide baseline for current mission framework | N/A (repo baseline) | `tests/test_orchestrator.py`, `tests/test_tools.py`, `tests/test_mcp.py`, `tests/test_llm.py` cover current orchestration contracts | implemented | Keep as non-vault baseline; isolate new vault test tree to prevent regressions. |
| Spec wording defect: “Draft/Cannon boundaries” typo | §13.2 requirement text | Uses “Cannon” instead of “Canonical” in requirement prose | spec-defect | Minor spec wording fix; non-blocking for implementation. |

## Ambiguity Gate Result

Ambiguity gate result: **CONDITIONALLY READY (AMBER)**

`NO_BEAD_CREATION_DUE_TO_AMBIGUITY`

Blocking ambiguities that should be closed before bead-level decomposition:
1. Command transport precedence: whether vault contracts are CLI-first with MCP wrappers, MCP-first with CLI wrappers, or dual from day 1.
2. Vault root resolution: whether vault path is repo-root by default or an explicit `--vault` path for all commands.
3. TODO semantics in spec that affect decomposition granularity:
   - `TODO-Q-RDG-1` (digest invocation mode)
   - `TODO-Q-FRN-1` (factor derivation formulas)
   - `TODO-Q-REV-1`/`TODO-Q-REV-2` (hold resurfacing + git mode configuration)
4. Coexistence boundary with current mission orchestrator (`run/status/auto`) to avoid breaking existing workflows while introducing vault commands.

Non-blocking clarification:
- Policy decisions resolved in spec §15 (Q1..Q14) are treated as fixed unless concrete defects appear.

## File-Level Implementation Map

### Existing Files to Update
- `src/mycelium/cli.py`
  - Add vault command group and argument contracts for §5.2 commands.
- `src/mycelium/mcp/server.py`
  - Add MCP tool wrappers for vault command API and error envelope mapping.
- `src/mycelium/tools.py`
  - Extend tool schema list to include vault command calls (or introduce namespaced tool registry).
- `tests/test_mcp.py`
  - Add MCP contract tests for new vault tools.
- `tests/test_orchestrator.py`
  - Keep mission tests; add regression checks that new CLI surface does not break existing run/status/auto flows.

### New Files/Modules to Add
- `src/mycelium/vault/commands/{ingest,delta,review,review_digest,graduate,context,frontier}.py`
- `src/mycelium/vault/models/{note.py,queue_item.py,delta_report.py,extraction_bundle.py,review_packet.py,decision_record.py}.py`
- `src/mycelium/vault/schema/{validators.py,errors.py,constants.py}`
- `src/mycelium/vault/pipeline/{stages.py,canonicalize.py,dedupe.py,novelty.py}`
- `src/mycelium/vault/review/{state_machine.py,digest.py,holds.py}`
- `src/mycelium/vault/promotion/{graduate.py,atomic_apply.py}`
- `src/mycelium/vault/retrieval/{context.py,frontier.py,graph.py}`
- `src/mycelium/vault/audit/{logger.py,egress_policy.py}`
- `tests/vault/unit/*`
- `tests/vault/integration/*`
- `tests/vault/e2e/*`
- `tests/vault/fixtures/{url_basic,pdf_basic,delta_overlap_only,delta_new_and_contradict,corrupted_frontmatter,idempotency_changed_content}/*`
- `tests/vault/perf/test_perf_thresholds.py`

## Decomposition-Ready Task Clusters

### Cluster C0: Contract + Skeleton Alignment (P0)
Owner role: platform lead
Done criteria:
- Command envelope and error enum constants defined for all required §5.2 commands.
- Vault root resolution strategy documented and implemented in one place.
- No regression in existing `run/status/auto` commands.

### Cluster C1: Schema/Model Foundation (P0)
Owner role: data model + validation lead
Done criteria:
- SCH-001..SCH-010 validators implemented.
- Deterministic ID helpers and strict/non-strict validator behavior covered by unit tests.
- Validation error codes map to spec-required codes.

### Cluster C2: Ingest Pipeline + Delta (P0)
Owner role: ingestion pipeline lead
Done criteria:
- Stage chain (`capture_extract`, `compare`, `delta_report`, `propose_queue`) implemented with stage-coded failures.
- SCH-008 extraction bundle + SCH-006 delta report persisted under required paths.
- DED-001/DEL-002/CONF-001 deterministic functions covered by unit + fixture tests.

### Cluster C3: Review Queue + Digest + Decision Records (P0)
Owner role: review workflow lead
Done criteria:
- Queue item lifecycle enforces REV-002 legal transitions and immutability errors.
- `review_digest` generates per-source packets (SCH-009) deterministically in test mode.
- `review` writes SCH-010 decision record every successful invocation.

### Cluster C4: Promotion (`graduate`) + Audit (P1)
Owner role: promotion/audit lead
Done criteria:
- `graduate` enforces approved-only + strict validation + per-item atomicity.
- Canonical writes occur only via promotion path and set `status: canon`.
- AUD-001/002 append-only JSONL events emitted for ingest/review/promotion.

### Cluster C5: Retrieval (`context`, `frontier`) (P1)
Owner role: retrieval/ranking lead
Done criteria:
- `context` returns bounded, citation-backed item sets.
- `frontier` returns non-empty seeded conflicts/questions and deterministic scores/tie-breaks.
- Factor derivations for CMD-FRN-002 documented and test-covered.

### Cluster C6: Security, Perf, and CI Gating (P2)
Owner role: verification/CI lead
Done criteria:
- SEC-001/002 egress policy enforcement and audit linkage complete.
- PERF-001 thresholds wired into bench gates with reproducible metadata.
- TST-R/TST-P suites required in CI before merge.

### Dependency Graph
- `C0 -> C1 -> C2 -> C3 -> C4 -> C5 -> C6`
- Parallelizable lanes:
  - `C1` and command plumbing in `C0` can overlap after envelope constants freeze.
  - Audit infrastructure in `C4` can start in parallel with late `C3` once event schema is fixed.
  - `C6` harness scaffolding can begin after `C1`, while perf thresholds are finalized after `C5`.

## Verification Matrix (Execution/Testability Gates)

| Gate | Command | Expected Output | Artifact Path(s) |
|---|---|---|---|
| Baseline safety | `pytest tests/test_orchestrator.py tests/test_tools.py tests/test_mcp.py tests/test_llm.py -q` | Existing mission framework remains green before vault work | test stdout + junit artifact (if enabled) |
| Schema unit gate | `pytest tests/vault/unit/test_schema_validation.py -q` | SCH-001..SCH-010 pass/fail behaviors asserted | `tests/vault/unit/` |
| Ingest integration gate | `pytest tests/vault/integration/test_ingest_pipeline.py -q` | Extract->delta->queue path completes and writes required artifacts | `Inbox/Sources/`, `Reports/Delta/`, `Inbox/ReviewQueue/` |
| Review transition gate | `pytest tests/vault/integration/test_review_transitions.py -q` | Illegal transitions fail with `ERR_QUEUE_IMMUTABLE`; hold semantics preserved | `Inbox/ReviewQueue/`, `Inbox/ReviewDigest/` |
| Digest determinism gate | `pytest tests/vault/integration/test_review_digest_determinism.py -q` | Packet count/order deterministic in test mode; SCH-009 valid | `Inbox/ReviewDigest/*.yaml` |
| Promotion atomicity gate | `pytest tests/vault/integration/test_graduate_atomicity.py -q` | Per-item atomic apply enforced; strict=false rejected when not dry-run | Canonical scope note paths + audit log |
| Frontier/context gate | `pytest tests/vault/integration/test_frontier_context.py -q` | Deterministic frontier ordering/scores + bounded cited context | retrieval command outputs |
| E2E workflow gate | `pytest tests/vault/e2e/test_roundtrip_workflows.py -q` | First ingest, repeat ingest, contradiction, review, promotion pass end-to-end | fixture vault outputs + logs |
| Regression gate | `pytest tests/vault/regression -q` | Dedupe/idempotency regressions fail closed | `tests/vault/regression/` |
| Perf gate | `pytest tests/vault/perf/test_perf_thresholds.py -q` | p95 thresholds enforced per PERF-001; breach fails gate | perf report JSON/MD under `Reports/Bench/` |

## Risks and Rollback Points for Decomposition

1. Risk: Canonical corruption from premature writes.
   - Mitigation: enforce `ERR_CANON_WRITE_FORBIDDEN` outside `graduate`; write-only Draft scope pre-promotion.
   - Rollback point: end of C2 (no canonical mutations yet), revert vault modules only.
2. Risk: Queue lifecycle drift (status mutation outside `review`).
   - Mitigation: single transition service + immutable-state tests.
   - Rollback point: end of C3 before enabling production promotion.
3. Risk: Non-deterministic digests/frontier break fixture reproducibility.
   - Mitigation: deterministic mode harness + normalization helper + byte-level fixture asserts.
   - Rollback point: keep deterministic mode mandatory in CI until factor derivations stabilize.
4. Risk: Promotion partial-failure leaves inconsistent canonical/draft state.
   - Mitigation: per-item transactions; preflight validation + apply/rollback per item.
   - Rollback point: disable `graduate` apply path behind feature flag; allow dry-run only.
5. Risk: Audit logs become mutable or lossy.
   - Mitigation: append-only writer, file locking strategy, append integrity tests.
   - Rollback point: quarantine new audit writer and retain existing logs untouched.
6. Risk: Existing mission CLI regressions due to command-surface expansion.
   - Mitigation: preserve `run/status/auto` tests as required baseline gate.
   - Rollback point: split vault command group from legacy CLI entrypoint if conflicts emerge.
7. Risk: Security leakage via egress before policy is enforceable.
   - Mitigation: start report-only mode with complete audit, then enforce allowlist.
   - Rollback point: hard-disable egress command paths if policy checks fail.
8. Risk: Performance targets missed late in cycle.
   - Mitigation: add perf harness at C1/C2; trend p95 continuously.
   - Rollback point: defer non-critical retrieval enhancements (C5) until PERF-001 passes.

## Suggested First Decomposition Pass Order

### P0 (must land first)
1. C0 Contract + skeleton alignment
2. C1 Schema/model foundation
3. C2 Ingest pipeline + delta
4. C3 Review queue + digest + decision records

P0 test gate to pass before P1:
- Baseline safety + schema unit + ingest integration + review transition + digest determinism all green.

### P1 (core completion)
1. C4 Promotion + audit
2. C5 Retrieval (`context`, `frontier`)

P1 test gate:
- Promotion atomicity + frontier/context + e2e roundtrip all green.

### P2 (release hardening)
1. C6 Security/perf/CI gates

P2 test gate:
- Regression suite + perf thresholds + egress policy tests all green; no waiver unless explicitly approved.

## Dependencies
- Blocked by:
  - Command transport precedence decision (CLI-first vs MCP-first vs dual)
  - Vault root resolution decision
  - TODO closure for `TODO-Q-RDG-1`, `TODO-Q-FRN-1`, `TODO-Q-REV-1`, `TODO-Q-REV-2`
- Blocks:
  - Bead-level decomposition and swarm implementation prompts

