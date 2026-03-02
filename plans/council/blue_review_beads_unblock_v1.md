# BlueRaven Review Beads Unblock Proposal v1

Date: 2026-03-02
Agent: BlueRaven
Phase: PLAN-REVIEW (planning-only)
Reviewed artifacts:
- `/Users/will/Developer/mycelium/mycelium/plans/council/teal_decompose_proposal_v1.md`
- `/Users/will/Developer/mycelium/mycelium/plans/council/silver_decompose_proposal_v1.md`
Source plan:
- `/Users/will/Developer/mycelium/mycelium/docs/plans/mycelium_refactor_plan_apr_round5.md`

## Bead Review Summary
- Reviewed: 2 decomposition artifacts; 0 created Round5 beads (both artifacts are gate-only).
- BV Analysis:
  - Commands run: `bv --robot-triage`, `bv --robot-insights`, `bv --robot-plan`, `bv --robot-priority`.
  - Cycles: none (`bv --robot-insights` reports `Cycles: null`, `cycle_count: 0`).
  - Bottlenecks: none in graph; existing open issues `mycelium-1`, `mycelium-2` appear as keystones but are unrelated to Round5 vault decomposition.
  - Parallel tracks: 2 tracks in current graph (`track-A` and `track-B`), both unrelated to this decomposition wave.
- Approved as-is: none (no bead graph exists to approve).
- Revised: none (planning-only, no `br update`).
- Split: none.
- Flagged for discussion: ambiguity closure package and missing blocker normalization.

## Findings (Pre-Bead Review)

1. `silver_decompose_proposal_v1.md` under-reports blocking TODO-Q items for decomposition-critical contracts.
- Evidence: Silver gate lists 5 blockers (RDG, FRN, REV-1, REV-2, SEC) and omits `TODO-Q-NAM-1`.
- Spec evidence: `TODO-Q-NAM-1` remains open and directly affects validator behavior and migration compatibility (`docs/plans/mycelium_refactor_plan_apr_round5.md:426`).
- Impact: Decomposition can diverge on note-ID validator/migration beads if `NAM-1` default is not fixed.

2. `teal_decompose_proposal_v1.md` correctly blocks decomposition but skips required BV run in the artifact notes.
- Evidence: Teal note states BV was intentionally not run.
- Round requirement: review flow explicitly requires BV analysis commands.
- Impact: Structural checks were not formally recorded in that artifact.

3. Neither artifact supplies a consolidated assumption/default pack to convert blockers into executable decomposition.
- Evidence: both artifacts stop at `NO_BEAD_CREATION_DUE_TO_AMBIGUITY` and only ask clarifying questions.
- Impact: No path to operationally achieve `blocking_ambiguities=0` without a new decision package.

## Blocker Accuracy Matrix (Against Plan TODO-Q Lines)

| TODO-Q | Spec line | Teal gate | Silver gate | Accuracy verdict |
|---|---:|---|---|---|
| `TODO-Q-NAM-1` | 426 | Included | Missing | Teal correct; Silver incomplete for decomposition safety |
| `TODO-Q-RDG-1` | 641 | Included | Included | Correct in both |
| `TODO-Q-FRN-1` | 745 | Included | Included | Correct in both |
| `TODO-Q-REV-1` | 958 | Included | Included | Correct in both |
| `TODO-Q-REV-2` | 1009 | Included | Included | Correct in both |
| `TODO-Q-SEC-1` | 1086 | Included | Included | Correct in both |
| `TODO-Q-CONF-1` | 934 | Not included | Not included | Acceptable as non-blocking for MVP1/MVP2 scope |

## Consolidated Assumption Pack (Proposed Defaults to Reach `blocking_ambiguities=0`)

Assumption A1 (`TODO-Q-RDG-1`): `review_digest` invocation model
- Default: no built-in scheduler in MVP1/MVP2 core.
- Authoritative contract: command/API invocation is source-of-truth; external scheduler and clients call same `review_digest` endpoint.
- Required metadata: every digest includes `trigger_type` (`manual|scheduled|client`) and `trigger_actor` in decision/audit fields.

Assumption A2 (`TODO-Q-NAM-1`): ID compatibility mode
- Default: `compat_mode=off`.
- Mode behavior when enabled: allow legacy slug-only IDs only for pre-existing notes; disallow slug-only IDs for new machine-generated notes.
- Machine generation invariant: always produce hybrid `<slug>--h-<12hex>` for new notes.
- Config location default: `Config/schema_policy.yaml` with `id_compatibility_mode`.

Assumption A3 (`TODO-Q-REV-1`): hold TTL persistence + resurfacing
- Source of truth: queue item persists `hold_until` (YYYY-MM-DD) plus mirrored entry in Review Decision Record for audit.
- Deterministic resurface rule: during digest generation, include held items when `status=pending_review` and `hold_until <= digest_date`.
- No background scheduler required.

Assumption A4 (`TODO-Q-REV-2`): Git Mode config + commit convention
- Default: Git Mode disabled.
- Enablement: `Config/promotion_policy.yaml` (`git_mode.enabled`) with optional per-command override flag.
- Commit convention (required): `promote:<source_id>:<packet_id>:<run_id>` with queue IDs in body.
- Granularity invariant: exactly one commit per Source packet apply batch.

Assumption A5 (`TODO-Q-FRN-1`): deterministic factor derivations
- `conflict_factor = clamp01(contradict_count / max(1, contradict_count + support_count))`
- `support_gap = clamp01(1 - min(1, support_count / 3))`
- `goal_relevance = deterministic_jaccard(tokens(goal_or_project), tokens(target_title+tags+linked_project_terms)); if no goal/project provided => 0.5`
- `novelty = clamp01(new_claim_count_30d / max(1, total_claim_count_linked))`
- `staleness = clamp01(days_since(last_reviewed_at_or_updated) / 90)`
- Tie-break remains spec-defined (`CMD-FRN-002`).

Assumption A6 (`TODO-Q-SEC-1`): burn-in tracking + mode transitions
- State file: `Config/egress_policy.yaml` with `mode`, `burn_in_started_at`, `last_transition_at`, `transition_actor`, `transition_reason`.
- Burn-in start: explicit `egress init` command (or first creation of policy file) sets `burn_in_started_at`.
- Transition rule: `report_only -> enforce` only via explicit command after `now - burn_in_started_at >= 14 days`; never implicit/automatic.

Assumption gate result if A1..A6 accepted:
- `blocking_ambiguities=0`

## Conditional Decomposition Map (Only if Assumptions Accepted)

### Proposed bead set (planning-only, not executed)

| Proposed bead title | Type | Priority | Depends on |
|---|---|---:|---|
| Define defaults: TODO-Q ambiguity closure pack (A1..A6) | docs | 0 | none |
| Implement IF-001 output envelope + shared error objects | feature | 1 | ambiguity-closure |
| Implement vault root + canonical/draft boundary guard | feature | 1 | ambiguity-closure |
| Implement dry-run planner (`planned_writes`) for write-capable commands | feature | 1 | boundary-guard |
| Implement schema validators SCH-001..SCH-010 + strict-mode adapter | feature | 1 | boundary-guard |
| Implement NAM compatibility-mode policy (`Config/schema_policy.yaml`) | feature | 1 | validators, ambiguity-closure |
| Implement ingest stage chain with canonical stage names + stage-scoped errors | feature | 1 | envelope, validators |
| Implement idempotency index `(normalized_locator,fingerprint)->source_id` | feature | 1 | ingest-stage-chain |
| Persist Extraction Bundle + Delta Report artifacts (SCH-008/SCH-006) | feature | 1 | ingest-stage-chain, idempotency-index |
| Persist Review Queue items (SCH-007) from propose_queue stage | feature | 1 | artifact-persistence |
| Implement `review_digest` packet generation + hold resurfacing filter | feature | 1 | queue-persistence, ambiguity-closure |
| Implement `review` transitions + Decision Record persistence (SCH-010) | feature | 1 | queue-persistence |
| Implement `graduate` strict per-item atomic promotion | feature | 0 | review-transitions, validators, boundary-guard |
| Implement Git Mode packet commit strategy | feature | 2 | graduate, ambiguity-closure |
| Implement `context` bounded retrieval with citation checks | feature | 2 | graduate |
| Implement `frontier` deterministic factor engine + ranking | feature | 2 | graduate, ambiguity-closure |
| Implement append-only audit JSONL writer (AUD-001/002) | feature | 1 | envelope |
| Implement egress policy state + mode transition enforcement | feature | 1 | audit-writer, ambiguity-closure |
| Add deterministic test mode + golden fixtures (unit/schema) | test | 1 | validators, artifact-persistence |
| Add integration/e2e lifecycle tests (review/digest/graduate/context/frontier) | test | 1 | review-digest, review-transitions, graduate, context, frontier |
| Add perf benchmark gates for PERF-001 thresholds | test | 2 | ingest-stage-chain, frontier |

### Acceptance criteria snippets per proposed bead
- ambiguity-closure:
  - [ ] A1..A6 defaults committed as normative config/ADR text.
  - [ ] `blocking_ambiguities=0` can be asserted without TODO-Q interpretation gaps.
- IF-001 envelope:
  - [ ] All new vault commands return `ok,command,timestamp,data,errors,warnings,trace`.
  - [ ] Error objects include `code,message,retryable`.
- boundary guard:
  - [ ] Non-graduate writes to canonical scope fail with `ERR_CANON_WRITE_FORBIDDEN`.
  - [ ] Allowed draft/durable paths remain writable.
- dry-run planner:
  - [ ] `dry_run=true` produces `data.planned_writes`.
  - [ ] No filesystem mutations occur in dry run.
- validators + strict mode:
  - [ ] Invalid schema fails in strict mode.
  - [ ] Read-only non-strict mode downgrades schema/link issues to warnings.
- NAM compat mode:
  - [ ] Legacy slug-only note behavior follows configured mode.
  - [ ] New machine-generated notes always use hybrid IDs.
- ingest stage chain:
  - [ ] Stage failures return canonical `stage` names.
  - [ ] Downstream stages do not run on invalid upstream output.
- idempotency index:
  - [ ] identical locator+fingerprint reuses `source_id`.
  - [ ] changed fingerprint records lineage (`prior_fingerprint`).
- extraction + delta persistence:
  - [ ] extraction artifacts validate against SCH-008.
  - [ ] delta reports validate against SCH-006 with required empty arrays present.
- queue persistence:
  - [ ] queue items validate against SCH-007.
  - [ ] non-`pending_review` mutation paths are blocked.
- review_digest + resurfacing:
  - [ ] one packet per source with SCH-009 fields.
  - [ ] held items resurface deterministically at `hold_until<=digest_date`.
- review transitions + decision record:
  - [ ] legal transitions only (`pending_review->approved|rejected`).
  - [ ] decision record persisted once per successful invocation.
- graduate atomic:
  - [ ] per-item atomic promotion preserves other valid items.
  - [ ] promoted notes end with `status: canon` in canonical scope.
- git mode:
  - [ ] one commit per source packet apply batch.
  - [ ] commit message matches required schema.
- context retrieval:
  - [ ] results bounded by limit.
  - [ ] every item includes resolvable citation(s).
- frontier deterministic:
  - [ ] factor fields present and in `[0..1]`.
  - [ ] repeated runs produce identical ranking/scores for deterministic fixture.
- audit writer:
  - [ ] audit file is JSONL parseable line-by-line.
  - [ ] appends do not rewrite prior lines.
- egress policy:
  - [ ] mode transition is explicit + audited.
  - [ ] enforce mode blocks blocklisted egress with `ERR_EGRESS_POLICY_BLOCK`.
- deterministic fixtures/tests:
  - [ ] golden fixtures normalize nondeterministic fields deterministically.
  - [ ] schema/unit tests cover required acceptance checks.
- integration/e2e tests:
  - [ ] lifecycle tests cover ingest -> review -> graduate.
  - [ ] context/frontier behavior verified end-to-end.
- perf gates:
  - [ ] p95 thresholds computed and reported.
  - [ ] threshold breach fails gate unless explicitly waived.

## Suggested swarm ordering
1. Lane A (contract foundation): ambiguity-closure -> envelope -> boundary guard -> validators -> NAM mode.
2. Lane B (ingest artifacts): ingest chain -> idempotency -> extraction/delta -> queue persistence.
3. Lane C (review/promotion): review_digest + review transitions -> graduate -> git mode.
4. Lane D (retrieval/security): context + frontier in parallel with audit + egress (after foundation).
5. Lane E (quality gates): deterministic fixtures/tests -> integration/e2e -> perf gates.

## Risk hotspots
- Canonical mutation integrity risk: boundary guard + graduate atomicity are P0/P1 and must be landed before any broader rollout.
- Determinism drift risk: frontier factor formulas and tie-break behavior require fixed fixtures early.
- Security fail-open risk: egress mode transition logic must fail closed and be audited.
- Schema migration risk: NAM compatibility mode can silently widen validator acceptance unless constrained to legacy-only behavior.

## Planning constraints compliance
- No implementation performed.
- No `br create/update/dep` executed.
- BV analysis commands executed and recorded.
