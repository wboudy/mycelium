# Council Merged Recommendations (Blue + Teal + Copper + Silver)

Date: 2026-03-01
Scope: `docs/plans/mycelium_refactor_plan_apr_round5.md`
Inputs:
- `blue_systems_contract_review.md`
- `teal_security_failure_review.md`
- `copper_execution_testability_review.md`
- `silver_todo_decisions_review.md`

## 1. Council Consensus

The council agrees on two top-level conclusions:

1. The refactor plan is directionally strong but not implementation-ready due to contract defects and unresolved policy decisions.
2. Current repository implementation is orchestration/MCP tooling, not vault ingestion, so delivery must be staged as a new subsystem with strict gates.

## 2. Must-Fix Spec Defects Before Decomposition

These are consensus P0 blockers (spec-level):

1. Review queue lifecycle is incomplete.
- Add an explicit queue decision command (`review`) with legal transitions `pending_review -> approved|rejected` and immutable-state behavior.

2. Failure durability rules conflict.
- Reconcile Delta/Audit durability with Quarantine semantics so failure behavior is unambiguous and testable.

3. Delta schema is underspecified vs requirements.
- Add required `warnings`, `failures`, and `pipeline_status` fields to Delta Report schema to satisfy extraction/link/failure requirements.

4. Pipeline stage ordering/dataflow mismatch.
- Define explicit link-proposal generation stage before Delta consumption, and align Queue stage inputs accordingly.

5. Promotion contract ambiguity.
- Enforce strict validation for mutating `graduate` execution; narrow validation scope to applicable note schemas; resolve `all_reviewed` vs status vocabulary mismatch.

6. Output contract gap for frontier ranking.
- Declare explicit `score`/rank field in `reading_targets` output schema.

## 3. TODO Decisions (Council Recommendation)

### Q1 ID strategy
Decision: adopt slug+hash hybrid for machine-generated canonical notes.
- Recommended format: `<slug>--h-<12hex>`.
- Human-authored/manual notes may remain slug-only initially.

### Q2 provenance locator granularity
Decision: require source-kind-specific locator object minima.
- URL/PDF minima are mandatory before MVP1.
- Other source kinds can finalize implementation in MVP2+.

### Q3 confidence rubric
Decision: deterministic weighted rubric by domain profile.
- Advisory only in MVP1.
- Must be finalized before MVP2 frontier/review prioritization.

### Q4 authoritative review UX
Decision: command/API (`graduate` + queue transition command) is source of truth.
- Obsidian/plugin can be a client surface later, not a second authority.

### Q5 egress allowlist/blocklist + sanitization
Decision: default-deny egress with explicit allowlist, strong blocklist, always-on sanitization, and mandatory audit digest/context.
- Must be decided and codified before MVP1.

### Q6 performance targets
Decision: set explicit numeric MVP1 ingest/delta p95 targets and artifacted benchmark policy now.
- Retrieval/frontier threshold enforcement can be finalized in MVP2.

## 4. MVP Gating (Consensus)

Before MVP1 implementation starts, close:
- Spec defect blockers in Section 2.
- TODO decisions: Q1, Q2(URL/PDF subset), Q4(authority model), Q5, Q6(ingest/delta targets).

May defer until MVP2:
- Q3 full calibration policy.
- Q2 non-MVP1 source-kind implementation specifics.
- Retrieval/frontier performance enforcement details.

## 5. Execution Order

### S0: Spec closure
- Patch round-5 spec with resolved contracts and TODO decisions.
- Add missing schemas/fields and transition semantics.
- Remove contradictory language.

### P0: Substrate build
- Shared command envelope + deterministic error taxonomy.
- Vault layout/schema/validator modules.
- Deterministic fixture/test harness.
- Thin CLI/MCP/tool adapters to unified core.

### P1: MVP1 delivery
- Ingest (URL/PDF), idempotency, dedupe/match, delta report, review queue proposals.
- Dry-run support with planned writes.
- URL/PDF provenance locator enforcement.

### P2: MVP2 delivery
- Queue lifecycle + graduate promotion atomicity.
- Frontier/context engines.
- Egress policy, audit stream, quarantine/recovery, migration/rollback gates.

## 6. Recommended Immediate Actions

1. Open a spec-patch PR that resolves the Section 2 defects and formally closes Q1/Q2(URL,PDF)/Q4/Q5/Q6.
2. Add a command-contract appendix defining exact `review` and `graduate` state transitions.
3. Add a small `spec-lint` tool/check so future spec updates cannot reintroduce contract drift.
4. Create implementation beads from the P0/P1/P2 order only after spec patch merges.

## 7. Source Artifacts

- `plans/council/blue_systems_contract_review.md`
- `plans/council/teal_security_failure_review.md`
- `plans/council/copper_execution_testability_review.md`
- `plans/council/silver_todo_decisions_review.md`
