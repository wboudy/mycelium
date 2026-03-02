# Teal Decision Merge v1

Date: 2026-03-02  
Agent: TealPeak  
Phase: DECISION-MERGE (planning only)  
Output path: `/Users/will/Developer/mycelium/mycelium/plans/council/teal_decision_merge_v1.md`

## Filled Args
- `PLAN_A_PATH`: `/Users/will/Developer/mycelium/mycelium/plans/council/blue_decision_recommendations_v1.md`
- `PLAN_B_PATH`: `/Users/will/Developer/mycelium/mycelium/plans/council/copper_decision_recommendations_v1.md`
- `PLAN_C_PATH`: `/Users/will/Developer/mycelium/mycelium/plans/council/silver_decision_recommendations_v1.md`
- `SPRINT_SPEC_PATH`: `/Users/will/Developer/mycelium/mycelium/docs/plans/mycelium_refactor_plan_apr_round5.md`
- `OUTPUT_PATH`: `/Users/will/Developer/mycelium/mycelium/plans/council/teal_decision_merge_v1.md`
- Additional source included: `/Users/will/Developer/mycelium/mycelium/plans/council/teal_decision_recommendations_v1.md`

## Scope Guard
This merge is scoped only to:
1. `FRN-1` frontier factor derivations
2. `MVP3-1` triage scoring + watery/dense thresholds + skip-list behavior
3. `MVP3-2` graph algorithms + performance targets

No implementation edits were made.

---

## 1) Requirement Traceability Matrix (Decision Scope)

| Decision | Source-of-truth requirement | Current spec text (evidence) | Repo evidence | Status | Gap to execute |
|---|---|---|---|---|---|
| FRN-1 | `CMD-FRN-002` + `Resolution (TODO-Q-FRN-1)` | Spec defines weighted score + deterministic derivations (`docs/plans/mycelium_refactor_plan_apr_round5.md:738-771`) | No frontier command/symbols found in `src/`/`tests` (`rg` scan no matches); CLI exposes only `run/status/auto` (`src/mycelium/cli.py:293-335`) | Provisional decision text exists; implementation missing | Finalize derivation policy and add testable ACs before coding |
| MVP3-1 | `Resolution (TODO-Q-MVP3-1)` | Current triage thresholds/skip behavior in spec (`docs/plans/mycelium_refactor_plan_apr_round5.md:1217-1226`) | No triage/skip-list runtime symbols in `src/`/`tests` (`rg` no matches) | Provisional decision text exists; implementation missing | Tighten anti-gaming/operational guardrails and define state machine transitions |
| MVP3-2 | `Resolution (TODO-Q-MVP3-2)` | Current graph algorithm/perf targets in spec (`docs/plans/mycelium_refactor_plan_apr_round5.md:1228-1236`) | No graph analytics symbols (`Tarjan/PageRank/hub/articulation`) in code/tests (`rg` no matches) | Provisional decision text exists; implementation missing | Finalize baseline algorithm tier + perf/fallback policy and test envelope |

Decision documents reviewed fully:
- Blue, Copper, Silver, and Teal decision recommendation artifacts (all read end-to-end).

---

## 2) Conflict Resolution Across Plans

### Conflict Map

| Topic | Blue | Copper | Silver | Teal | Final merge decision | Rationale |
|---|---|---|---|---|---|---|
| FRN novelty derivation | Recency-weighted mean | Mean over 30d | Decayed novelty | p75 over 30d | Recency-weighted mean with per-source cap | Better signal continuity than max/p75 alone; easier to explain/implement; lower spike gaming |
| FRN staleness reference time | `as_of_ts` | snapshot-based long decay | command-time (`ref_ts`) | snapshot-based, /45 | `as_of_ts` (command-time) | Removes cross-target coupling from `snapshot_ref_ts`; aligns operator expectation |
| FRN conflict/support | Count saturation by `/3` | Ratio and distinct support | Ratio-based | Distinct-source counts by `/3` | Distinct-source ratio for conflict + capped support target for gap | Combines anti-spam distinctness with bounded explainable support sufficiency |
| MVP3-1 thresholds | 0.67/0.34 + hysteresis | 0.67/0.34 + governance | 0.70/0.40 + hysteresis | 0.70/0.30 + stronger controls | Keep 0.67/0.34 base + add hysteresis bands | Lowest migration churn while reducing flapping |
| MVP3-1 skip streak | 3 | 3 + TTL | 3 + TTL + cap | 4 + age + cap + TTL | 4 + age gate + cap + TTL + pin protection | Better suppression safety and abuse resistance |
| MVP3-2 hub algorithm | degree+core | degree baseline + optional deep | degree+PageRank hybrid | robust-degree (cap) + optional deep | Robust-degree + core baseline; deep mode optional | Better anti-link-spam than degree-only; cheaper than mandatory PageRank in default path |
| MVP3-2 perf targets | 3/5/7 | 3/5/8 default | tighter medium + large tiers | 2.5/4.5/7.5 + budget cap | Default 3/5/7.5 + large-fixture advisory + hard budget fallback | Balances practicality and safety without over-tightening first rollout |

### Preserved Dissent Notes
- Silver prefers stronger large-fixture mandatory perf gates and PageRank in baseline hubs.
- Copper favors default fast path with deep analytics strictly optional and non-gating.
- Teal/Blue prioritize stronger anti-gaming adjustments for novelty and skip controls.

Execution implication: final plan keeps deep mode optional (not baseline) but mandates explicit large-fixture advisory benchmarks and fail-safe budget behavior.

---

## 3) Final Recommended Option Per Decision

## 3.1 FRN-1 Frontier Factor Derivations

### Final recommended option
**Option M (merged): deterministic, anti-gaming, command-time factors**

Formulas:
- `conflict_factor(T) = clamp01(distinct_conflict_source_ids(T) / max(1, distinct_conflict_source_ids(T) + distinct_support_source_ids(T)))`
- `support_gap(T) = 1.0 - clamp01(distinct_support_source_ids(T) / 3.0)`
- `goal_relevance(T)` keeps existing weighted project/tag rule, default `0.5` if no goal filters
- `novelty(T) = clamp01(weighted_mean_linked_delta_novelty_30d(T))`
  - with `w(d)=exp(-age_days(d)/45)`
  - per-source contribution cap: max 2 deltas per source in window
- `staleness(T) = clamp01(days_between(as_of_ts, review_ts(T)) / 45.0)`

### Rejected alternatives + why
- Rejected current spec `max_linked_delta_novelty`: spike-prone and gameable by one outlier run.
- Rejected pure p75 novelty: less smooth for sparse histories and harder to reason in low-sample targets.
- Rejected snapshot-relative staleness: cross-target coupling and operator confusion.

### Consequences
Good:
- Higher abuse resistance and more stable ranking signal.
- Deterministic and explainable enough for audit/debug.

Bad:
- Slightly more state/aggregation complexity.
- Requires deterministic windowing + source caps in implementation.

### Confidence
`0.83`

### Paste-ready normative spec text
```md
**Resolution (TODO-Q-FRN-1, merged):** Frontier factor derivations are deterministic and defined per reading target `T` at command evaluation timestamp `as_of_ts`.

Let:
- `review_ts(T)` = `last_reviewed_at` when present, otherwise `updated`.
- `distinct_conflict_source_ids(T)` = count of distinct source ids in schema-valid conflict records citing `T`.
- `distinct_support_source_ids(T)` = count of distinct supporting source ids linked to `T`.
- `linked_deltas_30d(T)` = linked Delta Reports for `T` with `created_at >= as_of_ts - 30d`.
- For each linked delta `d`, `age_days(d)=days_between(as_of_ts, d.created_at)` and `w(d)=exp(-age_days(d)/45)`.

Derivations:
- `conflict_factor(T) = clamp01(distinct_conflict_source_ids(T) / max(1, distinct_conflict_source_ids(T) + distinct_support_source_ids(T)))`
- `support_gap(T) = 1.0 - clamp01(distinct_support_source_ids(T) / 3.0)`
- `goal_relevance(T)`:
  - If both `project` and `tags` inputs are omitted: `0.5`
  - Else `clamp01(0.6*project_match + 0.4*tag_overlap)` with existing deterministic token normalization.
- `novelty(T)`:
  - if `linked_deltas_30d(T)` is empty: `0.0`
  - else `clamp01( sum(w(d)*d.novelty_score) / max(1e-9, sum(w(d))) )`
  - with per-source contribution cap of 2 most recent deltas within the 30-day window.
- `staleness(T) = clamp01(days_between(as_of_ts, review_ts(T)) / 45.0)`

All factor values MUST be in `[0..1]` and included in `reading_targets[*].factors`.
```

---

## 3.2 MVP3-1 Triage Scoring + Watery/Dense + Skip-list

### Final recommended option
**Option M (merged): fixed thresholds + hysteresis + governed skip-list**

Score:
- Keep current weighted score for migration continuity:
- `triage_score = clamp01(0.45*conflict_factor + 0.25*support_gap + 0.20*novelty + 0.10*staleness)`

Buckets with hysteresis:
- Enter `dense` when `score >= 0.67`, remain dense until `score < 0.60`
- Enter `watery` when `score < 0.34`, remain watery until `score >= 0.42`
- Otherwise `mixed`

Cadence and skip policy:
- Streaks advance once per `digest_date` only.
- Add to skip-list only if all conditions are true:
  - 4 consecutive watery evaluations
  - `conflict_factor == 0`
  - zero open-question references
  - target age >= 14 days
  - target not pinned
- Remove from skip-list on any of:
  - new conflict/open question
  - explicit manual unskip
  - TTL expiry at 30 days (auto-resurface)
- Skip-list cap: max 25% of active targets per snapshot.

### Rejected alternatives + why
- Rejected adaptive quantile thresholds: deterministic comparability risk and distribution gaming.
- Rejected 3-run skip threshold: too suppressive under noisy inputs.
- Rejected no-cap skip-list: can silently hide too much frontier.

### Consequences
Good:
- Reduced bucket flapping and suppression risk.
- Stronger operational safety and auditable transitions.

Bad:
- More state metadata (`watery_streak`, `skip_since`, `next_review_at`, `skip_reason`).
- Slightly larger test matrix.

### Confidence
`0.82`

### Paste-ready normative spec text
```md
**Resolution (TODO-Q-MVP3-1, merged):** MVP3 triage scoring and skip-list behavior are deterministic and stateful.

Score:
- `triage_score = clamp01(0.45*conflict_factor + 0.25*support_gap + 0.20*novelty + 0.10*staleness)`

Bucket transitions (hysteresis):
- Enter `dense` if `triage_score >= 0.67`; remain `dense` until `triage_score < 0.60`.
- Enter `watery` if `triage_score < 0.34`; remain `watery` until `triage_score >= 0.42`.
- Otherwise bucket is `mixed`.

Run cadence:
- A consecutive run is one evaluation per target per `digest_date`.
- Multiple evaluations on the same `digest_date` MUST NOT advance streak counters.

Skip-list add conditions (all required):
- 4 consecutive `watery` runs,
- `conflict_factor == 0`,
- no open-question references,
- target age `>= 14 days`,
- target not manually pinned.

Skip-list removal conditions (any):
- new conflict or open-question reference,
- explicit manual unskip,
- skip TTL expiry at 30 days (`next_review_at`).

Safety constraints:
- Skip-list size MUST NOT exceed 25% of active targets in a snapshot.
- All skip/unskip transitions MUST append audit events with prior state, new state, reason code, and factor snapshot.
```

---

## 3.3 MVP3-2 Graph Algorithms + Performance Targets

### Final recommended option
**Option M (merged): robust baseline + optional deep mode + budget fail-safe**

Baseline required algorithms:
- Graph substrate: canonical wikilink graph over Canonical Scope notes.
- Hub ranking: robust degree with anti-spam controls + core-number contribution.
  - `hub_score = 0.7*norm(robust_degree) + 0.3*norm(core_number)`
  - `robust_degree` counts unique inbound/outbound links with per-source contribution cap.
- Bridge detection: Tarjan articulation points + bridge edges on undirected projection.

Deep mode (optional):
- `analysis_depth=deep` enables PageRank and approximate betweenness.
- Deep mode is non-blocking for baseline release gates.

Performance and fail-safe:
- Medium fixture (`~5k` nodes / `~20k` edges):
  - graph build p95 `<= 3s`
  - baseline hub+bridge p95 `<= 5s`
  - baseline end-to-end p95 `<= 7.5s`
- Large fixture advisory (`~10k` nodes / `~50k` edges):
  - record p95s and trend regression alerts (advisory until promoted to gate)
- Budget fail-safe:
  - if graph exceeds `50k` nodes or `250k` edges, return bounded partial baseline output with `WARN_GRAPH_BUDGET_EXCEEDED` and audit details.

### Rejected alternatives + why
- Rejected degree-only hubs: high susceptibility to link-farm inflation.
- Rejected mandatory deep analytics in baseline: runtime and determinism risk for first rollout.
- Rejected overly aggressive medium gates (e.g., e2e `<=6s`) at initial adoption: high false-fail risk before optimization pass.

### Consequences
Good:
- Better structural signal quality while keeping predictable default cost.
- Clear degradation path under oversized graphs.

Bad:
- Two analysis paths increase maintenance burden.
- Requires transparent reporting to avoid confusion between baseline and deep outputs.

### Confidence
`0.80`

### Paste-ready normative spec text
```md
**Resolution (TODO-Q-MVP3-2, merged):** MVP3 graph analysis uses a deterministic baseline plus optional deep mode.

Baseline required outputs:
- `hubs` ranked by `hub_score = 0.7*norm(robust_degree) + 0.3*norm(core_number)`.
- `articulation_points` and `bridge_edges` via Tarjan algorithm (`O(V+E)`) on undirected projection.
- supporting metrics for each reported hub: `robust_degree`, `core_number`, `hub_score`.

Definitions:
- `robust_degree` uses unique links with per-source contribution cap to reduce link-spam inflation.

Optional deep mode (`analysis_depth=deep`):
- includes PageRank and approximate betweenness outputs;
- deterministic ordering and fixed seed are required in deterministic mode.

Performance targets:
- Medium fixture (`~5k` nodes / `~20k` edges):
  - graph build p95 `<= 3s`
  - baseline hub+bridge analysis p95 `<= 5s`
  - baseline end-to-end command p95 `<= 7.5s`
- Large fixture (`~10k` nodes / `~50k` edges): advisory p95 tracking with regression alerting.

Budget safety:
- If graph size exceeds `50k` nodes or `250k` edges, command MUST return bounded partial baseline outputs, emit `WARN_GRAPH_BUDGET_EXCEEDED`, and append audit details.
```

---

## 4) File-level Implementation Map (Decision Scope)

## Existing files to update
- `docs/plans/mycelium_refactor_plan_apr_round5.md`
  - Replace current FRN-1, MVP3-1, MVP3-2 resolved text blocks with merged normative text.
- `plans/council/*_decision_recommendations_v1.md`
  - No changes required; kept as council record.

## Proposed new implementation files (future execution)
- `src/mycelium/vault/frontier/factors.py` (FRN factor derivation logic)
- `src/mycelium/vault/frontier/triage.py` (bucket/hysteresis/skip state machine)
- `src/mycelium/vault/graph/baseline.py` (robust hubs + Tarjan)
- `src/mycelium/vault/graph/deep.py` (optional PageRank/approx betweenness)
- `src/mycelium/vault/graph/budget.py` (size budget guard and warning contract)
- `tests/vault/frontier/test_factors.py`
- `tests/vault/frontier/test_triage_skiplist.py`
- `tests/vault/graph/test_baseline_algorithms.py`
- `tests/vault/graph/test_graph_budget_fallback.py`
- `tests/vault/perf/test_mvp3_graph_perf.py`

Repository evidence for “new” status:
- No `frontier/context/review_digest/graduate/ingest/delta` command symbols in source/tests (`rg` scan empty).
- CLI currently only exposes `run/status/auto` (`src/mycelium/cli.py:293-335`).
- Tool schema currently fixed to 7 mission tools (`src/mycelium/tools.py:21-195`; `tests/test_tools.py:60-67`).

---

## 5) Dependency-ordered Execution Plan (Decision Adoption)

## Phase 0: Decision ratification
1. Ratify merged Decision Option M for FRN-1.
2. Ratify merged Decision Option M for MVP3-1.
3. Ratify merged Decision Option M for MVP3-2.

## Phase 1: Spec integration
4. Patch spec text blocks for FRN-1/MVP3-1/MVP3-2.
5. Add AC extensions for anti-gaming, hysteresis, skip-cap, graph budget fallback.
6. Run spec lint for requirement/AC completeness.

## Phase 2: Test contract design
7. Define deterministic fixture schemas for FRN novelty decay and skip-list cadence.
8. Define graph correctness fixtures (star/chain/ring + link-spam variant).
9. Define medium and large graph perf benchmark fixtures and hardware profile capture format.

## Phase 3: Implementation planning handoff
10. Produce bead set from merged decision text (post-approval only).
11. Sequence coding lanes: frontier factors -> triage state -> graph baseline -> budget fallback -> deep mode optional.
12. Gate release by baseline deterministic + perf criteria; deep mode non-gating initially.

Parallelization opportunities:
- Steps 7 and 8 can run in parallel after Step 5.
- Step 9 can begin once fixture formats are agreed (independent of algorithm code).

---

## 6) Verification Matrix

| Command | Expected output | Artifact path |
|---|---|---|
| `rg -n "Resolution \(TODO-Q-FRN-1\)|Resolution \(TODO-Q-MVP3-1\)|Resolution \(TODO-Q-MVP3-2\)" docs/plans/mycelium_refactor_plan_apr_round5.md` | Exactly one merged block per decision with updated text | `docs/plans/mycelium_refactor_plan_apr_round5.md` |
| `rg -n "AC-CMD-FRN-002-4|AC-MVP3-1-1|AC-MVP3-2-1|WARN_GRAPH_BUDGET_EXCEEDED" docs/plans/mycelium_refactor_plan_apr_round5.md` | New AC and warning contract references present | `docs/plans/mycelium_refactor_plan_apr_round5.md` |
| `PYTHONPATH=src pytest -q` | Existing baseline stays green before decision-driven implementation starts | repository test report |
| `pytest tests/vault/frontier/test_factors.py -q` (future) | Deterministic FRN factor tests pass including anti-gaming fixtures | `tests/vault/frontier/test_factors.py` |
| `pytest tests/vault/frontier/test_triage_skiplist.py -q` (future) | Hysteresis, streak cadence, skip cap and TTL behavior pass | `tests/vault/frontier/test_triage_skiplist.py` |
| `pytest tests/vault/graph/test_baseline_algorithms.py -q` (future) | Hub and Tarjan outputs match golden expected sets | `tests/vault/graph/test_baseline_algorithms.py` |
| `pytest tests/vault/graph/test_graph_budget_fallback.py -q` (future) | Oversized graph returns bounded output and warning code deterministically | `tests/vault/graph/test_graph_budget_fallback.py` |
| `pytest tests/vault/perf/test_mvp3_graph_perf.py -q` (future) | Medium fixture p95 gates pass, large fixture advisory reported | `tests/vault/perf/test_mvp3_graph_perf.py` |

---

## 7) Top 10 Risks/Gaps + Mitigation + Rollback

| # | Risk/Gap | Mitigation | Rollback point |
|---|---|---|---|
| 1 | Novelty manipulation via bursty delta creation | Recency weighting + per-source cap | Revert novelty to capped mean without recency weights |
| 2 | Source-splitting inflates conflict/support | Distinct-source counting + source domain bucketing | Apply per-domain cap and re-score |
| 3 | Goal/tag stuffing inflates relevance | Token normalization + duplicate suppression + contribution caps | Freeze goal_relevance at neutral `0.5` temporarily |
| 4 | Skip-list over-suppresses useful topics | 4-run streak + age gate + pin protection + 25% cap | Disable skip writes; continue bucketing without suppression |
| 5 | Bucket flapping causes operator mistrust | Hysteresis thresholds + digest-date cadence | Revert to fixed non-hysteresis buckets while investigating |
| 6 | Graph hub spam from link farms | Robust-degree with per-source caps | Temporarily report degree + source_diversity side-by-side |
| 7 | Oversized graph runtime blowups | Hard budget fallback + warning contract | Fail-safe to baseline partial output mode only |
| 8 | Deep mode nondeterminism | Fixed seeds + stable ordering + non-gating deep mode | Disable deep mode flag by config |
| 9 | Perf target brittleness on heterogeneous hardware | Require hardware profile metadata in perf reports | Downgrade strict gate to advisory until profile classes stabilized |
| 10 | Spec/code drift after merge adoption | Spec-first PR gate + traceability checklist | Block implementation merges until spec AC diffs are reconciled |

---

## 8) Human Final Call (Open Toggles)

Per decision, 1-2 explicit final toggles:

### FRN-1 toggles
1. Novelty decay horizon: `30d` vs `45d` in `w(d)=exp(-age/decay)`.
2. Staleness normalization denominator: `45` vs `60` days.

### MVP3-1 toggles
1. Skip streak length: `3` vs `4` consecutive watery runs.
2. Skip cap: `20%` vs `25%` of active targets.

### MVP3-2 toggles
1. Medium end-to-end p95 gate: `<=7.0s` vs `<=7.5s`.
2. Large-fixture status: advisory-only vs release-gating.

Default picks in this merge:
- FRN-1: `45d decay`, `45d staleness norm`.
- MVP3-1: `4-run streak`, `25% cap`.
- MVP3-2: `<=7.5s` medium gate, large fixture advisory.

---

## 9) Rejected Alternatives (Consolidated)

- Keep current patched FRN formulas unchanged.
  - Rejected due novelty spike persistence and snapshot-relative staleness coupling.
- Adaptive percentile triage thresholds.
  - Rejected for determinism loss and easier distribution gaming.
- Mandatory deep graph analytics in default path.
  - Rejected for rollout risk and baseline perf unpredictability.
- Degree-only hub scoring baseline.
  - Rejected for link-spam susceptibility and weak structural fidelity.

---

## 10) Final Merge Decision Summary

Final recommended options:
1. **FRN-1:** merged Option M (deterministic anti-gaming derivations with recency-weighted novelty and command-time staleness).
2. **MVP3-1:** merged Option M (fixed thresholds with hysteresis + governed skip-list).
3. **MVP3-2:** merged Option M (robust baseline graph analytics + optional deep mode + budget fail-safe).

This document is execution-grade for decision adoption planning; implementation remains out of scope in this turn.
