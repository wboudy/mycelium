## Plan: Human Decision UX + Nightly Review Workflow Decomposition Readiness (APR Round 5)

### Context
- Prior art: `cass search "human decision UX nightly review workflow operator readability" --limit 5` returned no results.
- Primary spec read in full: `docs/plans/mycelium_refactor_plan_apr_round5.md` (v1.1, 1282 lines).
- Existing components affected:
  - CLI orchestration only (`src/mycelium/cli.py`: `run`, `status`, `auto`; parser declarations at lines 293, 318, 334).
  - Orchestrator mission execution + HITL gate (`src/mycelium/orchestrator.py`: `run_agent`, `check_hitl_approval`).
  - MCP/tool layer with exactly 7 tools (`src/mycelium/tools.py`, `src/mycelium/mcp/server.py`; verified by `tests/test_tools.py::test_seven_tools`).
  - No vault command surfaces (`ingest`, `review`, `review_digest`, `graduate`, `context`, `frontier`) in `src/` or `tests/` (symbol scan returned no definitions).
- Baseline validation:
  - `PYTHONPATH=src pytest -q` passes (`86 passed in 5.60s`).

### Requirement Coverage Map

| Requirement / Decision Area | Repository Evidence | Status | Gap / Blocker |
|---|---|---|---|
| `INV-002` canonical mutation only by Promotion | HITL exists only for implementer shell/file tools (`src/mycelium/mcp/server.py:_requires_approval`, `_write_file`, `_run_command`) | partial | No canonical-scope boundary model, no promotion command, no `ERR_CANON_WRITE_FORBIDDEN` pathing by vault scope. |
| `IF-001` command envelope | Current CLI/MCP responses are heterogeneous dict/strings, not required envelope (`ok/command/timestamp/...`) | missing | Need shared command response adapter before implementing vault commands. |
| `IF-002` dry-run for write-capable commands | `run_agent(..., dry_run=True)` exists (`src/mycelium/orchestrator.py`) | partial | Spec requires dry-run semantics on vault write commands; those commands do not exist yet. |
| `IF-003` strict-mode semantics | No strict-mode flags in current command surface | missing | Need strict-mode policy layer and warning/error downgrade strategy. |
| `SCH-009` review packet schema | No `ReviewDigest` artifact writers in code or tests | missing | Packet model and schema validator absent. |
| `SCH-010` review decision record schema | No review decision record writer | missing | Requires durable decision ledger implementation. |
| `CMD-REV-001` authoritative `review` transitions | No `review` command definitions in CLI/MCP/tools | missing | Transition engine + immutable transition checks absent. |
| `CMD-RDG-001` `review_digest` grouped-by-source flow | No digest command or grouping code | missing | Must build packetization/readability layer first for worker focus area. |
| `CMD-GRD-001` `graduate` atomic apply | No `graduate` command or promotion subsystem | missing | Need promotion orchestrator + per-item atomicity + strict enforcement. |
| `REV-001A` reading-first workflow (approve_all/approve_selected/hold/reject) | Defined in spec only (`docs/plans/...:945+`) | missing | Core worker focus area; no UX artifacts/flows yet. |
| `REV-001B` constrained auto-approval lane | Defined in spec only (`docs/plans/...:961+`) | missing | No policy engine to classify low-risk semantic vs non-semantic changes. |
| `REV-002` explicit queue state transitions | No queue status state machine in code | missing | No persistence model for legal/illegal transitions. |
| `REV-003` strict promotion semantics + audit | No canonical promotion path in implementation | missing | No validator chain for SCH-001..010 at promotion time. |
| `AUD-002` JSONL append-only audit files | No JSONL audit subsystem under `Logs/Audit/` | missing | Need append-only writer + schema checks. |
| `SEC-003` egress mode transitions (`report_only -> enforce`) | No egress policy module in source | missing | Mode state and transition audit not implemented. |
| `CMD-FRN-002` deterministic frontier scoring | No `frontier` command implementation | missing | Also depends on unresolved factor derivations (`TODO-Q-FRN-1`). |
| `PERF-001` benchmark targets + gates | No benchmark harness in tests | missing | Need benchmark runner + threshold gating in CI. |
| `MVP1-001` ingest + digest + constrained auto-lane | No ingest/review/promotion pipeline in current codebase | missing | MVP1 work is net-new subsystem build. |
| `MVP2-001` queue lifecycle + deterministic frontier | No queue lifecycle nor frontier subsystem | missing | Depends on MVP1 storage/contracts first. |
| `TODO-Q-RDG-1` invocation model (manual/scheduler/client) | Open TODO in spec (`docs/plans/...:641`) | spec-defect | Decomposition blocked for ownership of nightly trigger semantics. |
| `TODO-Q-REV-1` hold TTL storage/resurface | Open TODO (`docs/plans/...:958`) | spec-defect | Needed for safe implementation of hold lifecycle and resurfacing behavior. |
| `TODO-Q-REV-2` Git Mode enablement/conventions | Open TODO (`docs/plans/...:1009`) | spec-defect | Promotion decomposition incomplete until commit boundary/config is fixed. |
| `TODO-Q-SEC-1` burn-in tracking + egress mode storage | Open TODO (`docs/plans/...:1086`) | spec-defect | Security workflow decomposition blocked on configuration authority. |

### Ambiguity Gate Result (NO_BEAD_CREATION_DUE_TO_AMBIGUITY)
Status: **BLOCKED FOR BEAD CREATION**

Blocking ambiguities that prevent safe decomposition handoff:
1. `TODO-Q-RDG-1` (`review_digest` trigger model): no authoritative invocation owner (manual vs scheduler vs client integration).
2. `TODO-Q-REV-1` (hold TTL resurfacing): hold metadata storage and resurfacing mechanism unresolved.
3. `TODO-Q-REV-2` (Git Mode config): commit granularity policy is set, but enablement and commit-message minimum contract are unresolved.
4. `TODO-Q-SEC-1` (egress burn-in): policy transition state store and transition trigger unresolved.
5. `TODO-Q-FRN-1` (frontier factors): weighted formula is defined, but factor derivations remain unspecified.

Non-blocking note:
- Q1..Q6 baseline policy decisions are already resolved in spec v1.1 decision record (`docs/plans/...:1268+`) and should remain settled unless defects are discovered.

### Architecture

#### State Machine (Review Queue + Nightly Digest)
States: [draft_proposed, pending_review, packeted_for_digest, approved, rejected, held, eligible_for_graduate, promoted_to_canon, apply_failed]
Transitions:
  draft_proposed → pending_review: `ingest` writes queue item (`Propose + Queue` stage)
  pending_review → packeted_for_digest: `review_digest` groups queue items into source packet(s)
  packeted_for_digest → approved: `review` decision `approve_all` or `approve_selected`
  packeted_for_digest → rejected: `review` decision `reject`
  packeted_for_digest → held: `review` decision `hold` with `hold_until`
  held → packeted_for_digest: hold TTL resurfaces item(s) into next eligible digest
  approved → eligible_for_graduate: packet decisions resolved and ready for apply
  eligible_for_graduate → promoted_to_canon: `graduate` strict validation + promotion apply succeeds
  eligible_for_graduate → apply_failed: `graduate` validation/promotion conflict fails for item
  apply_failed → eligible_for_graduate: reviewer resolves issue and re-approves
Initial: draft_proposed
Terminal: [rejected, promoted_to_canon]

#### Data Flow
1. Entry:
   - Source enters via `ingest` input contract.
2. Transform:
   - Capture/Normalize/Fingerprint/Extract/Compare/Delta/Propose stages produce Draft artifacts (`Inbox/Sources`, `Inbox/ReviewQueue`, `Reports/Delta`).
3. Human decision path:
   - `review_digest` aggregates queue items by source into packets (`Inbox/ReviewDigest`).
   - Reviewer action (`approve_all`, `approve_selected`, `hold`, `reject`) is persisted via `review` decision records.
4. Apply path:
   - `graduate --from_digest` applies approved items atomically per queue item to canonical scope.
5. Exit:
   - Canonical notes updated, audit JSONL appended, and optional Git Mode commit(s) emitted.

#### Component Boundaries
1. `command-adapters`:
   - CLI/MCP entrypoints and transport normalization into IF-001 envelope.
   - Can evolve independently from core vault logic.
2. `vault-domain`:
   - Schemas (SCH-001..010), naming/link validation, strict/dry-run policy.
   - Owns canonical vs draft boundary checks.
3. `ingestion-engine`:
   - Stage pipeline (capture -> propose_queue), idempotency index, delta generation.
4. `review-engine`:
   - Queue state transitions, packet generation, decision record persistence, hold resurfacing logic.
5. `promotion-engine`:
   - `graduate` strict validation, atomic apply, Git Mode boundary.
6. `governance-observability`:
   - JSONL audit writer, egress policy mode transitions, benchmark/perf artifacts.

### Decomposition-Ready Task Clusters

#### Cluster A: Command Contract Foundation
- Scope: Implement IF-001 envelope + IF-002/IF-003 shared middleware for future vault commands.
- Done criteria:
  - Uniform response envelope returned by all new vault commands.
  - Dry-run/strict behavior test harness available for command modules.
- Dependencies: none.

#### Cluster B: Review Data Model + Persistence
- Scope: Implement SCH-007/009/010 model objects and validators (queue item, packet, decision record).
- Done criteria:
  - Schema validation tests for valid/invalid packet + decision fixtures.
  - Deterministic serialization ordering in deterministic mode.
- Dependencies: A.

#### Cluster C: Review UX Engine (Human Decision Focus)
- Scope: `review_digest` + `review` packet and queue transitions, including `hold` behavior.
- Done criteria:
  - End-to-end packet workflow supports `approve_all`, `approve_selected`, `hold`, `reject`.
  - Immutable transition checks return `ERR_QUEUE_IMMUTABLE`.
- Dependencies: B.

#### Cluster D: Promotion Apply Engine
- Scope: `graduate` (`queue_id`, `all_approved`, `from_digest`) with strict validation and per-item atomicity.
- Done criteria:
  - Only approved items are promotable.
  - Failed items do not mutate canonical scope while others can proceed.
- Dependencies: B, C.

#### Cluster E: Governance Layer (Audit + Egress Mode)
- Scope: JSONL append-only audit writer + explicit egress mode transition storage and events.
- Done criteria:
  - Audit append-only tests pass.
  - `report_only -> enforce` transitions are explicit/auditable.
- Dependencies: A.

#### Cluster F: Ingestion + Dedupe + Frontier Baseline Integration
- Scope: `ingest`, `delta`, queue generation, confidence/novelty, deterministic `frontier` scoring.
- Done criteria:
  - MVP1 ingest artifacts produced and validated.
  - Frontier scoring deterministic with defined factors.
- Dependencies: A, B, E (and `TODO-Q-FRN-1` closure before final frontier implementation).

### Dependency Graph
- A -> B, E
- B -> C, D
- C -> D
- A + B + E -> F
- `TODO-Q-RDG-1` must close before C finalization
- `TODO-Q-REV-1` must close before C hold-resurface finalization
- `TODO-Q-REV-2` must close before D Git Mode finalization
- `TODO-Q-SEC-1` must close before E mode-transition finalization
- `TODO-Q-FRN-1` must close before F frontier finalization

### Risks and Rollback Points for Decomposition

#### Risks
- R1: Under-specified nightly trigger model causes divergent implementations between CLI/plugin/automation.
- R2: Hold TTL resurfacing semantics drift without a single metadata authority.
- R3: Git Mode ambiguity causes commit-history instability and hard-to-review packet applies.
- R4: Egress mode storage ambiguity leads to silent policy drift.
- R5: Frontier factor derivation ambiguity creates nondeterministic ranking despite deterministic formula.

#### Rollback Points
1. After Cluster A: keep adapters only; no domain data mutation introduced.
2. After Cluster B: schemas can be frozen with fixture-only artifacts before command wiring.
3. After Cluster C: if UX flow fails acceptance, revert to queue-item direct review mode while retaining validators.
4. After Cluster D: if promotion atomicity fails, hold apply path behind dry-run-only gate until fixed.
5. After Cluster E: if egress transition logic unstable, remain in explicit `report_only` and block enforcement flip.
6. After Cluster F: if frontier determinism fails, ship ingest/digest without frontier ranking until factor derivations are fixed.

### Suggested First Decomposition Pass Order
1. Close ambiguity blockers (`TODO-Q-RDG-1`, `TODO-Q-REV-1`, `TODO-Q-REV-2`, `TODO-Q-SEC-1`, `TODO-Q-FRN-1`) with explicit ownership and storage locations.
2. Deliver Cluster A (command contract foundation) and lock test helpers for envelope/dry-run/strict.
3. Deliver Cluster B (review schemas + validators) to stabilize readable packet artifacts.
4. Deliver Cluster C (review UX engine) to satisfy human decision UX and nightly packet workflow.
5. Deliver Cluster D (graduate apply) with strict-only non-dry-run policy and per-item atomicity.
6. Deliver Cluster E (audit/egress transition governance) to harden policy and traceability.
7. Deliver Cluster F (ingest/delta/frontier integration) last, after review/apply governance rails are stable.

### Dependencies
- Blocked by:
  - Spec ambiguity TODOs listed in Ambiguity Gate section.
- Blocks:
  - Bead decomposition and implementation swarms for nightly review workflow and promotion engine.
