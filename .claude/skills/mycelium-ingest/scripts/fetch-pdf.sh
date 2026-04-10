#!/usr/bin/env bash
set -euo pipefail

# Extract text from a PDF and format as an Obsidian collapsible callout.
# Usage: fetch-pdf.sh <path-or-url> <output-file>
#
# File output: collapsible [!quote] callout with full extracted text
# Stdout: JSON metadata { title, filename, description, url, final_url }

INPUT="${1:?Usage: fetch-pdf.sh <path-or-url> <output-file>}"
OUTFILE="${2:?Usage: fetch-pdf.sh <path-or-url> <output-file>}"

CLEANUP=""

# Resolve input to a local file
if [[ -f "$INPUT" ]]; then
  PDF_PATH="$INPUT"
  SOURCE_REF="$INPUT"
elif [[ "$INPUT" == http* ]]; then
  TMP=$(mktemp /tmp/fetch-pdf-XXXXXX.pdf)
  curl -sL "$INPUT" -o "$TMP"
  PDF_PATH="$TMP"
  SOURCE_REF="$INPUT"
  CLEANUP="$TMP"
else
  echo "Error: $INPUT is not a readable file or URL" >&2
  exit 1
fi

# Extract text via pdftotext
TEXT=$(pdftotext "$PDF_PATH" -)

# Derive title from filename (strip path + extension)
FILENAME=$(basename "$INPUT")
TITLE="${FILENAME%.pdf}"
TITLE="${TITLE%.PDF}"

# Build collapsible callout (same format as fetch-web.sh)
{
  echo '> [!quote]- Source Material'
  echo '>'
  echo "$TEXT" | while IFS= read -r line; do
    if [[ -z "$line" ]]; then
      echo '>'
    else
      printf '> %s\n' "$line"
    fi
  done
  echo '>'
  echo "> [Source: ${FILENAME}](${SOURCE_REF})"
} > "$OUTFILE"

# Cleanup temp file if downloaded
[[ -n "$CLEANUP" ]] && rm -f "$CLEANUP"

# Output metadata as JSON (to stdout, consumed by the agent)
jq -n \
  --arg title "$TITLE" \
  --arg filename "$FILENAME" \
  --arg url "$SOURCE_REF" \
  '{title: $title, filename: $filename, description: "", url: $url, final_url: $url}'
