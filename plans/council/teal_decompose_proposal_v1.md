# TealPeak Decomposition Proposal v1 (Gate Result)

Date: 2026-03-02  
Agent: TealPeak  
Phase: DECOMPOSITION (proposal-only)  
Source plan: `/Users/will/Developer/mycelium/mycelium/docs/plans/mycelium_refactor_plan_apr_round5.md`

## Pre-check
- Plan approval state: confirmed as spec `Status: Final (Hardened)`.
- Past work search: `cass search "mycelium refactor decomposition beads ambiguity gate" --limit 5` => no results.
- Clarify-resolution check: no council artifact indicating ambiguity closure for blocking TODOs.

## Ambiguity Gate
blocking_ambiguities=6

Blocking items:
1. `TODO-Q-RDG-1` (`review_digest` invocation owner: manual vs scheduler vs client integration).
2. `TODO-Q-NAM-1` (migration compatibility mode behavior and activation for note IDs).
3. `TODO-Q-REV-1` (hold TTL storage and deterministic resurfacing mechanism).
4. `TODO-Q-REV-2` (Git Mode enablement/configuration and commit convention).
5. `TODO-Q-FRN-1` (deterministic derivation formulas for frontier factors).
6. `TODO-Q-SEC-1` (14-day burn-in tracking and egress mode storage/transition authority).

## Gate Decision
NO_BEAD_CREATION_DUE_TO_AMBIGUITY

Per round constraints, decomposition stops here. No bead proposal graph is produced while `blocking_ambiguities>0`.

## Exact Clarifying Questions
1. For `TODO-Q-RDG-1`, who is the authoritative invoker of `review_digest` in MVP1/MVP2 (manual CLI, external scheduler, or client integration), and what is the canonical trigger contract?
2. For `TODO-Q-NAM-1`, what exact compatibility mode behavior is allowed for legacy IDs, and how is mode activation configured without weakening NAM-001 validation for new machine-generated notes?
3. For `TODO-Q-REV-1`, where is hold TTL persisted (queue item vs decision record vs config), and what exact deterministic rule resurfaces held items?
4. For `TODO-Q-REV-2`, how is Git Mode enabled/disabled (config path + default), and what minimum commit message schema is mandatory for packet apply batches?
5. For `TODO-Q-FRN-1`, what deterministic formulas map vault data to `conflict_factor`, `support_gap`, `goal_relevance`, `novelty`, and `staleness`?
6. For `TODO-Q-SEC-1`, where is egress mode state stored, what starts the 14-day burn-in clock, and what actor/operation is authorized to transition `report_only -> enforce`?

## Notes
- This is proposal-only; no `br create/update/dep` commands were executed.
- `bv --robot-insights` was intentionally not run because bead graph creation is blocked by ambiguity gate failure.
