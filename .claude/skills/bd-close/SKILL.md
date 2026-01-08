---
name: bd-close
description: >
  Close a completed bead. Use when finishing work, when the user says
  "close bead X", "done with X", "bd close X".
version: 1.0.0
author: mycelium
allowed-tools:
  - Bash
---

# BD Close - Close Completed Bead

Mark a bead as closed/completed.

## Arguments

- `$1`: Bead ID (required)
- `$2`: Close reason (optional)

## Instructions

Run this Python script:

```bash
python3 << 'PYEOF'
import sqlite3
import os
from datetime import datetime

bead_id = "$1" if "$1" else None
reason = "$2" if "$2" and "$2" != "$2" else "Completed"

if not bead_id or bead_id == "$1":
    print("Usage: /bd-close <bead-id> [reason]")
    print("Please provide a bead ID.")
    exit(1)

db_path = os.path.join(os.getcwd(), '.beads/beads.db')
if not os.path.exists(db_path):
    print("No beads database found at .beads/beads.db")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Check if bead exists
cur.execute("SELECT id, title, status FROM issues WHERE id = ?", (bead_id,))
row = cur.fetchone()

if not row:
    print(f"Bead '{bead_id}' not found.")
    conn.close()
    exit(1)

if row['status'] == 'closed':
    print(f"Bead '{bead_id}' is already closed.")
    conn.close()
    exit(0)

now = datetime.now().isoformat()

cur.execute("""
    UPDATE issues
    SET status = 'closed', closed_at = ?, close_reason = ?, updated_at = ?
    WHERE id = ?
""", (now, reason, now, bead_id))

conn.commit()
conn.close()

print(f"Closed bead: {bead_id}")
print(f"  Title: {row['title']}")
print(f"  Reason: {reason}")
PYEOF
```

## Output

Confirms the bead was closed with the reason.
