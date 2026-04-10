# BlueRaven Systems Contract Audit

Spec audited: `/Users/will/Developer/mycelium/mycelium-apr-spec/docs/plans/mycelium_refactor_plan_apr_round5.md`
Audit scope: internal consistency, contradictions, and underspecified normative contracts.

## Severity-Ranked Findings

### 1) CRITICAL: Review queue lifecycle is not executable end-to-end
- Evidence:
  - `L234-L243` defines queue status enum: `pending_review | approved | rejected`.
  - `L247-L248` forbids mutating non-`pending_review` items except via explicit state-transition operations.
  - `L383-L414` defines `graduate` as promotion executor for approved items, but no review/approval transition command exists.
  - `L594-L603` describes promotion semantics only, not review decision transitions.
- Contract defect:
  - There is no normative interface that transitions queue items from `pending_review` to `approved`/`rejected`, while immutability rules require such an interface.
  - Result: requirements cannot be satisfied without out-of-band/manual mutation.
- Proposed normative patch text:
```md
### 5.2.7 `review` (new command)
Input:
- `queue_id: string` OR `queue_item_paths: array[string]`
- `decision: enum` (`approve | reject`)
- Optional: `reason: string`, `actor: string`, `dry_run: boolean`

Output `data`:
- `updated: array[{queue_id, from_status, to_status}]`
- `audit_event_ids: array[string]`

Side effects:
- Applies explicit queue state transitions only:
  - `pending_review -> approved`
  - `pending_review -> rejected`
- Appends audit events.

Errors:
- `ERR_QUEUE_ITEM_INVALID`
- `ERR_QUEUE_IMMUTABLE`
- `ERR_SCHEMA_VALIDATION`

**Requirement CMD-REV-001:** `review` MUST be the only command that mutates queue decision state.
```

### 2) CRITICAL: Failure-path durability rules are contradictory
- Evidence:
  - `L227-L229` requires Delta Report existence after any ingestion attempt that reaches extraction (even if later stages fail).
  - `L531-L535` says failure after extraction before queue writing must produce either no new files OR all new files in `Quarantine/`.
  - `L334-L335` says ingest writes durable outputs under `Reports/Delta/` and `Logs/Audit/`.
- Contract defect:
  - Delta Report + audit durability on failure conflicts with “all new files in Quarantine” fallback.
- Proposed normative patch text:
```md
Replace AC-PIPE-002-1 with:
- AC-PIPE-002-1: If failure occurs after extraction, canonical directories remain unchanged. Durable failure artifacts (`Reports/Delta/*`, `Logs/Audit/*`) MAY be written; any invalid/partial draft artifacts MUST be quarantined under `Quarantine/` with diagnostics.
```

### 3) CRITICAL: Delta Report schema is missing required warning/failure structures referenced elsewhere
- Evidence:
  - `L524-L529` requires extraction warning `WARN_NO_CLAIMS_EXTRACTED` for zero-claim cases.
  - `L263-L264` requires unresolved-link warnings to be recorded in Delta Report warnings list.
  - `L227` references failure recording for failed runs.
  - `L195-L205` required Delta Report keys do not include `warnings` or `failures`.
- Contract defect:
  - Normative requirements reference fields absent from the normative schema.
- Proposed normative patch text:
```md
Amend SCH-006 required keys by adding:
- `pipeline_status: enum` (`completed | failed`)
- `warnings: array[WarningObject]` (required, empty array allowed)
- `failures: array[ErrorObject]` (required, empty array allowed)

Where `WarningObject` and `ErrorObject` follow IF-001 structures.

Add AC-SCH-006-4:
- AC-SCH-006-4: Zero-claim extraction records `WARN_NO_CLAIMS_EXTRACTED` in `warnings`.

Add AC-SCH-006-5:
- AC-SCH-006-5: Failed ingestion runs set `pipeline_status=failed` and include at least one `failures[]` entry with stage/code.
```

### 4) HIGH: Pipeline stage dataflow is inconsistent for link proposals
- Evidence:
  - `L514` defines Delta stage input as `MatchResults + link proposals`.
  - `L518-L520` defines Propose+Queue stage input/output without specifying link-proposal generation as a prior stage artifact.
  - `L203` requires `new_links` in Delta Report.
- Contract defect:
  - Link proposals are consumed before they are normatively produced.
- Proposed normative patch text:
```md
Revise §6.1.1 stages to:
6) Link Propose
Input: `ExtractionBundle + MatchResults + vault snapshot`
Output: `LinkProposals[]`
Errors: `ERR_SCHEMA_VALIDATION`

7) Delta
Input: `MatchResults + LinkProposals[]`
Output: Delta Report object (SCH-006)
Errors: `ERR_SCHEMA_VALIDATION`

8) Queue
Input: `ExtractionBundle + MatchResults + LinkProposals[]`
Output: Review Queue Items (SCH-007)
Errors: `ERR_SCHEMA_VALIDATION`
```

### 5) HIGH: Spec-lint rule LINT-003 is violated by the spec’s own required stage interfaces
- Evidence:
  - `L773-L776` requires required interfaces to specify inputs, outputs, side effects, errors.
  - `L488-L521` stage interfaces list only Input/Output/Errors (no side effects entries).
- Contract defect:
  - Spec fails its own lint rule as written.
- Proposed normative patch text:
```md
For each stage in §6.1.1, add explicit `Side effects:` line.
- Capture/Normalize/Fingerprint/Extract/Compare/Link Propose/Delta: `Side effects: none`.
- Queue: `Side effects: writes Review Queue Items under Inbox/ReviewQueue/`.

(If Delta persistence occurs in this stage model, state: `Side effects: writes Delta Report under Reports/Delta/`.)
```

### 6) HIGH: `graduate` strictness is contradictory between command contract and promotion invariant
- Evidence:
  - `L390-L392` lists `strict` as optional for `graduate`.
  - `L595-L597` requires Promotion to validate schemas in strict mode.
- Contract defect:
  - Optional strict flag implies non-strict promotions are possible, contradicting mandatory strict promotion validation.
- Proposed normative patch text:
```md
Amend §5.2.3 `graduate` input:
- Remove optional `strict` flag for mutating execution.
- If retained, define: `strict` MUST default to `true`; `strict=false` is permitted only with `dry_run=true` and MUST NOT mutate files.
```

### 7) HIGH: Promotion validation scope references irrelevant schemas for promoted items
- Evidence:
  - `L595-L599` says Promotion validates `SCH-001..SCH-007` for promoted items.
  - `L188-L249` shows SCH-006 (Delta Report) and SCH-007 (Queue Item) are artifact schemas, not promoted canonical notes.
- Contract defect:
  - Validation requirement is over-broad and mis-scoped.
- Proposed normative patch text:
```md
Replace REV-002 step (1) with:
1) Validate promoted notes against applicable note schemas only:
   - shared schema SCH-001
   - plus exactly one of SCH-002..SCH-005 by note `type`.
2) Validate queue item schema (SCH-007) before processing queue transitions.
3) Delta Report schema (SCH-006) remains ingest-stage validation, not a promotion precondition.
```

### 8) MEDIUM: `all_reviewed` input is undefined against status vocabulary
- Evidence:
  - `L388-L389` includes `all_reviewed: boolean` input for `graduate`.
  - `L242` status enum uses `pending_review | approved | rejected` (no `reviewed`).
- Contract defect:
  - Input terminology does not map to schema states.
- Proposed normative patch text:
```md
Replace `all_reviewed: boolean` with `all_approved: boolean` in §5.2.3.
Add explicit semantics: when true, `graduate` processes only items with `status=approved`.
```

### 9) MEDIUM: Frontier output contract omits the ranking field required by acceptance criteria
- Evidence:
  - `L452` declares `reading_targets: array[...]` without shape.
  - `L464` requires explicit numeric rank/score per target.
- Contract defect:
  - AC requires a field not declared in output contract.
- Proposed normative patch text:
```md
Amend §5.2.5 output:
- `reading_targets: array[{target, score, rationale, citations}]`
  - `score: number` (descending sort key)
```

### 10) MEDIUM: Supported source-kind test scope is underspecified against source-kind enum
- Evidence:
  - `L143` source kinds include `url|pdf|doi|arxiv|highlights|book|text_bundle`.
  - `L713` requires full pipeline run for each supported source-kind fixture.
  - `L731-L737` minimum fixture list includes URL/PDF and delta/idempotency cases, but not explicit DOI/arXiv/highlights/book fixtures.
- Contract defect:
  - “Supported source kind” in tests is ambiguous by milestone and may be interpreted as all seven now.
- Proposed normative patch text:
```md
Add to §13.2:
- "For each milestone, integration tests MUST cover every source kind declared as implemented for that milestone."

Add to §12:
- MVP1 implemented source kinds: `url`, `pdf`.
- MVP2+ expansion kinds: `doi`, `arxiv`, `highlights`, `book`, `text_bundle` (when enabled).
```

### 11) LOW: ID strategy appears both normative and unresolved
- Evidence:
  - `L252` defines normative ID patterns.
  - `L784` TODO says ID strategy selection still pending and impacts NAM-001.
- Contract defect:
  - Governance ambiguity: current rule is declared while strategy decision is still open.
- Proposed normative patch text:
```md
Replace TODO-Q1 with:
- "Resolved for spec v1.0: NAM-001 adopts slug-or-hash hybrid (`kebab-case` or `h-<hex>`). Any change requires MIG-002 migration+rollback and a spec version bump."
```

## Must-Fix-Before-Implementation Gates
1. Define executable queue review state-transition contract (new `review` command + state machine).
2. Reconcile failure durability/atomicity rules so Delta/Audit persistence and Quarantine behavior are non-contradictory.
3. Extend Delta Report schema to include warnings/failures/pipeline status referenced by extraction/link/failure requirements.
4. Fix pipeline stage ordering/dataflow for link proposals and Delta generation.
5. Resolve strictness and schema-scope rules for `graduate`/Promotion to prevent unsafe or ambiguous canonical writes.

## Auditor Note
The items above are blocking contract defects, not implementation nits. They should be patched in the spec before engineering decomposition or milestone burn-down.
