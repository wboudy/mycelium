# S0 Decision Workshop (Reading-First Canon Curation)

Date: 2026-03-01
Source plan: `plans/council/teal_merge_blue_copper_v1.md`

## How to use
- Review each decision in order.
- Choose an option (`A/B/C`) or explicitly defer.
- If deferred, keep related features behind a feature flag.

## D1: Queue transition contract
Context: Queue items are generated from ingestion proposals; promotion depends on deterministic review states.
Question: Which transitions are legal in MVP1?
Options:
- A: `pending_review -> approved|rejected` only (no reopen)
- B: Add `approved/rejected -> pending_review` reopen path
- C: Free-form status changes with policy checks
Recommended default: A
Consequence if too loose: inconsistent promotion behavior and harder audit guarantees.
Owner decision: TBD

## D2: Failure durability behavior
Context: Failures can occur after extraction but before queue writing.
Question: What must persist on failed runs?
Options:
- A: Write nothing on failure
- B: Persist Delta+Audit, quarantine partial artifacts, no canonical writes
- C: Persist all partial artifacts in place
Recommended default: B
Consequence if too strict (`A`): poor diagnostics. If too loose (`C`): high corruption risk.
Owner decision: TBD

## D3: `graduate` strictness semantics
Context: Spec currently uses `all_reviewed`; queue states are `pending_review|approved|rejected`.
Question: How should mutating promotion behave?
Options:
- A: Rename to `all_approved`; mutating runs always strict; non-strict allowed only for dry-run
- B: Keep `all_reviewed`; permissive mixed validation
- C: Require strict only for contradiction items
Recommended default: A
Consequence if ambiguous: rejected or invalid items may be promoted unintentionally.
Owner decision: TBD

## D4: Frontier ranking output contract
Context: Frontier is ranked but score shape is under-defined.
Question: Must each target include explicit numeric score?
Options:
- A: Yes, required numeric `score` for each target
- B: Optional score
- C: Rank only (no numeric score)
Recommended default: A
Consequence if non-numeric: unstable ranking behavior and weak testability.
Owner decision: TBD

## D5: Interface completeness rule
Context: Required interfaces must specify inputs/outputs/side effects/errors.
Question: Enforce this strictly in spec lint?
Options:
- A: Enforce now in S0
- B: Warn-only until MVP2
- C: Manual review only
Recommended default: A
Consequence if not enforced: implementer drift and inconsistent adapters.
Owner decision: TBD

## Q1: Note ID strategy
Context: IDs impact readability, collisions, and dedupe identity.
Options:
- A: slug-only
- B: hash-only
- C: slug+hash hybrid
Recommended default: C (generated notes), allow temporary manual slug-only
Consequence: A risks collisions; B hurts readability.
Owner decision: TBD

## Q2: Provenance locator granularity
Context: Provenance determines traceability for extracted claims.
Options:
- A: free-form locator string
- B: source-kind structured minima
- C: source-kind structured + snippet hash
Recommended default: C for URL/PDF in MVP1
Consequence: A weak auditability; C adds implementation cost.
Owner decision: TBD

## Q3: Confidence rubric
Context: Confidence drives prioritization and review triage.
Options:
- A: optional/no rubric until MVP2
- B: deterministic advisory rubric
- C: domain-calibrated weighted rubric
Recommended default: B in MVP1, evaluate C in MVP2
Consequence: A inconsistent triage; C is heavier upfront.
Owner decision: TBD

## Q4: Authoritative review UX
Context: Review decisions can come from CLI/plugin.
Options:
- A: CLI-only authority
- B: plugin-only authority
- C: command/API authority, CLI/plugin as clients
Recommended default: C
Consequence: multiple authorities increase drift/conflict risk.
Owner decision: TBD

## Q5: Default egress policy
Context: Outbound payloads may contain sensitive vault content.
Options:
- A: strict default-deny + allowlist + fail-closed redaction
- B: permissive default-allow + blocklist
- C: report-only burn-in then enforce strict
Recommended default: C -> A
Consequence: B increases exposure risk.
Owner decision: TBD

## Q6: Performance targets
Context: Needed for regression detection and release gating.
Options:
- A: qualitative-only
- B: fixed numeric p95 targets
- C: adaptive targets by source kind/size
Recommended default: B for MVP1 ingest/delta, evaluate C for MVP2
Consequence: A weak regression signal.
Owner decision: TBD

## Q7: Nightly review unit
Context: You prefer reading-first nightly curation.
Options:
- A: queue-item-level only
- B: source packet default + claim drill-down
- C: run-level batch only
Recommended default: B
Consequence: A is noisy; C can hide risky claim-level differences.
Owner decision: TBD

## Q8: Reviewer action vocabulary
Context: Review should be fast but expressive.
Options:
- A: approve/reject only
- B: approve_all/approve_selected/hold/reject
- C: custom labels and multi-state workflow
Recommended default: B
Consequence: A too rigid; C adds complexity for personal workflow.
Owner decision: TBD

## Q9: Auto-approval lane scope
Context: You want less manual friction but safe canon.
Options:
- A: no auto-lane
- B: safe auto-lane (exact duplicates, metadata-only, non-semantic formatting)
- C: broad auto-lane including new claims
Recommended default: B
Consequence: C increases bad-canon risk before review.
Owner decision: TBD

## Q10: Commit granularity for apply
Context: Git history should support rollback and understanding.
Options:
- A: one commit per queue item
- B: one commit per source packet
- C: one commit per nightly batch
Recommended default: B
Consequence: A noisy history; C weak rollback precision.
Owner decision: TBD

## Q11: Hold aging policy
Context: Holds can accumulate and stall curation.
Options:
- A: hold forever
- B: expire after N days and re-surface
- C: auto-reject after N days
Recommended default: B
Consequence: A creates stale backlog; C may discard useful items.
Owner decision: TBD

## Q12: Contradiction handling default
Context: Contradictions are high-value but high-risk canonical updates.
Options:
- A: auto-approve contradictions
- B: always human-review with side-by-side evidence
- C: suppress contradictions under threshold
Recommended default: B
Consequence: A can pollute canon quickly; C can hide important disputes.
Owner decision: TBD
