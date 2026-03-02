## Decomposition Pre-Check: SilverDune (UX + Retrieval + Nightly Review)

### Pre-Check Evidence
- Plan source reviewed: `docs/plans/mycelium_refactor_plan_apr_round5.md` (Status: `Final (Hardened)`).
- Prior deep-read briefs reviewed:
  - `plans/council/blue_deepread_decomposition_readiness_v1.md`
  - `plans/council/copper_deepread_decomposition_readiness_v1.md`
  - `plans/council/teal_deepread_decomposition_readiness_v1.md`
  - `plans/council/silver_deepread_decomposition_readiness_v1.md`
- Required prior-art search executed:
  - `cass search "mycelium review digest graduate frontier decomposition" --limit 5`
  - Result: no matches.
- Clarify-resolution check:
  - No repository artifact found that explicitly resolves all open ambiguity TODOs for decomposition-critical areas.

### Explicit Ambiguity Gate
blocking_ambiguities=5

Blocking items (all still unresolved in plan):
1. `TODO-Q-RDG-1` (`docs/plans/mycelium_refactor_plan_apr_round5.md:641`)
2. `TODO-Q-FRN-1` (`docs/plans/mycelium_refactor_plan_apr_round5.md:745`)
3. `TODO-Q-REV-1` (`docs/plans/mycelium_refactor_plan_apr_round5.md:958`)
4. `TODO-Q-REV-2` (`docs/plans/mycelium_refactor_plan_apr_round5.md:1009`)
5. `TODO-Q-SEC-1` (`docs/plans/mycelium_refactor_plan_apr_round5.md:1086`)

NO_BEAD_CREATION_DUE_TO_AMBIGUITY

### Exact Clarifying Questions (required before bead decomposition)
1. `TODO-Q-RDG-1`: What is the authoritative nightly trigger for `review_digest` in MVP1: manual CLI invocation, external scheduler trigger, or client/plugin initiated trigger? Which interface is source-of-truth for audit attribution?
2. `TODO-Q-REV-1`: Where is `hold_until` persisted (queue item vs packet vs decision record), and what concrete mechanism resurfaces held items after TTL without a built-in scheduler?
3. `TODO-Q-REV-2`: How is Git Mode enabled/configured (global config, per-command flag, or repo file), and what is the minimum required commit-message template (`source_id`, `run_id`, packet id fields)?
4. `TODO-Q-SEC-1`: Where is egress mode (`report_only` vs `enforce`) stored, and what exact rule transitions from 14-day burn-in to enforce mode?
5. `TODO-Q-FRN-1`: What deterministic data-source formulas define `conflict_factor`, `support_gap`, `goal_relevance`, `novelty`, and `staleness` so `CMD-FRN-002` can be implemented/tested without interpretation drift?

### Notes
- Round override honored: proposal-only; no `br create/update/dep` operations executed.
- Because `blocking_ambiguities>0`, decomposition into proposed atomic beads is intentionally not produced in this artifact.
