---
name: bd-ready
description: >
  Find beads that are ready to work on (no blocking dependencies).
  Use when checking what work is available, or when the user asks
  "what should I work on?", "show ready tasks", "bd ready".
version: 1.0.0
author: mycelium
allowed-tools:
  - Bash
---

# BD Ready - Find Unblocked Work

Find beads that have no blocking dependencies and are ready to work on.

## Instructions

Run this Python script to query the beads database:

```bash
python3 << 'PYEOF'
import sqlite3
import os

db_path = os.path.join(os.getcwd(), '.beads/beads.db')
if not os.path.exists(db_path):
    print("No beads database found at .beads/beads.db")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Find open issues that have no blocking dependencies
cur.execute("""
    SELECT i.id, i.title, i.priority, i.issue_type, i.assignee, i.status
    FROM issues i
    WHERE i.status IN ('open', 'in_progress')
    AND i.id NOT IN (
        SELECT d.issue_id FROM dependencies d
        JOIN issues blocker ON d.depends_on_id = blocker.id
        WHERE d.type = 'blocks'
        AND blocker.status NOT IN ('closed', 'tombstone')
    )
    ORDER BY i.priority ASC, i.created_at ASC
""")

rows = cur.fetchall()
conn.close()

if not rows:
    print("No ready tasks found.")
else:
    print(f"Found {len(rows)} ready task(s):\n")
    for row in rows:
        priority = f"P{row['priority']}"
        assignee = f" @{row['assignee']}" if row['assignee'] else ""
        status = f" [{row['status']}]" if row['status'] == 'in_progress' else ""
        print(f"  [{priority}] [{row['issue_type']}] {row['id']}: {row['title']}{assignee}{status}")
PYEOF
```

## Output

Shows a list of ready beads with:
- Priority (P0-P4)
- Type (task, bug, feature, epic, etc.)
- ID
- Title
- Assignee (if any)
- Status (if in_progress)
