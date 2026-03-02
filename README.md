# Mycelium

A local-first, Obsidian-compatible knowledge vault with a human-gated ingestion pipeline. Sources are ingested through a 7-stage pipeline that extracts structured claims, deduplicates against existing knowledge, computes deltas, and queues proposals for human review. Agents may draft, but canonical notes change only through explicit human promotion.

## Core Principles

1. **Human authority over canon** -- Canonical notes are never created or modified without explicit promotion via `graduate`. Agents write drafts only.
2. **Draft-first outputs** -- All agent-generated notes land in Draft Scope (`Inbox/`, `Reports/`, etc.). Canonical Scope is read-only to the pipeline.
3. **Provenance required** -- Every imported claim traces back to a source and locator. No anonymous knowledge.
4. **Idempotent ingestion** -- Re-ingesting the same source (same locator + fingerprint) reuses the same source ID. No duplicates.
5. **Obsidian-native storage** -- All canonical content is Markdown with YAML frontmatter. Open the vault in Obsidian and everything renders.

## Ingestion Pipeline

Sources flow through 7 stages. On failure, downstream stages are skipped but the Delta Report and audit events are still written.

```
1. capture        Acquire raw source (URL, PDF, text bundle)
2. normalize      Normalize text and locator (pure transform)
3. fingerprint    Compute content hash, check/update identity index
4. extract        Extract claims from normalized text, write Extraction Bundle
5. compare        Deduplicate: match extracted claims against canonical claims
6. delta          Build Delta Report summarizing all match results
7. propose_queue  Generate Review Queue Items from Delta Report
```

Each stage produces typed outputs consumed by the next. The pipeline is orchestrated by `pipeline.py` with stage-scoped error handling (`ERR-001`).

## Key Subsystems

### Deduplication Engine
Extracted claims are canonicalized (`DED-001`) and compared against existing canonical claims. The comparator assigns match classes: `EXACT`, `NEAR_DUPLICATE`, `SUPPORTING`, `CONTRADICTING`, or `NEW`. Merge rules (`DED-003`) determine the proposed action for each class.

### Review Queue
All canonical-impacting proposals require human decision. Queue items are grouped by source into Review Packets for efficient batch review. An auto-approval lane handles low-risk, non-semantic updates (provenance additions, metadata refreshes) while keeping semantic changes in human review.

Review decisions: `approve`, `reject`, or `hold` (deferred with TTL-based resurfacing).

### Graduation
The sole path from Draft to Canon. `graduate` promotes approved items, enforcing overwrite guards, queue status updates, and draft cleanup. Optional Git Mode commits each promotion individually for granular history.

### Egress Security
Outbound content is governed by allowlist/blocklist pattern matching with two modes: `report_only` (log violations) and `enforce` (block violations). Payloads are sanitized for API keys, emails, phone numbers, and local paths before transmission. All egress events are audit-logged.

### Graph Analysis
Wikilinks between notes form a directed knowledge graph. Hub scoring (in-degree + PageRank) identifies central concepts. Tarjan's algorithm detects bridges and articulation points -- structural vulnerabilities in the knowledge base.

### Triage and Lifecycle
Deterministic scoring with hysteresis classifies items by urgency. A skip-list with auto-resurface handles deferred items. Invalid artifacts are quarantined with diagnostic sidecars rather than silently dropped.

## Vault Layout

The vault separates human-curated canonical content from agent-generated drafts:

```
vault/
  Sources/              Canonical source notes
  Claims/               Canonical claim notes
  Concepts/             Canonical concept notes
  Questions/            Canonical question notes
  Projects/             Canonical project notes
  MOCs/                 Canonical maps of content
  Inbox/
    Sources/            Draft source notes and extraction bundles
    ReviewQueue/        Pending review queue items
    ReviewDigest/       Review packets and decision records
  Reports/
    Delta/              Delta reports (one per ingestion run)
  Logs/
    Audit/              Append-only JSONL audit trail
  Indexes/              Rebuildable indexes and caches
  Quarantine/           Invalid artifacts with diagnostic sidecars
  Config/
    review_policy.yaml  Hold TTL, Git Mode settings
    egress_policy.yaml  Egress mode and burn-in configuration
    source_reliability.yaml  Domain-to-reliability mapping
```

**Canonical Scope** (writable only via `graduate`): `Sources/`, `Claims/`, `Concepts/`, `Questions/`, `Projects/`, `MOCs/`.

**Draft Scope** (agent-writable): `Inbox/`, `Reports/`, `Logs/`, `Indexes/`, `Quarantine/`.

## Project Structure

```
mycelium/
  pyproject.toml
  AGENTS.md                Agent conventions and workflow rules
  README.md                This file
  docs/plans/              Specification documents
  src/mycelium/
    __init__.py            Package root
    cli.py                 CLI entry point (mycelium-py)
    pipeline.py            Pipeline orchestrator (chains 7 stages)
    models.py              Output Envelope (IF-001/IF-002)
    errors.py              Stage-scoped error types (ERR-001)
    schema.py              Frontmatter schema validation (SCH-001..010)
    invariants.py          System invariant enforcement (INV-001..005)
    strict.py              Strict Mode semantics (IF-003)
    note_format.py         Canonical note format (MIG-001)
    note_io.py             Note I/O for Markdown+YAML frontmatter
    vault_layout.py        Vault layout and scope boundaries (VLT-001)
    atomic_write.py        Atomic file writes (temp + os.replace)
    naming.py              Note ID naming rules (NAM-001)
    source_index.py        Source identity index (IDM-001)
    canonicalize.py        Claim canonicalization (DED-001)
    comparator.py          Match class assignment (DED-002)
    merge_rules.py         Merge rules per match class (DED-003)
    novelty.py             Novelty scoring (DEL-002)
    confidence.py          Advisory confidence rubric (CONF-001)
    source_reliability.py  Source reliability config
    delta_report.py        Delta Report persistence (SCH-006)
    review_queue.py        Review Queue Items (SCH-007)
    review_packet.py       Review Packets (SCH-009)
    review_policy.py       Review policy config
    review_workflow.py     Digest workflow (REV-001A)
    review_generation.py   Queue item generation (REV-001)
    review_decision.py     Decision records (SCH-010)
    auto_approval.py       Auto-Approval Lane (REV-001B)
    graduate.py            Draft-to-Canon promotion (CMD-GRD-001)
    triage.py              Triage scoring with hysteresis
    skip_list.py           Skip-list lifecycle
    quarantine.py          Quarantine with diagnostics (ERR-002)
    egress.py              Egress enforcement (SEC-001/002/003)
    egress_config.py       Egress policy config (SEC-003)
    sanitize.py            Payload sanitization (SEC-004)
    audit.py               Append-only audit logging (AUD-001)
    wikilink.py            Wikilink resolution (LNK-001)
    graph.py               Knowledge graph construction
    graph_analysis.py      Hub scoring and bridge detection
    migration.py           Schema migration framework (MIG-002)
    orchestrator.py        Mission orchestrator with HITL gate
    llm.py                 LLM interface via LiteLLM
    deterministic.py       Deterministic test mode (TST-G-002)
    spec_lint.py           Specification linting
    git_mode.py            Per-packet commit granularity (REV-004)
    stages/
      capture.py           Stage 1: Acquire raw source
      normalize.py         Stage 2: Normalize text and locator
      fingerprint.py       Stage 3: Compute fingerprint, update index
      extract.py           Stage 4: Extract claims, write bundle
      compare.py           Stage 5: Deduplicate against canonical claims
      delta.py             Stage 6: Build Delta Report
      propose_queue.py     Stage 7: Generate Review Queue Items
    commands/
      ingest.py            Ingest command (CMD-ING-001/002)
      review.py            Review command (CMD-REV-001)
      review_digest.py     Review Digest command (CMD-RDG-001)
      delta.py             Delta command (CMD-DEL-001)
      context.py           Context Pack command (CMD-CTX-001)
      frontier.py          Frontier command (CMD-FRN-001/002)
      future_stubs.py      Post-MVP stubs (connect, trace, ideas)
    mcp/
      server.py            MCP server with sandboxed tools
  tests/                   2300+ tests covering all modules
```

## Installation

```bash
pip install -e ".[dev]"
```

Requires Python 3.10+. Dependencies: `pyyaml`, `fastmcp`, `litellm`.

## Usage

### CLI

```bash
mycelium-py run <mission-path>     # Run a mission
mycelium-py status <mission-path>  # Check mission status
mycelium-py auto <mission-path>    # Auto-advance mission
```

### MCP Server

```bash
python -m mycelium.mcp
```

Exposes 7 tools for IDE integration: `read_progress`, `update_progress`, `list_files`, `read_file`, `write_file`, `run_command`, `search_codebase`. File operations are sandboxed. Commands use an allowlist with no shell execution.

## Testing

```bash
pytest                  # Run full suite (2300+ tests)
pytest tests/test_X.py  # Run specific module tests
```

Tests cover schema validation, pipeline stages, deduplication, review workflows, egress security, graph analysis, migration, and end-to-end integration scenarios. Golden fixtures provide deterministic regression testing.

## Specification

The full specification is at `docs/plans/mycelium_refactor_plan_apr_round5.md`. Key requirement IDs referenced throughout the codebase:

- **INV-001..005**: System invariants (canonical storage, human authority, draft-first, provenance, idempotency)
- **SCH-001..010**: Note and artifact schemas
- **PIPE-001/002**: Pipeline orchestration and atomic writes
- **DED-001..003**: Deduplication (canonicalization, comparison, merge rules)
- **REV-001..004**: Review system (queue generation, digest workflow, auto-approval, git mode)
- **SEC-001..004**: Security (egress enforcement, payload sanitization)
- **ERR-001/002**: Error handling (stage-scoped errors, quarantine)
- **MIG-001/002**: Migration (note format, schema migrations)

## License

MIT
