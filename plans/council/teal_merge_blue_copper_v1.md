# Teal Merge Master Plan v1 (Round-3 Synthesis)

Date: 2026-03-01
Merge lead: TealPeak
Output target: `/Users/will/Developer/mycelium/mycelium-apr-spec/plans/council/teal_merge_blue_copper_v1.md`
Primary spec: `/Users/will/Developer/mycelium/mycelium-apr-spec/docs/plans/mycelium_refactor_plan_apr_round5.md`

## 0) Inputs, Method, and Evidence Standard

Inputs read in full:
- `plans/council/blue_merge_copper_silver_v1.md`
- `plans/council/copper_merge_blue_teal_v1.md`
- `plans/council/council_merged_recommendations.md`
- `docs/plans/mycelium_refactor_plan_apr_round5.md`

Repository evidence reviewed:
- Runtime: `src/mycelium/cli.py`, `src/mycelium/mcp/server.py`, `src/mycelium/llm.py`, `src/mycelium/tools.py`, `src/mycelium/orchestrator.py`
- Tests: `tests/test_cli.py`, `tests/test_mcp.py`, `tests/test_llm.py`, `tests/test_orchestrator.py`, `tests/test_tools.py`
- Comparison security baseline: `SPEC.round5.md` (for prior default egress policy options)

Validation commands executed (2026-03-01):
- `cd mycelium-apr-spec && PYTHONPATH=src pytest -q` -> `146 passed in 4.90s`
- `cd mycelium-apr-spec && pytest -q` -> collection failure (`ModuleNotFoundError: mycelium`)
- `cd mycelium-apr-spec && ruff check src tests --statistics` -> `Found 459 errors.`
- `rg` scans for vault/security symbols -> no vault command implementations and no egress/audit policy symbols in runtime (`NO_MATCHES_SECURITY_SYMBOLS`)

Evidence discipline used in this merge:
- Status claims from source plans are accepted only when validated by repository symbols/tests/command output.
- Where evidence is missing or contradictory, this plan labels status `missing` or `spec-defect` and blocks downstream implementation.

## 1) Major Claim Validation Against Repo

| Claim | Repository evidence | Verdict |
|---|---|---|
| CLI surface is currently orchestration-only (`run`, `status`, `auto`) | `src/mycelium/cli.py:364`, `:389`, `:405` | Confirmed |
| MCP/tool surface has 7 mission/filesystem tools | `src/mycelium/tools.py:25`, `:42`, `:78`, `:100`, `:122`, `:158`, `:195` | Confirmed |
| No vault command implementations (`ingest`, `delta`, `graduate`, `context`, `frontier`) | symbol scan in `src/` and `tests/` found no command implementations | Confirmed |
| File writes are path-unbounded after approval | `src/mycelium/mcp/server.py:352-397`, write call at `:391` | Confirmed |
| Command execution uses `shell=True` | `src/mycelium/mcp/server.py:444` | Confirmed |
| External model calls are direct and not policy-gated | `src/mycelium/llm.py:225`, `:319` | Confirmed |
| Fail-closed unreadable-agent approval behavior exists | `src/mycelium/mcp/server.py:103`, tests `tests/test_mcp.py:439`, `:543` | Confirmed |
| Security/audit symbols required by sprint spec are absent | `ERR_EGRESS_POLICY_BLOCK`, `ingest_started`, `egress_blocked`, `promotion_applied`, allowlist/blocklist/redaction symbols absent in `src/` and `tests/` | Confirmed |
| Test baseline is environment-sensitive | `PYTHONPATH=src pytest -q` pass; plain `pytest -q` collection failures | Confirmed |
| Lint debt is material | `ruff check ... --statistics` shows 459 findings | Confirmed |

## 2) Cross-Plan Conflict Resolution (Explicit)

| Conflict ID | Plans in conflict | Conflict | Resolution | Concrete execution implication |
|---|---|---|---|---|
| CR-01 | Blue + Copper vs Sprint spec | Queue immutability requires explicit state transitions, but spec has no transition command contract | Add `review` command contract in S0 spec patch before implementation decomposition | Blocks P1/P2 queue/promotion coding until S0 merge |
| CR-02 | Blue + Copper vs Sprint spec | Delta/Failure requirements mention warnings/failures, but SCH-006 required fields omit them | Extend SCH-006 required fields with `pipeline_status`, `warnings[]`, `failures[]` | Prevents ambiguous failure serialization and broken acceptance tests |
| CR-03 | Copper vs Sprint spec | `all_reviewed` input conflicts with queue statuses `pending_review|approved|rejected` | Rename to `all_approved` in contract; map behavior deterministically | Removes workflow ambiguity in `graduate` automation |
| CR-04 | Blue + Copper vs Sprint spec | `reading_targets` schema omitted score while AC requires explicit numeric rank/score | Define target shape with required numeric `score` | Enables deterministic ranking tests and frontier API stability |
| CR-05 | Teal vs merge override | Teal review provided concrete default policy decisions; round-3 override requires TODO-Q1..Q6 remain options | Keep Q1..Q6 as option sets with recommended defaults and decision gates, not mandates | Preserves human decision authority while keeping implementation-ready options |
| CR-06 | Blue vs Teal emphasis | Blue emphasizes broad spec closure; Teal emphasizes security-first gating | Adopt dual gate: S0 spec closure + S0 security policy option matrix before P1 execution | Prevents building on contradictory contracts and avoids unsecured rollout |
| CR-07 | Council recommendations vs repo reality | Council merged rec suggests closure of Q1/Q2/Q4/Q5/Q6 “before MVP1”, but override prohibits converting unresolved policy into mandates | Reframe as “decision gate required before releasing affected features,” with fallback `defer + feature flag off` | Allows engineering progress without forcing unresolved governance choices |
| CR-08 | User operating mode vs queue friction | Personal usage preference is “nightly reading time” rather than continuous file-level moderation | Add reading-first nightly curation flow: digest + per-source review packets + batched apply | Preserves canonical safety while making review feel like reading, not bookkeeping |

## 3) Sprint Requirement Traceability Matrix

Status legend: `implemented` | `partial` | `missing` | `spec-defect`

| Requirement -> evidence -> status -> gap |
|---|
| `IF-001` (command envelope, `round5.md:269-295`) -> no vault command handlers in CLI/MCP/tools (`cli.py:364/389/405`, `tools.py` 7 tools only) -> `missing` -> add `src/mycelium/vault/envelope.py` and enforce in all vault command adapters |
| `IF-002` dry-run planned writes (`:298-302`) -> current dry-run is prompt-only (`orchestrator.py:516-523`) -> `partial` -> implement `data.planned_writes` contract for all write-capable vault commands |
| `CMD-ING-001` (`:347-353`) -> no `ingest` command in runtime -> `missing` -> add `src/mycelium/vault/commands.py::ingest` + adapters |
| `CMD-DEL-001` (`:377-381`) -> no `delta` command implementation -> `missing` -> add `delta` command + report validator path |
| `CMD-GRD-001` (`:407-413`) -> no `graduate` implementation -> `missing` -> add promotion engine with per-item atomicity |
| `SCH-007` immutability (`:247-248`) -> no explicit queue transition command in command contracts -> `spec-defect` -> add `review` command contract and lifecycle semantics |
| `CMD-CTX-001` (`:435-440`) -> no `context` command -> `missing` -> add retrieval module with bounded output and citations |
| `CMD-FRN-001` (`:461-464`) -> no `frontier` command and score shape omitted (`:452`) -> `missing` + `spec-defect` -> add command + explicit scored schema |
| `PIPE-001` stage-scoped failures (`:479-483`) -> no vault stage pipeline in code -> `missing` -> add stage executor with `stage` and deterministic error codes |
| `PIPE-002` + `ERR-002` (`:531-535`, `:646-650`) -> no quarantine subsystem in `src/` -> `missing` -> add quarantine module + diagnostic sidecar contract |
| `SCH-006` + failure/warnings references (`:227`, `:263`, `:524-529`) -> required keys omit warnings/failures/pipeline status -> `spec-defect` -> extend schema and validator |
| `REV-002` strict promotion (`:595-603`) -> no promotion engine; strict scope currently over-broad (`SCH-001..SCH-007`) -> `spec-defect` -> narrow strict validation scope to promoted entities + related queue checks |
| `AUD-001` append-only audit (`:607-620`) -> no append-only vault audit stream; current YAML rewrite (`orchestrator.py:98-113`) -> `missing` -> add append-only audit writer under `Logs/Audit/` |
| `SEC-001/SEC-002` egress policy and outbound context logging (`:623-633`) -> no allowlist/blocklist/redaction/audit symbols in runtime/tests (`NO_MATCHES_SECURITY_SYMBOLS`) -> `missing` -> add security policy, redaction, egress audit modules |
| `INV-002`/`VLT-001` canonical boundary (`:63-69`, `:110-114`) -> write path unbounded after approval (`mcp/server.py:391`) -> `missing` -> add path-boundary enforcement independent of HITL |
| `LINT-003` interface completeness (`:773-776`) -> stage interfaces in §6.1.1 omit side effects section -> `spec-defect` -> patch spec before implementation freeze |
| `TST-U/I/E2E/G/R` (`:702-760`) -> no vault test tree (`tests/vault/**`) yet -> `missing` -> create full vault unit/integration/e2e/golden/regression suites |
| `TODO-Q1..Q6` (`:784-789`) governance unresolved -> no decision mechanism in code -> `partial` -> maintain option sets + decision gates; enforce feature flags until decisions are made |

## 4) File-Level Implementation Map

### 4.1 Existing Files to Update

| File | Planned update | Why |
|---|---|---|
| `src/mycelium/cli.py` | Add vault command group (`ingest`, `delta`, `review`, `graduate`, `context`, `frontier`) while preserving `run/status/auto` | transport-agnostic command contracts |
| `src/mycelium/tools.py` | Extend tool schema registry and dispatch for vault commands; keep existing 7 tools backward-compatible | unified tool interface |
| `src/mycelium/mcp/server.py` | Add MCP wrappers for vault commands and enforce boundary/policy middleware | MCP parity and security control plane |
| `src/mycelium/llm.py` | Add optional outbound egress guard hook before provider call | SEC-001/SEC-002 compliance |
| `src/mycelium/orchestrator.py` | Thread reason/context metadata for audited outbound calls where vault content may be sent | auditability |
| `docs/plans/mycelium_refactor_plan_apr_round5.md` | S0 patch set for spec defects (CR-01..CR-04) | implementation-ready contract |
| `pyproject.toml` | Make package/test invocation consistent so plain `pytest -q` works | reliable CI gating |
| `README.md`, `CURRENT_STATE.md`, `ROADMAP.md` | Update command/runtime reality and vault feature-flag status | doc/runtime parity |

### 4.2 New Files to Add

| New path | Purpose |
|---|---|
| `src/mycelium/vault/__init__.py` | Vault subsystem root |
| `src/mycelium/vault/errors.py` | Stable error code taxonomy (`code`, `stage`, `retryable`) |
| `src/mycelium/vault/envelope.py` | IF-001 response envelope helpers |
| `src/mycelium/vault/layout.py` | canonical/draft/durable boundary rules and normalized paths |
| `src/mycelium/vault/models.py` | typed data models for notes/reports/queue |
| `src/mycelium/vault/schema.py` | SCH-001..SCH-007 validation schemas |
| `src/mycelium/vault/validators.py` | validation entrypoints and strict/non-strict behavior |
| `src/mycelium/vault/idempotency.py` | source identity index management |
| `src/mycelium/vault/dedupe.py` | claim canonicalization, match classification, novelty score |
| `src/mycelium/vault/delta_engine.py` | delta report generation and consistency checks |
| `src/mycelium/vault/review_queue.py` | queue persistence and transition state machine |
| `src/mycelium/vault/promotion.py` | per-item atomic promotion engine |
| `src/mycelium/vault/context.py` | bounded context-pack retrieval |
| `src/mycelium/vault/frontier.py` | scored frontier ranking engine |
| `src/mycelium/vault/quarantine.py` | quarantine placement + diagnostic sidecars |
| `src/mycelium/vault/audit.py` | append-only audit event stream |
| `src/mycelium/vault/pipeline/executor.py` | stage orchestration and failure isolation |
| `src/mycelium/vault/pipeline/{capture,normalize,fingerprint,extract,compare,link_propose,delta,queue}.py` | stage implementations |
| `src/mycelium/vault/commands.py` | single command core used by CLI/MCP/tools |
| `src/mycelium/security/policy.py` | egress allow/block policy engine |
| `src/mycelium/security/redaction.py` | outbound sanitization/redaction engine |
| `src/mycelium/security/audit.py` | security event writer helpers |
| `src/mycelium/vault/migrations/{apply,rollback}.py` | migration and rollback workflows |
| `scripts/spec_lint.py` | LINT-001..LINT-004 checker |
| `tests/vault/unit/*` | schema/envelope/dedupe/idempotency unit tests |
| `tests/vault/integration/*` | pipeline, queue, promotion, security, quarantine tests |
| `tests/vault/e2e/*` | first/repeat/contradiction/promotion/context/frontier flows |
| `tests/vault/fixtures/**` | deterministic golden fixtures |
| `tests/security/*` | egress policy, redaction, audit regression tests |

## 5) Task Graph (Atomic, Dependency-Ordered, Parallel Lanes)

Owner roles: `Spec`, `Platform`, `Data`, `Pipeline`, `Security`, `QA`, `Release`

Parallel lanes:
- Lane A: spec closure
- Lane B: command/interface substrate
- Lane C: data/schema core
- Lane D: ingestion engine
- Lane E: retrieval/frontier
- Lane F: security/audit
- Lane G: tests/release

| Task ID | Priority | Depends on | Owner | Lane | Parallelizable | Deliverable | Task done criteria |
|---|---|---|---|---|---|---|---|
| S0-1 | P0 | none | Spec | A | no | queue lifecycle contract patch (`review`) | spec defines legal transitions and error semantics; no ambiguous queue mutation path |
| S0-2 | P0 | none | Spec | A | yes | SCH-006 closure patch | required `pipeline_status`, `warnings[]`, `failures[]` fields added and ACs updated |
| S0-3 | P0 | none | Spec | A | yes | failure durability reconciliation | AC-PIPE-002 and AC-SCH-006 no longer conflict |
| S0-4 | P0 | S0-1 | Spec | A | no | `graduate` contract patch | `all_approved` semantics and strict behavior are deterministic |
| S0-5 | P0 | none | Spec | A | yes | frontier output + stage side-effects patch | `reading_targets` scored schema explicit; stage interfaces meet LINT-003 |
| S0-6 | P0 | none | Spec + Security | A | yes | TODO-Q1..Q6 option matrix appendix | options/recommendations/defer paths documented without mandates |
| S0-7 | P0 | S0-1,S0-4 | Spec + Product | A | yes | reading-first nightly review contract (`review_digest`, packet decisions, batch apply semantics) | spec defines digest/packet fields, decision actions, and deterministic apply behavior |
| S0-8 | P0 | S0-6,S0-7 | Spec + Security | A | yes | auto-approval lane policy | explicit safe auto-approve predicates, disallowed classes, and audit requirements defined |
| P0-1 | P0 | S0-* | Platform | B | yes | envelope + error taxonomy modules | IF-001 tests pass for all new vault handlers |
| P0-2 | P0 | S0-* | Data | C | yes | layout + models + schema validators | SCH-001..SCH-007 validator tests green |
| P0-3 | P0 | S0-* | QA | G | yes | deterministic fixture harness | two identical runs produce byte-identical normalized outputs |
| P0-4 | P0 | P0-1 | Platform | B | yes | CLI/MCP/tools command scaffolding | vault commands registered and discoverable behind feature flag |
| P0-5 | P0 | none | Release | G | yes | test invocation fix | plain `pytest -q` succeeds without import errors |
| P0-6 | P0 | none | Release | G | yes | lint gate strategy | lint gating policy ratified; trend is measurable and enforceable |
| P0-7 | P0 | S0-7,P0-1 | Platform | B | yes | nightly digest + packet renderer scaffold (`review digest`) | digest renders one packet per source with claim cards and proposed canonical impact |
| P1-1 | P1 | P0-2,P0-3 | Pipeline | D | yes | capture/normalize/fingerprint stages | stage-scoped errors with deterministic codes pass integration tests |
| P1-2 | P1 | P1-1 | Data | C | yes | idempotency index | identical source reuses `source_id`; changed content records lineage |
| P1-3 | P1 | P1-1 | Pipeline | D | yes | extract stage minimum outputs | `gist`, `bullets`, claims-or-warning behavior validated |
| P1-4 | P1 | P1-2,P1-3 | Pipeline | D | yes | dedupe + delta engine | match classes complete; novelty formula deterministic |
| P1-5 | P1 | P1-4,P0-4 | Platform | B | yes | `ingest` + `delta` commands | CMD-ING-001 and CMD-DEL-001 contract tests pass |
| P1-6 | P1 | P1-4 | Data | C | yes | queue proposal generation | REV-001 checks and queue schema validation pass |
| P1-7 | P1 | P1-5,P1-6,P0-7 | Platform | B | yes | nightly apply pipeline (`graduate --from-digest`) | source-level decisions map deterministically to queue-item approvals/rejections |
| P1-8 | P1 | P1-5,P1-6,P1-7 | QA | G | no | MVP1 e2e/golden suite | AC-MVP1-001-1/2 pass in CI |
| P2-1 | P2 | S0-1,P1-6 | Data | C | yes | queue transition engine | invalid transitions fail with `ERR_QUEUE_IMMUTABLE` |
| P2-2 | P2 | P2-1,S0-4 | Data | C | yes | `graduate` promotion engine | per-item atomicity and status/path updates pass |
| P2-3 | P2 | P1-4,S0-5 | Pipeline | E | yes | `context` + `frontier` engines | bounded citations and ranked scored outputs pass |
| P2-4 | P2 | S0-6,P0-1 | Security | F | yes | egress policy + redaction + audit | blocked/allowed egress and audit evidence tests pass |
| P2-5 | P2 | P1-1,S0-3 | Pipeline | D | yes | quarantine + recoverability | induced stage failures quarantine artifacts with diagnostics and no canonical mutation |
| P2-6 | P2 | P0-2 | Data | C | yes | migration/rollback framework | migration and byte-for-byte rollback tests pass |
| P2-7 | P2 | P2-2,P2-3,P2-4,P2-5,P2-6 | QA + Release | G | no | MVP2 release gate suite | AC-MVP2-001-1/2 + security + recovery + migration gates all pass |
| P2-8 | P2 | P2-7 | Release | G | no | docs parity update | docs align with shipped command surface and policy behavior |

## 6) Verification Matrix (Command -> Expected Output -> Artifact)

| Gate | Command | Expected output | Artifact path |
|---|---|---|---|
| Baseline regression | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q` | `146 passed` (current baseline) | test logs |
| Import-path correctness | `cd mycelium-apr-spec && pytest -q` | currently fails; target: full collection passes | test logs |
| Lint baseline | `cd mycelium-apr-spec && ruff check src tests --statistics` | currently `Found 459 errors.`; target: agreed gating threshold then burn-down | lint report |
| Spec lint | `cd mycelium-apr-spec && python scripts/spec_lint.py docs/plans/mycelium_refactor_plan_apr_round5.md` | no LINT-001..004 violations | `scripts/spec_lint.py` output |
| Schema unit gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/unit/test_schema.py` | valid/invalid fixture behavior matches SCH requirements | `tests/vault/unit/test_schema.py` |
| Envelope gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/unit/test_envelope.py` | all command envelopes conform to IF-001 | `tests/vault/unit/test_envelope.py` |
| Dry-run gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_dry_run.py` | no FS writes; `data.planned_writes` populated | temp fixture vault diff |
| Idempotency gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_idempotency.py` | identical source reuse + changed source lineage | `Indexes/`, `Reports/Delta/` fixtures |
| Delta integrity gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_delta_report.py` | count sums and novelty formula exact | `Reports/Delta/<run_id>.yaml` |
| Queue lifecycle gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_review_queue.py` | legal transitions pass; illegal transitions fail deterministically | `Inbox/ReviewQueue/*.yaml` |
| Nightly digest gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_review_digest.py` | digest groups queue items by source and renders claim cards with citations + canonical-impact summaries | `Inbox/ReviewDigest/<date>.md` |
| Nightly apply gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_graduate_from_digest.py` | `approve_all`, `approve_selected`, `hold`, `reject` decisions produce deterministic promotions/rejections | `Inbox/ReviewDigest/<date>.md`, audit log |
| Promotion atomicity gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_graduate.py` | per-item atomic outcomes and audit linkage pass | canonical dirs + `Logs/Audit/` |
| Context/frontier gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/e2e/test_context_frontier.py` | bounded context citations and explicit scored frontier ranking pass | e2e fixtures |
| Security egress gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/security/test_egress_policy.py tests/security/test_redaction.py tests/security/test_audit_events.py` | policy block/allow outcomes and audit fields pass | `Logs/Audit/*.jsonl` fixtures |
| Quarantine recovery gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_quarantine_recovery.py` | quarantined artifacts include diagnostics; canonical unchanged | `Quarantine/<run_id>/` |
| Migration rollback gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/migrations/test_rollback.py` | rollback restores canonical files byte-for-byte | migration fixtures |
| Final release gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault tests/security && pytest -q && ruff check src tests` | all vault/security + legacy tests and lint gate pass | CI artifacts |

## 7) Top 10 Risks/Gaps with Mitigation and Rollback

| Risk ID | Risk/Gap | Impact | Mitigation | Rollback trigger | Rollback action |
|---|---|---|---|---|---|
| R1 | Queue lifecycle contract gap | Promotion deadlock or unsafe mutation | S0-1 `review` contract + state machine before code rollout | any manual queue edits needed for normal flow | disable `graduate`, run draft-only mode |
| R2 | Failure durability ambiguity in spec | inconsistent implementations and flaky tests | S0-2/S0-3 schema+AC reconciliation | conflicting interpretations in PRs or tests | halt P1 merge until spec patch accepted |
| R3 | Missing warnings/failures in Delta schema | inability to represent partial/failed runs | extend SCH-006 and validators | failed runs lack required fields | mark run schema-invalid and quarantine artifacts |
| R4 | No egress policy engine | potential outbound data leakage | P2-4 policy+redaction+audit modules | outbound send without policy decision | hard-disable external egress feature flag |
| R5 | Canonical boundary not enforced in write tools | accidental canonical corruption | path-boundary guard independent of HITL | attempt to write canon path outside promotion | reject with `ERR_CANON_WRITE_FORBIDDEN` |
| R6 | `shell=True` blast radius in command tooling | command injection/exfiltration risk | role/policy command restrictions + audit | suspicious command pattern or unapproved scope | disable `run_command` for risky roles |
| R7 | Import-path mismatch for `pytest -q` | CI confidence gap | P0-5 packaging/test invocation fix | collection errors in CI | freeze release and revert to last passing tag |
| R8 | Lint debt (459 findings) masks regressions | noisy CI, lower signal | staged lint ratchet with explicit threshold and burn-down | lint error trend increases | block feature merges until debt reduced |
| R9 | TODO-Q1..Q6 forced prematurely | governance churn and rework | keep options with decision gates and deferral paths | decision merged without gate record | revert policy profile and keep feature flagged |
| R10 | Cross-tree drift (`mycelium` vs `mycelium-apr-spec`) | fixes applied to wrong tree | treat `mycelium-apr-spec` as current execution source; add parity check task | divergence detected between trees | stop release and run sync/parity remediation |
| R11 | Review UX too file-centric for personal workflow | queue gets ignored, stale approvals pile up | reading-first nightly digest + source-level actions | review cadence drops or digest backlog grows | auto-hold all pending items and keep draft-only mode |

## 8) TODO-Q1..Q6 Options (Recommendations, Not Mandates)

Policy rule for this merge: unresolved TODOs remain option sets for human decision. Recommended options are non-binding until approved.

### TODO-Q1: canonical note ID strategy
- Option A: slug-only.
- Option B: hash-only (`h-<hex>`).
- Option C: slug+hash hybrid (`<slug>--h-<hex>`).
- Recommended path: Option C for machine-generated notes; Option A tolerated for manual notes during migration.
- Decision gate: before P1 code freeze.

### TODO-Q2: minimum provenance locator granularity
- Option A: free-form string locator only.
- Option B: source-kind structured locator minima.
- Option C: source-kind structured locator + snippet hash.
- Recommended path: Option C for URL/PDF in MVP1; phase remaining source kinds later.
- Decision gate: before P1 fixture lock.

### TODO-Q3: confidence calibration rubric
- Option A: keep confidence optional/no rubric until MVP2.
- Option B: deterministic heuristic rubric (advisory).
- Option C: domain-calibrated weighted rubric.
- Recommended path: Option B advisory in MVP1; evaluate Option C for MVP2 frontier prioritization.
- Decision gate: before P2 ranking release.

### TODO-Q4: authoritative review UX
- Option A: CLI-only authority.
- Option B: plugin-only authority.
- Option C: command/API authority with CLI/plugin clients.
- Recommended path: Option C.
- Decision gate: before P2 review/promotion rollout.

### TODO-Q5: default egress policy and sanitization
- Option A: strict default-deny allowlist + fail-closed redaction.
- Option B: permissive default-allow + blocklist.
- Option C: report-only burn-in then enforce strict policy.
- Recommended path: staged `C -> A`.
- Decision gate: before any external vault egress feature is enabled.

### TODO-Q6: performance targets and measurement
- Option A: qualitative targets only.
- Option B: fixed numeric p95 targets for ingest/delta/frontier.
- Option C: adaptive targets by source kind/size.
- Recommended path: Option B for MVP1 ingest/delta; evaluate Option C for MVP2 retrieval/frontier.
- Decision gate: before benchmark suite freeze.

### Reading-First Nightly Review Decisions (new)

The following decisions make queue review feel like “nightly reading time” while preserving canonical safety.

### TODO-Q7: nightly review unit of work
- Option A: queue-item-level only (fine-grained, high effort).
- Option B: source-level packet default with optional claim drill-down.
- Option C: run-level batch (fast, lowest precision).
- Recommended path: Option B.
- Decision gate: before P0-7 implementation.

### TODO-Q8: reviewer action vocabulary
- Option A: `approve` / `reject` only.
- Option B: `approve_all`, `approve_selected`, `hold`, `reject`.
- Option C: add deferred labels and custom states.
- Recommended path: Option B.
- Decision gate: before P1-7 implementation.

### TODO-Q9: safe auto-approval lane
- Option A: none (all semantic changes human-reviewed).
- Option B: constrained auto-lane for exact duplicates + metadata-only updates + non-semantic formatting.
- Option C: broad auto-lane including new claims with high confidence.
- Recommended path: Option B.
- Decision gate: before enabling unattended ingestion in production mode.

### TODO-Q10: commit granularity for applied decisions
- Option A: one commit per queue item.
- Option B: one commit per source packet.
- Option C: one nightly batch commit.
- Recommended path: Option B.
- Decision gate: before P1-7 implementation.

### TODO-Q11: hold-item aging policy
- Option A: holds never expire.
- Option B: holds expire after N days and return to nightly digest.
- Option C: holds auto-reject after N days.
- Recommended path: Option B.
- Decision gate: before first nightly automation rollout.

### TODO-Q12: default contradiction handling
- Option A: auto-approve contradictions into canon.
- Option B: always human-review contradictions with side-by-side evidence.
- Option C: suppress contradictions unless confidence exceeds threshold.
- Recommended path: Option B.
- Decision gate: before enabling contradiction fixtures in MVP1.

## 9) Done Criteria Per Milestone

### S0 Done
- CR-01..CR-04 spec defects patched and merged.
- TODO option matrix (Q1..Q12) added with decision gates.
- Reading-first nightly review contract (S0-7) and auto-lane policy guardrails (S0-8) merged.
- Spec lint passes with no LINT-001..004 failures.

### P0 Done
- Envelope/error taxonomy and schema/layout validators merged.
- Vault command scaffolding discoverable behind feature flags.
- Deterministic fixture harness active.
- Nightly digest/packet renderer scaffold merged.
- Plain `pytest -q` import-path issue resolved.

### P1 Done (MVP1)
- URL/PDF ingest, idempotency, dedupe, delta report, and queue proposal generation are implemented.
- Dry-run planned-writes contract implemented for write-capable vault commands.
- Nightly digest decisions apply deterministically via batch apply flow.
- MVP1 acceptance criteria pass in CI with golden fixtures.

### P2 Done (MVP2)
- Queue lifecycle and `graduate` atomicity implemented and validated.
- `context` and `frontier` outputs satisfy bounded and scored contract checks.
- Egress policy, redaction, audit, quarantine/recovery, and migration rollback tests pass.
- MVP2 acceptance criteria pass in CI.

## 10) Immediate Execution Start Sequence

1. Implement S0 spec patch bundle first (`S0-1..S0-8`).
2. Open P0 workstream in parallel lanes (B/C/G) once S0 merges.
3. Do not start P1 ingest coding until S0 and P0 done criteria are green.
4. Keep policy-dependent capabilities feature-flagged until corresponding TODO decision gates are approved.
