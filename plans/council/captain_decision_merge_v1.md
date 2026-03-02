# Captain Decision Merge v1

## Inputs Merged
- /Users/will/Developer/mycelium/mycelium/plans/council/blue_decision_recommendations_v1.md
- /Users/will/Developer/mycelium/mycelium/plans/council/teal_decision_recommendations_v1.md
- /Users/will/Developer/mycelium/mycelium/plans/council/copper_decision_recommendations_v1.md
- /Users/will/Developer/mycelium/mycelium/plans/council/silver_decision_recommendations_v1.md

## Vote Matrix
- FRN-1: Blue=B, Teal=B, Copper=B, Silver=B (unanimous)
- MVP3-1: Blue=B, Teal=B, Copper=C, Silver=C (split 2-2)
- MVP3-2: Blue=B, Teal=B, Copper=C, Silver=C (split 2-2, but B/C are structurally close)

## Merged Recommendation Set

### 1) FRN-1 Frontier Factor Derivations (Consensus)
Recommended merged option: **B**

Why this wins:
- Unanimous across all 4 agents.
- Keeps deterministic ranking while improving signal quality over the currently patched baseline.
- Stronger anti-gaming posture than simple count-only factors.

Merged design shape:
- Keep weighted formula in CMD-FRN-002 as-is.
- Use deterministic factor derivations with bounded ratio logic and clear denominators.
- Novelty should use linked delta novelty aggregation with mild robustness (avoid single-run spikes dominating ranking).
- Staleness should be command-time deterministic with explicit reference timestamp.

Final-call toggles:
- Novelty aggregation: `max` vs `p75` vs `mean` of linked delta novelty.
- Staleness horizon: 30d vs 45d vs 90d normalization window.
- Goal relevance neutral default when no goal/tags provided: 0.5 vs reduced neutral.

### 2) MVP3-1 Triage + Thresholds + Skip-list (Split)
Recommended merged option: **B/C hybrid**

Why hybrid:
- B-side (Blue/Teal) contributes safer hysteresis and auditability.
- C-side (Copper/Silver) contributes stronger operational governance for skip-list lifecycle.
- Both camps reject adaptive quantiles as default for now.

Merged design shape:
- Keep fixed deterministic triage formula and fixed threshold bands.
- Add hysteresis for bucket transitions to prevent oscillation.
- Keep explicit skip-list safeguards:
  - deterministic entry criteria,
  - explicit re-check cadence,
  - immediate unskip on conflict/open-question emergence,
  - manual pin/unskip override,
  - max skip cap guardrail.

Final-call toggles:
- Skip recheck cadence: every digest vs every N digests.
- Skip cap: hard percentage cap vs absolute cap.
- Whether to include aging-based auto-expiry from skip-list by default.

### 3) MVP3-2 Graph Algorithms + Performance Targets (Convergent split)
Recommended merged option: **B/C converged two-tier model**

Why this wins:
- All four want a fast baseline path and optional deeper analytics path.
- Main disagreement is naming and strictness, not architecture.

Merged design shape:
- Baseline required path:
  - Hub detection via degree-family metric (allow robust-degree variant if deterministic and bounded).
  - Bridge detection via Tarjan articulation points/bridge edges.
  - Deterministic outputs with stable ordering.
- Optional deep mode:
  - PageRank/betweenness and other heavier metrics behind explicit flag.
  - Strict graph-budget controls and deterministic warning contract on budget exceed.
- Keep explicit p95 targets for baseline and end-to-end paths.

Final-call toggles:
- Baseline hub metric: plain degree vs robust-degree composite.
- End-to-end p95 target: `<=8s` vs tighter `<=7s`.
- Deep mode behavior when over budget: fail-safe partial output vs hard error.

## Cross-Cutting Risks
- Overfitting frontier ranking to current fixtures instead of robust behavior.
- Skip-list can silently suppress useful targets without caps/rechecks/audit visibility.
- Deep graph mode may exceed local budget unless strict guardrails are codified.

## Recommended Final Picks (if forcing one set now)
1. FRN-1: **Option B** with explicit deterministic reference timestamp and robust novelty aggregation.
2. MVP3-1: **B/C hybrid** (fixed thresholds + hysteresis + governed skip-list lifecycle).
3. MVP3-2: **B/C converged two-tier** (fast deterministic baseline + optional deep mode with budget safeguards).

## What To Patch Next (after your call)
- Replace FRN-1, MVP3-1, MVP3-2 resolution blocks in:
  - /Users/will/Developer/mycelium/mycelium/docs/plans/mycelium_refactor_plan_apr_round5.md
- Add/update acceptance criteria for:
  - deterministic fixture stability,
  - skip-list state transition auditability,
  - graph-budget fail-safe behavior.
