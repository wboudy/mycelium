---
name: bd-create
description: >
  Create a new bead. Use when creating tasks, when the user asks
  "create a task", "add a bead", "bd create".
version: 1.0.0
author: mycelium
allowed-tools:
  - Bash
---

# BD Create - Create New Bead

Create a new bead in the issue tracker.

## Arguments

- `$1`: Title (required)
- Options parsed from args:
  - `--type <type>`: task, bug, feature, epic, chore (default: task)
  - `--priority <0-4>`: 0=critical, 1=high, 2=medium, 3=low, 4=backlog (default: 2)
  - `--assignee <name>`: Assign to someone
  - `--description <text>`: Add description

## Instructions

Run this Python script:

```bash
python3 << 'PYEOF'
import sqlite3
import os
import random
import string
from datetime import datetime

# Parse arguments - these come from skill invocation
title = """$1""".strip()
issue_type = "task"
priority = 2
assignee = None
description = ""

# Simple arg parsing from remaining args
args = """$2 $3 $4 $5 $6 $7 $8 $9""".split()
i = 0
while i < len(args):
    arg = args[i].strip()
    if arg == "--type" and i+1 < len(args):
        issue_type = args[i+1].strip()
        i += 2
    elif arg == "--priority" and i+1 < len(args):
        priority = int(args[i+1].strip())
        i += 2
    elif arg == "--assignee" and i+1 < len(args):
        assignee = args[i+1].strip()
        i += 2
    elif arg == "--description" and i+1 < len(args):
        description = args[i+1].strip()
        i += 2
    else:
        i += 1

if not title or title == "$1":
    print("Usage: /bd-create \"Title\" [--type task] [--priority 2] [--assignee name] [--description text]")
    print("Please provide a title for the bead.")
    exit(1)

db_path = os.path.join(os.getcwd(), '.beads/beads.db')
if not os.path.exists(db_path):
    print("No beads database found at .beads/beads.db")
    exit(1)

# Generate ID
def gen_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=3))

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get prefix from existing issues
cur.execute("SELECT id FROM issues LIMIT 1")
row = cur.fetchone()
if row:
    prefix = row[0].rsplit('-', 1)[0]
else:
    prefix = "bead"

# Generate unique ID
while True:
    new_id = f"{prefix}-{gen_id()}"
    cur.execute("SELECT id FROM issues WHERE id = ?", (new_id,))
    if not cur.fetchone():
        break

now = datetime.now().isoformat()

cur.execute("""
    INSERT INTO issues (id, title, description, status, priority, issue_type, assignee, created_at, created_by, updated_at)
    VALUES (?, ?, ?, 'open', ?, ?, ?, ?, 'claude', ?)
""", (new_id, title, description, priority, issue_type, assignee, now, now))

conn.commit()
conn.close()

print(f"Created bead: {new_id}")
print(f"  Title: {title}")
print(f"  Type: {issue_type}")
print(f"  Priority: P{priority}")
if assignee:
    print(f"  Assignee: {assignee}")
if description:
    print(f"  Description: {description[:50]}...")
PYEOF
```

## Output

Shows the created bead with its generated ID and details.
