# TealPeak Review Beads Unblock Proposal v1

Date: 2026-03-02  
Agent: TealPeak  
Phase: PLAN-REVIEW (planning-only)

Inputs reviewed:
- Final plan: `/Users/will/Developer/mycelium/mycelium/docs/plans/mycelium_refactor_plan_apr_round5.md`
- Decomposition artifacts:
  - `/Users/will/Developer/mycelium/mycelium/plans/council/blue_decompose_proposal_v1.md`
  - `/Users/will/Developer/mycelium/mycelium/plans/council/copper_decompose_proposal_v1.md`

## 1) BV Analysis Snapshot (required commands run)

Commands executed:
- `bv --robot-triage`
- `bv --robot-insights`
- `bv --robot-plan`
- `bv --robot-priority`

Observed scope:
- BV analyzed current repository bead graph with 2 existing issues (`mycelium-1`, `mycelium-2`), not round5 decomposition beads.
- Therefore BV validates baseline graph health but does not validate the blue/copper decomposition proposals (they created no beads).

Key outputs:
- Cycles: none (`Cycles: null`, cycle advisory says no cycles).
- Bottlenecks: none (`Bottlenecks: []`).
- Parallel tracks: 2 (`track-A`, `track-B`) for existing issues.
- Priority recommendations: both existing issues suggested P1 -> P2 due no downstream unlocks.

Review implication:
- Structural bead graph issues are currently absent in repo, but this is a false comfort for round5 because no round5 beads exist yet.

## 2) Pre-Bead Review of Blue/Copper Artifacts

### 2.1 Blocker list accuracy vs spec TODO-Q lines

Spec TODO-Q lines (from final plan):
- `TODO-Q-NAM-1` line 426
- `TODO-Q-RDG-1` line 641
- `TODO-Q-FRN-1` line 745
- `TODO-Q-CONF-1` line 934
- `TODO-Q-REV-1` line 958
- `TODO-Q-REV-2` line 1009
- `TODO-Q-SEC-1` line 1086
- `TODO-Q-MVP3-1` line 1167
- `TODO-Q-MVP3-2` line 1168

Blue proposal (`blocking_ambiguities=6`) includes:
- `RDG-1`, `NAM-1`, `REV-1`, `REV-2`, `FRN-1`, `SEC-1`
- This is accurate for MVP1/MVP2 decomposition blockers.
- Blue correctly treats `CONF-1` as non-blocking MVP2+ calibration.

Copper proposal (`blocking_ambiguities=5`) includes:
- `RDG-1`, `REV-1`, `REV-2`, `SEC-1`, `FRN-1`
- Missing `NAM-1` from blocker set.

Verdict:
- **Blue blocker set is complete for MVP1/MVP2 gate.**
- **Copper blocker set is incomplete by one critical item (`NAM-1`).**
- Consolidated blocker count should be `blocking_ambiguities=6` until assumptions are explicitly ratified.

### 2.2 Coverage gap in both proposals
- Both artifacts stop at ambiguity failure without providing a conditional post-clarify decomposition map.
- That increases restart latency after clarify decisions are made.

## 3) Consolidated Assumption Pack (to set blocking_ambiguities=0)

If council accepts all defaults below, ambiguity gate becomes PASS (`blocking_ambiguities=0`).

### A1: `TODO-Q-RDG-1` default (review_digest invocation model)
Decision:
- Normative MVP1/MVP2 source-of-truth invocation is **manual command/API call** (`review_digest` explicit invocation).
- External scheduler/client integration is optional wrapper behavior and must call the same command contract.

Default acceptance checks:
- Contract tests assert deterministic outputs for explicit invocation.
- Audit details include `invoked_by` + trigger metadata when scheduler/client is used.

### A2: `TODO-Q-NAM-1` default (ID compatibility mode)
Decision:
- Add config `Config/validation.yaml`:
  - `naming.compat_mode: legacy_read_only`
  - `naming.legacy_cutoff_date: <required>`
- Behavior:
  - Existing pre-cutoff slug-only notes are accepted as legacy.
  - New machine-generated notes MUST use hybrid `<slug>--h-<12hex>`.
  - Hash-only and valid slug-only IDs remain accepted per NAM-001 rules, but generation default stays hybrid.

Default acceptance checks:
- Validator accepts legacy fixtures only when compat mode enabled.
- Generator tests show all new notes hybrid.

### A3: `TODO-Q-REV-1` default (hold TTL storage + resurfacing)
Decision:
- Canonical hold state stored in Review Decision Record (`SCH-010`) and mirrored in queue item `checks.hold_until` for query speed.
- Config: `Config/review_policy.yaml` with `hold_ttl_days: 14`.
- Resurface rule: item becomes digest-eligible when `hold_until <= digest_date`.

Default acceptance checks:
- Deterministic fixture with fixed clock resurfaces held items exactly on TTL date.

### A4: `TODO-Q-REV-2` default (Git mode enablement + commit contract)
Decision:
- Config: `Config/promotion.yaml` with `git_mode.enabled: false` default.
- When enabled: exactly one commit per Source packet apply batch.
- Commit message template: `promote:{source_id}:{packet_id}:{run_id}`.
- Commit body includes sorted `queue_ids` and actor.

Default acceptance checks:
- Fixture applying two packets produces exactly two commits with scoped diffs.

### A5: `TODO-Q-FRN-1` default (deterministic frontier factors)
Decision formulas (deterministic):
- `conflict_factor = clamp01(conflicting_claim_links / max(1, related_claim_links))`
- `support_gap = clamp01(1 - supporting_evidence_count / max(1, supporting_evidence_count + conflicting_evidence_count))`
- `goal_relevance = clamp01(jaccard(goal_token_set, target_token_set))`; if no goal provided, fixed `0.5`
- `novelty = clamp01(avg_recent_delta_novelty(target, window=30d))`; if no data, `0.0`
- `staleness = clamp01(days_since(last_reviewed_at_or_updated) / 90)`

Default acceptance checks:
- Seeded fixture yields byte-stable ordering/scores across runs.

### A6: `TODO-Q-SEC-1` default (burn-in tracking + mode storage)
Decision:
- Config: `Config/egress_policy.yaml` stores:
  - `mode: report_only|enforce`
  - `burn_in_started_at`
  - `last_transition_at`
  - `last_transition_actor`
  - `last_transition_reason`
- Burn-in start: first recorded `egress_attempted` event if field empty.
- Transition rule: only explicit `set_egress_mode(enforce, reason)` command allowed; guard requires elapsed >=14 days from `burn_in_started_at` unless explicit override flag + audit reason.

Default acceptance checks:
- Transition attempts before 14 days fail with deterministic error and audit event.

## 4) Conditional Decomposition Map (if A1-A6 accepted)

### Proposed bead set (proposal-only, no `br create/update/dep` executed)

| Proposed ID | Title | Type | Priority | Depends On | Acceptance Criteria Snippet |
|---|---|---|---|---|---|
| PB-01 | Implement command output envelope and command registry | feature | 0 | none | IF-001 envelope returned by all commands; contract test for `ok/errors/warnings/trace` keys. |
| PB-02 | Implement config subsystem for policy files | feature | 1 | PB-01 | Loads `Config/*.yaml`; rejects invalid schema with deterministic error codes. |
| PB-03 | Implement vault scope boundary guardrails | feature | 0 | PB-01, PB-02 | Non-promotion canonical writes rejected with `ERR_CANON_WRITE_FORBIDDEN`; boundary tests prove no canonical writes outside `graduate`. |
| PB-04 | Implement note validators SCH-001..SCH-005 | feature | 0 | PB-02, PB-03 | Invalid fixtures rejected with expected codes; valid fixtures pass strict mode. |
| PB-05 | Implement artifact validators SCH-006..SCH-010 | feature | 0 | PB-04 | Delta/Queue/Packet/Decision artifacts validate; required empty arrays preserved. |
| PB-06 | Implement naming+link validation with legacy compat mode | feature | 1 | PB-04, PB-02 | NAM/LNK checks enforce strict mode; compat mode allows legacy fixtures only. |
| PB-07 | Implement ingestion stage orchestrator with stage-scoped errors | feature | 0 | PB-03, PB-05 | Stage names match PIPE-003; failures return `stage` + deterministic code. |
| PB-08 | Implement extraction bundle persistence and minima checks | feature | 1 | PB-07, PB-05 | SCH-008 bundles persisted; zero-claim runs emit `WARN_NO_CLAIMS_EXTRACTED`. |
| PB-09 | Implement dedupe/match + delta report engine | feature | 0 | PB-07, PB-08 | Every extracted claim has exactly one match class; novelty formula recomputes exactly. |
| PB-10 | Implement source idempotency index service | feature | 1 | PB-07 | Repeat ingest reuses `source_id`; changed fingerprint records `prior_fingerprint`. |
| PB-11 | Implement review queue proposal generation | feature | 1 | PB-08, PB-09, PB-05 | Queue items created for canonical-impacting actions with `pending_review` status and checks metadata. |
| PB-12 | Implement review_digest packet generation | feature | 1 | PB-11, PB-05 | One packet per source with deterministic ordering; packet schema SCH-009 enforced. |
| PB-13 | Implement review decision transitions and decision records | feature | 0 | PB-11, PB-12, PB-05 | Legal transitions only; `hold` keeps pending state; SCH-010 decision record emitted per invocation. |
| PB-14 | Implement graduate promotion apply engine (strict + atomic) | feature | 0 | PB-13, PB-06, PB-03 | Applies approved-only; per-item atomicity; promoted notes `status: canon` in canonical dirs. |
| PB-15 | Implement append-only audit JSONL subsystem | feature | 0 | PB-02 | `ingest_started` + single terminal event required; append-only tests preserve prior bytes. |
| PB-16 | Implement egress policy + sanitization + mode transitions | feature | 0 | PB-02, PB-15 | Allowlist/blocklist and redaction enforced; mode transitions auditable; pre-burn-in enforce blocked unless override audited. |
| PB-17 | Implement quarantine and diagnostic sidecar flow | feature | 1 | PB-07, PB-15 | Invalid/partial artifacts moved to `Quarantine/` with diagnostic sidecar; canonical files not overwritten. |
| PB-18 | Implement context command bounded citations | feature | 1 | PB-14, PB-06 | Output bounded by limit; each item includes resolvable citations. |
| PB-19 | Implement frontier deterministic scoring engine | feature | 1 | PB-14, PB-06 | Uses A5 formulas + weighted aggregation + tie-break rules; deterministic fixture is byte-identical across runs. |
| PB-20 | Build deterministic golden fixture harness | test | 1 | PB-05 | TST-G-001/002 fixture categories available; deterministic mode normalizes timestamps/IDs. |
| PB-21 | Build integration and E2E workflow test suite | test | 0 | PB-07, PB-14, PB-16, PB-17, PB-20 | First/repeat/contradiction/review/promotion/context/frontier workflows pass with expected artifacts. |
| PB-22 | Build migration/rollback validation suite | test | 1 | PB-06, PB-14 | MIG-002 migration + rollback tests pass byte-for-byte on canonical notes. |
| PB-23 | Build performance bench gate suite | test | 2 | PB-21 | PERF-001 p95 thresholds enforced and reported with hardware metadata. |

## 5) Dependency Graph (parent -> child)

- `PB-01 -> PB-03, PB-02`
- `PB-02 -> PB-04, PB-06, PB-15, PB-16`
- `PB-03 -> PB-04, PB-07, PB-14`
- `PB-04 -> PB-05, PB-06`
- `PB-05 -> PB-07, PB-08, PB-11, PB-12, PB-13, PB-20`
- `PB-07 -> PB-08, PB-09, PB-10, PB-17`
- `PB-08 -> PB-09, PB-11`
- `PB-09 -> PB-11`
- `PB-11 -> PB-12, PB-13`
- `PB-13 -> PB-14`
- `PB-06 -> PB-14, PB-18, PB-19, PB-22`
- `PB-14 -> PB-18, PB-19, PB-21, PB-22`
- `PB-15 -> PB-16, PB-17`
- `PB-16 -> PB-21`
- `PB-17 -> PB-21`
- `PB-20 -> PB-21`
- `PB-21 -> PB-23`

## 6) Swarm Ordering and Risk Hotspots

### Swarm ordering (recommended)
1. Wave 0: Ratify A1-A6 (policy clarify closure).
2. Wave 1 (parallel): `PB-01`, `PB-02`, `PB-15`.
3. Wave 2 (parallel): `PB-03`, `PB-04`, `PB-05`, `PB-06`.
4. Wave 3 (parallel): `PB-07`, `PB-10`, `PB-20`.
5. Wave 4 (parallel): `PB-08`, `PB-09`, `PB-11`, `PB-17`.
6. Wave 5: `PB-12`, `PB-13`, `PB-14`, `PB-16`.
7. Wave 6 (parallel): `PB-18`, `PB-19`, `PB-22`.
8. Wave 7: `PB-21`, then `PB-23`.

### Risk hotspots
- R1: Canonical boundary regression before promotion gate hardens (`PB-03`, `PB-14`).
- R2: Egress mode transition edge-cases and burn-in override misuse (`PB-16`).
- R3: Determinism drift in frontier factors and fixture normalization (`PB-19`, `PB-20`).
- R4: Queue state drift if direct mutation bypasses `review` (`PB-13`).
- R5: Migration compat mode accidentally broadens acceptance for new notes (`PB-06`, `PB-22`).

## 7) Bead Review Summary

- Reviewed: 2 decomposition artifacts (`blue_decompose_proposal_v1`, `copper_decompose_proposal_v1`)
- BV Analysis:
  - Cycles: none (current repo graph)
  - Bottlenecks: none (current repo graph)
  - Parallel tracks: 2 (current repo graph)
- Approved as-is:
  - Blue blocker list completeness (`blocking_ambiguities=6`) for MVP1/MVP2
- Revised (proposal-level corrections):
  - Copper blocker set should include `TODO-Q-NAM-1`; corrected consolidated gate to 6
- Split:
  - none (no beads existed to split)
- Flagged for discussion:
  - Ratification of A1-A6 assumption pack before any bead creation

## 8) Two Concrete Disagreements and Resolutions

1. Disagreement: Copper omits `TODO-Q-NAM-1` from blocker set (`5` vs `6`).  
   Resolution: include `NAM-1` as blocking until compatibility-mode defaults (A2) are ratified.

2. Disagreement: Both Blue and Copper stop at gate failure without conditional decomposition map.  
   Resolution: keep fail-closed gate, but pre-publish conditional bead graph (Section 4) to eliminate post-clarify planning latency.

