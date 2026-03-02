# CopperHawk review_beads Unblock Proposal v1

ROLE_ACK: WORKER
PHASE: PLAN-REVIEW
AGENT: CopperHawk
Date: 2026-03-02

## Scope
- Final plan reviewed: `docs/plans/mycelium_refactor_plan_apr_round5.md`
- Decomposition artifacts reviewed:
  - `plans/council/blue_decompose_proposal_v1.md`
  - `plans/council/silver_decompose_proposal_v1.md`

## BV Analysis (Required Commands)

Commands run:
- `bv --robot-triage`
- `bv --robot-insights`
- `bv --robot-plan`
- `bv --robot-priority`

Result summary:
- Current bead graph analyzed by BV is unrelated bootstrap work (`mycelium-1`, `mycelium-2`) and not the round5 vault decomposition set.
- Cycles: none (`Cycles: null`, advisory says no cycles detected).
- Bottlenecks: none (`Bottlenecks: []`), two equal keystone nodes in current graph.
- Parallel tracks: 2 (`track-A`, `track-B`) in current graph.
- Priority suggestions: both existing P1 issues suggested toward P2 due no downstream unblock effect.

Review implication:
- BV does not validate blue/silver round5 decomposition directly because no round5 beads were created yet.
- Pre-bead review must therefore focus on ambiguity blocker correctness and unblock assumptions.

## Pre-Bead Review of Blue/Silver Artifacts

### Gate correctness check
- Blue gate result: `NO_BEAD_CREATION_DUE_TO_AMBIGUITY` with `blocking_ambiguities=6`.
- Silver gate result: `NO_BEAD_CREATION_DUE_TO_AMBIGUITY` with `blocking_ambiguities=5`.
- Both correctly avoid bead creation under unresolved ambiguity.

### Blocker accuracy vs final plan TODO lines

| TODO-Q | Spec evidence | Blue | Silver | Accuracy verdict |
|---|---|---|---|---|
| `TODO-Q-NAM-1` | `mycelium_refactor_plan_apr_round5.md:426` | included | not included | **Include as blocker** (ID compatibility mode affects validator + migration decomposition). |
| `TODO-Q-RDG-1` | `...:641` | included | included | Accurate blocker. |
| `TODO-Q-FRN-1` | `...:745` | included | included | Accurate blocker. |
| `TODO-Q-REV-1` | `...:958` | included | included | Accurate blocker. |
| `TODO-Q-REV-2` | `...:1009` | included | included | Accurate blocker. |
| `TODO-Q-SEC-1` | `...:1086` | included | included | Accurate blocker. |

Consolidated blocker count for safe decomposition: `blocking_ambiguities=6`.

## Consolidated Assumption Pack (to set blocking_ambiguities=0)

If ratified, this pack resolves all six blockers and enables decomposition.

### A1 — `TODO-Q-NAM-1` default
- Default: `compatibility_mode: legacy_slug_read_only` in `Config/validation.yaml`, default `disabled`.
- Rule: new machine-generated notes MUST use hybrid `<slug>--h-<12hex>`; legacy slug-only IDs are accepted only for pre-existing notes when mode is enabled.
- Determinism: validator behavior is fully config-driven and test-fixture reproducible.

### A2 — `TODO-Q-RDG-1` default
- Default authority: `review_digest` is command/API authoritative and may be invoked manually or by external scheduler/client wrappers.
- Acceptance anchor: contract tests target command invocation semantics only; scheduler is out-of-scope plumbing.
- Audit attribution: invoker passes `actor` explicitly.

### A3 — `TODO-Q-REV-1` default
- Hold source of truth: `hold_until` stored in Review Decision Record and mirrored in queue item metadata.
- Resurface rule: digest includes held items when `status=pending_review` and `hold_until <= digest_date`.
- Time basis: UTC date comparison on normalized `digest_date` (no background daemon required).

### A4 — `TODO-Q-REV-2` default
- Git Mode config: `Config/promotion.yaml` with `git_mode.enabled` default `false`.
- Commit granularity: exactly one commit per source packet apply batch (existing REV-004).
- Commit template minimum: `promote:{source_id}:{packet_id}:{run_id}`.

### A5 — `TODO-Q-FRN-1` default
- Deterministic factor formulas:
  - `conflict_factor = min(1, contradicting_count / max(1, total_claims_for_target))`
  - `support_gap = 1 - min(1, supporting_sources_count / 3)`
  - `goal_relevance = jaccard(goal_tags, target_tags)` (0 when no goal tags)
  - `novelty = min(1, new_claims_last_30d / 5)`
  - `staleness = min(1, days_since_last_reviewed_or_updated / 90)`
- Tie-break remains per spec (conflict desc, older review timestamp, lexical id).

### A6 — `TODO-Q-SEC-1` default
- Egress mode store: `Config/egress_policy.yaml` with `{mode, burn_in_started_at, burn_in_days, transitioned_by, transition_reason}`.
- Burn-in start: first persisted `report_only` policy activation timestamp.
- Transition authority: explicit policy transition command/action only (no silent auto-switch), requiring actor+reason and audit event.

Assumption pack outcome if accepted: `blocking_ambiguities=0`.

## Conditional Decomposition Map (only if assumptions accepted)

Planning-only proposal; no `br create/update/dep` executed.

### Proposed beads

1. `Define vault command contract envelope + router`
- Type: `feature`, Priority: `0`
- Depends on: none
- Acceptance criteria:
  - IF-001 envelope returned for `ingest|delta|review|review_digest|graduate|context|frontier` stubs.
  - Error taxonomy constants match spec IDs.

2. `Implement note-id compatibility mode switch (NAM-1)`
- Type: `task`, Priority: `0`
- Depends on: 1
- Acceptance criteria:
  - Validator enforces hybrid IDs by default.
  - Legacy slug-only acceptance only when compatibility mode enabled.

3. `Implement review queue item schema validator (SCH-007)`
- Type: `feature`, Priority: `0`
- Depends on: 1,2
- Acceptance criteria:
  - Queue YAML validates required keys and immutable fields.
  - Invalid queue item returns deterministic validation error.

4. `Implement review decision record writer (SCH-010)`
- Type: `feature`, Priority: `0`
- Depends on: 1,3
- Acceptance criteria:
  - Every successful `review` writes one schema-valid decision record.
  - Hold decision records keep queue status unchanged.

5. `Implement review state transition engine (REV-002/CMD-REV-001)`
- Type: `feature`, Priority: `0`
- Depends on: 3,4
- Acceptance criteria:
  - Legal transitions only `pending_review -> approved|rejected`.
  - Non-pending mutation fails with `ERR_QUEUE_IMMUTABLE`.

6. `Implement review_digest packet builder (SCH-009/CMD-RDG-001)`
- Type: `feature`, Priority: `0`
- Depends on: 3
- Acceptance criteria:
  - One packet per source with deterministic ordering in deterministic mode.
  - Packet action schema supports only approved action set.

7. `Implement hold TTL resurfacing in digest query (REV-1)`
- Type: `task`, Priority: `1`
- Depends on: 4,6
- Acceptance criteria:
  - Held items resurface exactly when `hold_until <= digest_date`.
  - UTC boundary behavior validated via fixtures.

8. `Implement auto-approval lane policy evaluator (REV-001B)`
- Type: `feature`, Priority: `1`
- Depends on: 3,5,6
- Acceptance criteria:
  - `NEW` and `CONTRADICTING` never auto-approved.
  - Allowed classes include explicit policy reason codes in audit details.

9. `Implement graduate strict preflight + eligibility checks`
- Type: `feature`, Priority: `0`
- Depends on: 5,8
- Acceptance criteria:
  - `dry_run=false && strict=false` fails with `ERR_SCHEMA_VALIDATION`.
  - Only approved queue items are eligible.

10. `Implement graduate per-item atomic apply engine`
- Type: `feature`, Priority: `0`
- Depends on: 9
- Acceptance criteria:
  - One failing item does not block other valid promotions.
  - Promoted notes land in canonical scope with `status: canon`.

11. `Implement Git Mode commit batching for graduate (REV-004)`
- Type: `feature`, Priority: `1`
- Depends on: 10
- Acceptance criteria:
  - Exactly one commit per source packet apply batch when enabled.
  - Commit message template includes `source_id`, `packet_id`, `run_id`.

12. `Implement append-only audit JSONL subsystem (AUD-001/002)`
- Type: `feature`, Priority: `0`
- Depends on: 1
- Acceptance criteria:
  - Ingest/review/promotion events append-only under `Logs/Audit/`.
  - Existing lines remain byte-identical after append.

13. `Implement egress policy state + transition control (SEC-1)`
- Type: `feature`, Priority: `1`
- Depends on: 12
- Acceptance criteria:
  - Policy mode persisted in `Config/egress_policy.yaml`.
  - Mode transitions require explicit actor/reason and audit event.

14. `Implement frontier factor derivation engine (FRN-1 assumptions)`
- Type: `feature`, Priority: `1`
- Depends on: 1
- Acceptance criteria:
  - All five factors computed deterministically from vault data.
  - Repeated seeded runs produce identical factor vectors.

15. `Implement frontier ranking + tie-break contract`
- Type: `feature`, Priority: `1`
- Depends on: 14
- Acceptance criteria:
  - Score formula and tie-break ordering match CMD-FRN-002.
  - Fixture verifies byte-identical ordered outputs.

16. `Add end-to-end review->digest->graduate->audit integration suite`
- Type: `test`, Priority: `0`
- Depends on: 5,6,7,9,10,12
- Acceptance criteria:
  - End-to-end flow covers `approve_all`, `approve_selected`, `hold`, `reject`.
  - Audit and queue states validated at each transition.

### Dependency graph (condensed)
- `1 -> {2,3,12,14}`
- `3 -> {4,5,6,8}`
- `4 -> 7`
- `5 -> {8,9}`
- `6 -> 7`
- `8 -> 9`
- `9 -> 10 -> 11`
- `12 -> 13`
- `14 -> 15`
- `{5,6,7,9,10,12} -> 16`

## Swarm ordering (conditional)

Wave 1 (2-3 agents): Beads 1,2,3,12 in parallel.
Wave 2 (3 agents): Beads 4,5,6 in parallel; start 14 when 1 lands.
Wave 3 (2 agents): Beads 7,8,9.
Wave 4 (2 agents): Beads 10,11 and 15.
Wave 5 (1-2 agents): Bead 13 and Bead 16 stabilization pass.

## Risk hotspots

1. Queue immutability regressions during `review` apply logic.
2. UTC date-edge errors in hold resurfacing.
3. Partial promotion failure semantics violating per-item atomicity.
4. Auto-approval misclassification causing semantic changes to bypass human review.
5. Audit append concurrency/tamper risks.
6. Frontier nondeterminism from hidden unstable inputs.

## Concrete disagreements with prior artifacts

1. Disagreement: silver excludes `TODO-Q-NAM-1` from blockers.
- Resolution: include `TODO-Q-NAM-1` in blocker set because validator and migration decomposition depend on explicit compatibility-mode behavior.

2. Disagreement: blue and silver stop at ambiguity fail without a ratifiable default pack.
- Resolution: attach explicit assumption defaults (A1-A6) so council can approve once and immediately unlock decomposition with `blocking_ambiguities=0`.

## Review verdict

- Current blue/silver proposals are directionally correct (fail-closed), but incomplete for unblock execution because they do not converge on a common assumption pack.
- Recommended next step: council ratifies A1-A6 in one clarify artifact, then decomposition can proceed without reopening blocker semantics.
