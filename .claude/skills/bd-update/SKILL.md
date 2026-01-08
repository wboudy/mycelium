---
name: bd-update
description: >
  Update a bead's status, priority, labels, or other fields. Use when
  changing bead state, when the user says "update bead X", "set status",
  "add label", "bd update X".
version: 1.0.0
author: mycelium
allowed-tools:
  - Bash
---

# BD Update - Update Bead

Update a bead's status, priority, assignee, or labels.

## Arguments

- `$1`: Bead ID (required)
- Options:
  - `--status <status>`: open, in_progress, blocked, closed
  - `--priority <0-4>`: 0=critical, 1=high, 2=medium, 3=low, 4=backlog
  - `--assignee <name>`: Assign to someone (use "" to unassign)
  - `--label <label>`: Add a label
  - `--remove-label <label>`: Remove a label
  - `--notes <text>`: Append to notes

## Instructions

Run this Python script:

```bash
python3 << 'PYEOF'
import sqlite3
import os
from datetime import datetime

bead_id = "$1" if "$1" and "$1" != "$1" else None

# Parse options
args = """$2 $3 $4 $5 $6 $7 $8 $9""".split()
status = None
priority = None
assignee = None
add_label = None
remove_label = None
notes = None

i = 0
while i < len(args):
    arg = args[i].strip()
    if arg == "--status" and i+1 < len(args):
        status = args[i+1].strip()
        i += 2
    elif arg == "--priority" and i+1 < len(args):
        priority = int(args[i+1].strip())
        i += 2
    elif arg == "--assignee" and i+1 < len(args):
        assignee = args[i+1].strip()
        i += 2
    elif arg == "--label" and i+1 < len(args):
        add_label = args[i+1].strip()
        i += 2
    elif arg == "--remove-label" and i+1 < len(args):
        remove_label = args[i+1].strip()
        i += 2
    elif arg == "--notes" and i+1 < len(args):
        notes = args[i+1].strip()
        i += 2
    else:
        i += 1

if not bead_id:
    print("Usage: /bd-update <bead-id> [--status X] [--priority N] [--assignee X] [--label X] [--remove-label X] [--notes X]")
    print("Please provide a bead ID and at least one option.")
    exit(1)

db_path = os.path.join(os.getcwd(), '.beads/beads.db')
if not os.path.exists(db_path):
    print("No beads database found at .beads/beads.db")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Check if bead exists
cur.execute("SELECT * FROM issues WHERE id = ?", (bead_id,))
row = cur.fetchone()

if not row:
    print(f"Bead '{bead_id}' not found.")
    conn.close()
    exit(1)

now = datetime.now().isoformat()
updates = []
params = []

if status:
    updates.append("status = ?")
    params.append(status)
    if status == 'closed':
        updates.append("closed_at = ?")
        params.append(now)

if priority is not None:
    updates.append("priority = ?")
    params.append(priority)

if assignee is not None:
    updates.append("assignee = ?")
    params.append(assignee if assignee else None)

if notes:
    current_notes = row['notes'] or ""
    new_notes = current_notes + "\n\n" + notes if current_notes else notes
    updates.append("notes = ?")
    params.append(new_notes)

if updates:
    updates.append("updated_at = ?")
    params.append(now)
    params.append(bead_id)
    cur.execute(f"UPDATE issues SET {', '.join(updates)} WHERE id = ?", params)

# Handle labels
if add_label:
    cur.execute("INSERT OR IGNORE INTO labels (issue_id, label, created_at, created_by) VALUES (?, ?, ?, 'claude')",
                (bead_id, add_label, now))
    print(f"Added label: {add_label}")

if remove_label:
    cur.execute("DELETE FROM labels WHERE issue_id = ? AND label = ?", (bead_id, remove_label))
    print(f"Removed label: {remove_label}")

conn.commit()

# Show updated state
cur.execute("SELECT * FROM issues WHERE id = ?", (bead_id,))
row = cur.fetchone()
cur.execute("SELECT label FROM labels WHERE issue_id = ?", (bead_id,))
labels = [l['label'] for l in cur.fetchall()]

conn.close()

print(f"Updated bead: {bead_id}")
print(f"  Status: {row['status']}")
print(f"  Priority: P{row['priority']}")
if row['assignee']:
    print(f"  Assignee: {row['assignee']}")
if labels:
    print(f"  Labels: {', '.join(labels)}")
PYEOF
```

## Output

Shows the updated bead state.
