# BlueRaven Decomposition Proposal v1 (Gate Result)

Date: 2026-03-02
Agent: BlueRaven
Phase: DECOMPOSITION (proposal-only)
Palette: `decompose`
Source plan: `/Users/will/Developer/mycelium/mycelium/docs/plans/mycelium_refactor_plan_apr_round5.md`

## Pre-check
- Plan review/approval: confirmed from spec header `Status: Final (Hardened)` (`docs/plans/mycelium_refactor_plan_apr_round5.md:3`).
- Clarify-resolution check: no artifact in `plans/council/` closes the outstanding blocking TODO-Q items; prior council decomposition findings remain blocked.
- Past work search: `cass search "mycelium round5 decomposition clarify ambiguity gate" --limit 5` => no results.
- Proposal-only override respected: no `br create`, `br update`, `br dep add`, or `br sync` executed.

## Ambiguity Gate
blocking_ambiguities=6

Blocking ambiguities requiring explicit clarify before bead creation:
1. `TODO-Q-RDG-1` (`docs/plans/mycelium_refactor_plan_apr_round5.md:641`): authoritative invocation model for `review_digest` is undefined.
2. `TODO-Q-NAM-1` (`docs/plans/mycelium_refactor_plan_apr_round5.md:426`): migration compatibility mode behavior + activation mechanism for note IDs is undefined.
3. `TODO-Q-REV-1` (`docs/plans/mycelium_refactor_plan_apr_round5.md:958`): hold TTL storage location and deterministic resurface mechanism are undefined.
4. `TODO-Q-REV-2` (`docs/plans/mycelium_refactor_plan_apr_round5.md:1009`): Git Mode enablement/config and mandatory commit convention are undefined.
5. `TODO-Q-FRN-1` (`docs/plans/mycelium_refactor_plan_apr_round5.md:745`): deterministic derivation formulas for frontier factors are undefined.
6. `TODO-Q-SEC-1` (`docs/plans/mycelium_refactor_plan_apr_round5.md:1086`): burn-in tracking source-of-truth and egress mode state storage/transition authority are undefined.

Non-blocking note:
- `TODO-Q-CONF-1` is MVP2+ calibration scope and does not block initial decomposition for MVP1/MVP2 foundations.

## Gate Decision
NO_BEAD_CREATION_DUE_TO_AMBIGUITY

Per round constraints, decomposition stops here. No bead proposal graph is produced while `blocking_ambiguities>0`.

## Exact Clarifying Questions
1. For `TODO-Q-RDG-1`, what is the canonical invoker for `review_digest` (manual command, external scheduler, or client integration), and what event/trigger contract is normative?
2. For `TODO-Q-NAM-1`, what exact compatibility-mode rules are permitted for legacy slug-only IDs, and how is that mode enabled without weakening NAM-001 for new machine-generated notes?
3. For `TODO-Q-REV-1`, where is `hold_until` persisted as source-of-truth, and what deterministic rule resurfaces held items into digest eligibility?
4. For `TODO-Q-REV-2`, where is Git Mode configured (path + defaults), and what minimum commit message schema is mandatory for packet apply batches?
5. For `TODO-Q-FRN-1`, what deterministic formulas compute `conflict_factor`, `support_gap`, `goal_relevance`, `novelty`, and `staleness` from vault data?
6. For `TODO-Q-SEC-1`, what starts the 14-day burn-in clock, where is egress mode persisted, and which actor/operation is authorized to transition `report_only -> enforce`?

## Validation Notes
- `bv --robot-insights` intentionally not run because no bead graph may be created when ambiguity gate fails.
