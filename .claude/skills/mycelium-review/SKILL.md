---
name: mycelium-review
description: Review pending knowledge vault proposals. Use when the user says "review queue", "what's pending", "nightly review", "approve/reject", or wants to process the review queue before bed.
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
---

# Mycelium Review

Review pending proposals in the knowledge vault's review queue.

**Vault location**: `./vault` (project-local)

## Workflow

### 1. List pending items

```bash
ls vault/Inbox/ReviewQueue/
```

If empty, report "No pending items" and exit.

### 2. Summarize the queue

For each `.yaml` file in `Inbox/ReviewQueue/`:
- Read the file
- Extract: `item_type`, `proposed_action`, `status`, match class, claim text
- Group by source/run_id

Present a summary table:
```
Pending Review (N items from M sources):

Source: [ref]  |  Run: [run_id]
  1. [claim summary] — [match_class] — [proposed_action]
  2. [claim summary] — [match_class] — [proposed_action]
  ...
```

### 3. Get user decisions

For each item or batch, ask the user:
- **approve** — graduate to canonical scope
- **reject** — discard
- **hold** — defer (resurfaces after hold TTL)
- **skip** — leave as pending, move to next

### 4. Execute decisions

For approved items:
```bash
MYCELIUM_VAULT_ROOT=vault python -m mycelium.cli review --queue-id <id> --decision approve --reason "<reason>"
```

For rejected items:
```bash
MYCELIUM_VAULT_ROOT=vault python -m mycelium.cli review --queue-id <id> --decision reject --reason "<reason>"
```

### 5. Report

```
Review complete:
  Approved: N
  Rejected: N
  Held: N
  Remaining: N
```
