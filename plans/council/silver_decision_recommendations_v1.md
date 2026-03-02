# SilverDune Decision Recommendations v1

## Scope
Decisions evaluated (exactly three):
1. `FRN-1` frontier factor derivations
2. `MVP3-1` triage scoring + watery/dense thresholds + skip-list behavior
3. `MVP3-2` graph algorithms + performance targets

## Assumptions (explicit)
- Current plan defaults for these decisions are provisional candidates, not final truth.
- Determinism remains mandatory for test mode and fixture reproducibility.
- Reader UX priority: rankings must be explainable, stable, and hard to game.
- No hidden scheduler dependency should be introduced for core behavior unless explicitly declared.

---

## 1) FRN-1 frontier factor derivations

### Context
`CMD-FRN-002` already defines weighted aggregation and tie-break order. The unresolved quality question is whether factor derivations produce intuitive and robust reading targets for humans.

### Option A
Keep current patched derivations in the plan:
- conflict saturation by `/3`
- support gap by distinct source count `/3`
- goal relevance weighted project/tag match
- novelty = max linked delta novelty
- staleness relative to `snapshot_ref_ts`

### Option B
Switch to evidence-ratio + time-decay derivations:
- conflict/support as ratios against target-local evidence volume
- novelty as **recency-decayed** linked delta signal (not max)
- staleness measured against command reference time

### Option C
Feedback-trained derivation layer:
- learn factor derivations from reviewer actions over time
- apply calibrated mappings per vault/domain

### Recommendation
Pick **Option B**.

Why:
- Better reader ergonomics: decayed novelty prevents one old “spike” from dominating forever.
- Better comprehension: ratio-based conflict/support is easier to explain than arbitrary fixed thresholds.
- Better robustness: command-time staleness aligns with operator expectation (“how stale now?”) rather than only intra-snapshot age.
- Still deterministic and testable.

### Consequences
Good:
- More stable and believable reading-target ordering.
- Better resistance to stale novelty inflation.
- Easier reviewer trust via explanation fields.

Bad:
- Slightly higher implementation complexity (decay computation + timestamp discipline).
- Requires additional fixtures for decay behavior and boundary conditions.

### Test implications
Add/adjust fixtures and ACs:
- New fixture: target with old high novelty vs recent medium novelty to verify decay ordering.
- New fixture: equal weighted score, tie-break via conflict then recency then lexical id.
- Update AC set with explicit derivation checks:
  - `AC-CMD-FRN-002-4`: factor derivations are deterministic and bounded.
  - `AC-CMD-FRN-002-5`: novelty decays with age of linked delta reports.

### Failure modes / gaming risks
- Gaming by mass-linking contradictory claims to inflate conflict.
  - Mitigation: per-source/day contribution cap.
- Gaming by tag stuffing to inflate relevance.
  - Mitigation: cap tag_overlap contribution and require exact token normalization.
- Timestamp drift causing flaky staleness.
  - Mitigation: deterministic test clock + UTC normalization.

### Proposed normative spec text (paste-ready)
```md
**Resolution (TODO-Q-FRN-1, revised):** Frontier factor derivations are deterministic and defined as follows for each reading target `T` in filtered snapshot `S`.

Let:
- `ref_ts` = command reference timestamp (fixed in deterministic test mode).
- `review_ts(T)` = `last_reviewed_at` when present, else `updated`.
- `contradict_count(T)` = number of contradiction links citing `T`.
- `support_count(T)` = number of distinct supporting source links citing `T`.
- `linked_deltas(T)` = Delta Reports linked to `T` with `(novelty_score, created_at)`.

Derivations:
- `conflict_factor(T) = clamp01(contradict_count(T) / max(1, contradict_count(T) + support_count(T)))`
- `support_gap(T) = 1.0 - clamp01(support_count(T) / 3.0)`
- `goal_relevance(T)`:
  - if both `goal` and `project/tags` filters are omitted: `0.5`
  - else `clamp01(0.6*project_match + 0.4*tag_overlap)`
- `novelty(T)`:
  - if `linked_deltas(T)` empty: `0.0`
  - else `clamp01( sum(novelty_score_r * exp(-age_days_r/45)) / sum(exp(-age_days_r/45)) )`
- `staleness(T) = clamp01(days_between(ref_ts, review_ts(T)) / 60.0)`

All factors MUST be in `[0..1]` and included in `reading_targets[*].factors`.
```

### Confidence
`0.84`

---

## 2) MVP3-1 triage scoring + watery/dense thresholds + skip-list behavior

### Context
Current patched MVP3 triage is simple and deterministic, but skip-list behavior can hide content too aggressively and bucket boundaries may oscillate near thresholds.

### Option A
Keep current patched model:
- static thresholds (`dense>=0.67`, `watery<0.34`)
- skip after 3 watery runs if no conflict/open question
- immediate unskip on conflict/open question

### Option B
Dynamic quantile model:
- compute thresholds from vault distribution each run
- watery/dense are percentile-based

### Option C
Static thresholds + **hysteresis + guardrails**:
- keep deterministic fixed thresholds
- add anti-oscillation hysteresis
- add skip-list TTL/cap and goal-protection safeguards

### Recommendation
Pick **Option C**.

Why:
- Best UX stability: avoids flip-flopping bucket labels between adjacent runs.
- Better operator trust: fixed thresholds are understandable; hysteresis prevents jitter.
- Better product usefulness: skip-list can’t silently bury relevant targets.

### Consequences
Good:
- More stable triage labels across runs.
- Safer skip-list behavior with automatic resurfacing.
- Fewer “where did this item go?” surprises.

Bad:
- More state to maintain (`skip_since`, `skip_reason`, TTL metadata).
- Slightly more complex acceptance tests.

### Test implications
Add/adjust fixtures and ACs:
- Boundary fixtures around `0.34/0.67` for transition stability.
- Hysteresis fixture for near-threshold oscillation.
- Skip-list lifecycle fixture: add -> hold hidden -> resurface on TTL.
- Add ACs:
  - `AC-MVP3-TRI-001`: bucket transitions honor hysteresis.
  - `AC-MVP3-TRI-002`: skip-list never hides items with active conflict/open-question links.
  - `AC-MVP3-TRI-003`: skip-list entries auto-resurface after TTL unless requalified.

### Failure modes / gaming risks
- Gaming by reducing evidence links to force watery classification.
  - Mitigation: require minimum observation window before skip eligibility.
- Gaming by suppressing open-question links to push skip.
  - Mitigation: protect targets referenced by active project goals.
- Overlarge skip list reducing discovery.
  - Mitigation: hard cap skip-list size as fraction of active targets.

### Proposed normative spec text (paste-ready)
```md
**Resolution (TODO-Q-MVP3-1, revised):** MVP3 triage model, thresholds, and skip-list policy are deterministic and include hysteresis safeguards.

Score:
- `triage_score = clamp01(0.40*conflict_factor + 0.20*support_gap + 0.20*novelty + 0.10*staleness + 0.10*goal_relevance)`

Buckets:
- `dense` if `triage_score >= 0.70`
- `mixed` if `0.40 <= triage_score < 0.70`
- `watery` if `triage_score < 0.40`

Hysteresis:
- `dense -> mixed` only after 2 consecutive runs with `triage_score < 0.65`
- `watery -> mixed` on first run with `triage_score >= 0.45`

Skip-list eligibility:
- add target only when all are true:
  - 3 consecutive `watery` runs
  - `conflict_factor = 0`
  - no open-question references
  - `goal_relevance < 0.35`
- skipped target metadata MUST include `skip_since`, `skip_reason`, and `next_review_at`
- default skip TTL is 30 days; target resurfaces automatically on/after `next_review_at`
- skip-list size MUST be capped at 20% of active targets
- targets with new conflict/open-question links or manual unskip MUST be removed immediately from skip-list
```

### Confidence
`0.81`

---

## 3) MVP3-2 graph algorithms + performance targets

### Context
Current patched MVP3 algorithm set is degree-centrality hubs + Tarjan bridges/articulation with medium-size perf targets. This is simple but vulnerable to link-farm bias and under-specifies UX-oriented explainability.

### Option A
Keep current patched approach:
- hubs by degree centrality
- bridges by Tarjan articulation/bridge edges
- targets: medium fixture only (`5k/20k`)

### Option B
Heavier graph analytics:
- PageRank + betweenness + community detection as default
- larger insight quality, higher compute cost

### Option C
Two-tier practical model:
- Core deterministic structural set always on: degree + PageRank hybrid for hubs, Tarjan for bridges
- Optional expensive analytics only behind explicit flag
- Dual-size performance targets (medium + large fixtures)

### Recommendation
Pick **Option C**.

Why:
- Better reader usefulness: hub ranking not dominated by raw link count spam.
- Better ergonomics: bridge outputs remain simple and explainable.
- Better reliability: performance envelope is explicit for both medium and large vaults.

### Consequences
Good:
- Stronger hub quality and interpretability.
- Maintains deterministic, fast default path.
- Scales better due explicit tiering.

Bad:
- More implementation work than degree-only.
- Requires extra benchmark and correctness fixtures.

### Test implications
Add/adjust fixtures and ACs:
- Correctness fixtures:
  - star graph (hub expected), chain graph (known articulation points), ring graph (no articulation).
- Determinism fixture for stable ordered outputs.
- Performance fixtures:
  - medium (`~5k nodes / ~20k edges`)
  - large (`~10k nodes / ~50k edges`).
- Add ACs:
  - `AC-MVP3-GRAPH-001`: hub ordering uses hybrid score and is deterministic.
  - `AC-MVP3-GRAPH-002`: Tarjan outputs exact articulation/bridge sets on known fixtures.
  - `AC-MVP3-GRAPH-003`: medium/large p95 targets both enforced.

### Failure modes / gaming risks
- Link-farm MOCs inflating hub score.
  - Mitigation: hybrid score + per-note-type contribution caps.
- Bridge false positives from template nodes.
  - Mitigation: filter/weight system-generated nodes.
- Performance regressions on larger vaults.
  - Mitigation: dual-fixture perf gates with fail-closed thresholds.

### Proposed normative spec text (paste-ready)
```md
**Resolution (TODO-Q-MVP3-2, revised):** MVP3 graph analysis uses a deterministic two-tier algorithm set with explicit performance targets.

Graph substrate:
- Canonical wikilink graph over Canonical Scope notes.
- Directed edges for link traversal; undirected projection for articulation/bridge analysis.

Algorithms:
- Hub ranking score:
  - `hub_score = 0.6*norm(in_degree) + 0.4*norm(page_rank)`
  - output top-K hubs with component metrics (`in_degree`, `page_rank`, `hub_score`)
- Bridge analysis:
  - Tarjan articulation points + bridge edges on undirected projection (`O(V+E)`)
- Optional advanced mode (`--advanced-graph`): approximate betweenness for top-N candidates only.

Minimum outputs:
- `hubs`, `articulation_points`, `bridge_edges`, `components_summary`

Performance targets:
- Medium fixture (`~5k` nodes / `~20k` edges):
  - graph build p95 `<= 2.5s`
  - core analysis p95 `<= 4.0s`
  - end-to-end command p95 `<= 6.0s`
- Large fixture (`~10k` nodes / `~50k` edges):
  - graph build p95 `<= 6.0s`
  - core analysis p95 `<= 9.0s`
  - end-to-end command p95 `<= 14.0s`

Determinism:
- output ordering ties resolved lexically by stable target id.
- deterministic mode MUST yield byte-identical normalized outputs for same fixture snapshot.
```

### Confidence
`0.78`

---

## If I Were Final Decider
Exact picks:
1. **FRN-1**: Option B (ratio + decayed novelty + command-time staleness).
2. **MVP3-1**: Option C (fixed thresholds with hysteresis and guarded skip-list).
3. **MVP3-2**: Option C (hybrid hub score + Tarjan core + dual-size perf gates).

Why these three together:
- They maximize reader trust and review ergonomics while keeping deterministic implementation and testability intact.
