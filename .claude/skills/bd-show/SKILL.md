---
name: bd-show
description: >
  Show detailed information about a bead. Use when checking bead details,
  when the user asks "show bead X", "what is bead X", "bd show X".
version: 1.0.0
author: mycelium
allowed-tools:
  - Bash
---

# BD Show - Display Bead Details

Show detailed information about a specific bead.

## Arguments

- `$1`: Bead ID (required)

## Instructions

Run this Python script with the bead ID:

```bash
python3 << 'PYEOF'
import sqlite3
import sys
import os

bead_id = "$1" if "$1" else None

if not bead_id or bead_id == "$1":
    print("Usage: /bd-show <bead-id>")
    print("Please provide a bead ID.")
    exit(1)

db_path = os.path.join(os.getcwd(), '.beads/beads.db')
if not os.path.exists(db_path):
    print("No beads database found at .beads/beads.db")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get issue details
cur.execute("SELECT * FROM issues WHERE id = ?", (bead_id,))
row = cur.fetchone()

if not row:
    print(f"Bead '{bead_id}' not found.")
    conn.close()
    exit(1)

print(f"=== {row['id']} ===")
print(f"Title: {row['title']}")
print(f"Status: {row['status']}")
print(f"Priority: P{row['priority']}")
print(f"Type: {row['issue_type']}")
if row['assignee']:
    print(f"Assignee: {row['assignee']}")
print(f"Created: {row['created_at']}")
if row['closed_at']:
    print(f"Closed: {row['closed_at']}")
    if row['close_reason']:
        print(f"Close reason: {row['close_reason']}")

if row['description']:
    print(f"\nDescription:\n{row['description']}")

if row['notes']:
    print(f"\nNotes:\n{row['notes']}")

# Get labels
cur.execute("SELECT label FROM labels WHERE issue_id = ?", (bead_id,))
labels = [l['label'] for l in cur.fetchall()]
if labels:
    print(f"\nLabels: {', '.join(labels)}")

# Get dependencies
cur.execute("""
    SELECT d.depends_on_id, d.type, i.title, i.status
    FROM dependencies d
    JOIN issues i ON d.depends_on_id = i.id
    WHERE d.issue_id = ?
""", (bead_id,))
deps = cur.fetchall()
if deps:
    print(f"\nDependencies:")
    for d in deps:
        status_mark = "x" if d['status'] == 'closed' else " "
        print(f"  [{status_mark}] {d['depends_on_id']}: {d['title']} ({d['type']})")

# Get dependents (issues blocked by this one)
cur.execute("""
    SELECT d.issue_id, d.type, i.title, i.status
    FROM dependencies d
    JOIN issues i ON d.issue_id = i.id
    WHERE d.depends_on_id = ?
""", (bead_id,))
dependents = cur.fetchall()
if dependents:
    print(f"\nBlocks:")
    for d in dependents:
        print(f"  - {d['issue_id']}: {d['title']}")

conn.close()
PYEOF
```

## Output

Shows:
- ID, title, status, priority, type
- Assignee and timestamps
- Description and notes
- Labels
- Dependencies (what this blocks/is blocked by)
