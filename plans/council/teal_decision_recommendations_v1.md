# TealPeak Decision Recommendations v1

Date: 2026-03-02  
Agent: TealPeak  
Phase: DESIGN-DECISION  
Lens: Security, abuse resistance, failure behavior, auditability, operational safety

Scope (exactly 3 decisions):
1. FRN-1 frontier factor derivations
2. MVP3-1 triage scoring + watery/dense thresholds + skip-list behavior
3. MVP3-2 graph algorithms + performance targets

Note: current spec patches are treated as **provisional candidates**, not final truth.

## Decision 1: FRN-1 Frontier Factor Derivations

### Context
Need deterministic, testable factor derivations for `conflict_factor`, `support_gap`, `goal_relevance`, `novelty`, and `staleness` that are hard to game and cheap enough for routine use.

### Option A (current patched baseline)
- Use current resolved formulas in §5.2.7:
  - `conflict_factor = clamp01(conflict_refs/3)`
  - `support_gap = 1 - clamp01(support_sources/3)`
  - `goal_relevance` from project/tag match mixture
  - `novelty = max_linked_delta_novelty`
  - `staleness = days_between(snapshot_ref_ts, review_ts)/30`

### Option B (security-hardened deterministic)
- Keep deterministic structure but harden against manipulation:
  - `conflict_factor(T) = clamp01(distinct_conflict_source_ids(T) / 3.0)`
  - `support_gap(T) = 1.0 - clamp01(distinct_support_source_ids(T) / 3.0)`
  - `goal_relevance(T)` same project/tag weighted rule as current patch (preserves explainability)
  - `novelty(T) = clamp01(p75_linked_delta_novelty_30d(T))` (not max)
  - `staleness(T) = clamp01(days_between(snapshot_ref_ts, review_ts(T)) / 45.0)`

### Option C (heavy evidence model)
- Introduce provenance-weighted Bayesian or graph-propagated confidence factors.
- Better theoretical quality, higher complexity, weaker explainability for MVP2.

### Recommendation
**Pick Option B.**

Why:
- `max_linked_delta_novelty` is single-event gameable; p75 dampens spikes while preserving signal.
- Distinct-source counts reduce repeated-claim spam from one source.
- 45-day staleness avoids over-amplifying stale score due short inactivity windows.
- Keeps deterministic and easy-to-audit behavior.

### Consequences
Good:
- Better abuse resistance (spam contradictions/support, novelty spikes).
- More stable rankings across noisy ingest batches.
- Minimal extra compute over current formulas.

Bad:
- Requires maintaining source distinctness sets and percentile aggregation.
- Slightly less reactive to true single-source breakthroughs.

### Test implications
- Add fixture: repeated contradicting claims from same source should not increase `conflict_factor` beyond distinct-source cap.
- Add fixture: one anomalous high-novelty run should not dominate `novelty` if p75 unchanged.
- Add fixture: staleness sensitivity comparison for 30d vs 45d normalization.
- AC update proposal:
  - Add AC-CMD-FRN-002-4: factor derivation unit tests verify deterministic outputs for adversarial spam fixtures.

### Failure modes / gaming risks
- Source-splitting attack (synthetic many source IDs) can still inflate distinct counts.
- Tag stuffing can still inflate `goal_relevance`.
- Mitigation:
  - Domain-normalized source bucketing (cap per normalized locator domain contribution).
  - Tag normalization and allowlist for project tags in relevance calculation.

### Proposed normative spec text block (paste-ready)
```md
**Normative update (FRN-1 hardened deterministic factors):**
For each reading target `T` in snapshot `S`:
- `conflict_factor(T) = clamp01(distinct_conflict_source_ids(T) / 3.0)`
- `support_gap(T) = 1.0 - clamp01(distinct_support_source_ids(T) / 3.0)`
- `goal_relevance(T)` follows existing project/tag weighted rule in §5.2.7.
- `novelty(T) = clamp01(p75_linked_delta_novelty_30d(T))`, where percentile is computed over linked Delta Reports in the last 30 days; if none linked, `0.0`.
- `staleness(T) = clamp01(days_between(snapshot_ref_ts, review_ts(T)) / 45.0)`.

Determinism requirements:
- Inputs are sourced only from persisted vault artifacts.
- Aggregation order is deterministic (stable sort by target id, run id).
- Any missing values use explicit defaults documented above.
```

**Confidence:** 0.84

---

## Decision 2: MVP3-1 Triage Scoring, Watery/Dense Thresholds, Skip-List

### Context
Need triage bucketing and skip-list behavior that reduces attention thrash without hiding important work or enabling suppression attacks.

### Option A (current patched baseline)
- `triage_score = 0.45*conflict + 0.25*support_gap + 0.20*novelty + 0.10*staleness`
- Buckets: dense `>=0.67`, mixed `[0.34,0.67)`, watery `<0.34`
- Skip-list add after 3 consecutive watery runs with no conflict/open-question.

### Option B (safety-hardened hysteresis)
- Keep score weights (conflict-first) for continuity.
- Adjust thresholds and skip controls:
  - dense `>=0.70`
  - mixed `[0.30, 0.70)`
  - watery `<0.30`
- Skip-list add rule:
  - require 4 consecutive watery runs,
  - `conflict_factor=0`, no open questions,
  - target age `>=14d`,
  - target is not manually pinned.
- Skip-list remove rule:
  - any new conflict/open question,
  - explicit manual unskip,
  - or automatic expiry after 30 days.
- Guardrail: max 25% of targets may be skipped in one snapshot; overflow remains watery but not skipped.

### Option C (aggressive adaptive quantiles)
- Dynamic percentile-based thresholds per run.
- Faster adaptation, weaker comparability and easier to game by distribution shaping.

### Recommendation
**Pick Option B.**

Why:
- Hysteresis and age/pin constraints reduce false suppression of emerging topics.
- Fixed thresholds preserve deterministic and cross-run comparability.
- Skip-cap prevents silent disappearance of large topic sets.

### Consequences
Good:
- Better operational safety; fewer accidental blind spots.
- More stable triage behavior across oscillating inputs.
- Clear reviewer override points (pin/unskip).

Bad:
- Slightly slower suppression of truly low-value watery items.
- Adds policy complexity and additional test matrix.

### Test implications
- Add fixture: oscillating target around threshold should not flip skip state rapidly.
- Add fixture: pinned target never enters skip-list regardless of watery streak.
- Add fixture: skip cap enforcement at 25% snapshot limit.
- Add fixture: skip expiry re-evaluation after 30 days.
- AC update proposal:
  - Add AC-MVP3-1-1: skip-list state transitions are deterministic and auditable.
  - Add AC-MVP3-1-2: skip-cap and pin overrides are enforced.

### Failure modes / gaming risks
- Adversary may attempt to push target watery repeatedly via low-signal ingest.
- Collusive tag manipulation could lower relevance and inflate watery streaks.
- Mitigation:
  - require minimum observation age and non-pinned condition for skip.
  - log every skip transition with factor snapshot and actor.

### Proposed normative spec text block (paste-ready)
```md
**Normative update (MVP3-1 triage/skip safety):**
- `triage_score = clamp01(0.45*conflict_factor + 0.25*support_gap + 0.20*novelty + 0.10*staleness)`.
- Buckets:
  - `dense` if `triage_score >= 0.70`
  - `mixed` if `0.30 <= triage_score < 0.70`
  - `watery` if `triage_score < 0.30`
- Skip-list add conditions (all required):
  - 4 consecutive `watery` runs,
  - `conflict_factor == 0`,
  - no open-question references,
  - target age `>= 14 days`,
  - target not manually pinned.
- Skip-list removal conditions (any):
  - new conflict/open question,
  - explicit manual unskip,
  - skip entry age exceeds 30 days (auto-expire and re-evaluate).
- Safety cap: no more than 25% of snapshot targets may be in skip-list at once.
- Every skip transition MUST append an audit event containing prior state, new state, factor snapshot, and reason.
```

**Confidence:** 0.81

---

## Decision 3: MVP3-2 Graph Algorithms and Performance Targets

### Context
Need minimum viable graph analytics that are deterministic, useful, resistant to link-spam gaming, and performant under realistic graph sizes.

### Option A (current patched baseline)
- Hubs: top-K by degree centrality.
- Bridges: articulation points + bridge edges via Tarjan (`O(V+E)`).
- Targets for 5k nodes / 20k edges:
  - build `<=3s`,
  - hub+bridge `<=5s`,
  - end-to-end `<=8s`.

### Option B (hardened hybrid baseline + deep mode)
- Baseline (required):
  - Hubs by **robust degree**: unique canonical inbound links with per-source contribution cap.
  - Bridges via Tarjan articulation points + bridge edges.
- Deep mode (optional):
  - approximate betweenness + PageRank behind explicit flag (`--analysis=deep`), non-blocking for MVP3 baseline.
- Performance targets (same fixture size):
  - graph build p95 `<= 2.5s`
  - baseline hub+bridge p95 `<= 4.5s`
  - baseline end-to-end p95 `<= 7.5s`
- Budget/fail-safe:
  - if graph exceeds budget (`>20k nodes` or `>100k edges`), return bounded partial output + warning/audit event rather than unbounded runtime.

### Option C (advanced-only)
- Require PageRank + exact betweenness/community detection in MVP3 baseline.
- Higher insight, high CPU cost and DoS surface.

### Recommendation
**Pick Option B.**

Why:
- Tarjan stays linear and deterministic.
- Robust-degree reduces trivial link-spam hub inflation.
- Deep mode allows richer analysis without making baseline brittle.
- Explicit budget caps prevent runaway runtime and resource exhaustion.

### Consequences
Good:
- Better abuse resistance and operational predictability.
- More realistic SLAs for routine runs.
- Clear degraded-mode behavior under oversized graphs.

Bad:
- More implementation complexity (baseline + deep modes).
- Must maintain explainability of robust-degree weighting.

### Test implications
- Add fixture: star-spam graph to verify robust-degree dampening.
- Add fixture: deterministic articulation/bridge outputs for known graph.
- Add fixture: over-budget graph triggers bounded fallback with warning.
- AC update proposal:
  - Add AC-MVP3-2-1: baseline analysis meets performance targets on seeded fixture.
  - Add AC-MVP3-2-2: over-budget graph path fails-safe with deterministic warning and partial output contract.

### Failure modes / gaming risks
- Link-storm attack to inflate hub rank.
- Giant graph ingestion causing CPU/memory exhaustion.
- Deterministic deep-mode drift if approximation seeds not fixed.
- Mitigation:
  - per-source cap in robust degree,
  - hard graph budget + timeout,
  - fixed seeds and deterministic ordering for approximate algorithms.

### Proposed normative spec text block (paste-ready)
```md
**Normative update (MVP3-2 graph analytics hardening):**
Graph substrate remains Canonical Scope wikilink graph.

Baseline required outputs:
- `hubs`: top-K by robust degree centrality (unique canonical inbound links with per-source contribution cap).
- `articulation_points` and `bridge_edges` via Tarjan algorithm (`O(V+E)`).

Optional deep mode (`--analysis=deep`):
- approximate betweenness and PageRank; deep mode outputs MUST be deterministic under fixed seed.

Performance targets on seeded fixture (`~5k` nodes / `~20k` edges):
- graph build p95 `<= 2.5s`
- baseline hub+bridge analysis p95 `<= 4.5s`
- baseline end-to-end graph analysis p95 `<= 7.5s`

Budget safety:
- If graph exceeds budget (`>20k` nodes or `>100k` edges), command MUST return bounded partial baseline outputs with warning `WARN_GRAPH_BUDGET_EXCEEDED` and emit audit details.
```

**Confidence:** 0.79

---

## If I Were Final Decider

I would adopt:
1. **FRN-1: Option B** (distinct-source factors, p75 novelty, 45-day staleness).
2. **MVP3-1: Option B** (hysteresis thresholds + safe skip-list guardrails and cap).
3. **MVP3-2: Option B** (robust-degree + Tarjan baseline, optional deep mode, explicit graph budget fail-safe).

Rationale for all three picks:
- Maximum safety-per-complexity for MVP trajectory.
- Deterministic and testable behavior with stronger abuse resistance.
- Better operational failure behavior (bounded execution, auditable transitions, controlled degradation).
