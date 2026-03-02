# CopperHawk Decision Recommendations v1

ROLE_ACK: WORKER
PHASE: DESIGN-DECISION
AGENT: CopperHawk
Date: 2026-03-02

## Override Handling
- Orchestrator override applied (decision council round): no further waiting for clarifications.
- Any unresolved clarification points are treated as explicit assumptions for this recommendation version.
- This artifact is final for planning-mode decision recommendation.

## Inputs Reviewed
- Plan: `docs/plans/mycelium_refactor_plan_apr_round5.md`
- Council artifacts: `plans/council/*`

## Assumptions (Explicit)
1. The recently patched spec resolutions for FRN-1 / MVP3-1 / MVP3-2 are **provisional candidates**, not final policy.
2. Recommendations must optimize for implementation complexity, maintainability, migration risk, and rollout practicality.
3. Deterministic behavior and fixture reproducibility are non-negotiable for acceptance.

## Ambiguity Inventory + Targeted Questions (for ratification)

### Q1
- Context: FRN-1 `goal_relevance` neutral default when no goal/project filters are provided.
- Options:
  - A) neutral `0.5`
  - B) conservative `0.0`
- Recommendation: A — avoids suppressing all untargeted exploration and preserves stable ranking spread.
- Question: Should untargeted runs use neutral `0.5`, or strict `0.0` for `goal_relevance`?

### Q2
- Context: MVP3-1 skip-list aging policy.
- Options:
  - A) no TTL (only event-based unskip)
  - B) fixed TTL revisit (e.g., 30 days)
- Recommendation: B — prevents silent long-lived suppression and enables periodic reevaluation.
- Question: Approve fixed skip-list recheck TTL at 30 days?

### Q3
- Context: MVP3-2 advanced graph metrics in default command path.
- Options:
  - A) mandatory deep metrics (PageRank/betweenness) in default run
  - B) fast default (degree + Tarjan), deep metrics optional flag
- Recommendation: B — aligns with p95 targets and lowers rollout risk while preserving extensibility.
- Question: Approve deep metrics as optional (`analysis_depth=deep`) rather than mandatory default?

---

## Decision 1: FRN-1 Frontier Factor Derivations

### Context
Need deterministic formulas for `conflict_factor`, `support_gap`, `goal_relevance`, `novelty`, `staleness` that are implementation-simple, hard to game, and fixture-stable.

### Option A
Adopt current patched formulas as-is (`conflict_refs/3`, `support_sources/3`, max-linked novelty, 30-day staleness normalization).

### Option B
Use ratio-based conflict/support normalization + averaged recent novelty + slower staleness decay + weighted project/tag relevance.

### Option C
Use learned/statistical scoring model (embedding/retrieval quality signals) with periodic calibration.

### Recommendation
**Pick Option B.**

Why:
- Lower gaming risk than fixed `/3` saturation and `max` novelty spike behavior.
- Still deterministic and local-data-only (no external models/services).
- Manageable implementation complexity in MVP2 codebase.

### Consequences
Good:
- Better score stability across different vault sizes.
- Reduces single-artifact spikes dominating ranking.
- Easier to explain and debug than ML-driven ranking.

Bad:
- Slightly more formula complexity than current patched defaults.
- Requires explicit token normalization policy for goal relevance.

### Test implications
Add/update fixtures + AC:
- `frontier_factor_conflict_support_balance` fixture.
- `frontier_goal_relevance_neutral` fixture (no filters).
- `frontier_novelty_window_30d` fixture with deterministic dates.
- `frontier_staleness_decay_90d` fixture.
- AC update: assert factor monotonicity under controlled evidence deltas.

### Failure modes / gaming risks
- Link spam to inflate support counts.
- Artificial contradiction creation to inflate conflict factor.
- Tag stuffing to inflate goal relevance.

Mitigations:
- Count **distinct supporting source_ids** not raw link count.
- Count contradiction references from schema-valid conflict records only.
- Normalize/deduplicate goal tokens and cap repeated-token contribution.

### Proposed normative spec text (paste-ready)
```md
**Resolution (TODO-Q-FRN-1):** Frontier factor derivations are deterministic and defined as follows for each target `T` in snapshot `S`.

Let:
- `contradict_refs(T)` = number of schema-valid conflict records citing `T`.
- `support_sources(T)` = number of distinct supporting `source_id` values linked to `T`.
- `snapshot_ref_ts` = max `updated` timestamp across all targets in `S`.
- `review_ts(T)` = `last_reviewed_at` when present, otherwise `updated`.
- `goal_tokens` = normalized token set from input `goal` plus `project` (if provided).
- `target_tokens(T)` = normalized token set from target title/tags/project terms.

Derivations:
- `conflict_factor(T) = clamp01( contradict_refs(T) / max(1, contradict_refs(T) + support_sources(T)) )`
- `support_gap(T) = 1.0 - clamp01( support_sources(T) / 3.0 )`
- `goal_relevance(T)`:
  - if no `goal` and no `project` input: `0.5`
  - else `clamp01( 0.6*project_match(T) + 0.4*jaccard(goal_tokens, target_tokens(T)) )`
  - where `project_match(T)=1.0` if project matches, otherwise `0.0`
- `novelty(T) = clamp01( mean(linked_delta_novelty_scores(T, lookback=30d)) )`; if none linked, `0.0`
- `staleness(T) = clamp01( days_between(snapshot_ref_ts, review_ts(T)) / 90.0 )`

All factor inputs MUST be derived only from vault artifacts and deterministic time normalization in test mode.
```

Confidence: **0.81**

---

## Decision 2: MVP3-1 Triage Scoring + Watery/Dense Thresholds + Skip-list Behavior

### Context
Need an actionable triage model that separates dense vs watery targets without introducing unstable threshold drift or irreversible suppression.

### Option A
Static thresholds only (current patched model): `dense>=0.67`, `watery<0.34`, skip after 3 watery runs.

### Option B
Dynamic percentile thresholds per run (e.g., top 25% dense, bottom 25% watery).

### Option C
Static thresholds with safeguards: hysteresis-like unskip rules, protected classes, and periodic TTL recheck.

### Recommendation
**Pick Option C** (using the patched score weights as base, with stronger skip-list governance).

Why:
- Keeps deterministic reproducibility (better than percentile drift).
- Adds practical controls against over-suppressing relevant targets.
- Operationally safer rollout: simple policy config + explicit auditable transitions.

### Consequences
Good:
- Predictable bucket assignments across fixtures and releases.
- Skip-list remains reversible and observable.
- Reduced risk of “forgotten” topics due to stale watery classification.

Bad:
- More policy state to manage (`watery_streak`, `skip_reason`, `skip_set_at`).
- Slightly more review logic complexity in digest/frontier commands.

### Test implications
Add/update fixtures + AC:
- `triage_bucket_boundaries` (edge values: 0.33/0.34/0.67).
- `triage_watery_streak_skip` (3 consecutive watery runs).
- `triage_unskip_on_conflict` and `triage_unskip_on_open_question`.
- `triage_skip_ttl_revisit_30d` fixture.
- AC update: ensure skipped targets are omitted by default but returned with `include_skip=true`.

### Failure modes / gaming risks
- Suppressing conflict/question links to force skip-list entry.
- Mass-tagging low-value targets to avoid watery status.
- Oscillation around threshold boundaries.

Mitigations:
- Skip eligibility requires `conflict_factor==0` and zero open-question refs.
- Keep target state machine metadata and audit skip/unskip events.
- Unskip immediately on new conflict/question evidence.

### Proposed normative spec text (paste-ready)
```md
**Resolution (TODO-Q-MVP3-1):** MVP3 triage scoring, buckets, and skip-list behavior are defined as follows.

Triage score:
- `triage_score = clamp01(0.45*conflict_factor + 0.25*support_gap + 0.20*novelty + 0.10*staleness)`

Buckets:
- `dense` if `triage_score >= 0.67`
- `mixed` if `0.34 <= triage_score < 0.67`
- `watery` if `triage_score < 0.34`

Skip-list behavior:
- A target is eligible for skip-list entry only when all are true:
  - `bucket == watery` for 3 consecutive runs
  - `conflict_factor == 0`
  - no open-question references
  - target is not manually pinned
- Removal from skip-list occurs on first of:
  - any new conflict reference
  - any new open-question reference
  - manual unskip
  - periodic recheck at 30 days (`skip_set_at + 30d`)
- Skipped targets are excluded by default and included only when `include_skip=true`.
- All skip-list transitions MUST emit audit events with reason codes.
```

Confidence: **0.78**

---

## Decision 3: MVP3-2 Graph Algorithms + Performance Targets

### Context
Need minimum viable graph analytics for `/connect`/`/trace` era that can ship with bounded complexity and predictable runtime.

### Option A
Patched baseline: degree-centrality hubs + Tarjan articulation/bridge detection; fixed p95 targets (3s/5s/8s).

### Option B
Mandatory deep analytics in default path (PageRank + betweenness + community detection).

### Option C
Two-tier approach: Option A as default required path, optional deep mode for richer analytics not in default p95 budget.

### Recommendation
**Pick Option C** (with Option A as required baseline).

Why:
- Best rollout practicality: default stays fast and deterministic.
- Maintains maintainability and low migration risk.
- Leaves headroom for richer future analytics without jeopardizing baseline SLA.

### Consequences
Good:
- Predictable performance on medium graphs.
- Clear separation of required vs optional algorithmic complexity.
- Easier regression triage when performance slips.

Bad:
- Two code paths to test (`default` vs `deep`).
- Some users may expect deep metrics in default output.

### Test implications
Add/update fixtures + AC:
- Graph fixture tiers: `small`, `medium (~5k/20k)`, `stress`.
- Determinism tests for articulation/bridge outputs.
- Performance benches for default path and separate deep-mode benchmark (non-blocking initially).
- AC update: default path must pass SLA; deep mode reports metrics but does not gate MVP3 baseline.

### Failure modes / gaming risks
- Link farms create artificial hubs.
- Duplicate links inflate degree counts.
- Fragmentation from alias notes undermines articulation/bridge quality.

Mitigations:
- Deduplicate edges by `(src, dst, edge_type)` before analysis.
- Report `source_diversity` metric alongside hub rank.
- Add canonicalization/link normalization pre-pass.

### Proposed normative spec text (paste-ready)
```md
**Resolution (TODO-Q-MVP3-2):** Minimum viable graph algorithms and performance targets are defined as follows.

Required default analysis path (`analysis_depth=default`):
- Graph substrate: canonical wikilink graph over Canonical Scope notes.
- Hub detection: top-K by degree centrality over deduplicated edges.
- Bridge detection: articulation points and bridge edges via Tarjan algorithm (`O(V+E)`).
- Required outputs: `hubs`, `articulation_points`, `bridge_edges`, plus supporting metrics (`degree`, `source_diversity`, `component_id`).

Optional deep path (`analysis_depth=deep`, non-blocking for MVP3 baseline):
- May include PageRank, betweenness, and community metrics.
- Deep-path benchmarks are recorded but do not gate default-path SLAs unless explicitly enabled.

Performance targets on seeded medium fixture (`~5k` nodes / `~20k` edges):
- graph build p95 `<= 3s`
- default hub+bridge analysis p95 `<= 5s`
- end-to-end default graph analysis command p95 `<= 8s`
```

Confidence: **0.84**

---

## If I Were Final Decider

1. **FRN-1:** adopt **Option B** (ratio-based deterministic factors with averaged novelty and 90-day staleness).
2. **MVP3-1:** adopt **Option C** (patched score + fixed thresholds + governed skip-list lifecycle).
3. **MVP3-2:** adopt **Option C** (default fast degree+Tarjan path, optional deep metrics path).

These three picks maximize deterministic behavior, testability, and rollout safety while avoiding over-engineering in first implementation.
