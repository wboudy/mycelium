---
name: mycelium-ingest
description: Ingest a URL, PDF, or text into the Mycelium knowledge vault. Use when the user says "ingest this", "capture this URL", "add to vault", "save this knowledge", or provides a URL to process through the knowledge pipeline.
user-invocable: true
argument-hint: "<url-or-text>"
allowed-tools:
  - Bash
  - Read
  - Write
  - Agent
---

# Mycelium Ingest

Capture knowledge from a URL or text and process it through the Mycelium pipeline.

**Vault location**: `./vault` (project-local)

## Workflow

### 1. Classify input

Determine if the input is:
- A URL (starts with http/https)
- A file path (local PDF or text file)
- Inline text

### 2. Run capture + normalize + fingerprint

```bash
MYCELIUM_VAULT_ROOT=vault python -m mycelium.cli ingest --url "<url>"
# or
MYCELIUM_VAULT_ROOT=vault python -m mycelium.cli ingest --text "<text>"
# or
MYCELIUM_VAULT_ROOT=vault python -m mycelium.cli ingest --pdf "<path>"
```

This runs stages 1-3 (capture, normalize, fingerprint) and the rule-based extract stage 4.

### 3. Agent-enhanced extraction

The rule-based extraction is weak. After the pipeline runs, read the extraction bundle:

```bash
cat vault/Inbox/Sources/<run_id>_extraction.yaml
```

Review the extracted claims. If they are poor quality (too generic, missed key insights):

1. Read the captured source text from the extraction bundle's `normalized_text` field
2. Extract better claims yourself — look for:
   - Empirical assertions (studies show, data indicates)
   - Causal claims (X causes Y, X leads to Y)  
   - Definitions (X is defined as, X refers to)
   - Procedural claims (to do X, first Y then Z)
3. Write an improved extraction bundle with proper provenance

### 4. Review the delta report

```bash
cat vault/Reports/Delta/<delta-file>.yaml
```

Check novelty score and match groups. For a new vault, everything will be NEW.

### 5. Report

Output a summary:
```
Ingested: [source ref]
Claims extracted: N
Novelty score: X.XX
Queue items: N pending review
Delta report: vault/Reports/Delta/<file>
```

## Quality Checks

- [ ] Pipeline completed successfully (ok: true in output)
- [ ] Extraction bundle written to Inbox/Sources/
- [ ] Delta report written to Reports/Delta/
- [ ] Review queue items created in Inbox/ReviewQueue/
- [ ] Audit event logged in Logs/Audit/
