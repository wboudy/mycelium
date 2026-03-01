# BlueRaven Merge Master Plan v1 (Copper + Silver)

Date: 2026-03-01  
Merge lead: BlueRaven  
Output target: `/Users/will/Developer/mycelium/mycelium-apr-spec/plans/council/blue_merge_copper_silver_v1.md`

## 0) Inputs, Method, and Evidence

### 0.1 Inputs read in full
- `plans/council/copper_execution_testability_review.md` (215 lines)
- `plans/council/silver_todo_decisions_review.md` (304 lines)
- `plans/council/council_merged_recommendations.md` (115 lines)
- Source of truth: `docs/plans/mycelium_refactor_plan_apr_round5.md` (789 lines)

### 0.2 Repository evidence validated
Primary runtime and tests were validated in `mycelium-apr-spec`:
- CLI surface: `src/mycelium/cli.py:349-459`
- MCP/tool surface: `src/mycelium/tools.py:21-234`, `src/mycelium/mcp/server.py:1-701`
- Existing state baseline: `CURRENT_STATE.md:4-15`, `CURRENT_STATE.md:57-63`, `CURRENT_STATE.md:116-119`
- Current tests: `tests/test_mcp.py`, `tests/test_tools.py`, `tests/test_orchestrator.py`, `tests/test_llm.py`, `tests/test_cli.py`

Validation commands executed:
- `cd mycelium-apr-spec && PYTHONPATH=src pytest -q` -> `146 passed`
- `cd mycelium-apr-spec && pytest -q` -> import collection failure (`ModuleNotFoundError: mycelium`)
- `cd mycelium-apr-spec && ruff check src tests` -> fails (`Found 459 errors`)

## 1) Major-Claim Validation (from Copper/Silver/Council)

| Claim | Evidence | Verdict |
|---|---|---|
| Runtime is orchestration-focused, not vault-ingestion | `CURRENT_STATE.md:4-15`, `src/mycelium/cli.py:349-459`, `src/mycelium/tools.py:21-234` | Confirmed |
| CLI command surface is `run/status/auto` | `src/mycelium/cli.py:363-447` | Confirmed |
| MCP/tool surface is 7 tools | `src/mycelium/tools.py:21-234`, `tests/test_tools.py:36-38`, `src/mycelium/mcp/server.py:1-11` | Confirmed |
| No vault command symbols implemented (`ingest/delta/graduate/frontier`) | Symbol scan over `src`/`tests` found no matches for these interfaces | Confirmed |
| Canonical write boundaries are not enforced | `src/mycelium/mcp/server.py:385-392` writes arbitrary `file_path` with no vault/canon guard | Confirmed |
| Test baseline exists but env-sensitive | `PYTHONPATH=src pytest -q` passes; plain `pytest -q` fails import collection | Confirmed |
| Lint debt is release-relevant | `ruff check src tests` -> 459 findings | Confirmed |
| Roadmap text lags runtime reality for MCP status | `ROADMAP.md:116-147` frames MCP as unimplemented while runtime MCP server exists (`src/mycelium/mcp/server.py`) | Confirmed |
| TODO-Q1..Q6 unresolved in source-of-truth spec | `docs/plans/mycelium_refactor_plan_apr_round5.md:784-789` | Confirmed |

## 2) Conflict Resolution Ledger (explicit)

| Conflict ID | Conflict | Sources | Resolution | Rationale |
|---|---|---|---|---|
| CR-01 | Vault spec scope vs current orchestration runtime | Spec round5 vs `src/mycelium/*` | Implement vault as a new bounded subsystem (`mycelium.vault`) with thin CLI/MCP adapters | Avoid destabilizing existing orchestration workflow while delivering spec scope |
| CR-02 | Roadmap says MCP future, runtime already has MCP server | `ROADMAP.md:116-147` vs `src/mycelium/mcp/server.py:1-701` | Treat current MCP as v1; roadmap should describe v2 expansion to vault contracts | Prevent planning against stale assumptions |
| CR-03 | Security timing mismatch: Copper places egress hardening in later phase; Silver requires early decision | Copper §5/§7 vs Silver TODO-Q5 | Split into: S0 policy decision + P1 minimum enforcement + P2 full hardening | Balances MVP velocity with security obligations |
| CR-04 | Silver proposes concrete TODO decisions; council override requires non-mandatory options | Silver TODO sections + override | Keep Q1..Q6 as ranked options with recommended defaults; require human decision gate | Honors override and avoids freezing policy unilaterally |
| CR-05 | Spec contract defects block decomposition | Round5 lines `227`, `247`, `388`, `514`, `596`, `773` etc | Add S0 spec-patch gate before implementation decomposition | Prevent building against contradictory contracts |

## 3) Requirement Traceability Matrix (execution-focused)

Status legend: `implemented` | `partial` | `missing` | `unclear`

| Requirement(s) | Source-of-truth ref | Repo evidence | Status | Gap / implementation target |
|---|---|---|---|---|
| INV-001, INV-002, VLT-001 (canonical boundaries + promotion gate) | `57-68`, `110-114` | `src/mycelium/mcp/server.py:385-392`, `src/mycelium/cli.py:363-447` | missing | Add vault path boundary layer and canon-write guard in `src/mycelium/vault/layout.py` + `promotion.py` |
| INV-003 + IF-002 (draft-first outputs + dry-run write plans) | `71-76`, `298-303` | Dry-run exists only for orchestrator prompt path (`src/mycelium/cli.py:382-385`, `src/mycelium/orchestrator.py:516-523`) | partial | Add write-capable dry-run contract with `data.planned_writes` for vault commands |
| INV-004 + SCH-003 (provenance required) | `77-83`, `154-173` | No claim schema/promotion engine in runtime | missing | Add claim/source models and provenance validators in `src/mycelium/vault/schema.py` and `validators.py` |
| INV-005 + IDM-001 (idempotent source identity) | `84-89`, `538-543` | No source identity index module | missing | Add `src/mycelium/vault/idempotency.py` + durable index under `Indexes/` |
| SCH-001..SCH-005 (note schemas) | `120-187` | No vault note schema module | missing | Add schema models/validators + unit fixtures |
| SCH-006 (delta report schema) | `191-229` | No delta-report writer/validator | missing | Add `src/mycelium/vault/delta_engine.py` + report validator |
| SCH-007 (review queue schema) | `234-249` | No queue persistence/state machine | missing | Add `src/mycelium/vault/review_queue.py` |
| NAM-001 + LNK-001 (id naming and link resolution) | `252-263` | No link checker / note-id alignment validator | missing | Add `src/mycelium/vault/linkcheck.py` + id validation hooks |
| IF-001 (uniform output envelope) | `269-295` | MCP helpers return heterogeneous dict shapes (`server.py:377-403`, `451-468`) | missing | Add `src/mycelium/vault/envelope.py`; enforce across vault CLI/MCP/tool adapters |
| CMD-ING-001 (`ingest`) | `307-353` | CLI has only `run/status/auto` (`cli.py:363-447`) | missing | Add `vault/commands.py::ingest` + adapter wiring |
| CMD-DEL-001 (`delta`) | `354-381` | No `delta` command/tool exports | missing | Add `vault/commands.py::delta` + adapter wiring |
| CMD-GRD-001 (`graduate`) | `383-414` | No review lifecycle/promotion command in runtime | missing | Add `vault/commands.py::graduate`, `review_queue.py`, `promotion.py` |
| CMD-CTX-001 (`context`) | `415-440` | No retrieval command surface in CLI/MCP | missing | Add `vault/context.py` + command adapter |
| CMD-FRN-001 (`frontier`) | `441-465` | No frontier ranking command | missing | Add `vault/frontier.py` + command adapter |
| PIPE-001, PIPE-002, EXT-001 | `479-535`, `524-529` | No stage pipeline package | missing | Add `vault/pipeline/` stage modules + executor |
| DED-001/002/003 + DEL-002 | `553-584` | No canonicalizer/comparator/novelty module | missing | Add `vault/dedupe.py` + deterministic scoring |
| REV-001 + REV-002 | `588-603` | No queue transition command/promotion semantics implementation | missing | Add explicit review-transition command + per-item atomic promotion |
| AUD-001 (append-only audit logs) | `607-620` | Existing usage logging writes mission yaml (`orchestrator.py:354-419`), not append-only audit stream | partial | Add `vault/audit.py` writing append-only `Logs/Audit/*.jsonl` |
| SEC-001 + SEC-002 (egress policy + evidence) | `623-633` | No egress policy module in runtime | missing | Add `vault/egress_policy.py` + audit integration |
| ERR-001 + ERR-002 (stage failure + quarantine) | `639-650` | No quarantine subsystem | missing | Add `vault/quarantine.py` + stage-scoped error mapping |
| MIG-001 + MIG-002 | `654-665` | No migration/rollback framework found | missing | Add `vault/migrations/` apply/rollback tooling + fixtures |
| TST-U/I/E2E/G/R | `702-760` | Test suite exists but mission/MCP-oriented (`tests/test_mcp.py`, etc.) | partial | Add dedicated vault unit/integration/e2e/golden/regression suites |
| LINT-001..LINT-004 | `763-781` | No `spec-lint` utility present | missing | Add `scripts/spec_lint.py` + CI target |

Traceability summary (current repo vs round5 scope):
- `implemented`: 0
- `partial`: 3
- `missing`: 20
- `unclear`: 0

## 4) TODO-Q1..Q6 Decision Set (ranked options, not mandates)

Final decisions remain human-owned. Ranked options below synthesize Silver recommendations with Copper feasibility constraints.

### TODO-Q1: Note ID strategy (`784`)
1. **Option A (Recommended default): hybrid ID for generated notes**  
   Format: `<slug>--h-<12hex>` for ingestion-generated notes; allow legacy slug-only for manual notes during migration.
   - Pros: collision resistance + readable links.
   - Cons: longer filenames; migration logic needed.
2. Option B: hash-only IDs (`h-<hex>` for all notes).
   - Pros: simplest uniqueness story.
   - Cons: poor readability/audit ergonomics.
3. Option C: slug-only IDs.
   - Pros: simplest UX.
   - Cons: collision and dedupe ambiguity risk.

### TODO-Q2: Provenance locator granularity (`785`)
1. **Option A (Recommended default): source-kind object minima**  
   URL/PDF minima mandatory before MVP1; other source kinds phased.
2. Option B: free-form `locator` string in MVP1; tighten in MVP2.
3. Option C: mixed strictness by confidence band.

### TODO-Q3: Confidence rubric (`786`)
1. **Option A (Recommended default): deterministic weighted rubric, advisory in MVP1, enforced in MVP2 prioritization**.
2. Option B: full mandatory calibration before MVP1.
3. Option C: keep confidence optional/unscored through MVP2.

### TODO-Q4: Review UX authority (`787`)
1. **Option A (Recommended default): command/API authority; plugin as client only**.
2. Option B: plugin-first authority.
3. Option C: dual authority (CLI + plugin independent).

### TODO-Q5: Egress policy defaults (`788`, `635`)
1. **Option A (Recommended default): default-deny + explicit allowlist + sanitization tiers + mandatory audit digest**.
2. Option B: directory-boundary-only checks in MVP1; pattern-level later.
3. Option C: permissive-by-default with blocklist only.

### TODO-Q6: Performance targets (`789`)
1. **Option A (Recommended default): set numeric targets now; measure in MVP1; enforce retrieval gates in MVP2**.
2. Option B: hard-fail perf gates from day one.
3. Option C: defer all numeric targets until post-MVP2.

## 5) File-Level Implementation Map

### 5.1 Existing files to update

| File | Change | Requirement anchors |
|---|---|---|
| `src/mycelium/cli.py` | Add vault command group (`ingest`, `delta`, `review`, `graduate`, `context`, `frontier`) with shared envelope rendering and dry-run behavior | IF-001, IF-002, CMD-* |
| `src/mycelium/tools.py` | Extend tool schemas/dispatch for vault commands; keep existing 7 mission tools backward-compatible | IF-001, CMD-* |
| `src/mycelium/mcp/server.py` | Add thin MCP wrappers for vault commands; preserve current mission tool behavior | IF-001, CMD-* |
| `pyproject.toml` | Ensure import/test invocation consistency (`pytest` without `PYTHONPATH` workaround) | TST-* release hygiene |
| `CURRENT_STATE.md` | Split “current state” vs “target vault state” to reduce scope confusion | Governance/traceability |
| `ROADMAP.md` | Correct MCP status language; separate MCP-v1 current vs vault-v2 expansion | Docs/runtime parity |
| `README.md` | Clarify available command surfaces and experimental vault feature flag state | Docs/runtime parity |

### 5.2 New files/modules to add

| New path | Purpose | Requirement anchors |
|---|---|---|
| `src/mycelium/vault/__init__.py` | Vault subsystem package root | structural |
| `src/mycelium/vault/errors.py` | Canonical error taxonomy and codes | PIPE-001, ERR-001 |
| `src/mycelium/vault/envelope.py` | IF-001 response envelope helpers | IF-001 |
| `src/mycelium/vault/layout.py` | Vault path model + canonical boundary guards | INV-001/002, VLT-001 |
| `src/mycelium/vault/models.py` | Typed note/report/queue models | SCH-001..007 |
| `src/mycelium/vault/schema.py` | Schema definitions | SCH-* |
| `src/mycelium/vault/validators.py` | Shared validation entrypoints | SCH-*, NAM-001 |
| `src/mycelium/vault/idempotency.py` | `(normalized_locator, fingerprint)->source_id` index | INV-005, IDM-001 |
| `src/mycelium/vault/dedupe.py` | Canonicalization + match classification | DED-* |
| `src/mycelium/vault/delta_engine.py` | Delta report generation + novelty scoring | DEL-001/002, SCH-006 |
| `src/mycelium/vault/review_queue.py` | Queue persistence and transition logic | SCH-007, REV-001 |
| `src/mycelium/vault/promotion.py` | Promotion and per-item atomicity | REV-002, CMD-GRD-001 |
| `src/mycelium/vault/context.py` | Context-pack retrieval engine | CMD-CTX-001 |
| `src/mycelium/vault/frontier.py` | Frontier ranking engine | CMD-FRN-001 |
| `src/mycelium/vault/audit.py` | Append-only audit log writer | AUD-001 |
| `src/mycelium/vault/egress_policy.py` | Allow/block/sanitize engine | SEC-001/002 |
| `src/mycelium/vault/quarantine.py` | Quarantine copy + diagnostics | ERR-002 |
| `src/mycelium/vault/pipeline/executor.py` | Stage orchestration and stage-tagged errors | PIPE-001/002 |
| `src/mycelium/vault/pipeline/{capture,normalize,fingerprint,extract,compare,link_propose,delta,queue}.py` | Stage implementations | §6 stage contracts |
| `src/mycelium/vault/commands.py` | Single command core used by CLI/MCP/tools adapters | IF-001, CMD-* |
| `src/mycelium/vault/migrations/{apply,rollback}.py` | Schema/layout migration + rollback | MIG-002 |
| `scripts/spec_lint.py` | Spec lint utility for LINT-* | LINT-* |
| `tests/vault/unit/*` | Unit contract tests | TST-U-001 |
| `tests/vault/integration/*` | Pipeline and boundary tests | TST-I-001 |
| `tests/vault/e2e/*` | Workflow tests | TST-E2E-001 |
| `tests/vault/fixtures/*` | Golden fixtures | TST-G-* |
| `tests/vault/regression/*` | Dedupe/idempotency regressions | TST-R-001 |

## 6) Execution Task Graph (atomic, dependency-ordered, parallel lanes)

Owner roles:
- `Contract` (spec contracts)
- `Platform` (CLI/MCP/tool adapters)
- `Data` (schemas/layout/id)
- `Ingestion` (pipeline, dedupe, delta)
- `Security` (egress/audit)
- `QA` (fixtures/tests/CI)
- `Release` (gates, rollback, docs parity)

Parallel lanes:
- Lane A: Contract/spec
- Lane B: Platform adapters
- Lane C: Data model
- Lane D: Ingestion pipeline
- Lane E: Retrieval/ranking
- Lane F: Security/compliance
- Lane G: QA/Release

| Task ID | Priority | Depends on | Owner | Lane | Deliverable | Task done criteria |
|---|---|---|---|---|---|---|
| S0.1 | P0 | none | Contract | A | Spec patch for review lifecycle, Delta warnings/failures, stage ordering, `all_reviewed` fix, frontier score contract | Spec diff merged; no unresolved contradictions for queue transitions/failure semantics |
| S0.2 | P0 | none | Contract + Product | A | TODO-Q1..Q6 decision record with selected options (or explicit defer list) | Signed decision record exists; MVP1-required TODOs marked selected/deferred |
| S0.3 | P0 | S0.1 | QA | G | `scripts/spec_lint.py` + CI check | LINT-001..004 checks run in CI and fail on violations |
| P0.1 | P0 | S0.1 | Data | C | `vault/errors.py`, `vault/envelope.py` | Unit tests validate IF-001 envelope shape and error-code stability |
| P0.2 | P0 | S0.1 | Data | C | `vault/layout.py`, `vault/models.py`, `vault/schema.py`, `vault/validators.py` | SCH-001..SCH-007 tests pass for valid + invalid fixtures |
| P0.3 | P0 | P0.1 | Platform | B | Adapter scaffolding in CLI/MCP/tools for vault commands (feature-flagged) | Command names discoverable without enabling mutating execution |
| P0.4 | P0 | none | QA | G | Packaging fix for `pytest -q` import path | `pytest -q` works without manual `PYTHONPATH=src` |
| P0.5 | P0 | none | QA | G | Lint baseline reduction | `ruff check src tests` returns 0 for touched scope (or agreed temporary baseline file) |
| P0.6 | P0 | P0.2 | QA | G | Deterministic fixture harness | Re-running same fixture yields byte-identical normalized outputs |
| P1.1 | P1 | P0.2 | Ingestion | D | Capture/Normalize/Fingerprint stages for URL/PDF | Stage contracts + stage-scoped errors validated |
| P1.2 | P1 | P1.1 | Data | C | Source identity index and revision lineage | Re-ingest same content reuses `source_id`; changed fingerprint captures lineage |
| P1.3 | P1 | P1.1 | Ingestion | D | Extract stage minimum outputs and warning behavior | `gist`, `bullets`, and claims-or-warning behavior passes fixtures |
| P1.4 | P1 | P1.3 | Ingestion | D | Canonicalization, dedupe classes, novelty formula | DED/DEL unit tests pass deterministically |
| P1.5 | P1 | P1.2,P1.4 | Ingestion | D | Link proposal + Delta report generation | Delta schema valid; counts and match groups consistent |
| P1.6 | P1 | P1.3,P1.5 | Data | C | Queue proposal generation (`Inbox/ReviewQueue`) | Queue items include required fields/checks |
| P1.7 | P1 | P0.3,P1.5,P1.6 | Platform | B | `ingest` and `delta` CLI/MCP/tool adapters | CMD-ING-001 and CMD-DEL-001 contract tests pass |
| P1.8 | P1 | S0.2,P1.3 | Data | C | URL/PDF locator minima enforcement | Q2 URL/PDF policy tests pass and promotion gate blocks weak locator cases |
| P1.9 | P1 | P1.7,P1.8,P0.6 | QA | G | MVP1 e2e + goldens | AC-MVP1-001-* gates pass |
| P2.1 | P2 | S0.1,P1.6 | Data | C | `review` transition command and immutable queue semantics | Legal transitions only; invalid transitions return `ERR_QUEUE_IMMUTABLE` |
| P2.2 | P2 | P2.1 | Platform | B | `graduate` per-item atomic promotion | Failed item causes no canonical mutation for that item; others can succeed |
| P2.3 | P2 | P1.5 | Ingestion | E | `context` engine with bounded citations | CMD-CTX-001 tests pass |
| P2.4 | P2 | P1.5,S0.1 | Ingestion | E | `frontier` ranking with explicit score field | CMD-FRN-001 tests pass with scored targets |
| P2.5 | P2 | S0.2,P1.7 | Security | F | Egress policy v1 (selected Q5 option) + audit events | SEC-001/002 integration tests pass |
| P2.6 | P2 | P1.1 | Ingestion | D | Quarantine + recoverability behavior | ERR-001/002 induced-failure tests pass |
| P2.7 | P2 | P0.2 | Data | C | Migration/rollback framework | MIG-002 tests pass for migration + rollback |
| P2.8 | P2 | P2.2,P2.3,P2.4,P2.5,P2.6,P2.7 | QA + Release | G | MVP2 release gate suite | MVP2 acceptance gates green, rollback drills validated |
| P2.9 | P2 | P2.8 | Release | G | Docs alignment update (README/ROADMAP/CURRENT_STATE) | No doc/runtime contradiction for command and MCP status |

## 7) Verification Matrix (commands, outputs, artifacts)

| Gate | Command | Expected output | Artifact path |
|---|---|---|---|
| Baseline test sanity | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q` | Passes (`146 passed` currently) | `tests/` |
| Packaging correctness | `cd mycelium-apr-spec && pytest -q` | Currently fails import; target is full collection and execution without import errors | pytest output log |
| Lint hygiene | `cd mycelium-apr-spec && ruff check src tests` | Currently fails (459); target is 0 for release gate | Ruff report |
| Spec lint | `cd mycelium-apr-spec && python scripts/spec_lint.py docs/plans/mycelium_refactor_plan_apr_round5.md` | No LINT-001..004 violations | CI/spec-lint artifact |
| Schema unit gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/unit/test_schema.py` | SCH-001..007 green on valid/invalid fixtures | `tests/vault/unit/test_schema.py` |
| Envelope contract gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/unit/test_envelope.py` | IF-001 conformance for all vault commands | `tests/vault/unit/test_envelope.py` |
| Dry-run contract gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_dry_run.py` | `data.planned_writes` populated; no filesystem mutations | temp fixture vault |
| Idempotency gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_idempotency.py` | identical re-ingest reuses `source_id`; changed content records prior fingerprint | `Indexes/source_identity.yaml`, `Reports/Delta/*.yaml` |
| Delta consistency gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_delta_report.py` | count sums and novelty formula hold | `Reports/Delta/<run_id>.yaml` |
| Queue lifecycle gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_review_queue.py` | legal transitions only; immutable-state violations rejected | `Inbox/ReviewQueue/*.yaml` |
| Graduate atomicity gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_graduate.py` | per-item atomicity and `status: canon` enforcement | canonical dirs + audit log |
| Context/frontier gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/e2e/test_context_frontier.py` | bounded context items with citations; scored frontier outputs | e2e output fixture |
| Security/egress gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_egress_audit.py` | blocklisted egress blocked + audit events emitted | `Logs/Audit/*.jsonl` |
| Quarantine/recovery gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_quarantine_recovery.py` | invalid artifacts quarantined with diagnostics; no canonical overwrite | `Quarantine/` |
| Migration rollback gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/migrations/test_rollback.py` | rollback restores canonical files byte-for-byte | migration fixture snapshots |
| Final release gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault && pytest -q && ruff check src tests` | all new+legacy tests/lint pass | CI logs and junit artifacts |

## 8) Risks / Blockers / Mitigation / Rollback

| ID | Risk/Gap | Severity | Trigger | Mitigation | Rollback point |
|---|---|---|---|---|---|
| R1 | Spec contracts remain contradictory (queue/failure semantics) | Critical | Ambiguous implementation decisions across teams | Enforce S0.1 merge gate before code decomposition | Roll back to pre-vault branch; freeze implementation branch |
| R2 | TODO-Q1..Q6 left undecided for MVP1 gates | Critical | Team blocks on ID/provenance/security/perf policy questions | Run S0.2 decision workshop; mark explicit defers | Keep vault commands feature-flagged off |
| R3 | CLI/MCP/tool adapter drift from shared core behavior | High | Different outputs/errors by interface | Single `vault/commands.py` core + contract tests on all adapters | Disable adapter entrypoints; retain core tests |
| R4 | Canonical write guard defects cause unauthorized mutations | Critical | Canonical dirs modified during ingest/failures | Shared boundary guard in storage layer + failure injection tests | Disable `graduate`; force draft-only mode |
| R5 | Non-deterministic IDs/timestamps destabilize goldens | High | Flaky CI on fixture comparisons | Deterministic harness and normalizer in P0.6 | Relax golden comparisons to normalized form temporarily |
| R6 | Packaging/import mismatch (`pytest -q`) hides regressions | High | CI/dev run different commands and outcomes | Fix import path and standardize single test invocation | Require `PYTHONPATH=src` in CI until fixed |
| R7 | Lint debt obscures new quality regressions | Medium | CI noise from legacy findings | Baseline cleanup or explicit temporary baseline file with burn-down | Gate only changed files while backlog burns down |
| R8 | Egress policy too permissive/too strict | High | Data leakage or workflow blockage | Start default-deny with explicit override audit trail | Set `MYCELIUM_EGRESS_ENABLED=0` emergency kill switch |
| R9 | Migration/rollback procedure incomplete | High | Schema changes corrupt canonical corpus | Build MIG-002 tests and rehearsal before release | Revert to snapshot and disable migrator |
| R10 | Roadmap/docs drift from runtime/spec reality | Medium | Engineers build against stale docs | Add doc-contract checks in release criteria | Revert docs section and mark experimental scope clearly |
| R11 | Performance targets chosen without stable benchmark harness | Medium | Premature perf gate failures | Collect benchmark baseline first; enforce thresholds gradually | Downgrade perf checks to warnings for one cycle |
| R12 | `.mycelium` runtime assumptions break e2e fixture reproducibility | Medium | Missing templates cause false negatives | Fixture generators create full `.mycelium` test roots | Fall back to hermetic fixture repo copies |

### Rollback strategy by phase
- **RP-S0 (spec phase):** if spec patch causes unresolved disputes, halt implementation and continue in read-only planning mode.
- **RP-P0 (substrate):** keep vault adapters hidden behind feature flag; release only orchestration runtime.
- **RP-P1 (MVP1):** if ingest/delta unstable, disable `ingest`/`delta` adapters and retain artifacts for debugging.
- **RP-P2 (MVP2):** if promotion/security unstable, disable `review`/`graduate`/egress paths and run draft-only mode.

## 9) Milestone Done Criteria

### S0 done
- S0.1 spec-patch merged.
- S0.2 TODO decision record published (including explicit defers).
- S0.3 spec-lint gate active in CI.

### P0 done
- Shared envelope/error taxonomy in use by vault command core.
- Schema/layout validators passing.
- Vault commands discoverable (feature-flagged).
- Packaging + lint baseline gate defined and passing per agreed policy.

### MVP1 done (P1)
- URL/PDF ingest implemented with idempotency, dedupe, delta report, queue proposal generation.
- Dry-run contracts and planned writes implemented for write-capable commands.
- URL/PDF provenance minima and tests pass.
- MVP1 acceptance (`AC-MVP1-001-1/2`) passes in CI.

### MVP2 done (P2)
- Queue lifecycle (`review`) and atomic `graduate` promotion live.
- `context` and `frontier` pass bounded/scored output tests.
- Egress policy + append-only audit + quarantine/recovery + migration rollback gates pass.
- MVP2 acceptance (`AC-MVP2-001-1/2`) plus TST-I/E2E/G/R gates pass.

## 10) Must-Fix-Before-Implementation Gate List

1. Resolve round5 spec contract defects (queue transitions, failure durability, delta warnings/failures, stage order, graduate strictness scope).
2. Record human decisions (or explicit defers) for TODO-Q1..Q6 with MVP1 gating tags.
3. Standardize test invocation (`pytest -q` import behavior) so gate signals are trustworthy.
4. Define lint policy for release gates (full cleanup vs phased baseline with strict changed-file rules).
5. Confirm feature-flag strategy for safe rollback of vault command surfaces.

## 11) Immediate Next Actions (execution start)

1. Open S0 spec patch PR implementing CR-01..CR-05 resolutions.
2. Hold 60-minute decision session for TODO-Q1/Q2(URL+PDF)/Q4/Q5/Q6 and capture chosen options.
3. Create implementation beads from task IDs S0.* and P0.* only after S0 merge.
4. Start P0.4 (pytest import path fix) and P0.5 (lint gate policy) in parallel so future vault gates are stable.

