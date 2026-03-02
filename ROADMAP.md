# Mycelium Roadmap

## Completed

### Knowledge Vault Refactor (v0.2.0)

The core system has been rewritten from a multi-agent workflow framework into
an Obsidian-compatible knowledge vault. What shipped:

- 7-stage ingestion pipeline (capture through propose_queue)
- Typed notes with schema-validated frontmatter (source, claim, concept,
  question, project, moc)
- Two-scope model (Draft Scope / Canonical Scope) with `graduate` promotion
- Deduplication engine with 5 match classes
- Review system: queue items, digests, packets, decision records, auto-approval
- Delta reports and novelty scoring per ingestion run
- Egress policy enforcement with sanitization
- Append-only audit log
- Quarantine for invalid artifacts
- Wikilink graph with hub scoring and bridge detection
- Schema migration framework
- MCP server with 7 sandboxed tools
- CLI with run/status/auto commands
- 2300+ tests

### Post-Refactor Hardening

- HITL gate: fail-closed, case-insensitive agent normalization
- SSRF protection: scheme allowlist, host blocklist, size cap
- yaml.safe_dump across all modules
- Path traversal guards on all vault I/O
- Command allowlist and sandbox on MCP server
- Atomic writes for all persistence
- POSIX atomic append for audit log

## Next

### Source Connectors

The pipeline accepts URLs, PDFs, and text bundles. Additional source kinds
defined in the spec (DOI, arXiv, highlights, book notes) are stubbed but not
yet implemented.

### LLM-Backed Extraction

The extract stage currently uses rule-based extraction. Integrating LLM calls
(via LiteLLM) for claim extraction, entity recognition, and gist generation
would improve quality on complex sources.

### Frontier Command

The frontier command (CMD-FRN-001/002) is partially implemented. Full ranking
of unclear, weakly supported, and conflicting topics needs the graph analysis
pipeline connected to the triage scoring.

### Git Mode

Per-packet commit granularity during graduation (REV-004) is defined in the
spec and partially wired. Needs end-to-end testing and CLI integration.

### Obsidian Plugin

A companion Obsidian plugin could surface review queue items, frontier topics,
and delta reports directly in the editor sidebar.
