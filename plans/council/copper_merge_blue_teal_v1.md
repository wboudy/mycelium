# CopperHawk Master Merge Plan (Blue + Teal + Council)

Date: 2026-03-01  
Merge lead: CopperHawk  
Primary spec: `/Users/will/Developer/mycelium/mycelium-apr-spec/docs/plans/mycelium_refactor_plan_apr_round5.md`

## 1) Inputs, Scope, and Evidence Discipline

Merged inputs:
- `PLAN_A`: `plans/council/blue_systems_contract_review.md`
- `PLAN_B`: `plans/council/teal_security_failure_review.md`
- `PLAN_C`: `plans/council/council_merged_recommendations.md`

Repository evidence scope used to validate plan claims:
- Runtime: `mycelium-apr-spec/src/mycelium/cli.py`, `orchestrator.py`, `llm.py`, `tools.py`, `mcp/server.py`
- Tests: `mycelium-apr-spec/tests/test_cli.py`, `test_mcp.py`, `test_orchestrator.py`, `test_tools.py`, `test_llm.py`
- Prior baseline spec for security defaults/options: `mycelium-apr-spec/SPEC.round5.md`

Validation commands executed:
- `cd mycelium-apr-spec && PYTHONPATH=src pytest -q` -> `146 passed`
- `cd mycelium-apr-spec && pytest -q` -> import collection failure (`ModuleNotFoundError: mycelium`)
- `cd mycelium-apr-spec && ruff check src tests` -> fails (format/import debt)
- `rg` symbol scans for vault commands/security/audit contracts -> no matches for required vault-domain interfaces and egress-policy error codes

Current implementation baseline (fact):
- CLI command set is `run`, `status`, `auto` only (`src/mycelium/cli.py:363-447`).
- Tool schemas/MCP expose only 7 mission/filesystem tools (`src/mycelium/tools.py:21-234`, `src/mycelium/mcp/server.py:1-11`).
- No implementations for `ingest`, `delta`, `graduate`, `context`, `frontier`, review queue lifecycle, delta schema validators, quarantine subsystem, or egress-policy/audit contracts required by round-5.

## 2) Contradiction Resolution Ledger (Blue vs Teal vs Council vs Sprint Spec)

| Conflict | Evidence | Resolution | Rationale |
|---|---|---|---|
| Queue immutability requires explicit transitions, but no transition command exists | Spec: `SCH-007` immutability (`round5.md:247-248`), `graduate` contract (`383-413`), no `5.2.7` command (`307-466` only 6 commands) | Add mandatory queue decision interface (`review` command) before MVP2 implementation decomposition | Blue finding is valid; execution otherwise depends on out-of-band mutation |
| Failure durability vs quarantine wording ambiguity | Spec requires durable Delta on failed post-extraction attempts (`227`), ingest writes durable outputs (`334-335`), but AC-PIPE-002-1 says “no files or all in Quarantine” (`534`) | Clarify: durable `Reports/Delta` + `Logs/Audit` are allowed on failure; invalid/partial draft artifacts must quarantine | Removes contradictory interpretations while preserving recoverability + auditability |
| Delta schema referenced fields are absent | Spec references warning/failure recording (`227`, `263`, `524-529`) but required SCH-006 keys omit `warnings`, `failures`, `pipeline_status` (`195-205`) | Extend SCH-006 required fields with `pipeline_status`, `warnings[]`, `failures[]` | Blue and council merged recommendations align; needed for testable contract completeness |
| Stage interface lint rule requires side effects but stage specs omit them | `LINT-003` requires interfaces include side effects (`773-776`), stage list has input/output/errors only (`488-521`) | Add explicit `Side effects` for each stage | Makes spec self-consistent and lint-passable |
| `graduate` strict behavior is ambiguous | `graduate` exposes optional `strict` (`391`), promotion mandates strict mode (`596`) | Mutating `graduate` must always run strict; optional `strict=false` allowed only with `dry_run=true` | Preserves safety invariant without removing dry-run flexibility |
| `all_reviewed` vocabulary mismatch with queue states | `graduate` input `all_reviewed` (`388`) vs queue statuses `pending_review|approved|rejected` (`242`) | Rename to `all_approved` and define exact behavior | Eliminates ambiguous state mapping |
| `frontier` output lacks declared score field despite AC | Output declares `reading_targets: array[...]` (`452`), AC requires explicit numeric score (`464`) | Define shape: `reading_targets: [{target, score, rationale, citations}]` | Needed for deterministic ranking and contract testing |
| Teal proposes hard TODO decisions; council override requires optionality | Teal Section 4 labels “Decision Set” for Q1/Q2/Q4/Q5, while merge override says keep TODO-Q1..Q6 as recommendations/options | Keep all TODO-Q1..Q6 as option sets; define recommended default paths and decision gates | Complies with override and preserves human policy authority |
| Path mismatch risk (`mycelium/` vs `mycelium-apr-spec/`) | Inputs target `mycelium-apr-spec/*`; runtime/tests exist there and were validated (`146 passed`) | Treat `mycelium-apr-spec` tree as execution source of truth for this plan; mirror guidance can be ported later to sibling tree | Avoids false negatives from cross-tree drift |

## 3) Requirement Traceability Matrix (Merged, Evidence-Backed)

Status legend: `implemented` | `partial` | `missing` | `spec-defect`

| Requirement(s) | Spec evidence | Repo evidence | Status | Gap and implementation target |
|---|---|---|---|---|
| IF-001 command envelope across vault commands | `round5.md:269-295` | No vault command handlers exist in CLI/MCP/tools; only orchestration commands (`cli.py:363-447`) and 7 MCP tools (`tools.py:21-234`) | missing | Add `src/mycelium/vault/envelope.py` + enforce in all new vault commands/adapters |
| IF-002 dry-run planned writes for write-capable vault commands | `298-302` | Existing dry-run is prompt-only (`run_agent` dry-run path in `orchestrator.py`), no vault writes/plans | partial | Implement in `src/mycelium/vault/commands.py` for `ingest`, `review`, `graduate` |
| CMD-ING-001 ingest contract | `307-352` | No `ingest` symbol in `src/mycelium`/tests (`rg` no match) | missing | Add `ingest` core + CLI/MCP/tool adapters |
| CMD-DEL-001 delta contract | `354-381` | No `delta` command implementation | missing | Add `delta` reader/validator command |
| CMD-GRD-001 graduate contract | `383-413` | No `graduate` command implementation | missing | Add `graduate` promotion engine + atomicity guarantees |
| Queue lifecycle mutability contract | `242`, `247-248`, `684-690` | No review/transition command surface (`5.2.1..5.2.6 only`) | spec-defect | Add `5.2.7 review` command + queue state machine module |
| CMD-CTX-001 context and CMD-FRN-001 frontier | `415-439`, `441-464` | No `context`/`frontier` commands in runtime/tests | missing | Add retrieval and frontier modules with bounded outputs and citations |
| PIPE-001 stage-scoped failures | `479-483` | No vault pipeline stage system; current errors are orchestration-level strings | missing | Add stage executor and typed stage errors (`code`, `stage`, `retryable`) |
| PIPE-002 staging/atomicity and ERR-002 quarantine | `531-535`, `646-650` | No quarantine subsystem (`rg` no `quarantine` symbol) | missing | Add `src/mycelium/vault/quarantine.py` + staged write/atomic move model |
| SCH-006 Delta schema completeness vs warning/failure references | `195-205`, `227`, `263`, `524-529` | No delta-schema validators in runtime/tests | spec-defect | Add fields + validator modules + tests |
| REV-002 strict promotion and schema scope | `595-603` | No promotion engine; contract text over-broad (`SCH-001..SCH-007` on promoted items) | spec-defect | Narrow strict validation to applicable note schemas; enforce queue-item/schema checks separately |
| AUD-001 append-only audit logs | `607-620` | Current state rewrite is `save_progress` YAML overwrite (`orchestrator.py:98-112`), no append-only audit subsystem | missing | Add append-only audit writer under `Logs/Audit/` with event schema |
| SEC-001/SEC-002 egress policy + outbound audit context | `623-633`, TODO-Q-SEC-1 (`635`) | No egress symbols/codes (`NO_MATCHES_EGRESS_AUDIT_SYMBOLS`); LLM sends via `litellm.completion` (`llm.py:319`) | missing | Add `src/mycelium/security/policy.py`, `redaction.py`, `audit.py`, and integrate in outbound call path |
| INV-002/VLT-001 canon boundary enforcement | `63-69`, `110-114` | `write_file` writes arbitrary path after HITL (`mcp/server.py:352-397`) | missing | Add path-boundary guard (`ERR_CANON_WRITE_FORBIDDEN`) independent of HITL |
| LINT-003 interface completeness | `773-776` | Stage interfaces omit side-effects fields (`488-521`) | spec-defect | Patch spec and add `scripts/spec_lint.py` gate |
| TST-I/E2E/G/R vault test coverage | `709-760` | Existing tests are mission orchestration/tooling; no vault fixture tree | missing | Add `tests/vault/{unit,integration,e2e,fixtures,regression}` |
| TODO-Q1..Q6 governance | `784-789` | No decision framework in runtime; prior spec has candidate security defaults (`SPEC.round5.md:437-447`) | partial | Keep open as option sets with explicit decision gates per milestone |

## 4) File-Level Implementation Map (Existing vs New)

### 4.1 Existing files to update

| File | Change |
|---|---|
| `src/mycelium/cli.py` | Add vault command subparsers: `ingest`, `delta`, `review`, `graduate`, `context`, `frontier`; keep existing `run/status/auto` unchanged |
| `src/mycelium/tools.py` | Add tool schemas + dispatch mappings for new vault commands |
| `src/mycelium/mcp/server.py` | Add MCP wrappers for vault commands; add policy guard middleware for file/command tools |
| `src/mycelium/orchestrator.py` | Add optional egress gate hook and reason context propagation for external sends |
| `src/mycelium/llm.py` | Route outbound payload through egress policy + redaction + audit emitter before `litellm.completion` |
| `docs/plans/mycelium_refactor_plan_apr_round5.md` | Apply S0 spec corrections (queue lifecycle, delta schema extensions, strictness, side-effects, output shapes) |
| `pyproject.toml` | Add stable test invocation guidance/tooling hook to remove `PYTHONPATH` drift |

### 4.2 New files/modules to add

| Path | Purpose |
|---|---|
| `src/mycelium/vault/envelope.py` | IF-001 command envelope and error/warning object types |
| `src/mycelium/vault/layout.py` | Canon/draft/durable path policy and root normalization |
| `src/mycelium/vault/models.py` | Typed payload models for notes/reports/queue |
| `src/mycelium/vault/schema.py` | SCH-001..SCH-007 validators |
| `src/mycelium/vault/idempotency.py` | `(normalized_locator,fingerprint)->source_id` index |
| `src/mycelium/vault/pipeline/{capture,normalize,fingerprint,extract,compare,link_propose,delta,queue}.py` | Stage implementations matching spec contracts |
| `src/mycelium/vault/review_queue.py` | Queue state machine + transition enforcement |
| `src/mycelium/vault/promotion.py` | `graduate` execution with per-item atomicity |
| `src/mycelium/vault/context.py` | Citation-bounded context retrieval |
| `src/mycelium/vault/frontier.py` | Frontier ranking with explicit score field |
| `src/mycelium/vault/quarantine.py` | Quarantine artifact + diagnostic sidecar handling |
| `src/mycelium/security/policy.py` | Egress allow/block policy engine |
| `src/mycelium/security/redaction.py` | Sanitization/redaction transform + fail-closed behavior |
| `src/mycelium/security/audit.py` | Append-only JSONL event log (optionally hash-chain) |
| `tests/vault/unit/*.py` | Schema, envelope, dedupe, novelty, queue transition unit tests |
| `tests/vault/integration/*.py` | Pipeline + policy + audit + quarantine integration tests |
| `tests/vault/e2e/*.py` | End-to-end ingest/repeat/contradiction/promotion/context/frontier flows |
| `tests/vault/fixtures/**` | Golden fixture packs (`url_basic`, `pdf_basic`, overlap, contradictions, corrupted, idempotency-changed) |
| `scripts/spec_lint.py` | LINT-001..LINT-004 enforcement for spec consistency |

## 5) Dependency-Ordered Execution Plan (S0 -> P0 -> P1 -> P2)

## 5.1 S0 Spec Closure (mandatory before implementation decomposition)

| Task | Priority | Depends on | Owner role | Done criteria |
|---|---|---|---|---|
| S0-1 queue lifecycle patch (`review` command + legal transitions) | P0 | none | Systems Architect | `round5.md` includes `5.2.7 review`; immutability semantics executable |
| S0-2 delta schema closure (`warnings`, `failures`, `pipeline_status`) | P0 | none | Data Model Architect | SCH-006 includes fields + AC for zero-claim and failed-run recording |
| S0-3 failure durability wording reconciliation | P0 | none | Systems Architect | AC-PIPE-002-1 no longer conflicts with Delta/Audit durability |
| S0-4 `graduate` strictness/scope/vocabulary patch | P0 | S0-1 | Systems Architect | `all_approved` term adopted; strict mutating behavior mandatory |
| S0-5 stage interface side-effects + frontier output shape patch | P0 | none | Spec Editor | LINT-003 no longer self-violated; `reading_targets` shape includes `score` |
| S0-6 TODO governance appendix (Q1..Q6 options, no forced closure) | P0 | none | Product Owner + Security Lead | TODOs preserved as option matrices with milestone decision gates |

Milestone gate (`S0 exit`): spec patches merged and spec-lint passes.

## 5.2 P0 Substrate Build (parallelizable lanes)

| Task | Priority | Depends on | Owner role | Parallel lane | Done criteria |
|---|---|---|---|---|---|
| P0-1 command envelope + error taxonomy | P0 | S0 | Platform Engineer | A | All new command handlers emit IF-001 keys in tests |
| P0-2 vault layout + schema validators | P0 | S0 | Data Engineer | B | SCH-001..SCH-007 tests green |
| P0-3 deterministic fixture harness | P0 | S0 | QA Engineer | C | TST-G-002 baseline deterministic tests green |
| P0-4 CLI/MCP/tool adapter scaffolding | P0 | P0-1 | Platform Engineer | A | Command names registered across CLI/MCP/tools |
| P0-5 repo hygiene gate hardening | P0 | none | Release Engineer | D | `pytest -q` (without manual `PYTHONPATH`) and lint strategy documented/enforced |

Milestone gate (`P0 exit`): command substrate stable, schemas validated, deterministic test harness operational.

## 5.3 P1 MVP1 Delivery (ingest/delta core)

| Task | Priority | Depends on | Owner role | Parallel lane | Done criteria |
|---|---|---|---|---|---|
| P1-1 pipeline stages capture->queue | P1 | P0-2 | Ingestion Engineer | E | Stage contracts implemented with stage-scoped errors |
| P1-2 idempotency index and revision lineage | P1 | P1-1 | Ingestion Engineer | E | Same payload reuses `source_id`; changed payload records `prior_fingerprint` |
| P1-3 dedupe/match/novelty engine | P1 | P1-1 | ML/Rules Engineer | F | DED-001/2/3 + DEL-002 tests pass |
| P1-4 delta report writer + schema validator | P1 | P1-2,P1-3 | Data Engineer | B | DEL-001 consistency checks pass on golden fixtures |
| P1-5 ingest + delta command endpoints | P1 | P1-4,P0-4 | Platform Engineer | A | CMD-ING-001 + CMD-DEL-001 contract tests pass |
| P1-6 review queue generation for canonical-impacting actions | P1 | P1-3 | Data Engineer | B | REV-001 tests green |

Milestone gate (`P1/MVP1 exit`): URL/PDF ingest, idempotency, dedupe, delta reports, queue proposals all verified.

## 5.4 P2 MVP2 Delivery (review/promotion/frontier/security)

| Task | Priority | Depends on | Owner role | Parallel lane | Done criteria |
|---|---|---|---|---|---|
| P2-1 review queue transition engine | P2 | P1-6,S0-1 | Backend Engineer | B | Invalid transitions deterministically fail with `ERR_QUEUE_IMMUTABLE` |
| P2-2 graduate promotion engine (per-item atomic) | P2 | P2-1,S0-4 | Backend Engineer | B | CMD-GRD-001 + REV-002 integration tests pass |
| P2-3 context/frontier engines | P2 | P1-4,S0-5 | Retrieval Engineer | F | Context citations and frontier scoring tests pass |
| P2-4 egress policy + redaction + audit controls | P2 | S0-6,P0-1 | Security Engineer | G | SEC-001/SEC-002/AUD-001 tests pass |
| P2-5 quarantine/recovery behavior | P2 | P1-1,S0-3 | Reliability Engineer | E | ERR-001/ERR-002 induced-failure tests pass |
| P2-6 migration/rollback framework | P2 | P0-2 | Data Engineer | B | MIG-002 migration + rollback tests pass |

Milestone gate (`P2/MVP2 exit`): queue lifecycle + promotion + frontier + security controls + recovery + migration all green.

## 6) Verification Matrix (Execution-Grade)

| Gate | Command | Expected output | Artifact path |
|---|---|---|---|
| Baseline regression | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q` | Pass (`146 passed` baseline) | `tests/` logs |
| Packaging gate | `cd mycelium-apr-spec && pytest -q` | Must pass collection without path hacks | test collection log |
| Lint gate | `cd mycelium-apr-spec && ruff check src tests` | Must pass (currently failing) | lint log |
| Spec lint gate | `cd mycelium-apr-spec && python scripts/spec_lint.py docs/plans/mycelium_refactor_plan_apr_round5.md` | No LINT-001..004 violations | spec-lint report |
| P0 schema gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/unit/test_schema.py` | SCH validators green | `tests/vault/unit/test_schema.py` |
| P0 envelope gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/unit/test_envelope.py` | IF-001 envelopes validated | `tests/vault/unit/test_envelope.py` |
| P1 dry-run gate | `cd mycelium-apr-spec && PYTHONPATH=src python -m mycelium.cli ingest --url fixtures/url_basic/input.json --dry-run` | `ok=true`, `data.planned_writes` populated, no FS diffs | temp vault diff report |
| P1 idempotency gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_idempotency.py` | source reuse + prior fingerprint checks pass | `Indexes/source_identity.*`, `Reports/Delta/*.yaml` |
| P1 delta integrity gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_delta_report.py` | counts and novelty formula checks pass | `Reports/Delta/<run_id>.yaml` |
| P2 queue lifecycle gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_review_queue.py` | illegal transitions rejected | `Inbox/ReviewQueue/*.yaml` |
| P2 promotion atomicity gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_graduate.py` | per-item atomic promotion, status/path assertions pass | canonical note paths + audit log |
| P2 security/egress gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/security/test_egress_policy.py tests/security/test_redaction.py tests/security/test_audit_events.py` | blocked/allowed behavior + audit fields validated | `Logs/Audit/*.jsonl` fixtures |
| P2 quarantine recovery gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault/integration/test_quarantine_recovery.py` | quarantined artifact + diagnostics; no canonical mutation | `Quarantine/<run_id>/` |
| Release gate | `cd mycelium-apr-spec && PYTHONPATH=src pytest -q tests/vault tests/security` | full vault/security suite pass | CI junit + artifacts |

## 7) Top Risks/Gaps, Mitigations, and Rollback

| # | Risk/Gap | Impact | Mitigation | Rollback trigger | Rollback action |
|---|---|---|---|---|---|
| R1 | Queue lifecycle contract incomplete | Promotion deadlock/unsafe mutation | Implement `review` command + state machine in S0 | Any manual queue edits detected | Block `graduate`; allow draft-only operation |
| R2 | Failure durability wording ambiguity | Divergent implementations, inconsistent recovery | Patch AC-PIPE-002-1 in S0 | Conflicting test expectations across teams | Freeze ingest release until spec patch merges |
| R3 | Delta schema missing warning/failure fields | Incomplete observability and broken ACs | Extend SCH-006; enforce validator | Missing `warnings/failures` in failed runs | Treat run as schema-invalid and quarantine output |
| R4 | No egress policy engine | Potential data leak | Build default-deny policy + redaction + audit in P2 | Unclassified outbound send attempt | Disable external egress path, local-only mode |
| R5 | Path boundary not enforced in write tools | Canonical corruption risk | Add layout guard independent of HITL | Attempted canon path write without promotion | Return `ERR_CANON_WRITE_FORBIDDEN`, no writes |
| R6 | `shell=True` command execution blast radius | Command injection/overreach risk | Add command allowlist/role-scoped policy | Suspicious command pattern or policy miss | Disable `run_command` for non-maintainer roles |
| R7 | Packaging/test invocation drift (`pytest` import failures) | False confidence, CI instability | Fix invocation model and package install strategy in P0 | CI collections fail | Halt milestone advancement |
| R8 | Lint debt hides substantive regressions | Slow review and noisy CI | Establish lint debt burn-down + enforced threshold | Lint error count grows release-over-release | Freeze feature merges; debt sprint |
| R9 | TODO policy decisions forced prematurely | Governance mismatch and rework | Keep Q1..Q6 as option matrices with decision gates | Decision made without gate record | Revert to previous policy profile |
| R10 | Cross-tree drift (`mycelium` vs `mycelium-apr-spec`) | Applying fixes in wrong repository | Treat `mycelium-apr-spec` as source for this program and mirror via explicit porting task | Divergent behavior between trees | Add sync task; block release until parity check passes |

## 8) TODO-Q1..Q6 Decision Options (Recommendations, Not Forced Choices)

Policy note: these remain open decisions; this plan provides options and recommended default paths for human approval.

### TODO-Q1 (ID strategy)
- Option A: slug-only
- Option B: hash-only (`h-<hex>`)
- Option C: slug+hash hybrid (`<slug>--h-<hex>`)  
Recommended path: Option C for generated notes; permit Option A for manually curated canon notes with collision lint checks.
Decision gate: before P1 code freeze.

### TODO-Q2 (provenance locator granularity)
- Option A: minimal string locators
- Option B: source-kind-specific structured locators
- Option C: hybrid structured locator + snippet hash  
Recommended path: Option C for URL/PDF in MVP1; extend to DOI/arXiv/highlights/book/text_bundle by MVP2.
Decision gate: before P1 fixture lock.

### TODO-Q3 (confidence rubric)
- Option A: no confidence field in MVP1
- Option B: simple deterministic heuristic
- Option C: domain-calibrated weighted rubric  
Recommended path: Option B advisory in MVP1; evaluate Option C at MVP2 planning.
Decision gate: before P2 ranking release.

### TODO-Q4 (authoritative review UX)
- Option A: CLI-only authority
- Option B: plugin-only authority
- Option C: command/API authority with CLI + plugin clients  
Recommended path: Option C (single backend authority, multiple frontends).
Decision gate: before P2 review/promotion rollout.

### TODO-Q5 (egress allowlist/blocklist/sanitization)
- Option A: strict default-deny with explicit allowlist and fail-closed redaction
- Option B: permissive default-allow with blocklist
- Option C: report-only mode then enforce  
Recommended path: staged A via C transition (report-only burn-in, then enforce default-deny).
Decision gate: before enabling any external vault egress.

### TODO-Q6 (performance targets)
- Option A: qualitative-only targets
- Option B: fixed p95 budgets for ingest/delta/frontier
- Option C: adaptive budgets by source kind/size  
Recommended path: Option B for MVP1 (`ingest`/`delta`), evaluate Option C for MVP2 frontier/retrieval.
Decision gate: before P1 benchmark suite freeze.

## 9) Milestone Done Criteria (Explicit)

- `S0 Done`: spec defects patched; TODO option matrix and decision gates documented; spec-lint passes.
- `P0 Done`: envelope + schemas + deterministic harness + adapter scaffolding merged; packaging/lint gates ratcheted.
- `P1 Done (MVP1)`: URL/PDF ingest, idempotency, dedupe, delta report, queue proposal flows fully tested with golden fixtures.
- `P2 Done (MVP2)`: queue transition lifecycle, graduate atomicity, context/frontier, egress policy, audit, quarantine, and migration rollback all passing.

## 10) Immediate Next Actions

1. Apply S0 spec patch PR first (contract contradictions + output schema gaps + TODO option appendix).
2. Create engineering beads/issues from P0 task table only after S0 merge.
3. Stand up vault/security test directories before implementing pipeline logic, so acceptance criteria are executable from day one.
4. Record TODO-Q1..Q6 gate decisions in change control log before P1/P2 freeze points.
