# Changelog

## 0.2.0 — Knowledge Vault Refactor (2026-03)

Complete rewrite from a multi-agent workflow framework into a local-first,
Obsidian-compatible knowledge vault with a structured ingestion pipeline.

### Architecture

- **7-stage ingestion pipeline** (capture, normalize, fingerprint, extract,
  compare, delta, propose_queue) processes sources into structured knowledge.
- **Typed notes** (source, claim, concept, question, project, moc) with YAML
  frontmatter and Markdown bodies, stored in Obsidian-compatible vault layout.
- **Two-scope model**: Draft Scope (machine-written, disposable) and Canonical
  Scope (human-approved, authoritative). Promotion between them requires
  explicit `graduate` command.
- **Review system**: queue items, review digests, review packets, decision
  records, and auto-approval lanes for low-risk proposals.
- **MCP server** (7 tools) for external agent integration via FastMCP.
- **CLI** (`mycelium-py`) with `run`, `status`, and `auto` commands for
  LiteLLM-backed agent orchestration.

### Core Modules

- `models.py` — OutputEnvelope, ErrorObject, WarningObject (structured errors).
- `note_io.py` — Read/write Obsidian-compatible Markdown+YAML notes.
- `schema.py` — Frontmatter validation for all note types.
- `vault_layout.py` — Canonical/Draft scope enforcement, path traversal guards.
- `pipeline.py` — End-to-end ingestion orchestrator.
- `stages/` — capture, normalize, fingerprint, extract, compare, delta,
  propose_queue.
- `comparator.py` — Claim matching (exact, near-duplicate, supporting,
  contradicting, new).
- `confidence.py` — Multi-factor confidence scoring.
- `review_queue.py`, `review_workflow.py`, `review_decision.py` — Human review
  pipeline.
- `graduate.py` — Draft-to-Canon promotion with overwrite guard.
- `delta_report.py` — Durable delta artifacts per ingestion run.
- `audit.py` — Append-only JSONL audit log.
- `egress.py`, `egress_config.py` — Outbound data policy enforcement.
- `sanitize.py` — PII/secret redaction for egress payloads.
- `quarantine.py` — Isolation of invalid/partial artifacts.
- `migration.py` — Schema migration framework.
- `graph.py`, `graph_analysis.py` — Wikilink graph and analysis.
- `source_index.py`, `source_reliability.py` — Source tracking and scoring.
- `novelty.py`, `triage.py` — Knowledge frontier and triage ranking.
- `mcp/server.py` — MCP server with HITL gate, command allowlist, sandbox.
- `orchestrator.py` — LiteLLM-backed multi-agent orchestration.
- `cli.py` — CLI entry point.

### Security Hardening (2026-03, post-refactor)

- HITL gate made fail-closed with case-insensitive agent normalization.
- SSRF protection on URL capture: scheme allowlist, host blocklist, size cap.
- `yaml.dump` replaced with `yaml.safe_dump` across all modules.
- Path traversal guards on all vault I/O operations.
- Command allowlist and sandbox enforcement on MCP `run_command`.
- Atomic writes for all persistence operations.
- POSIX atomic append for concurrent audit log writes.

### Testing

- 2358 tests covering all modules and acceptance criteria from the spec.
- Deterministic test mode for golden fixture reproducibility.
- Regression tests for deduplication and idempotency.

## 0.1.0 — Initial Release (2024-12)

- Multi-agent workflow framework (Scientist, Implementer, Verifier, Maintainer).
- Markdown-based progress tracking with YAML migration.
- Basic CLI tooling.
- `.mycelium/` directory structure for agent templates and missions.
