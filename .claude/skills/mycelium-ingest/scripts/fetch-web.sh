#!/usr/bin/env bash
set -euo pipefail

# Fetch a web page, format as collapsible Obsidian callout, write to file.
# Metadata JSON goes to stdout; formatted content goes to output file.
#
# Usage: fetch-web.sh <url> <output-file>
#
# Output file: Obsidian collapsible callout ready to append to a note
# Stdout: JSON metadata { title, description, url, final_url }

URL="${1:-}"
OUTPUT="${2:-}"

if [[ -z "$URL" || -z "$OUTPUT" ]]; then
  echo "Usage: fetch-web.sh <url> <output-file>" >&2
  exit 1
fi

# Create output directory if needed
mkdir -p "$(dirname "$OUTPUT")"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# --- Step 1: Fetch via playbooks JSON mode (single call for metadata + content) ---
npx playbooks get "$URL" --json > "$TMPDIR/page.json" 2>/dev/null

# Parse metadata with jq
TITLE=$(jq -r '.title // empty' "$TMPDIR/page.json")
DESCRIPTION=$(jq -r '.description // empty' "$TMPDIR/page.json")
FINAL_URL=$(jq -r '.finalUrl // empty' "$TMPDIR/page.json")

# Extract markdown content
jq -r '.markdown // empty' "$TMPDIR/page.json" > "$TMPDIR/raw.md"

# --- Step 2: Strip YAML frontmatter if present ---
# Playbooks prepends frontmatter like:
#   ---
#   title: "..."
#   description: "..."
#   url: "..."
#   ---
awk '
  BEGIN { in_front = 0; front_count = 0; done = 0 }
  {
    if (done) { print; next }
    if (NR == 1 && $0 == "---") { in_front = 1; front_count++; next }
    if (in_front && $0 == "---") { front_count++; done = 1; next }
    if (in_front) { next }
    done = 1; print
  }
' "$TMPDIR/raw.md" > "$TMPDIR/body.md"

# Trim leading blank lines
sed -i '/./,$!d' "$TMPDIR/body.md"

# --- Step 3: Format as collapsible Obsidian callout ---
{
  echo "> [!quote]- Source Material"

  # Prefix every line with "> "
  # Empty lines become ">" (Obsidian needs continuation in callouts)
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ -z "$line" ]]; then
      echo ">"
    else
      echo "> $line"
    fi
  done < "$TMPDIR/body.md"

  echo ">"
  echo "> [Original page](${URL})"
} > "$OUTPUT"

# --- Step 4: Output metadata JSON to stdout ---
jq -n \
  --arg title "$TITLE" \
  --arg description "$DESCRIPTION" \
  --arg url "$URL" \
  --arg final_url "$FINAL_URL" \
  '{title: $title, description: $description, url: $url, final_url: $final_url}'
