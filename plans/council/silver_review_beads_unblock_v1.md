# SilverDune Review Beads Unblock Proposal v1

## Scope
- Agent: SilverDune
- Phase: PLAN-REVIEW (planning-only)
- Inputs reviewed:
  - `docs/plans/mycelium_refactor_plan_apr_round5.md`
  - `plans/council/teal_decompose_proposal_v1.md`
  - `plans/council/copper_decompose_proposal_v1.md`

## Bead Review Summary
- Reviewed: 2 decomposition artifacts (0 newly-created plan beads in this wave)
- Existing `br` graph reviewed: 2 legacy issues (`mycelium-1`, `mycelium-2`), unrelated to round-5 decomposition set

### BV Analysis
Commands run:
- `bv --robot-triage`
- `bv --robot-insights`
- `bv --robot-plan`
- `bv --robot-priority`

Observed results (for current `.beads` graph only):
- Cycles: none (`Cycles: null`, `cycle_count: 0`)
- Bottlenecks: none (`Bottlenecks: []`)
- High centrality issues: `mycelium-1`, `mycelium-2` (PageRank 0.5 each)
- Parallel tracks: 2 tracks (one issue per track)

Interpretation:
- BV output is structurally healthy but not useful for round-5 decomposition quality because it analyzes legacy blocker issues unrelated to review-digest/promotion/frontier plan work.
- For this wave, artifact quality and ambiguity closure are the primary review signal.

## Review of Decomposition Artifacts

### Teal Proposal (`teal_decompose_proposal_v1.md`)
- Gate discipline: PASS
- CASS pre-check: PASS
- Ambiguity gate rigor: PASS (`blocking_ambiguities=6`)
- Strength: includes `TODO-Q-NAM-1` as blocker, which is a valid unresolved TODO in final plan (`line 426`)
- Gap: skipped BV analysis entirely; preferred approach is to run BV and explicitly note non-applicability to proposed bead set

### Copper Proposal (`copper_decompose_proposal_v1.md`)
- Gate discipline: PASS
- CASS pre-check: PASS
- Ambiguity gate rigor: PASS (`blocking_ambiguities=5`)
- Strength: clear clarify questions and explicit fail-closed behavior
- Gap: excludes `TODO-Q-NAM-1` from blocker set despite unresolved TODO in final spec (`line 426`)

## Blocker Accuracy Validation Against Final Plan TODO-Q Lines

Reference TODO-Q lines from final plan:
- `TODO-Q-NAM-1` line 426
- `TODO-Q-RDG-1` line 641
- `TODO-Q-FRN-1` line 745
- `TODO-Q-CONF-1` line 934
- `TODO-Q-REV-1` line 958
- `TODO-Q-REV-2` line 1009
- `TODO-Q-SEC-1` line 1086

### Accuracy Assessment
- Correct blockers for decomposition now:
  - `TODO-Q-RDG-1`, `TODO-Q-REV-1`, `TODO-Q-REV-2`, `TODO-Q-SEC-1`, `TODO-Q-FRN-1`
- Additional blocker to include:
  - `TODO-Q-NAM-1` should be treated as decomposition-blocking for schema/ID validation and migration lane planning.
- Not blocking for current decomposition wave:
  - `TODO-Q-CONF-1` is explicitly MVP2+ calibration, while MVP1 deterministic advisory rubric is already defined (`CONF-001`), so this should not block initial decomposition.

Consolidated blocker count for unblock pass: `blocking_ambiguities=6`.

## Consolidated Assumption Pack (to force `blocking_ambiguities=0`)

If all assumptions below are accepted as defaults, decomposition can proceed safely.

### A1 — `TODO-Q-NAM-1` (ID migration compatibility mode)
Recommended default:
- Add config key `id_compat_mode` with values: `strict_hybrid|legacy_read_only`.
- Default: `strict_hybrid`.
- `legacy_read_only` behavior:
  - existing slug-only IDs are accepted for read/validate if file already exists before migration cutover;
  - new machine-generated notes still MUST use hybrid format.

### A2 — `TODO-Q-RDG-1` (review_digest trigger authority)
Recommended default:
- Authoritative trigger is explicit command invocation (`review_digest`) via CLI/MCP.
- External scheduler/client integrations are optional wrappers that invoke the same command contract.
- Acceptance tests target direct command path only.

### A3 — `TODO-Q-REV-1` (hold TTL storage and resurfacing)
Recommended default:
- Canonical `hold_until` stored in Review Decision Record (`SCH-010`) and mirrored in packet decision (`SCH-009`) for operator readability.
- Resurface rule: include held queue items when `digest_date >= hold_until` during `review_digest` generation.
- No background scheduler required; resurfacing is evaluated on each digest generation call.

### A4 — `TODO-Q-REV-2` (Git Mode enablement + commit convention)
Recommended default:
- Git Mode enablement via `graduate --git-mode` (flag) with config fallback `git_mode_default=false`.
- Commit granularity remains one commit per source packet batch (`REV-004`).
- Commit message minimum template:
  - `promote(packet=<packet_id>, source=<source_id>, runs=<run_ids_csv>)`

### A5 — `TODO-Q-SEC-1` (burn-in tracking and mode storage)
Recommended default:
- Persist egress mode state in durable policy file: `Logs/Audit/egress_policy_state.yaml`.
- Required fields: `mode`, `burn_in_started_at`, `burn_in_days`, `last_transition_at`, `last_transition_actor`, `reason`.
- Transition policy:
  - start in `report_only`;
  - allow transition to `enforce` only by explicit command/action after `now >= burn_in_started_at + 14d`.

### A6 — `TODO-Q-FRN-1` (deterministic frontier factor derivations)
Recommended default formulas:
- `conflict_factor = min(1, contradicting_edges / max(1, related_claims))`
- `support_gap = 1 - min(1, support_count / support_target)` where `support_target=3`
- `goal_relevance = min(1, (tag_overlap_score + project_match_score)/2)`
  - `tag_overlap_score = overlap(tags_target, tags_goal)` normalized [0..1]
  - `project_match_score = 1` if project matches filter else `0`
- `novelty = min(1, avg_recent_delta_novelty_last_30d)`
- `staleness = min(1, days_since(last_reviewed_at or updated)/30)`

Determinism constraints:
- all numeric inputs sourced from vault artifacts only
- fixed lookback windows (`30d`)
- lexical tie-break fallback unchanged per `CMD-FRN-002`

## Conditional Decomposition Map (If Assumptions A1–A6 are accepted)

### Proposed Beads (proposal-only; no `br create/update/dep` executed)

1. Title: `Implement command envelope middleware for vault commands`
- Type: feature
- Priority: 0
- Acceptance criteria snippet:
  - [ ] New vault command handlers return IF-001 envelope keys exactly.
  - [ ] Error/warning objects include required fields (`code`, `message`, `retryable`).

2. Title: `Implement schema validators for review packets and decision records`
- Type: feature
- Priority: 0
- Acceptance criteria snippet:
  - [ ] Packet validator enforces `SCH-009` including `approve_selected` ID validation.
  - [ ] Decision record validator enforces `SCH-010` including hold semantics.

3. Title: `Implement ID compatibility mode for NAM-001 migration path`
- Type: task
- Priority: 1
- Acceptance criteria snippet:
  - [ ] `strict_hybrid` blocks new non-hybrid machine IDs.
  - [ ] `legacy_read_only` accepts pre-existing slug-only IDs without permitting new slug-only machine outputs.

4. Title: `Implement review_digest grouped-by-source generator`
- Type: feature
- Priority: 1
- Acceptance criteria snippet:
  - [ ] Generates one packet per source with deterministic ordering in deterministic mode.
  - [ ] Includes required packet decision slots (`approve_all|approve_selected|hold|reject`).

5. Title: `Implement hold TTL resurfacing during digest generation`
- Type: feature
- Priority: 1
- Acceptance criteria snippet:
  - [ ] Held items resurface when `digest_date >= hold_until`.
  - [ ] Behavior is deterministic and does not rely on background scheduler.

6. Title: `Implement review command state transitions with immutability guard`
- Type: feature
- Priority: 1
- Acceptance criteria snippet:
  - [ ] Legal transitions only from `pending_review` to `approved|rejected`.
  - [ ] Illegal transitions return `ERR_QUEUE_IMMUTABLE`.

7. Title: `Implement auto-approval lane policy classifier`
- Type: feature
- Priority: 1
- Acceptance criteria snippet:
  - [ ] `NEW` and `CONTRADICTING` are never auto-approved.
  - [ ] Auto-approved items include policy reason codes in audit details.

8. Title: `Implement graduate from_digest strict atomic apply path`
- Type: feature
- Priority: 0
- Acceptance criteria snippet:
  - [ ] Applies only approved queue items from packet decisions.
  - [ ] Per-item atomicity: failed item does not mutate canonical scope while others may proceed.

9. Title: `Implement Git Mode apply adapter and commit template enforcement`
- Type: task
- Priority: 2
- Acceptance criteria snippet:
  - [ ] One commit per source packet apply batch when Git Mode enabled.
  - [ ] Commit message matches required template fields.

10. Title: `Implement append-only JSONL audit writer and mode transition events`
- Type: feature
- Priority: 1
- Acceptance criteria snippet:
  - [ ] Audit log lines are JSON-parseable and append-only.
  - [ ] Mode transitions (`report_only -> enforce`) emit actor/timestamp/reason events.

11. Title: `Implement egress policy state store and burn-in enforcement gate`
- Type: feature
- Priority: 1
- Acceptance criteria snippet:
  - [ ] Policy state persisted with burn-in metadata.
  - [ ] Enforce transition blocked until burn-in threshold satisfied and explicit transition invoked.

12. Title: `Implement deterministic frontier factor derivation engine`
- Type: feature
- Priority: 1
- Acceptance criteria snippet:
  - [ ] All five factors computed with deterministic formulas and bounded [0..1].
  - [ ] Repeated fixture runs produce byte-identical ordering/scores.

13. Title: `Add integration/e2e/regression tests for digest-review-graduate workflow`
- Type: test
- Priority: 1
- Acceptance criteria snippet:
  - [ ] End-to-end test covers approve_all/approve_selected/hold/reject plus graduate apply.
  - [ ] Regression tests cover immutable transitions and resurfacing edge cases.

14. Title: `Add performance bench harness for PERF-001 thresholds`
- Type: test
- Priority: 2
- Acceptance criteria snippet:
  - [ ] Bench reports p50/p95/p99 for required commands.
  - [ ] Threshold breach fails gate unless explicit waiver.

### Proposed Dependencies (child -> parent)
- 2 -> 1
- 3 -> 2
- 4 -> 2
- 5 -> 4
- 6 -> 2
- 7 -> 6
- 8 -> 4
- 8 -> 6
- 9 -> 8
- 10 -> 1
- 11 -> 10
- 12 -> 1
- 13 -> 4
- 13 -> 5
- 13 -> 6
- 13 -> 8
- 13 -> 12
- 14 -> 8
- 14 -> 12

### Suggested Swarm Ordering
Wave 1 (foundation):
- Beads 1, 2, 10 in parallel

Wave 2 (policy + packet core):
- Beads 3, 4, 6, 11, 12 in parallel where dependencies allow

Wave 3 (review ergonomics + apply path):
- Beads 5, 7, 8

Wave 4 (hardening):
- Beads 9, 13, 14

### Risk Hotspots
1. Hold resurfacing timezone/off-by-one errors (digest date vs timestamp boundary).
2. Git Mode packet isolation mistakes causing cross-packet diff contamination.
3. Frontier factor deterministic derivation drift causing flaky ranking tests.
4. Egress mode transition race conditions between policy state and audit append.

## Disagreements with Prior Artifacts (and resolution)
1. Disagreement: Copper excludes `TODO-Q-NAM-1` from blockers.
- Resolution: include `TODO-Q-NAM-1` in blocker set and resolve via Assumption A1 to prevent migration/validation drift.

2. Disagreement: Teal skipped BV analysis completely because no beads were created.
- Resolution: run BV anyway for baseline project-graph health, then explicitly mark it as non-representative for round-5 decomposition set.

## Final Review Position
- Current state: pre-bead gate remains FAIL until assumptions A1–A6 are ratified.
- Conditional state: once assumptions are accepted, this artifact provides a decomposition-ready, dependency-ordered bead proposal without requiring additional clarify round-trips.
