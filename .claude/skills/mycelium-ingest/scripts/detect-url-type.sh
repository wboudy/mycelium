#!/usr/bin/env bash
set -euo pipefail

# Classify input as "pdf", "twitter", or "web"
# Usage: detect-url-type.sh <url-or-path>
# Output: single word to stdout

INPUT="${1:-}"

if [[ -z "$INPUT" ]]; then
  echo "Usage: detect-url-type.sh <url-or-path>" >&2
  exit 1
fi

# Local PDF file (exists on disk and ends in .pdf)
if [[ -f "$INPUT" && "${INPUT,,}" == *.pdf ]]; then
  echo "pdf"
  exit 0
fi

# Strip protocol and www prefix for URL-based checks
NORMALIZED=$(echo "$INPUT" | sed -E 's|^https?://||; s|^www\.||')

# Remote PDF URL (strip query params for extension check)
URL_PATH="${NORMALIZED%%\?*}"
if [[ "${URL_PATH,,}" == *.pdf ]]; then
  echo "pdf"
elif [[ "$NORMALIZED" =~ ^(x\.com|twitter\.com)/ ]]; then
  echo "twitter"
else
  echo "web"
fi
