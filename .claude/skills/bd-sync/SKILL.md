---
name: bd-sync
description: >
  Sync beads database to JSONL and commit to git. Use when saving work,
  when the user says "sync beads", "save beads", "bd sync".
version: 1.0.0
author: mycelium
allowed-tools:
  - Bash
---

# BD Sync - Sync Beads to Git

Export beads database to JSONL and commit to the beads-sync branch.

## Instructions

Run this Python script to export and sync:

```bash
python3 << 'PYEOF'
import sqlite3
import json
import os
import subprocess
from datetime import datetime

db_path = os.path.join(os.getcwd(), '.beads/beads.db')
jsonl_path = os.path.join(os.getcwd(), '.beads/issues.jsonl')

if not os.path.exists(db_path):
    print("No beads database found at .beads/beads.db")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get all issues
cur.execute("""
    SELECT id, title, description, notes, status, priority, issue_type,
           assignee, created_at, created_by, updated_at, closed_at, close_reason,
           deleted_at, deleted_by, delete_reason, original_type
    FROM issues ORDER BY id
""")

issues = []
for row in cur.fetchall():
    issue = {
        'id': row['id'],
        'title': row['title'],
        'description': row['description'],
        'status': row['status'],
        'priority': row['priority'],
        'issue_type': row['issue_type'],
        'created_at': row['created_at'],
        'created_by': row['created_by'],
        'updated_at': row['updated_at'],
    }
    if row['notes']:
        issue['notes'] = row['notes']
    if row['assignee']:
        issue['assignee'] = row['assignee']
    if row['closed_at']:
        issue['closed_at'] = row['closed_at']
    if row['close_reason']:
        issue['close_reason'] = row['close_reason']
    if row['deleted_at']:
        issue['deleted_at'] = row['deleted_at']
        issue['deleted_by'] = row['deleted_by']
        issue['delete_reason'] = row['delete_reason']
        issue['original_type'] = row['original_type']

    # Get labels
    cur.execute("SELECT label FROM labels WHERE issue_id = ?", (row['id'],))
    labels = [l['label'] for l in cur.fetchall()]
    if labels:
        issue['labels'] = labels

    # Get dependencies
    cur.execute("""
        SELECT issue_id, depends_on_id, type, created_at, created_by
        FROM dependencies WHERE issue_id = ?
    """, (row['id'],))
    deps = []
    for d in cur.fetchall():
        deps.append({
            'issue_id': d['issue_id'],
            'depends_on_id': d['depends_on_id'],
            'type': d['type'],
            'created_at': d['created_at'],
            'created_by': d['created_by']
        })
    if deps:
        issue['dependencies'] = deps

    issues.append(issue)

conn.close()

# Write to JSONL
with open(jsonl_path, 'w') as f:
    for issue in issues:
        f.write(json.dumps(issue) + '\n')

print(f"Exported {len(issues)} issues to {jsonl_path}")

# Check for beads-sync worktree
worktree_path = os.path.join(os.getcwd(), '.git/beads-worktrees/beads-sync')
if os.path.exists(worktree_path):
    # Copy to worktree
    worktree_jsonl = os.path.join(worktree_path, '.beads/issues.jsonl')
    os.makedirs(os.path.dirname(worktree_jsonl), exist_ok=True)
    with open(worktree_jsonl, 'w') as f:
        for issue in issues:
            f.write(json.dumps(issue) + '\n')

    # Commit and push
    try:
        subprocess.run(['git', '-C', worktree_path, 'add', '.beads/issues.jsonl'], check=True)
        result = subprocess.run(['git', '-C', worktree_path, 'diff', '--cached', '--quiet'])
        if result.returncode != 0:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            subprocess.run(['git', '-C', worktree_path, 'commit', '-m', f'bd sync: {now}'], check=True)
            subprocess.run(['git', '-C', worktree_path, 'push', 'origin', 'beads-sync'], check=True)
            print("Committed and pushed to beads-sync branch")
        else:
            print("No changes to commit")
    except subprocess.CalledProcessError as e:
        print(f"Git operation failed: {e}")
else:
    print("No beads-sync worktree found - exported to local JSONL only")
PYEOF
```

## Output

Shows export status and git sync result.
