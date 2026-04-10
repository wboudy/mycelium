# CopperHawk Review: Execution + Testability Audit

Date: 2026-03-01  
Reviewer: CopperHawk  
Primary spec audited: `mycelium-apr-spec/docs/plans/mycelium_refactor_plan_apr_round5.md`

## 1) Scope and Evidence Method

This review ignores the base-prompt `forecasting_engine/` and `event_scraper/` scope per override and audits feasibility/testability against the actual repository implementation in `mycelium/`.

Evidence sources used:
- Spec requirements/milestones: `mycelium-apr-spec/docs/plans/mycelium_refactor_plan_apr_round5.md` (requirements at lines 57-778).
- Runtime implementation: `mycelium/src/mycelium/cli.py`, `orchestrator.py`, `llm.py`, `tools.py`, `mcp/server.py`.
- Tests: `mycelium/tests/test_mcp.py`, `test_tools.py`, `test_orchestrator.py`, `test_llm.py`.
- Current-state docs: `mycelium-apr-spec/CURRENT_STATE.md`, `README.md`, `ROADMAP.md`, `WORKFLOW.md`.

Repository fact baseline:
- Current command surface is mission orchestration (`run`, `status`, `auto`), not vault ingestion (`ingest`, `delta`, `graduate`, `context`, `frontier`) (`mycelium/src/mycelium/cli.py:278-389`).
- Current MCP/tool surface is 7 mission/filesystem tools only (`read_progress`, `update_progress`, `list_files`, `read_file`, `write_file`, `run_command`, `search_codebase`) (`mycelium/src/mycelium/tools.py:21-234`, `mycelium/src/mycelium/mcp/server.py:495-626`).
- No vault-domain symbols (`ingest`, `graduate`, `source_id`, `normalized_locator`, `fingerprint`, `novelty_score`, `Quarantine`) are implemented in `mycelium/src` or `mycelium/tests` (repo-wide `rg` check).

Validation commands run:
- `cd mycelium && PYTHONPATH=src pytest -q` -> `86 passed`.
- `cd mycelium && pytest -q` -> collection failure (`ModuleNotFoundError: mycelium`).
- `cd mycelium && ruff check src tests` -> fails (large style/import debt, line-length issues).

## 2) Requirement Traceability Matrix (Execution/Testability Focus)

Status legend: `implemented` | `partial` | `missing` | `unclear`

| Requirement | Repo evidence | Status | Gap and exact implementation location |
|---|---|---|---|
| INV-001/INV-002/INV-003 + VLT-001 (draft/canon boundaries + promotion gate) | No canonical vault directory abstraction; existing writes target arbitrary filesystem paths via `_write_file` (`mycelium/src/mycelium/mcp/server.py:285-337`) | missing | Add `mycelium/src/mycelium/vault/layout.py` (`VaultPaths`, boundary guards) and `mycelium/src/mycelium/vault/promotion.py` (`promote_items`, canon-write guard with `ERR_CANON_WRITE_FORBIDDEN`) |
| INV-004 + SCH-003 (provenance required) | No claim/source schema validators in runtime/tests | missing | Add `mycelium/src/mycelium/vault/schema.py` and `mycelium/src/mycelium/vault/validators.py`; add provenance checks in promotion path |
| INV-005 + IDM-001 (idempotent source identity) | No source identity index or `(locator,fingerprint)->source_id` map | missing | Add `mycelium/src/mycelium/vault/idempotency.py` and durable index file `Indexes/source_identity.yaml` managed by `storage.py` |
| SCH-001..SCH-007 (note/report/queue schemas) | No vault note model code; tests only cover mission/mcp tooling (`mycelium/tests/test_*.py`) | missing | Add schema models and validation suite: `mycelium/src/mycelium/vault/models.py`, `schema.py`; tests in `mycelium/tests/vault/test_schema.py` |
| NAM-001 + LNK-001 (id alignment + wikilink strict mode) | No link-checker or filename/id validator | missing | Add `mycelium/src/mycelium/vault/linkcheck.py` and validator hooks in `promotion.py` |
| IF-001 (uniform command output envelope) | Current commands/tools return heterogeneous dicts (`_run_command`, `_write_file`, etc.) (`mycelium/src/mycelium/mcp/server.py:339-401`) | missing | Add `mycelium/src/mycelium/vault/envelope.py` with typed `CommandEnvelope`; enforce in CLI+MCP adapters |
| IF-002 (dry-run with planned writes) | Dry-run exists for orchestrator prompt only (`run_agent(..., dry_run=True)`) (`mycelium/src/mycelium/orchestrator.py:336-343`) | partial | Extend dry-run contract to every write-capable vault command in `vault/commands.py` with `data.planned_writes` |
| CMD-ING-001 (`ingest`) | No ingest command in CLI/MCP/tool schemas (`mycelium/src/mycelium/cli.py:290-377`, `tools.py:21-234`) | missing | Add command entrypoints in `cli.py`, `mcp/server.py`, and `tools.py`; core logic in `vault/commands.py::ingest` |
| CMD-DEL-001 (`delta`) | No delta command | missing | Add `vault/commands.py::delta` and command adapters in CLI/MCP/tools |
| CMD-GRD-001 (`graduate`) | No review queue lifecycle or graduate command | missing | Add `vault/review_queue.py`, `vault/promotion.py`, `vault/commands.py::graduate` |
| CMD-CTX-001 (`context`) | Existing “context” appears only as prompt context, not retrieval command (`mycelium/src/mycelium/orchestrator.py:147-175`) | missing | Add `vault/context.py` retrieval engine + `commands.py::context` |
| CMD-FRN-001 (`frontier`) | No frontier command or ranking | missing | Add `vault/frontier.py` + `commands.py::frontier` |
| PIPE-001 + PIPE-002 + EXT-001 (stage chain + staged atomicity + minimum extraction outputs) | No ingestion pipeline modules/stage errors | missing | Add stage modules under `mycelium/src/mycelium/vault/pipeline/` (`capture.py`, `normalize.py`, `fingerprint.py`, `extract.py`, `compare.py`, `delta.py`, `queue.py`) |
| DEL-001 + DED-001/2/3 + DEL-002 (dedupe/match/novelty) | No comparator/canonicalizer/novelty engine | missing | Add `vault/dedupe.py` and `vault/delta_engine.py`; tests in `tests/vault/test_dedupe.py` |
| REV-001 + REV-002 (queue generation + promotion semantics) | No queue item persistence/state machine | missing | Add `vault/review_queue.py` state machine and strict transition checks (`ERR_QUEUE_IMMUTABLE`) |
| AUD-001 (append-only audit logs) | Current logging writes aggregate usage into mission YAML, not append-only audit stream (`mycelium/src/mycelium/orchestrator.py:184-234`) | partial | Add `vault/audit.py` line-appender under `Logs/Audit/` and emit ingest/promotion events |
| SEC-001 + SEC-002 (egress policy and auditability) | No egress allowlist/blocklist sanitization layer | missing | Add `vault/egress_policy.py` + policy config file + audit hook integration |
| ERR-001 + ERR-002 (stage-scoped recoverability + quarantine) | No quarantine artifact path/diagnostic sidecars | missing | Add `vault/quarantine.py` and explicit stage error mapping in `pipeline/executor.py` |
| MIG-001 + MIG-002 (git-friendly notes + migration/rollback) | No migration framework for vault schema evolution | unclear | Add `mycelium/src/mycelium/vault/migrations/` with `apply.py`, `rollback.py`, fixtures in `tests/vault/migrations/` |
| MVP1-001 (URL/PDF ingest + dedupe + queue + promotion gate) | Not present in runtime or tests | missing | Implement via P0/P1 tasks below |
| MVP2-001 (queue lifecycle + graduate + frontier) | Not present in runtime or tests | missing | Implement via P2 tasks below |
| TST-U-001/TST-I-001/TST-E2E-001/TST-G-001/TST-G-002/TST-R-001 | Tests exist but for mission orchestration domain only (`mycelium/tests/test_mcp.py`, `test_tools.py`, etc.) | partial | Create vault test tree (`tests/vault/unit`, `integration`, `e2e`, `fixtures`, `regression`) and deterministic harness utilities |
| LINT-001..LINT-004 (spec lint) | No spec-lint utility in repo | missing | Add `mycelium/scripts/spec_lint.py` and CI target `make spec-lint` |

Coverage summary from audit:
- `implemented`: 0
- `partial`: 4
- `missing`: 17
- `unclear`: 1

## 3) Command-Contract Feasibility Assessment

### 3.1 Current feasibility

- Round-5 command set is **not feasible in current shape** because the command substrate does not exist.
- Existing command stack is mission orchestration + generic filesystem shell tools, with no vault-domain storage model.
- The only reusable parts are infrastructure patterns:
  - CLI argument plumbing (`mycelium/src/mycelium/cli.py`).
  - MCP tool decorator/export pattern (`mycelium/src/mycelium/mcp/server.py`).
  - LLM tool schema registration (`mycelium/src/mycelium/tools.py`).

### 3.2 Contract defects that must be fixed first

1. No standard envelope (`IF-001`) across command surfaces.
2. No typed error-code taxonomy for stage-scoped failures (`PIPE-001`, `ERR-001`).
3. No dry-run write plan contract for write-capable commands (`IF-002`).
4. No explicit command parity contract between CLI and MCP paths.

### 3.3 Contract-first corrective design

Add a single command core with adapters:
- Core: `mycelium/src/mycelium/vault/commands.py`
- Envelope: `mycelium/src/mycelium/vault/envelope.py`
- CLI adapter: `mycelium/src/mycelium/cli.py` (`ingest`, `delta`, `graduate`, `context`, `frontier`)
- MCP adapter: `mycelium/src/mycelium/mcp/server.py` tool exports for same commands
- Tool schema adapter: `mycelium/src/mycelium/tools.py` schemas + dispatch entries

Rule: adapters are thin; all logic and validation in core to prevent contract drift.

## 4) Missing Acceptance Criteria and Ownership Ambiguity

## 4.1 Missing/weak acceptance criteria to add

1. **Deterministic ID contract**: specify `run_id`, `queue_id`, and `source_id` format + deterministic test-mode behavior.
2. **Queue state machine contract**: enumerate legal transitions (`pending_review -> approved/rejected`) and explicit no-op semantics.
3. **Frontier ranking determinism**: tie-break rules for equal score.
4. **Audit log format**: require line-delimited JSON schema and append verification method.
5. **Egress defaults**: define baseline allowlist/blocklist patterns and redaction rules (currently TODO only).
6. **Migration gate**: require pre/post migration hash manifest for canonical notes.
7. **Release gate contract**: exact CI jobs that block merge for MVP1 and MVP2.

## 4.2 Ownership gaps

Current spec names requirements but not accountable owners. Assign explicit ownership per stream:
- `Platform Owner`: command envelope, adapter parity, CLI/MCP compatibility.
- `Data Model Owner`: schemas, note IDs, link resolution, migration policy.
- `Ingestion Owner`: capture/normalize/extract/idempotency/dedupe pipeline.
- `Security Owner`: egress policy and audit evidence controls.
- `QA Owner`: fixtures, deterministic mode, regression gate maintenance.
- `Release Owner`: milestone go/no-go decisions and rollback execution.

## 5) Revised Implementation Plan (Dependency-Ordered, Parallel Lanes)

## 5.1 P0/P1/P2 Prioritized Order

- **P0**: command substrate + schemas + deterministic test harness (prerequisite for all milestones).
- **P1**: MVP1 ingest/delta pipeline with idempotency and dedupe.
- **P2**: MVP2 review/promotion/frontier + security/audit hardening.

## 5.2 Atomic task graph

| Task ID | Priority | Depends on | Owner | Parallel lane | Deliverable | Done criteria |
|---|---|---|---|---|---|---|
| T0.1 | P0 | none | Platform | Lane A | `vault/envelope.py` + error code enum | All new vault commands return IF-001 envelope in unit tests |
| T0.2 | P0 | none | Data Model | Lane B | `vault/layout.py`, `vault/models.py`, `vault/schema.py`, `vault/validators.py` | SCH-001..SCH-007 validator tests passing |
| T0.3 | P0 | none | QA | Lane C | deterministic test harness (`tests/vault/conftest.py`) + fixture scaffolds | TST-G-002 baseline test passing |
| T0.4 | P0 | T0.1 | Platform | Lane A | CLI/MCP/tool adapters wired for placeholder vault commands | `--help` and MCP tool registry include 5 new command names |
| T0.5 | P0 | T0.1,T0.2 | QA | Lane C | CI bootstrap for vault test targets | CI job runs `tests/vault/unit` green |
| T1.1 | P1 | T0.2 | Ingestion | Lane D | pipeline stages capture/normalize/fingerprint | Stage interfaces implemented; stage-scoped errors asserted |
| T1.2 | P1 | T1.1 | Ingestion | Lane D | idempotency index + source revision tracking | repeated-ingest fixture reuses `source_id`; changed-content captures `prior_fingerprint` |
| T1.3 | P1 | T1.1 | Ingestion | Lane E | extractor minimum outputs | `gist`, `bullets`, and claims/warnings behavior verified |
| T1.4 | P1 | T1.3 | Ingestion | Lane E | dedupe comparator + novelty scoring | DED-001/2/3 + DEL-002 unit tests passing |
| T1.5 | P1 | T1.2,T1.4 | Ingestion | Lane D | delta report writer (`Reports/Delta/`) | DEL-001 checks pass for all fixture classes |
| T1.6 | P1 | T1.4 | Data Model | Lane B | review queue generator (`Inbox/ReviewQueue/`) | REV-001 checks persisted for each canonical-impacting proposal |
| T1.7 | P1 | T1.5,T1.6,T0.4 | Platform | Lane A | `ingest` + `delta` command implementations (CLI/MCP/tools) | CMD-ING-001 + CMD-DEL-001 contract tests passing |
| T1.8 | P1 | T1.7 | QA | Lane C | MVP1 e2e fixtures (`url_basic`, `pdf_basic`, overlap/new+contradict`) | AC-MVP1-001-1/2 passing end-to-end |
| T2.1 | P2 | T1.6 | Data Model | Lane B | queue lifecycle transition engine | invalid transitions return `ERR_QUEUE_IMMUTABLE` |
| T2.2 | P2 | T2.1 | Platform | Lane A | `graduate` with per-item atomicity + canon status updates | CMD-GRD-001 + REV-002 integration tests passing |
| T2.3 | P2 | T1.5 | Ingestion | Lane E | `context` + `frontier` engines | CMD-CTX-001 + CMD-FRN-001 tests passing with seeded fixture |
| T2.4 | P2 | T1.7 | Security | Lane F | append-only audit logger + egress policy enforcement | AUD-001 + SEC-001/002 tests passing |
| T2.5 | P2 | T1.1 | Ingestion | Lane D | quarantine behavior and recovery handling | ERR-001 + ERR-002 induced-failure tests passing |
| T2.6 | P2 | T0.2 | Data Model | Lane B | migration/rollback framework | MIG-002 migration+rollback fixture tests passing |
| T2.7 | P2 | T2.2,T2.3,T2.4,T2.5,T2.6 | QA/Release | Lane C | full regression/golden suite + release gate | TST-I/E2E/G/R gates all green for MVP2 |

Milestone done criteria:
- **P0 done**: contract substrate and schema validators in place; deterministic harness exists; command adapters compile and expose new command names.
- **P1 done (MVP1)**: ingest+delta complete with idempotency/dedupe/delta reports/queue generation and URL+PDF e2e fixtures green.
- **P2 done (MVP2)**: graduate/review lifecycle/frontier complete; audit+egress+quarantine+migration gates green.

## 6) Verification Matrix (Commands, Expected Output, Artifacts)

| Gate | Command | Expected output | Artifact path |
|---|---|---|---|
| Baseline sanity | `cd mycelium && PYTHONPATH=src pytest -q` | all existing tests pass (`86 passed` baseline) | `mycelium/tests/` |
| Packaging hygiene (current blocker) | `cd mycelium && pytest -q` | currently fails import collection; must pass before release | N/A (collection phase) |
| Lint hygiene (current blocker) | `cd mycelium && ruff check src tests` | currently fails; must be green by end of P0 | N/A |
| P0 schema gate | `cd mycelium && PYTHONPATH=src pytest -q tests/vault/unit/test_schema.py` | SCH-001..SCH-007 validators green | `mycelium/tests/vault/unit/test_schema.py` |
| P0 contract envelope gate | `cd mycelium && PYTHONPATH=src pytest -q tests/vault/unit/test_envelope.py` | all command handlers conform to IF-001 envelope keys | `mycelium/tests/vault/unit/test_envelope.py` |
| P1 ingest dry-run gate | `cd mycelium && PYTHONPATH=src python -m mycelium.cli ingest --url fixtures/url_basic.html --dry-run` | `ok=true`, `data.planned_writes` non-empty, no filesystem diff | temp vault under `mycelium/tests/tmp/vault/` |
| P1 idempotency gate | `cd mycelium && PYTHONPATH=src pytest -q tests/vault/integration/test_idempotency.py` | second identical ingest reuses `source_id`; changed content records `prior_fingerprint` | `Indexes/source_identity.yaml`, `Reports/Delta/*.yaml` |
| P1 delta correctness gate | `cd mycelium && PYTHONPATH=src pytest -q tests/vault/integration/test_delta_report.py` | counts equal sum(match groups), novelty score formula exact | `Reports/Delta/<run_id>.yaml` |
| P2 queue immutability gate | `cd mycelium && PYTHONPATH=src pytest -q tests/vault/integration/test_review_queue.py` | invalid transitions fail with `ERR_QUEUE_IMMUTABLE` | `Inbox/ReviewQueue/*.yaml` |
| P2 graduate atomicity gate | `cd mycelium && PYTHONPATH=src pytest -q tests/vault/integration/test_graduate.py` | per-item atomic promotion; canon statuses and paths correct | `Claims/`, `Sources/`, audit log |
| P2 frontier/context gate | `cd mycelium && PYTHONPATH=src pytest -q tests/vault/e2e/test_frontier_context.py` | seeded contradictions/questions produce non-empty conflicts/open_questions with citations | e2e fixture vault output |
| P2 security/audit gate | `cd mycelium && PYTHONPATH=src pytest -q tests/vault/integration/test_audit_egress.py` | blocklisted egress fails with `ERR_EGRESS_POLICY_BLOCK` and emits audit event | `Logs/Audit/*.jsonl` |
| P2 migration rollback gate | `cd mycelium && PYTHONPATH=src pytest -q tests/vault/migrations/test_rollback.py` | rollback restores canonical notes byte-for-byte | migration fixture snapshots |
| Final release gate | `cd mycelium && PYTHONPATH=src pytest -q tests/vault && ruff check src tests` | all vault + legacy tests pass and lint clean | CI artifacts + junit/logs |

## 7) Risk Register, Mitigations, and Rollback Plan

| Risk | Impact | Trigger signal | Mitigation | Rollback point |
|---|---|---|---|---|
| R1: Spec/runtime scope mismatch (vault vs mission tooling) | schedule slip and architectural churn | adapter code starts duplicating logic across CLI/MCP/tools | isolate vault in new `mycelium.vault` package; keep legacy orchestration untouched | RP0: after T0.4, disable new commands behind feature flag |
| R2: Contract drift between CLI and MCP | inconsistent behavior and test flake | same command passes in one surface, fails in another | single core command implementation with thin adapters only | RP1: revert adapter wiring while preserving core unit tests |
| R3: Non-deterministic fixtures | unstable CI and blocked releases | golden tests fail intermittently on timestamps/IDs | deterministic mode with fixed clock/ID generator and output normalizer | RP0: gate merge on deterministic fixture repeatability |
| R4: Promotion boundary bugs | accidental canonical mutation | diffs under canonical dirs during ingest failures | enforce canon guard in shared storage layer + failure injection tests | RP2: emergency disable `graduate` command, keep draft-only mode |
| R5: Egress policy under-specified | data leakage | outbound payload includes blocklisted paths | explicit default deny policy + allowlist exceptions + audit digest | RP2: hard-disable egress (`MYCELIUM_EGRESS_ENABLED=0`) |
| R6: Test debt in existing repo (import/lint blockers) | CI noise masks vault regressions | `pytest -q` and `ruff check` remain red | fix packaging invocation and lint debt as P0 exit criteria | RP0: no milestone advancement until hygiene gates pass |

Rollback strategy by milestone:
- **RP0 (after P0)**: keep new command flags off by default; no canonical writes possible.
- **RP1 (after P1)**: if ingest regressions appear, disable `ingest/delta` adapters and preserve generated fixtures for debugging.
- **RP2 (after P2)**: if promotion/security regressions appear, run in draft-only mode (`graduate` disabled), retaining audit trail and queue artifacts.

## 8) Cross-Plan Conflict Resolution (Explicit)

Conflict A:
- Round-5 spec defines a vault ingestion product.
- Current code/docs define mission-orchestration tooling.

Resolution:
- Treat vault system as a **new bounded subsystem** (`mycelium.vault`) instead of refactoring mission orchestrator in place.
- Keep legacy commands (`run/status/auto`) stable while MVP1/MVP2 vault commands ship in parallel.

Conflict B:
- `ROADMAP.md` marks MCP server as Phase-2 future work.
- MCP server already exists with 7 tools (`mycelium/src/mycelium/mcp/server.py`).

Resolution:
- Update roadmap narrative to “MCP v1 exists; MCP v2 expands to vault command contracts.”

Conflict C:
- `README.md` and `WORKFLOW.md` describe behaviors (e.g., `model:deep` routing, beads-first state) not present in audited runtime code.

Resolution:
- Add doc-contract tests (or lint checks) that fail when docs claim unsupported runtime features.

## 9) Final Feasibility Verdict

- **MVP1 feasibility**: achievable only after P0 substrate work; not feasible as a direct extension of current command set.
- **MVP2 feasibility**: feasible after MVP1 stabilization plus dedicated ownership for queue/promotion/security.
- **Critical prerequisite**: enforce packaging and lint/test gates first so milestone test gates are trustworthy.

