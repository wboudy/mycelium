# Copper Decision Merge v1

ROLE_ACK: WORKER
PHASE: DECISION-MERGE
AGENT: CopperHawk
Date: 2026-03-02
Finalization note: finalized from already collected evidence per orchestrator directive; no additional searching performed.

## Run Arguments
- PLAN_A_PATH: `/Users/will/Developer/mycelium/mycelium/plans/council/blue_decision_recommendations_v1.md`
- PLAN_B_PATH: `/Users/will/Developer/mycelium/mycelium/plans/council/teal_decision_recommendations_v1.md`
- PLAN_C_PATH: `/Users/will/Developer/mycelium/mycelium/plans/council/silver_decision_recommendations_v1.md`
- SPRINT_SPEC_PATH: `/Users/will/Developer/mycelium/mycelium/docs/plans/mycelium_refactor_plan_apr_round5.md`
- COPPER_SOURCE_PATH: `/Users/will/Developer/mycelium/mycelium/plans/council/copper_decision_recommendations_v1.md`
- OUTPUT_PATH: `/Users/will/Developer/mycelium/mycelium/plans/council/copper_decision_merge_v1.md`

## Scope Guard
This merge is strictly scoped to three decisions only:
1. FRN-1 frontier factor derivations
2. MVP3-1 triage scoring + watery/dense thresholds + skip-list behavior
3. MVP3-2 graph algorithms + performance targets

No implementation/code changes are proposed in this artifact.

## Evidence Baseline (Spec + Repo)

### Sprint spec source-of-truth evidence
- `CMD-FRN-002` deterministic scoring exists with weighted formula (`.../mycelium_refactor_plan_apr_round5.md:738`).
- FRN factor derivations already patched but still candidate-level for this council merge (`...:753`).
- MVP3 section includes provisional candidate resolutions for triage and graph analytics (`...:1214`, `...:1217`, `...:1228`).

### Repository implementation evidence
- No frontier/triage/graph algorithm implementation symbols found in source/tests (`rg` on `frontier|triage_score|watery|dense|Tarjan|PageRank|betweenness` returned no matches in `src/` and `tests/`).
- Current CLI surface remains mission orchestration only (`run|status|auto`) in `src/mycelium/cli.py` (`add_parser` lines around 293/318/334).

Interpretation:
- These three decisions are policy/spec-level finalization work; they are not yet represented in runtime code paths.

## Requirement Traceability Matrix (Decision Scope)

| Decision | Requirement/TODO | Spec Evidence | Plan Claims Compared | Repo Evidence | Merge Status |
|---|---|---|---|---|---|
| FRN-1 | `CMD-FRN-002` + `TODO-Q-FRN-1` | lines 738, 753 | Blue/Teal/Silver/Copper all propose deterministic alternatives with differing formulas | No `frontier` implementation in `src/`/`tests` | Final recommendation selected below |
| MVP3-1 | `TODO-Q-MVP3-1` | line 1217 | Blue/Teal/Silver/Copper differ on thresholds/hysteresis/skip policy | No triage engine code in repo | Final recommendation selected below |
| MVP3-2 | `TODO-Q-MVP3-2` | line 1228 | Blue/Teal/Silver/Copper differ on hub algorithm and perf envelope | No graph-analysis command implementation | Final recommendation selected below |

## Conflict Resolution (with Rationale)

### Decision 1: FRN-1 (Frontier Factor Derivations)

#### Alternatives considered
- Option A: Keep current patched formulas unchanged.
- Option B: Deterministic hardening with anti-gaming/fidelity improvements (varies by plan).
- Option C: Learned or heavy adaptive model.

#### Final recommended option
**Option B (deterministic hardened, maintainable variant).**

Chosen formula family (merged):
- `conflict_factor` and `support_gap` based on **distinct source evidence**, bounded with simple clamp.
- `goal_relevance` keeps project/tag weighted deterministic rule with neutral fallback.
- `novelty` uses **recency-weighted mean** over linked deltas (not max, not percentile-only).
- `staleness` uses **command reference time** (`as_of_ts`) against target-local review/update timestamp.

Why this merge is preferred:
- Lower gaming exposure than raw-count or max-spike novelty.
- Better stability and explainability than percentile-only novelty.
- Lower implementation complexity and migration risk than ML/adaptive models.

#### Rejected alternatives + why
- Rejected A: fixed `/3` + `max novelty` can over-react to one stale spike.
- Rejected C: higher complexity, weaker deterministic reproducibility, harder rollback.

#### Dissent notes preserved
- Teal preferred p75 novelty (more outlier-robust).
- Blue preferred stronger immediate recency (30-day staleness denominator).
- Silver preferred stronger ratio normalization and explicit decay at 45 days.

#### Consequences
Good:
- Deterministic, explainable, anti-spam improvements.
- Better ranking robustness across vault sizes.

Bad:
- Requires timestamp hygiene and decay fixture coverage.
- Slightly more compute than max-based novelty.

#### Failure modes / gaming risks
- Source-splitting to inflate distinct-source counts.
- Tag stuffing for relevance inflation.
- Timestamp manipulation.

Mitigations:
- Domain/locator bucketing caps.
- Token normalization and deduped tags.
- strict UTC parse + deterministic test clock.

#### Confidence
`0.83`

#### Paste-ready normative spec text
```md
**Resolution (TODO-Q-FRN-1) [Council Merge v1]:** Frontier factor derivations are deterministic and defined for each target `T` at command timestamp `as_of_ts`.

Let:
- `distinct_conflict_sources(T)` = number of distinct `source_id` values in schema-valid conflict records citing `T`.
- `distinct_support_sources(T)` = number of distinct supporting `source_id` values linked to `T`.
- `review_ts(T)` = `last_reviewed_at` when present, otherwise `updated`.
- `linked_deltas(T)` = linked Delta Reports with `(novelty_score, created_at)`.
- `age_days(d)` = days between `as_of_ts` and `d.created_at`.
- `w(d) = exp(-age_days(d)/45)`.

Derivations:
- `conflict_factor(T) = clamp01(distinct_conflict_sources(T) / 3.0)`
- `support_gap(T) = 1.0 - clamp01(distinct_support_sources(T) / 3.0)`
- `goal_relevance(T)`:
  - if no `goal` and no `project/tags` filters: `0.5`
  - else `clamp01(0.6*project_match(T) + 0.4*tag_overlap(T))`
- `novelty(T)`:
  - if no linked deltas: `0.0`
  - else `clamp01( sum(w(d)*d.novelty_score) / max(1e-9, sum(w(d))) )`
- `staleness(T) = clamp01(days_between(as_of_ts, review_ts(T)) / 45.0)`

All factor values MUST be in `[0..1]` and included in output `reading_targets[*].factors`.
```

---

### Decision 2: MVP3-1 (Triage + Watery/Dense + Skip-list)

#### Alternatives considered
- Option A: keep current patched thresholds and skip rules.
- Option B: fixed-score model with stronger safety guardrails.
- Option C: dynamic quantile/percentile thresholds.

#### Final recommended option
**Option B (fixed deterministic model + governance guardrails).**

Chosen policy merge:
- Keep current deterministic score weights for continuity.
- Add explicit run cadence semantics (`digest_date`-based streaking).
- Add hysteresis to reduce bucket oscillation.
- Add guarded skip-list policy: streak requirement, pin protection, TTL revisit, hard cap.

Why this merge is preferred:
- Maintains deterministic comparability across runs.
- Reduces accidental suppression and threshold flapping.
- Practical to roll out with auditability and low migration risk.

#### Rejected alternatives + why
- Rejected A: too easy to oscillate and over-skip.
- Rejected C: percentile thresholds are harder to explain/test deterministically.

#### Dissent notes preserved
- Teal favored stricter watery threshold (`<0.30`) and 4-run skip gate.
- Silver favored adding `goal_relevance` into triage score itself.
- Blue favored minimal threshold movement with narrower hysteresis.

#### Consequences
Good:
- More stable triage labels.
- Skip-list behavior becomes transparent and reversible.

Bad:
- More policy state to maintain (`watery_streak`, `skip_since`, `next_review_at`).
- Larger transition test matrix.

#### Failure modes / gaming risks
- Repeated low-signal ingests to force watery streak.
- Hiding conflict/question links before evaluation.

Mitigations:
- Require conflict/question clean state + non-pinned + minimum age for skip.
- Audit every skip/unskip with reason and factor snapshot.

#### Confidence
`0.80`

#### Paste-ready normative spec text
```md
**Resolution (TODO-Q-MVP3-1) [Council Merge v1]:** MVP3 triage buckets and skip-list behavior are deterministic and safety-guarded.

Score:
- `triage_score = clamp01(0.45*conflict_factor + 0.25*support_gap + 0.20*novelty + 0.10*staleness)`

Buckets:
- enter `dense` when `triage_score >= 0.67`
- enter `watery` when `triage_score < 0.34`
- otherwise `mixed`

Hysteresis:
- `dense -> mixed` only after 2 consecutive `digest_date` evaluations with `triage_score < 0.62`
- `watery -> mixed` on first evaluation with `triage_score >= 0.42`

Consecutive run semantics:
- streak counters advance at most once per target per `digest_date`.

Skip-list add conditions (all required):
- 4 consecutive `watery` evaluations
- `conflict_factor == 0`
- no open-question references
- target age `>= 14d`
- target is not manually pinned

Skip-list removal (any):
- new conflict reference
- new open-question reference
- manual unskip
- periodic revisit at `skip_since + 30d`

Safety cap:
- skipped targets MUST NOT exceed 25% of active targets per snapshot.

Skipped targets are excluded by default and included only when `include_skip=true`.
All skip transitions MUST emit audit events with reason codes and factor snapshots.
```

---

### Decision 3: MVP3-2 (Graph Algorithms + Performance Targets)

#### Alternatives considered
- Option A: degree-only hubs + Tarjan bridges + current performance envelope.
- Option B: hardened baseline + optional deep mode.
- Option C: heavy analytics mandatory in default path.

#### Final recommended option
**Option B (two-tier graph analysis: robust default + optional deep mode).**

Chosen algorithm merge:
- Baseline default path:
  - canonical wikilink graph substrate
  - hubs by composite of normalized degree and normalized core number
  - articulation points + bridge edges by Tarjan on undirected projection
- Optional deep mode:
  - PageRank / approximate betweenness behind explicit flag (non-gating baseline)

Chosen performance envelope:
- Keep spec-compatible baseline gates for medium fixture (`<=3s`, `<=5s`, `<=8s`).
- Add large-fixture advisory targets (non-blocking initially) to reduce rollout shock.

Why this merge is preferred:
- Better hub quality than degree-only, lower complexity than deep-by-default.
- Maintains deterministic baseline and practical rollout.
- Preserves optional future sophistication without violating SLA.

#### Rejected alternatives + why
- Rejected A: degree-only hubs vulnerable to link-farm noise.
- Rejected C: too expensive/risky as mandatory default for MVP3 baseline.

#### Dissent notes preserved
- Silver favored PageRank in baseline hub score.
- Teal favored stricter medium SLA (`2.5/4.5/7.5`) and explicit graph budget fail-safe.
- Blue favored simpler degree+core baseline without large-fixture gate.

#### Consequences
Good:
- Better structural signal with manageable compute.
- Deterministic and explainable outputs.

Bad:
- Dual-mode path adds test burden.
- Core-number introduces extra metric education for users.

#### Failure modes / gaming risks
- Link-spam hub inflation.
- Very large graph causing runtime blowups.

Mitigations:
- Deduplicate edges and cap repeated source contributions.
- Graph budget warning/fallback path.
- Lexical tie-break for deterministic ordering.

#### Confidence
`0.82`

#### Paste-ready normative spec text
```md
**Resolution (TODO-Q-MVP3-2) [Council Merge v1]:** MVP3 graph analysis uses a deterministic two-tier model.

Default required path (`analysis_depth=default`):
- Build directed wikilink graph over Canonical Scope notes and undirected projection for connectivity analysis.
- Hub score:
  - `hub_score = 0.7*norm(total_degree) + 0.3*norm(core_number)`
  - report top-K hubs with metrics (`total_degree`, `core_number`, `hub_score`)
- Bridge analysis:
  - articulation points and bridge edges via Tarjan (`O(V+E)`) on undirected projection.

Optional deep path (`analysis_depth=deep`):
- may include PageRank and approximate betweenness with deterministic seeds/order.
- deep-path metrics are non-gating for baseline SLA unless explicitly enabled.

Performance targets (medium fixture `~5k nodes / ~20k edges`):
- graph build p95 `<= 3s`
- default hub+bridge analysis p95 `<= 5s`
- default end-to-end graph analysis p95 `<= 8s`

Advisory large-fixture targets (`~10k nodes / ~50k edges`, non-gating initially):
- graph build p95 `<= 6s`
- default core analysis p95 `<= 9s`
- default end-to-end p95 `<= 14s`
```

## File-Level Implementation Map (Decision Rollout)

### Files to update (spec/planning)
- `docs/plans/mycelium_refactor_plan_apr_round5.md`
  - Replace/adjust FRN-1 resolution block (current around line 753).
  - Replace/adjust MVP3-1 resolution block (current around line 1217).
  - Replace/adjust MVP3-2 resolution block (current around line 1228).
- `plans/council/copper_decision_merge_v1.md`
  - Council decision record (this file).

### Future code files likely impacted (not edited in this task)
- New retrieval/scoring modules (expected):
  - `src/mycelium/vault/retrieval/frontier.py`
  - `src/mycelium/vault/retrieval/triage.py`
  - `src/mycelium/vault/retrieval/graph_analysis.py`
- New tests (expected):
  - `tests/vault/test_frontier_factors.py`
  - `tests/vault/test_triage_skiplist.py`
  - `tests/vault/test_graph_algorithms.py`
  - `tests/vault/test_graph_perf.py`

## Dependency-Ordered Execution Plan (Planning Only)

### D0 (P0): Decision lock + spec patch prep
- Inputs: blue/teal/silver/copper recommendation artifacts + sprint spec.
- Output: ratified merged normative text for FRN-1, MVP3-1, MVP3-2.
- Depends on: none.

### D1 (P0): FRN-1 normative update + AC deltas
- Apply merged FRN text and add AC notes for anti-gaming/determinism.
- Depends on: D0.

### D2 (P0): MVP3-1 normative update + state semantics
- Apply merged triage/skip-list semantics and cadence/hysteresis rules.
- Depends on: D0.

### D3 (P0): MVP3-2 normative update + perf envelope
- Apply two-tier graph algorithm definition and baseline/advisory targets.
- Depends on: D0.

### D4 (P1): Verification pack alignment
- Define fixture updates and benchmark expectations from D1-D3.
- Depends on: D1, D2, D3.

Parallelization notes:
- D1-D3 can run in parallel after D0 freeze.
- D4 waits on all D1-D3 outputs.

## Verification Matrix

| Check | Command | Expected Output | Artifact |
|---|---|---|---|
| Spec anchors present | `rg -n "Resolution \(TODO-Q-FRN-1\)|Resolution \(TODO-Q-MVP3-1\)|Resolution \(TODO-Q-MVP3-2\)" docs/plans/mycelium_refactor_plan_apr_round5.md` | Exactly 3 updated resolution blocks found | updated spec file |
| FRN deterministic contract | `pytest tests/vault/test_frontier_factors.py -q` | factor bounds + deterministic outputs pass | test report |
| Triage skip semantics | `pytest tests/vault/test_triage_skiplist.py -q` | streak/hysteresis/skip-cap/TTL tests pass | test report |
| Graph baseline correctness | `pytest tests/vault/test_graph_algorithms.py -q` | hub/articulation/bridge fixtures pass | test report |
| Graph perf baseline | `pytest tests/vault/test_graph_perf.py -q` | medium p95 thresholds pass | benchmark artifact |
| Existing CLI unaffected | `pytest tests/test_orchestrator.py tests/test_mcp.py tests/test_llm.py tests/test_tools.py -q` | current mission-orchestration tests stay green | regression safety report |

## Risk Register (Top 10 Risks/Gaps)

1. FRN novelty decay window mis-tuned, causing under-prioritization of true new signals.
2. Distinct-source counting vulnerable to source-splitting attacks.
3. Goal relevance tokenization drift between environments.
4. Triage hysteresis state bugs causing bucket lock-in.
5. Skip-list cap side effects reducing suppression efficacy for truly watery sets.
6. Skip-list TTL revisit flood causing sudden queue spikes.
7. Degree/core composite hub score over-weights structural but low-value nodes.
8. Optional deep mode introduces deterministic drift if seeds/order not fixed.
9. Advisory large-fixture targets ignored too long, delaying scale readiness.
10. Acceptance criteria updates lag behind normative text changes, causing test/spec mismatch.

## Rollback Plan

- Rollback point R1 (after D1): revert FRN-1 block to previous patched text if factor tests regress severely.
- Rollback point R2 (after D2): disable skip-list hysteresis/cap additions by reverting to static prior semantics.
- Rollback point R3 (after D3): keep current baseline graph text (degree+Tarjan) if composite hub score proves unstable.
- Rollback point R4 (after D4): freeze advisory-only rollout (no gating changes) until fixture and benchmark reliability is restored.

## Human Final Call (Open Toggles)

### FRN-1 toggles
1. Staleness denominator: `45` days vs `60` days.
2. Novelty aggregation: recency-weighted mean vs p75 percentile.

### MVP3-1 toggles
1. Watery skip streak threshold: `3` vs `4` consecutive runs.
2. Skip-list cap: `20%` vs `25%` active targets.

### MVP3-2 toggles
1. Baseline hub score: `degree+core` vs `degree+PageRank`.
2. Large-fixture targets: advisory-only vs immediate release gate.

## Final Recommended Option Summary
- FRN-1: **Option B** (deterministic hardening with recency-weighted novelty and as-of staleness).
- MVP3-1: **Option B** (fixed deterministic thresholds + guarded skip lifecycle and hysteresis).
- MVP3-2: **Option B** (robust two-tier graph analysis with deterministic default path and optional deep mode).
