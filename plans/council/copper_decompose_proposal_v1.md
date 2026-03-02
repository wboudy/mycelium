# CopperHawk Decomposition Proposal v1

ROLE_ACK: WORKER
PHASE: DECOMPOSITION
COUNCIL_LENS: Orchestration, queues, human-review lane, automation workflow
Date: 2026-03-02

## Pre-check

- Plan approval check: PASS
  - Evidence: `docs/plans/mycelium_refactor_plan_apr_round5.md` header shows `Status: Final (Hardened)`.
- Clarify-resolution check: FAIL
  - Evidence: unresolved policy TODOs remain in the finalized plan and are still called out as blockers across council briefs.
- Prior-art search executed (required):
  - Command: `cass search "mycelium round5 decomposition orchestration queues human review lane" --limit 5`
  - Result: `No results found.`

## Ambiguity Gate (Explicit)

Gate decision inputs reviewed:
- Final plan: `docs/plans/mycelium_refactor_plan_apr_round5.md`
- Prior deep-read briefs:
  - `plans/council/blue_deepread_decomposition_readiness_v1.md`
  - `plans/council/silver_deepread_decomposition_readiness_v1.md`
  - `plans/council/teal_deepread_decomposition_readiness_v1.md`
  - `plans/council/copper_deepread_decomposition_readiness_v1.md`

blocking_ambiguities=5

Blocking ambiguity set (in-scope for orchestration/queue/human-review automation):
1. `TODO-Q-RDG-1`: authoritative `review_digest` invocation ownership/model is unresolved (manual vs scheduler vs client integration).
2. `TODO-Q-REV-1`: hold TTL (`14 days`) storage + deterministic resurfacing mechanism unresolved.
3. `TODO-Q-REV-2`: Git Mode enablement/configuration and commit metadata minimum unresolved.
4. `TODO-Q-SEC-1`: egress policy burn-in tracking/state location and transition authority unresolved.
5. `TODO-Q-FRN-1`: deterministic derivation formulas for frontier factors unresolved.

Ambiguity gate result: FAIL

NO_BEAD_CREATION_DUE_TO_AMBIGUITY

## Exact Clarifying Questions

1. For `review_digest`, who is the normative trigger owner for MVP1/MVP2: user-invoked command only, external scheduler, or client-integrated trigger? If multiple are allowed, which one is the source-of-truth for acceptance tests?
2. Where is hold metadata canonicalized for resurfacing logic: queue item file, review decision record, or both? What exact deterministic rule resurfaces held items (e.g., `hold_until <= digest_date`) and which timestamp source is authoritative?
3. Is Git Mode opt-in via config or command flag, and what exact minimum commit message contract is required to satisfy REV-004 + audit traceability?
4. Where is egress mode state persisted during `report_only -> enforce` burn-in (path + schema), and which action is authorized to transition mode (explicit command, config change, or automated threshold check)?
5. For frontier factor derivations, what deterministic formulas map vault data to `conflict_factor`, `support_gap`, `goal_relevance`, `novelty`, and `staleness` for fixture-stable scoring?

## Decomposition Status

- Bead proposal generation: BLOCKED by ambiguity gate.
- `br create`, `br update`, `br dep add`: intentionally NOT executed (proposal-only round + gate fail).
- `bv --robot-insights`: intentionally NOT executed because no beads were proposed/created due to gate fail.

## Next Action After Clarify

- Re-run ambiguity gate.
- Proceed to atomic bead proposal only when `blocking_ambiguities=0`.
