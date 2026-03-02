# BlueRaven Decision Recommendations v1

Date: 2026-03-02
Agent: BlueRaven
Phase: DESIGN-DECISION
Scope: exactly 3 decisions
1) FRN-1 frontier factor derivations
2) MVP3-1 triage scoring + watery/dense thresholds + skip-list behavior
3) MVP3-2 graph algorithms + performance targets

## Inputs Reviewed
- Plan: `/Users/will/Developer/mycelium/mycelium/docs/plans/mycelium_refactor_plan_apr_round5.md`
- Council artifacts: `/Users/will/Developer/mycelium/mycelium/plans/council/*.md`

## Ambiguity Sweep

Per orchestrator override, missing clarifications are treated as explicit assumptions in this artifact.
Recommendations below are final for this decision round.

Assumptions explicitly adopted:
- A1: FRN novelty should not be `max(...)` forever if recency weighting is available.
- A2: FRN staleness should be computed against command `as_of_ts` not `snapshot_ref_ts=max(updated in S)`.
- A3: MVP3 skip-list “consecutive runs” means one evaluation per `digest_date` cycle.
- A4: MVP3 hub scoring should not be degree-only if we care about structural fidelity.
- A5: Perf gates should include hardware profile class, not just raw p95 numbers.

Clarify packet sent (5 questions, <=5 constraint respected):
- Message subject: `Clarify packet: FRN-1 + MVP3-1/2 decision ambiguities`
- Recipient fallback used: `DustyCat` (CaptainRusty identity unavailable in this project)
- No answer received in-turn; this is recorded for traceability only and does not block final recommendations.

---

## Decision 1: FRN-1 Frontier Factor Derivations

### Context
The plan now includes a resolved FRN-1 block (`§5.2.7`) with deterministic formulas. The current patch is deterministic, but two fidelity risks remain:
- `novelty(T) = max_linked_delta_novelty(T)` can be permanently dominated by one historical spike.
- `staleness(T)` uses `snapshot_ref_ts=max(updated in S)`, coupling one target’s update behavior to all others in that filtered snapshot.

### Option A (Current Patched Default)
- Keep existing resolved formulas in `§5.2.7` unchanged.

### Option B (Recommended)
- Keep deterministic five-factor model and weights in CMD-FRN-002.
- Improve only derivation internals for fidelity + anti-gaming:
  - replace novelty `max(...)` with recency-weighted mean
  - compute staleness against command `as_of_ts`
  - keep deterministic project/tag relevance defaults and explicit fallbacks

### Option C
- Use richer ranking features (embedding similarity, learned model, adaptive weighting).
- Better semantic fidelity but lower auditability, higher complexity, and harder deterministic guarantees.

### Recommendation
**Pick Option B.**
Why:
- Preserves determinism and spec testability.
- Improves ranking signal fidelity (reduces stale novelty spikes).
- Reduces cross-target coupling artifacts in staleness.
- Keeps complexity moderate and implementation feasible for near-term rollout.

### Consequences
Good:
- More stable and explainable rankings over time.
- Harder to game by creating one high-novelty outlier delta.
- Better separation between target-local state and snapshot-global noise.

Bad:
- Slightly more computation than simple `max`.
- Requires recency metadata quality (`created_at`) on linked deltas.
- May alter existing fixture expectations; migration of golden baselines needed.

### Test Implications
Required fixtures/AC updates:
- New fixture: `frontier_novelty_spike_decay` (single old novelty spike should decay influence).
- New fixture: `frontier_staleness_isolation` (updating unrelated target should not alter staleness of others).
- Update AC-CMD-FRN-002-1 golden outputs to new derivation.
- Add AC: repeated runs with same `as_of_ts` are byte-identical.

### Failure Modes / Gaming Risks
- Tag stuffing to inflate `goal_relevance`.
- Duplicate conflict records inflating `conflict_factor`.
- Manual timestamp manipulation in source artifacts.
Mitigations:
- deduplicate conflicts by unique `(target_id, existing_claim_id, new_claim_key)`.
- cap tag contribution and ignore duplicate tags.
- use parsed UTC timestamps only; reject invalid/naive datetime input.

### Proposed Normative Spec Text (Paste-ready)
```md
**Resolution (TODO-Q-FRN-1) [Revised]:** Frontier factor derivations are deterministic and defined per reading target `T` at command evaluation timestamp `as_of_ts`.

Let:
- `conflict_refs(T)` = count of distinct conflict records citing `T`.
- `support_sources(T)` = count of distinct supporting `source_id` values linked to `T`.
- `review_ts(T)` = `last_reviewed_at` when present, otherwise `updated`.
- `linked_deltas(T)` = Delta Reports linked to `T`.
- `age_days(d)` = days between `as_of_ts` and Delta Report `d.created_at`.
- `w(d) = exp(-age_days(d)/30)`.

Derivations:
- `conflict_factor(T) = clamp01(conflict_refs(T) / 3.0)`
- `support_gap(T) = 1.0 - clamp01(support_sources(T) / 3.0)`
- `goal_relevance(T)`:
  - If both `project` and `tags` inputs are omitted: `0.5`
  - Otherwise:
    - `project_match = 1.0` if `project` provided and `T.project == project`; `0.0` if provided and not equal; `0.5` if omitted or unknown.
    - `tag_overlap = |T.tags ∩ input.tags| / max(1, |input.tags|)`; if `input.tags` omitted, `tag_overlap = 0.5`.
    - `goal_relevance(T) = clamp01(0.6*project_match + 0.4*tag_overlap)`
- `novelty(T) = clamp01( sum_{d in linked_deltas(T)} (w(d) * d.novelty_score) / max(1e-9, sum_{d in linked_deltas(T)} w(d)) )`; if no linked deltas, `0.0`.
- `staleness(T) = clamp01(days_between(as_of_ts, review_ts(T)) / 30.0)`
```

### Confidence
**0.84**

---

## Decision 2: MVP3-1 Triage Scoring + Watery/Dense Thresholds + Skip-list Behavior

### Context
The plan now defines a triage score, fixed bucket thresholds, and skip-list entry/removal. Remaining ambiguity is operational:
- what counts as a “run” for consecutive watery detection
- how to avoid bucket flapping near thresholds
- how to prevent skip-list gaming/over-pruning of low-signal but strategically important topics

### Option A (Current Patched Default)
- Keep existing `triage_score` weights and fixed thresholds.
- Skip after 3 consecutive watery runs with conflict=0 and no open-question references.

### Option B (Recommended)
- Keep deterministic weighted score and buckets.
- Add explicit cadence and hysteresis semantics:
  - one evaluation per `digest_date`
  - hysteresis thresholds for entering/leaving dense/watery
  - stronger skip-entry predicate and auto-recheck TTL

### Option C
- Adaptive percentile thresholds from rolling distribution.
- Better dynamic calibration but harder interpretability and harder fixture stability.

### Recommendation
**Pick Option B.**
Why:
- Maintains deterministic explainability.
- Reduces threshold flapping and accidental over-skipping.
- Gives clean testable state transitions across runs.

### Consequences
Good:
- More stable bucket transitions.
- Better skip-list safety for latent but important targets.
- Stronger anti-gaming constraints with explicit cadence.

Bad:
- Slightly more stateful logic (needs streak tracking by target).
- Additional test matrix for transition hysteresis and TTL behavior.

### Test Implications
Required fixtures/AC updates:
- `triage_boundary_flap` fixture with scores around bucket boundaries.
- `triage_skiplist_streak` fixture across 5 digest dates.
- `triage_skiplist_reactivation` fixture: conflict/question should unskip immediately.
- Add AC for deterministic streak behavior keyed by `digest_date` (not call count).

### Failure Modes / Gaming Risks
- Over-invocation to artificially build “consecutive watery” if cadence undefined.
- Suppressing question creation to force skip-list entry.
- Manual unskip churn creating noisy state transitions.
Mitigations:
- streak counter advances only once per `digest_date`.
- require both low triage and no conflict/question signals.
- audit every skip/unskip transition with reason.

### Proposed Normative Spec Text (Paste-ready)
```md
**Resolution (TODO-Q-MVP3-1) [Revised]:** MVP3 triage model and bucket transitions are deterministic.

Score:
- `triage_score = clamp01(0.45*conflict_factor + 0.25*support_gap + 0.20*novelty + 0.10*staleness)`

Bucket thresholds with hysteresis:
- Enter `dense` when `triage_score >= 0.70`; remain `dense` until `triage_score < 0.62`.
- Enter `watery` when `triage_score < 0.34`; remain `watery` until `triage_score >= 0.42`.
- Otherwise bucket is `mixed`.

Run cadence:
- A "consecutive run" is one evaluation per target per `digest_date`.
- Multiple invocations on same `digest_date` do not increment streak counters.

Skip-list behavior:
- Add target when all hold for 3 consecutive `digest_date` evaluations:
  - bucket is `watery`
  - `conflict_factor == 0`
  - target has zero open-question references
- Remove target immediately on:
  - any non-zero conflict signal OR
  - any open-question reference OR
  - explicit manual unskip action
- Skipped targets remain retrievable via explicit `include_skip=true`.
```

### Confidence
**0.79**

---

## Decision 3: MVP3-2 Graph Algorithms + Performance Targets

### Context
The plan currently defines:
- hubs by degree centrality top-K
- bridges via Tarjan articulation/bridge edges
- p95 targets for 5k nodes / 20k edges
This is deterministic and simple, but degree-only hubs are often noisy in knowledge graphs (index/MOC nodes can dominate).

### Option A (Current Patched Default)
- Keep degree-only hubs + Tarjan bridges + existing 3/5/8 p95 targets.

### Option B (Recommended)
- Keep Tarjan bridge detection and deterministic complexity class.
- Upgrade hub ranking fidelity with a lightweight composite score:
  - normalized degree + normalized core number
- Keep deterministic tie-breaks and preserve output transparency with raw metrics.
- Keep near-current performance targets with a slightly tighter end-to-end gate.

### Option C
- Add approximate/exact betweenness and community detection as baseline outputs.
- Better semantics for bridges/hubs but likely overkill for minimum viable MVP3 and higher runtime risk.

### Recommendation
**Pick Option B.**
Why:
- Better hub signal fidelity than degree-only with minimal complexity increase.
- Still deterministic and testable.
- Preserves Tarjan’s strong structural bridge detection and linear complexity for bridge-related outputs.

### Consequences
Good:
- Lower risk of “hub = noisy high-degree index note” artifacts.
- Better alignment with actual structural importance via core-number contribution.
- Predictable runtime remains feasible for 5k/20k fixtures.

Bad:
- Core-number adds computation and more metrics to explain.
- Hub ranking may shift significantly from current degree-only patch baselines.

### Test Implications
Required fixtures/AC updates:
- `graph_star_vs_core` fixture to validate degree-only bias correction.
- `graph_articulation_known_truth` fixture with exact articulation and bridge edges.
- `graph_perf_medium` fixture pinned at ~5k nodes / ~20k edges with hardware profile metadata.
- Add AC: deterministic lexical tie-break on equal hub score.

### Failure Modes / Gaming Risks
- Artificial link spam to inflate degree/core.
- MOC/meta-note overlinking to dominate hubs.
- Massive graph density spikes threatening p95 targets.
Mitigations:
- optional note-type weighting and/or filter for hub reporting class.
- cap duplicate/self links in build stage.
- fail gate if edge-count exceeds fixture envelope without documented waiver.

### Proposed Normative Spec Text (Paste-ready)
```md
**Resolution (TODO-Q-MVP3-2) [Revised]:** Minimum viable graph algorithms and targets are deterministic.

Graph substrate:
- Build directed wikilink graph `Gd` over Canonical Scope notes.
- Build undirected projection `Gu` for structural connectivity analytics.

Hub detection:
- `degree(T) = in_degree_Gd(T) + out_degree_Gd(T)`
- `core(T) = core_number_Gu(T)`
- `hub_score(T) = 0.7*norm(degree(T)) + 0.3*norm(core(T))`
- `hubs` = top-K nodes by `hub_score`, tie-break by lexical target id.

Bridge detection:
- Compute `articulation_points` and `bridge_edges` on `Gu` via Tarjan algorithm (`O(V+E)`).

Minimum outputs:
- `hubs`
- `articulation_points`
- `bridge_edges`
- `metrics` containing `degree`, `core`, `hub_score` per reported hub.

Performance targets on seeded fixture (`~5k` nodes / `~20k` edges):
- graph build p95 `<= 3s`
- hub+bridge analysis p95 `<= 5s`
- end-to-end graph analysis command p95 `<= 7s`
```

### Confidence
**0.72**

---

## If I Were Final Decider
1. **FRN-1:** Adopt Option B (recency-weighted novelty + `as_of_ts` staleness) and replace current FRN derivation block with the provided normative text.
2. **MVP3-1:** Adopt Option B with explicit `digest_date` cadence and hysteresis transitions; keep score weights unchanged for continuity.
3. **MVP3-2:** Adopt Option B (degree+core composite hubs + Tarjan bridges) and tighten e2e target to p95 `<=7s` while preserving 3s/5s sub-targets.

These three picks maximize determinism + ranking fidelity without overcommitting to expensive graph/ML methods too early.
