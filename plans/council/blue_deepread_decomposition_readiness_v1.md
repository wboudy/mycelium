# ROLE_ACK: WORKER

## Plan: Mycelium Round5 Refactor Decomposition Readiness (BlueRaven)

### Context
- Prior art: `cass search "mycelium refactor round5 decomposition readiness command contracts queue promotion" --limit 5` returned no results (2026-03-02).
- Primary spec reviewed in full: `docs/plans/mycelium_refactor_plan_apr_round5.md` (v1.1, 1282 lines).
- Repository surfaces reviewed: `AGENTS.md`, `README.md`, `ROADMAP.md`, `src/mycelium/*`, `src/mycelium/mcp/*`, `tests/test_tools.py`, `tests/test_mcp.py`, `tests/test_orchestrator.py`.
- Existing components affected:
  - CLI transport: `src/mycelium/cli.py`
  - Orchestration runtime: `src/mycelium/orchestrator.py`
  - Tool schema bridge: `src/mycelium/tools.py`
  - MCP server/tool implementations: `src/mycelium/mcp/server.py`
  - Existing test harness: `tests/test_tools.py`, `tests/test_mcp.py`, `tests/test_orchestrator.py`

## Architecture

### State Machine (Queue + Promotion Integrity)
States: [source_captured, artifacts_staged, queue_pending_review, queue_approved, queue_rejected, queue_held_pending, promotion_applied_canon, failed_quarantined]
Transitions:
  source_captured -> artifacts_staged: ingest pipeline completes extract/compare/delta/propose_queue successfully
  source_captured -> failed_quarantined: stage failure with quarantine + diagnostics
  artifacts_staged -> queue_pending_review: queue item persisted with `status=pending_review`
  queue_pending_review -> queue_approved: `review` direct/digest approve path
  queue_pending_review -> queue_rejected: `review` reject path
  queue_pending_review -> queue_held_pending: `review` hold path (status stays pending_review, hold metadata recorded)
  queue_approved -> promotion_applied_canon: `graduate` strict validation passes, per-item atomic promotion succeeds
  queue_approved -> failed_quarantined: promotion validation or write failure for that item
  queue_held_pending -> queue_pending_review: hold TTL resurface event
Initial: source_captured
Terminal: [promotion_applied_canon, queue_rejected, failed_quarantined]

### Data Flow
1. Inputs enter via command surface (`ingest`, `review`, `review_digest`, `graduate`, `context`, `frontier`) with IF-001 output envelope.
2. Ingest path executes stage chain (`capture -> normalize -> fingerprint -> extract -> compare -> delta -> propose_queue`) and emits draft + durable artifacts.
3. Review path mutates queue state only through `review` and persists a decision record.
4. Promotion path (`graduate`) enforces strict schema/link checks, then writes canonical notes and audit events atomically per queue item.
5. Retrieval path (`context`, `frontier`) is read-only over canonical graph and deterministic ranking outputs.

### Component Boundaries
- `command_api` boundary:
  - Responsibility: typed command inputs/flags, IF-001 envelope, error code normalization.
  - Interface: transport-neutral service callable from CLI and MCP adapters.
- `vault_fs` boundary:
  - Responsibility: vault-root resolution, canonical/draft path policy, atomic write primitives, dry-run planner.
  - Interface: plan/apply operations over vault-relative paths.
- `schema_validation` boundary:
  - Responsibility: SCH-001..SCH-010 validators, strict/non-strict behavior.
  - Interface: validate(note/artifact, strict) -> diagnostics.
- `ingestion_pipeline` boundary:
  - Responsibility: stage execution, stage-scoped errors, idempotency index, artifact generation.
- `review_promotion` boundary:
  - Responsibility: queue state machine, packet semantics, graduate atomicity, git-mode apply.
- `retrieval_scoring` boundary:
  - Responsibility: context pack traversal, frontier scoring/tie-break determinism.
- `audit_egress` boundary:
  - Responsibility: append-only JSONL audit log, egress allow/block/sanitize policy.

## Requirement Coverage Map (Evidence-Backed)

| Requirement | Expected Contract | Repository Evidence | Status | Gap / Decomposition Implication |
|---|---|---|---|---|
| INV-001, VLT-001 | Canonical Markdown in vault layout (`Inbox/*`, `Sources/`, `Claims/`, etc.) with strict scope boundaries | Spec defines layout (`docs/plans/mycelium_refactor_plan_apr_round5.md:110-130`); repo has no such paths/symbols (`rg` search for `Inbox/Sources`, `Claims/`, `Logs/Audit` in `src/` and `tests/` returned no hits) | missing | Build vault filesystem layer and explicit scope guard first.
| INV-002 | Canonical writes only via `graduate`; forbidden direct canonical writes (`ERR_CANON_WRITE_FORBIDDEN`) | Spec contract (`docs/plans/mycelium_refactor_plan_apr_round5.md:79-84`); current `_write_file` accepts arbitrary path after HITL (`src/mycelium/mcp/server.py:285-337`) | partial | Add canonical boundary enforcement and route canonical mutation exclusively through graduate engine.
| INV-003 | Draft-first outputs for generated notes/proposals | No ingest/queue/promotion implementation in runtime (`src/mycelium/cli.py:290-376`, `src/mycelium/tools.py:21-234`) | missing | Introduce ingest pipeline artifact staging before any canonical path support.
| INV-004, SCH-003 | Provenance required on claim notes; promotion refusal when missing provenance | No claim note schema validator/promotion validator in codebase (`src/mycelium/*`, `tests/*`) | missing | Implement schema validator package before review/promotion apply.
| INV-005, IDM-001 | Idempotency on `(normalized_locator, fingerprint) -> source_id` | No source index or idempotency store symbols in runtime/tests | missing | Add deterministic identity index in `Indexes/` before ingest completion criteria.
| IF-001 | Common output envelope for all commands (`ok`, `command`, `timestamp`, `data`, `errors`, `warnings`, `trace`) | Spec envelope (`docs/plans/mycelium_refactor_plan_apr_round5.md:439-466`); current CLI/MCP return ad-hoc dicts/strings (`src/mycelium/mcp/server.py:325-336`, `384-401`; CLI prints text output) | missing | Create shared response envelope utility and adapt both CLI and MCP wrappers.
| IF-002 | Dry run for write-capable commands with planned operations | Spec (`docs/plans/mycelium_refactor_plan_apr_round5.md:468-479`); only orchestrator `run_agent(dry_run)` exists (`src/mycelium/orchestrator.py:336-342`) | partial | Implement dry-run planner in filesystem/pipeline/promotion layers.
| IF-003 | Strict mode semantics + warning downgrade for read-only paths | Spec (`docs/plans/mycelium_refactor_plan_apr_round5.md:482-488`); no strict-mode command surfaces in runtime | missing | Add strict-mode plumbing after schema validators exist.
| CMD-ING-001/002 | `ingest` command artifacts + idempotency record | `mycelium-py` only has `run/status/auto` (`src/mycelium/cli.py:290-376`); tools expose mission/fs helpers only (`src/mycelium/tools.py:25-233`) | missing | Add ingest command service and CLI/MCP adapters.
| CMD-DEL-001 | `delta` returns complete match groups + counts | No `delta` command implementation symbols in `src/` and `tests/` | missing | Add delta reader over SCH-006 artifacts.
| CMD-REV-001, REV-002 | `review` is authoritative queue state transition op; immutable enforcement (`ERR_QUEUE_IMMUTABLE`) | Spec (`docs/plans/mycelium_refactor_plan_apr_round5.md:578-610`, `978-988`); no queue state machine code/tests in repo | missing | Build queue store + transition validator prior to digest/apply.
| CMD-RDG-001, SCH-009 | reading-first digest packets grouped by Source | No packet/digest schema implementation in runtime/tests | missing | Add digest generator after queue schema support.
| CMD-GRD-001, REV-003 | `graduate` strict per-item atomic promotion + canonical status updates | Spec (`docs/plans/mycelium_refactor_plan_apr_round5.md:643-677`, `991-1001`); no graduate/promotion engine currently | missing | Implement promotion transaction layer with per-item rollback guards.
| CMD-CTX-001 | bounded context pack with citations | No `context` command surface in CLI/MCP | missing | Add retrieval module once canonical graph index exists.
| CMD-FRN-001/002 | deterministic frontier output and scoring formula | No `frontier` implementation; no ranking fixtures/tests | missing | Implement after canonical graph + conflict/question data availability.
| PIPE-001/003, EXT-001, DEL-001 | stage-scoped ingest errors, canonical stage names, extraction minima, delta generation | No stage interface module and no stage-scoped error contract in runtime | missing | Define typed stage interfaces and error model early.
| REV-001A/001B | packet workflow + constrained auto-approval policy | No policy engine for match class routing | missing | Implement policy evaluator in review/promotion subsystem.
| AUD-001/002 | append-only JSONL audit logs under `Logs/Audit/` | No audit event writer in runtime/tests; no audit file contract | missing | Implement audit append subsystem before egress and graduate completion.
| SEC-001..SEC-004 | egress allowlist/blocklist/sanitization and mode transitions | No egress policy engine in runtime/tests | missing | Build egress middleware with explicit mode state + audit integration.
| MVP1-001 | end-to-end ingest/review digest/auto-lane/provenance gate bundle | Milestone defined (`docs/plans/mycelium_refactor_plan_apr_round5.md:1121-1139`); runtime currently mission-orchestration only (`README.md:3-13`, `src/mycelium/cli.py`) | missing | Requires net-new vault subsystem.
| MVP2-001 | queue lifecycle + graduate + frontier/context stability | Milestone defined (`docs/plans/mycelium_refactor_plan_apr_round5.md:1140-1148`) with no corresponding implementation symbols | missing | Dependency on completion of MVP1 foundation + retrieval layer.
| TST-U/I/E2E/G/R/P | layered fixture-driven test strategy including deterministic mode and perf p95 thresholds | Existing tests validate 7 mission tools/orchestrator only (`tests/test_mcp.py:1-543`, `tests/test_tools.py:1-192`, `tests/test_orchestrator.py:1-283`) | partial | Add dedicated vault test suite and benchmark harness; preserve existing tests as legacy lane.
| Contract gap: vault root binding | Commands are vault-relative but spec lacks one normative command-context contract for vault root binding | Paths are consistently “vault-relative” in spec (`docs/plans/mycelium_refactor_plan_apr_round5.md:108-130`, `471-474`) without explicit binding field | spec-defect | Add explicit contract patch before decomposition finalization: every command invocation must include or inherit `vault_root` context.

## Ambiguity Gate Result
- Result: **CONDITIONAL PASS** (decomposition can proceed for foundation lanes, but implementation start should wait on unresolved contract decisions below).
- Blocking ambiguities for safe decomposition:
  - `vault_root` binding is implicit across all vault-relative contracts; this is underspecified for CLI/MCP transport parity.
  - TODO-Q-FRN-1 leaves frontier factor derivations undefined (`docs/plans/mycelium_refactor_plan_apr_round5.md:745`), which blocks deterministic frontier implementation details.
  - TODO-Q-REV-1 leaves hold TTL storage/resurface mechanism unresolved (`docs/plans/mycelium_refactor_plan_apr_round5.md:958`), impacting queue resurfacing scheduler boundaries.
  - TODO-Q-SEC-1 leaves egress mode storage/burn-in tracking unresolved (`docs/plans/mycelium_refactor_plan_apr_round5.md:1086`), impacting deploy-safe policy transitions.
- Policy from AGENTS gate: **NO_BEAD_CREATION_DUE_TO_AMBIGUITY** until these decisions are ratified or explicit defaults are accepted.

## Decomposition-Ready Task Clusters (Dependency Ordered)

### Cluster 1: Contract Surface and Runtime Split
- Scope:
  - Introduce transport-neutral command service interfaces for `ingest|delta|review|review_digest|graduate|context|frontier`.
  - Define unified IF-001 envelope builder and error taxonomy.
  - Preserve existing `run|status|auto` mission orchestration path behind legacy namespace.
- Primary files:
  - Add: `src/mycelium/vault/commands.py`, `src/mycelium/vault/envelope.py`, `src/mycelium/vault/errors.py`
  - Update: `src/mycelium/cli.py`, `src/mycelium/mcp/server.py`
- Done criteria:
  - CLI/MCP can invoke command stubs and return IF-001 envelope with deterministic error codes.

### Cluster 2: Vault Filesystem + Schema Validation Core
- Scope:
  - Implement vault root resolver, canonical/draft boundary guard, atomic writer, dry-run operation planner.
  - Implement SCH-001..SCH-010 validators with strict/non-strict diagnostics.
- Primary files:
  - Add: `src/mycelium/vault/fs.py`, `src/mycelium/vault/schemas/*.py`, `src/mycelium/vault/validators.py`
  - Add tests: `tests/vault/test_fs_boundaries.py`, `tests/vault/test_schema_validation.py`
- Done criteria:
  - Boundary tests prove canonical writes blocked outside graduate path.
  - Validator fixtures cover required schema failures and warnings.

### Cluster 3: Ingestion Pipeline + Idempotency + Delta Artifacts
- Scope:
  - Implement stage chain (`capture|normalize|fingerprint|extract|compare|delta|propose_queue`) with stage-scoped failure reporting.
  - Persist Extraction Bundle, Delta Report, queue items in draft scope.
  - Build idempotency index under `Indexes/`.
- Primary files:
  - Add: `src/mycelium/vault/ingest_pipeline.py`, `src/mycelium/vault/idempotency.py`, `src/mycelium/vault/delta.py`
  - Add tests: `tests/vault/test_ingest_pipeline.py`, `tests/vault/test_idempotency.py`
- Done criteria:
  - CMD-ING-001/002, DEL-001, PIPE-001/003 acceptance checks pass for URL/PDF fixtures.

### Cluster 4: Review Queue + Digest + Decision Record
- Scope:
  - Implement queue lifecycle constraints and immutable transition checks.
  - Implement `review_digest` packet generation and `review` direct/digest decision application.
  - Persist SCH-009 packet artifacts and SCH-010 decision records.
- Primary files:
  - Add: `src/mycelium/vault/review_queue.py`, `src/mycelium/vault/review_digest.py`, `src/mycelium/vault/review_apply.py`
  - Add tests: `tests/vault/test_review_transitions.py`, `tests/vault/test_review_digest.py`
- Done criteria:
  - Illegal transitions return `ERR_QUEUE_IMMUTABLE`.
  - Deterministic digest reproduction passes in deterministic test mode.

### Cluster 5: Promotion/Graduate Engine + Git Mode
- Scope:
  - Implement `graduate` per-item atomic promotion, strict validation gate, canonical status updates, and audit targets.
  - Add optional git-mode commit batching per Source packet.
- Primary files:
  - Add: `src/mycelium/vault/graduation.py`, `src/mycelium/vault/git_mode.py`
  - Add tests: `tests/vault/test_graduate_atomicity.py`, `tests/vault/test_git_mode.py`
- Done criteria:
  - AC-CMD-GRD-001 and AC-REV-003 pass; canonical writes happen only via graduate path.

### Cluster 6: Retrieval Layer (`context`, `frontier`) Deterministic Outputs
- Scope:
  - Build canonical graph traversal and bounded context pack retrieval.
  - Implement frontier score engine with deterministic tie-breaks once factor derivation decision is fixed.
- Primary files:
  - Add: `src/mycelium/vault/context_service.py`, `src/mycelium/vault/frontier_service.py`
  - Add tests: `tests/vault/test_context.py`, `tests/vault/test_frontier_determinism.py`
- Done criteria:
  - CMD-CTX-001 and CMD-FRN-001/002 acceptance tests pass on seeded fixtures.

### Cluster 7: Audit, Egress Policy, Performance + Lint Gates
- Scope:
  - Implement append-only audit JSONL writer and egress policy engine.
  - Add performance harness for PERF-001 p95 targets.
  - Add spec-lint checks for LINT-001..LINT-004 and migration/rollback test hooks.
- Primary files:
  - Add: `src/mycelium/vault/audit.py`, `src/mycelium/vault/egress.py`, `scripts/bench_vault.py`, `scripts/spec_lint.py`
  - Add tests: `tests/vault/test_audit.py`, `tests/vault/test_egress.py`, `tests/vault/test_perf_targets.py`
- Done criteria:
  - Security/audit and perf gates produce reproducible artifacts and fail closed on violations.

## Dependency Graph and Parallelization
- Graph:
  - C1 -> C2 -> C3 -> C4 -> C5
  - C2 -> C6
  - C3 -> C6
  - C5 -> C7
  - C6 -> C7
- Parallel lanes:
  - Lane A (contracts/foundation): C1 + C2 sequential, then handoff.
  - Lane B (ingest/review): C3 and C4 (C4 starts once queue artifacts exist from C3).
  - Lane C (promotion): C5 after C4.
  - Lane D (retrieval): C6 starts after C2+C3 stable artifacts are available.
  - Lane E (governance): C7 once C5/C6 outputs stabilize.

## Risks and Rollback Points for Decomposition
- Risk: Current runtime is mission-orchestrator centric (`README.md:3-13`, `src/mycelium/cli.py:290-376`) and may regress if vault commands are bolted into same entrypoints.
  - Mitigation: dual-surface architecture (legacy namespace + vault namespace) until vault acceptance suite is green.
  - Rollback point: feature-flag disable vault CLI/MCP bindings while retaining core modules.
- Risk: Canonical boundary corruption via generic write tool path (`src/mycelium/mcp/server.py:318-325`).
  - Mitigation: centralize all file writes through `vault/fs.py` policy gate, deny canonical writes outside graduate.
  - Rollback point: lock canonical scope read-only and replay from draft artifacts.
- Risk: Frontier determinism blocked by unresolved factor derivations (TODO-Q-FRN-1).
  - Mitigation: freeze explicit interim factor derivation contract before implementation.
  - Rollback point: ship `context` only, hold `frontier` behind experimental flag.
- Risk: Hold/resurface semantics ambiguous (TODO-Q-REV-1), causing non-deterministic queue behavior.
  - Mitigation: formalize TTL storage schema and resurface trigger contract before C4 completion.
  - Rollback point: disable hold action in production profile; allow approve/reject only.
- Risk: Egress policy mode/burn-in tracking unresolved (TODO-Q-SEC-1).
  - Mitigation: keep `report_only` default with explicit config checkpoint and audit event on transition.
  - Rollback point: force `report_only` and block enforce-mode transitions.
- Risk: Existing test suite gives false confidence because it covers only 7 mission tools (`tests/test_mcp.py`, `tests/test_tools.py`).
  - Mitigation: create dedicated `tests/vault/` acceptance matrix mapped to requirement IDs.
  - Rollback point: do not deprecate legacy tests; enforce both suites in CI.

## Suggested First Decomposition Pass Order
1. Resolve ambiguity gate items (vault_root binding + frontier factors + hold TTL storage + egress mode storage).
2. Execute C1 contract surface with strict IF-001 envelope compliance and legacy runtime isolation.
3. Execute C2 filesystem/schema core and freeze schema validator APIs.
4. Execute C3 ingest/idempotency and prove artifact correctness on golden fixtures.
5. Execute C4 review/digest transitions and enforce immutable queue state rules.
6. Execute C5 graduate atomicity and canonical write gate.
7. Execute C6 retrieval (`context` then `frontier`) and C7 governance/perf/lint gates.

## Validation Notes Collected During Deep-Read
- Test execution evidence:
  - `PYTHONPATH=src pytest -q tests/test_tools.py tests/test_mcp.py tests/test_orchestrator.py` => `70 passed`.
  - This confirms baseline mission tooling stability, not Round5 vault spec compliance.
- Known environment caveat:
  - Shell locale warnings (`LC_ALL: cannot change locale`) observed; non-blocking for decomposition planning.

## Dependencies
- Blocked by:
  - Explicit resolution of ambiguity gate items listed above.
- Blocks:
  - Safe bead decomposition and implementation swarm kickoff.
