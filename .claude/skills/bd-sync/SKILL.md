---
name: bd-sync
description: >
  Sync beads_rust state to JSONL and commit to git. Use when saving work,
  when the user says "sync beads" or "save beads".
version: 2.0.0
author: mycelium
allowed-tools:
  - Bash
---

# BR Sync - Flush and Commit Beads State

`br` is non-invasive and never runs git commands. This skill flushes issue state and commits `.beads/` explicitly.

## Instructions

Run:

```bash
br sync --flush-only
git add .beads/
if git diff --cached --quiet; then
  echo "No .beads changes to commit"
else
  git commit -m "sync beads"
fi
```

## Output

Shows whether `.beads/` changes were flushed and committed.
