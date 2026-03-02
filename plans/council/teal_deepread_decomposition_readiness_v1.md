# TealPeak Deep-Read Decomposition Readiness Brief (v1)

Date: 2026-03-02  
Role: Worker (Planning)  
Scope: Security, failure/recovery semantics, egress/audit policies, safety invariants  
Primary spec: `docs/plans/mycelium_refactor_plan_apr_round5.md` (v1.1)

## 1) Context

### Prior art
- CASS query run: `cass search "mycelium refactor decomposition readiness security failure egress audit" --limit 5`
- Result: no prior artifacts found.

### Repository evidence reviewed
- Spec: `docs/plans/mycelium_refactor_plan_apr_round5.md` (full read)
- Repo contracts/docs: `AGENTS.md`, `README.md`, `ROADMAP.md`
- Source: `src/mycelium/{cli.py,llm.py,orchestrator.py,tools.py,mcp/server.py}`
- Tests: `tests/{test_llm.py,test_mcp.py,test_orchestrator.py,test_tools.py}`
- Baseline tests: `PYTHONPATH=src pytest -q` => `86 passed`

## 2) Architecture Deep Sketch (for decomposition)

### 2.1 State Machine (normative target from spec)

#### A) Ingestion + Review + Promotion lifecycle
States: `[input_received, captured, normalized, fingerprinted, extracted, compared, delta_written, queued, pending_review, approved, rejected, promoted, quarantined, failed]`

Transitions:
- `input_received -> captured`: capture success
- `captured -> normalized`: normalize success
- `normalized -> fingerprinted`: fingerprint success
- `fingerprinted -> extracted`: extract success
- `extracted -> compared`: compare success
- `compared -> delta_written`: delta report persisted (success or failure-finalization)
- `delta_written -> queued`: queue proposals created
- `queued -> pending_review`: queue item persisted with `status=pending_review`
- `pending_review -> approved`: `review` approve / approve_all / approve_selected
- `pending_review -> rejected`: `review` reject
- `pending_review -> pending_review`: `review` hold (with `hold_until`)
- `approved -> promoted`: `graduate` strict validation + canonical apply + audit append
- `* -> quarantined`: invalid/partial artifact handling (`ERR-002` path)
- `capture|normalize|fingerprint|extract|compare|delta|propose_queue -> failed`: explicit stage-scoped error (`PIPE-001`, `ERR-001`)

Initial: `input_received`  
Terminal: `[promoted, rejected, failed]`

#### B) Egress policy lifecycle
States: `[report_only, enforce]`

Transitions:
- `report_only -> enforce`: explicit mode transition command/config change with audit event (`SEC-003`)
- `enforce -> report_only`: explicit rollback transition with audit event

Initial: `report_only` (burn-in)  
Terminal: `[]`

### 2.2 Data Flow
1. Data enters through command interface (`ingest`, `review`, `graduate`, `context`, `frontier`).
2. Pipeline writes Draft artifacts (`Inbox/*`) + durable artifacts (`Reports/Delta/*`, `Logs/Audit/*`, `Quarantine/*`).
3. Review transitions mutate queue state only via `review`.
4. Promotion (`graduate`) is sole canonical mutation gate (`Sources/`, `Claims/`, etc.).
5. Context/frontier reads canonical graph + derived indexes.
6. Any external egress passes through policy check + optional sanitization + auditable emit.

### 2.3 Component Boundaries
- `interface/commands`: transport-agnostic command handlers + IF-001 envelope.
- `vault/layout`: canonical vs draft path classifier + guardrails.
- `schemas/validators`: SCH-001..010 + NAM/LNK enforcement.
- `pipeline/ingest`: capture/normalize/fingerprint/extract/compare/delta/propose_queue.
- `review/queue`: queue storage + `review` + `review_digest` + `graduate`.
- `security/egress`: allowlist/blocklist/sanitizer/mode-control.
- `audit/logging`: append-only JSONL writer + audit event schema.
- `recovery/quarantine`: failure-finalization and diagnostics sidecars.
- `retrieval`: `context` and `frontier` deterministic ranking.
- `tests/fixtures/bench`: deterministic fixtures, regression and p95 gates.

## 3) Requirement Coverage Map (evidence-backed)

Status key: `implemented | partial | missing | spec-defect`

| Requirement(s) | Status | Repository evidence | Gap / decomposition implication |
|---|---|---|---|
| IF-001 + CMD surface (`ingest`, `delta`, `review`, `review_digest`, `graduate`, `context`, `frontier`) | missing | CLI only registers `run/status/auto` (`src/mycelium/cli.py:293-376`); tool layer exposes only 7 mission tools (`src/mycelium/tools.py:21-207`, `tests/test_tools.py:60-67`) | New command API layer required before any vault workflow can execute. |
| INV-001, VLT-001 (canonical vault substrate/boundary) | missing | No vault directory model in code; generic file IO in MCP (`src/mycelium/mcp/server.py:285-324`) | Must introduce vault path taxonomy and write-guard middleware. |
| INV-002 (canonical writes only via promotion) | missing | `_write_file` writes arbitrary path with no canonical gate (`src/mycelium/mcp/server.py:324`) | Hard blocker for safe decomposition; canonical mutation path must be centralized in `graduate`. |
| INV-003 (draft-first outputs) | missing | No ingestion artifact pipeline or draft-scope routing exists in source/tests | Requires draft artifact factories and planned-write ledger. |
| INV-004 + SCH-003 provenance minima | missing | No claim/source note schemas or provenance validator in repo | Implement schema package first; gate promotions on provenance checks. |
| INV-005 + IDM-001 idempotent `(locator,fingerprint)->source_id` | missing | No source identity index or source note lifecycle in code | Add index storage + deterministic identity service before ingest E2E. |
| SCH-001..SCH-005 note schemas | missing | No schema validator module; tests target mission progress utilities only (`tests/test_mcp.py`, `tests/test_tools.py`) | Schema engine is foundational dependency for queue/promotion. |
| SCH-006 Delta Report | missing | No `Reports/Delta` writer in codebase | Implement delta schema writer with explicit empty arrays + pipeline status semantics. |
| SCH-007 Review Queue Item | missing | No queue item persistence or immutable-state checks in code | Implement queue storage + transition guardrail before review/graduate. |
| SCH-008 Extraction Bundle | missing | No extract stage artifacts; no ingest pipeline modules | Add staged extract artifact emission and validation path. |
| SCH-009 Review Packets + SCH-010 Decision Record | missing | No `review_digest`/`review` command implementations | Must land packet schema + deterministic apply before promotion automation. |
| NAM-001 + LNK-001 | missing | No note-id validator/link checker modules | Needed before strict promotion/canonical graph integrity checks. |
| IF-002 (dry-run writes + planned_writes) | partial | `run_agent(..., dry_run=True)` returns prompt only (`src/mycelium/orchestrator.py:336-342`); no planned write schema for vault commands | Dry-run contract must be rebuilt around command write plans. |
| IF-003 (strict mode semantics) | missing | No strict-mode option in current command surface; no schema warning downgrade path | Requires validator severity framework + command-level strict flag plumbing. |
| PIPE-001 / PIPE-003 stage-scoped failures | missing | No capture->normalize->... stage engine in code | Build staged pipeline with canonical stage names and structured errors. |
| PIPE-002 + ERR-002 (atomic staging + quarantine) | missing | No quarantine subsystem; no canonical/draft atomic boundary | Implement failure finalization path with sidecar diagnostics. |
| DED-001/002/003 + DEL-001/002 + CONF-001 | missing | No dedupe/comparator/canonicalization/novelty modules | Create deterministic claim canonicalization and match engine before Delta compliance. |
| REV-001/001A/001B/002/003/004 | missing | No review queue lifecycle; no `graduate`; no git-mode packet apply | Needs queue FSM + decision artifacts + per-item atomic promotion design. |
| AUD-001/AUD-002 append-only JSONL | missing | No append-only audit log in current flow | Implement append-only writer with tamper-evident checks and event schema. |
| SEC-001/002/003/004 egress policy + sanitization + audit | missing | LLM calls go direct to `litellm.completion` (`src/mycelium/llm.py:223`); no allowlist/blocklist/redaction path | Security-critical lane required before enabling externalized context commands. |
| ERR-001 recoverable explicit failure behavior | partial | CLI auto-loop has iteration/cost/failure breakers (`src/mycelium/cli.py:159-214`) but no vault pipeline stage recovery | Reuse breaker patterns, but add stage-scoped recoverability + retry semantics to ingest pipeline. |
| MIG-001/MIG-002 migration + rollback | missing | No schema migration framework/tests found | Must define migration/rollback harness before any breaking schema rollout. |
| MVP1-001, MVP2-001 capability bundles | missing | Core commands absent; tests are orchestration-era (`tests/test_orchestrator.py`) | Plan requires full re-baseline from command/schemas upward. |
| TST-U/I/E2E/G/R/P coverage requirements | missing | Current suite validates orchestration tools (`86 passed`) but no vault fixtures or perf benches | Stand up deterministic fixture stack and benchmark harness as dedicated lane. |
| Security primitive: implementer HITL approvals (non-spec legacy control) | implemented | `check_hitl_approval` and MCP `_requires_approval` (`src/mycelium/orchestrator.py:237-258`, `src/mycelium/mcp/server.py:49-64`), tested (`tests/test_orchestrator.py:159-171`, `tests/test_mcp.py:300-382`) | Keep as defense-in-depth; do not treat as substitute for vault/egr/security policy. |
| LLM reliability retries (supporting control) | implemented | Retry loop in `complete` (`src/mycelium/llm.py:195-301`), tested (`tests/test_llm.py:181-253`) | Reuse for extract/egress clients; add stage+policy context to errors/audit. |
| Spec TODO-Q-NAM-1 (migration compatibility mode for IDs) | spec-defect | Open TODO in spec §4.3.1 | Blocker for note-id validator behavior and migration acceptance tests. |
| Spec TODO-Q-REV-1 (hold TTL config/resurface mechanism) | spec-defect | Open TODO in spec §8.1.1, despite fixed 14-day policy | Blocker for deterministic hold resurfacing implementation and tests. |
| Spec TODO-Q-REV-2 (Git mode enablement/commit convention) | spec-defect | Open TODO in spec §8.3.1 | Blocks REV-004 decomposition granularity and commit audit semantics. |
| Spec TODO-Q-FRN-1 (deterministic factor derivations) | spec-defect | Open TODO in spec §5.2.7 | Blocks precise frontier scoring implementation even if aggregate formula is fixed. |
| Spec TODO-Q-SEC-1 (burn-in tracking + mode storage) | spec-defect | Open TODO in spec §9.2 | Critical blocker for enforceable SEC-003 transition behavior. |

## 4) Ambiguity Gate Result

Result: **CONDITIONAL FAIL**  
Gate rationale: decomposition into executable beads is unsafe until blocking spec ambiguities are resolved for policy-critical lanes.

`NO_BEAD_CREATION_DUE_TO_AMBIGUITY`

### Blocking ambiguities (must resolve first)
1. `TODO-Q-SEC-1`: burn-in clock origin, mode storage location, and transition authority are unspecified.
2. `TODO-Q-REV-1`: hold TTL resurface mechanism lacks deterministic source-of-truth behavior.
3. `TODO-Q-REV-2`: Git Mode enablement and commit metadata contract are undefined.
4. `TODO-Q-NAM-1`: compatibility-mode rules can alter validator acceptance and migration safety.
5. `TODO-Q-FRN-1`: deterministic derivation of frontier factors remains unspecified.

### Proposed concrete decisions (non-mandate recommendations)
- For `TODO-Q-SEC-1`: store egress policy in `Config/egress_policy.yaml` with fields `{mode, burn_in_started_at, last_transition_at, transitioned_by, transition_reason}`; compute burn-in as wall-clock delta at egress-time; require explicit transition command/event (no silent auto-switch).
- For `TODO-Q-REV-1`: store hold metadata directly in decision record + queue sidecar; resurface logic derived from `hold_until <= today` during digest generation.
- For `TODO-Q-REV-2`: Git Mode toggle in config; commit message convention `promote:{source_id}:{packet_id}:{run_id}`.
- For `TODO-Q-NAM-1`: compatibility mode read-only for legacy slug IDs; all new machine-generated notes remain hybrid format.
- For `TODO-Q-FRN-1`: freeze deterministic factor derivation formulas in a dedicated ADR before coding frontier.

## 5) Decomposition-Ready Task Clusters (3-8)

### Cluster C0: Command + Envelope Foundation
- Owner role: Platform
- Scope: Implement IF-001 output envelope, command registry, common strict/dry-run flags.
- Dependencies: none
- Done criteria:
  - Command stubs exist for `ingest|delta|review|review_digest|graduate|context|frontier`.
  - All command responses pass envelope contract tests.

### Cluster C1: Vault Boundary + Path Policy Core
- Owner role: Platform + Security
- Scope: Canonical/draft path classifier, canonical write guard (`ERR_CANON_WRITE_FORBIDDEN`), safe path normalization.
- Dependencies: C0
- Done criteria:
  - Canonical writes blocked outside promotion path.
  - Boundary tests prove no canonical diffs without promotion.

### Cluster C2: Schemas + Validators + Deterministic IDs
- Owner role: Data Model
- Scope: SCH-001..SCH-010 validators, NAM-001 checker, LNK-001 helper, deterministic IDs/keys.
- Dependencies: C0, C1
- Done criteria:
  - Invalid fixtures fail with expected codes.
  - Deterministic test mode yields stable normalized outputs.

### Cluster C3: Ingestion Pipeline + Delta + Queue
- Owner role: Ingestion
- Scope: Stage engine (`capture..propose_queue`), extraction bundle, delta report, queue item generation, idempotency index.
- Dependencies: C1, C2
- Done criteria:
  - Successful URL/PDF ingest creates source note, extraction bundle, delta report, queue items.
  - Stage failures are explicit and stage-scoped.

### Cluster C4: Review Lifecycle + Promotion Apply
- Owner role: Review/Promotion
- Scope: `review_digest`, `review`, `graduate`, queue FSM, per-item atomic apply, optional Git Mode contract.
- Dependencies: C2, C3
- Done criteria:
  - Legal transitions only; immutable-state errors enforced.
  - `graduate --from_digest` deterministic on fixture.

### Cluster C5: Security/Audit/Recovery Lane
- Owner role: Security + Reliability
- Scope: Append-only audit JSONL, egress policy engine, sanitization/redaction, quarantine + diagnostic sidecars.
- Dependencies: C1, C2, C3 (C4 for promotion audit completeness)
- Done criteria:
  - SEC-001..004 and AUD-001..002 integration tests passing.
  - Failure fixtures produce quarantine artifacts and no canonical corruption.

### Cluster C6: Context + Frontier Retrieval
- Owner role: Retrieval
- Scope: bounded `context`, deterministic `frontier` scoring and factors, citation enforcement.
- Dependencies: C2, C4, C5 (for egress-safe output path)
- Done criteria:
  - Seeded contradiction/question fixtures produce deterministic frontier outputs.
  - Context output bounded and citation-complete.

### Cluster C7: Fixtures/Regression/Perf Gate
- Owner role: QA/Release
- Scope: golden fixtures, regression suite, perf bench thresholds, migration/rollback tests.
- Dependencies: C2 onward (parallelized as subsystems mature)
- Done criteria:
  - TST-U/I/E2E/G/R/P gates operational.
  - p95 thresholds enforced with reproducible hardware metadata.

### Dependency graph
- `C0 -> C1 -> C2 -> C3 -> C4 -> C6`
- `C2 -> C7`
- `C3 -> C5`
- `C4 -> C5`
- `C5 -> C6`
- `C4 -> C7`

Parallelization opportunities:
- C7 fixture scaffolding can start after C2 while C3/C4 build.
- C5 audit writer can start early (after C1/C2) before full egress enforcement.
- C6 retrieval prototypes can start with fixture mocks, but finalization waits on C4/C5 outputs.

## 6) Risks and Rollback Points for Decomposition

| Risk | Trigger | Mitigation | Rollback point |
|---|---|---|---|
| Canonical boundary bypass | Any non-`graduate` code path writes canonical directories | Centralize writes behind path-policy service + deny-by-default | Revert to last passing boundary-gate commit; disable write commands by feature flag |
| Shell execution abuse from legacy tool path | `run_command` remains unrestricted (`shell=True`) | Fence legacy MCP tools behind explicit development mode; remove from vault command plane | Feature-flag off command execution lane |
| Audit tampering / rewrite | Logs rewritten instead of append-only | Dedicated append-only writer + file-lock + line-hash validation | Switch to immutable daily log files and disable mutation endpoints |
| Egress leakage before policy complete | Commands call provider directly without policy gate | Route all outbound payloads through policy adapter first; default deny in enforce mode | Force `report_only` and block non-audited outbound calls |
| Non-atomic promotion corruption | Batch apply partially mutates canonical content | Per-item transaction staging + temp paths + commit/rename | Rehydrate from last canonical git checkpoint; replay approved queue ids |
| Queue state drift | Direct edits bypass `review` transitions | Make queue files immutable except command transitions; state machine tests | Restore queue snapshot + decision records from audit trail |
| Determinism drift in fixtures | Time/id randomness leaks into artifacts | Deterministic mode clock/id injection and normalization harness | Pin deterministic fixtures and reject drift in CI |
| Frontier ranking instability | Factor formulas or tie-break changes silently | Factor ADR + explicit fixture snapshots + byte-stable output tests | Revert frontier scoring module to prior tagged snapshot |
| Migration incompatibility | NAM/schema upgrades invalidate existing notes | Migration dry-run + rollback scripts + compatibility mode boundaries | Restore canonical notes from pre-migration backup and rerun validator |
| Ownership deadlock between lanes | Security/pipeline/review teams block each other | Declare dependency contracts and integration checkpoints per cluster | Freeze downstream lanes; continue independent test/fixture prep |

## 7) Suggested First Decomposition Pass Order

1. Resolve blocking TODO decisions (SEC-1, REV-1, REV-2, NAM-1, FRN-1) as ADRs.
2. Land C0 command/envelope skeleton with no-op handlers and contract tests.
3. Land C1 vault boundary/path policy guardrails (deny unsafe writes first).
4. Land C2 schema+validator core and deterministic ID utilities.
5. Land C3 ingest/delta/queue pipeline in strict draft-scope only mode.
6. Land C4 review/review_digest/graduate lifecycle with per-item atomic apply.
7. Land C5 audit+egress+quarantine controls (fail-closed default).
8. Land C6 context/frontier retrieval and C7 full fixture/perf gate hardening.

## 8) Decomposition Readiness Verdict

- Current readiness for safe execution decomposition: **Not ready for bead decomposition** due to unresolved policy ambiguities in security/review/frontier identity semantics.
- Readiness for preparatory planning decomposition: **Ready** for dependency-ordered cluster planning (C0-C7) with explicit ambiguity resolution checkpoint first.
