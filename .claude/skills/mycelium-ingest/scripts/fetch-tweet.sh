#!/usr/bin/env bash
set -euo pipefail

# Fetch a tweet/thread, format as Obsidian blockquote, write to file.
# Metadata JSON goes to stdout; formatted content goes to output file.
#
# Usage: fetch-tweet.sh <url> <output-file>
#
# Output file: Obsidian blockquote ready to append to a note
# Stdout: JSON metadata { author, name, date, likes, retweets, replies, url, article_title }

URL="${1:-}"
OUTPUT="${2:-}"

if [[ -z "$URL" || -z "$OUTPUT" ]]; then
  echo "Usage: fetch-tweet.sh <url> <output-file>" >&2
  exit 1
fi

# Create output directory if needed
mkdir -p "$(dirname "$OUTPUT")"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# --- Step 1: Fetch JSON metadata ---
bird read "$URL" --json > "$TMPDIR/tweet.json" 2>/dev/null

# Parse metadata with jq
AUTHOR=$(jq -r '.author.username // empty' "$TMPDIR/tweet.json")
NAME=$(jq -r '.author.name // empty' "$TMPDIR/tweet.json")
TWEET_ID=$(jq -r '.id // empty' "$TMPDIR/tweet.json")
CONV_ID=$(jq -r '.conversationId // empty' "$TMPDIR/tweet.json")
LIKES=$(jq -r '.likeCount // 0' "$TMPDIR/tweet.json")
RETWEETS=$(jq -r '.retweetCount // 0' "$TMPDIR/tweet.json")
REPLIES=$(jq -r '.replyCount // 0' "$TMPDIR/tweet.json")
CREATED_AT=$(jq -r '.createdAt // empty' "$TMPDIR/tweet.json")
ARTICLE_TITLE=$(jq -r '.article.title // empty' "$TMPDIR/tweet.json")

# Parse date: "Fri Jan 30 19:08:51 +0000 2026" → "2026-01-30"
DATE_FORMATTED=$(python3 -c "
from datetime import datetime
raw = '$CREATED_AT'
if raw:
    dt = datetime.strptime(raw, '%a %b %d %H:%M:%S %z %Y')
    print(dt.strftime('%Y-%m-%d'))
else:
    print('unknown')
")

# --- Step 2: Fetch plain text content ---
# Check if this is part of a thread (conversationId differs from id)
if [[ -n "$CONV_ID" && -n "$TWEET_ID" && "$CONV_ID" != "$TWEET_ID" ]]; then
  # It's a reply or part of a thread — fetch full thread
  bird thread "$URL" --plain > "$TMPDIR/content.txt" 2>/dev/null
else
  # Single tweet / article
  bird read "$URL" --plain > "$TMPDIR/content.txt" 2>/dev/null
fi

# --- Step 3: Strip the metadata lines bird appends at the end ---
# bird --plain appends lines like:
#   date: Fri Jan 30 19:08:51 +0000 2026
#   url: https://x.com/...
#   likes: 217  retweets: 20  replies: 13
# Also strip the leading "@handle (Name):" attribution line that bird adds

# Remove: trailing metadata block (date:/url:/likes: lines)
#         leading blank lines and "@Handle (Name):" author line
#         "Article: ..." title line (already have title from JSON metadata)
awk '
  { lines[NR] = $0 }
  END {
    # Find where trailing metadata starts (scan backwards)
    meta_start = NR + 1
    for (i = NR; i >= 1; i--) {
      if (lines[i] ~ /^(date|url|likes|retweets|replies):/) {
        meta_start = i
      } else {
        break
      }
    }

    # Find content start: skip leading blanks, author line, and Article: line
    content_start = 1
    for (i = 1; i < meta_start; i++) {
      if (lines[i] ~ /^[[:space:]]*$/) { content_start = i + 1; continue }
      if (lines[i] ~ /^@[^ ]+ \(.*\):/) { content_start = i + 1; continue }
      if (lines[i] ~ /^Article: /) { content_start = i + 1; continue }
      break
    }

    # Print content lines only
    for (i = content_start; i < meta_start; i++) {
      print lines[i]
    }
  }
' "$TMPDIR/content.txt" > "$TMPDIR/body.txt"

# Trim leading/trailing blank lines
sed -i '/./,$!d' "$TMPDIR/body.txt"
sed -i -e :a -e '/^\n*$/{$d;N;ba;}' "$TMPDIR/body.txt"

# --- Step 4: Format as Obsidian blockquote ---
{
  echo "> @${AUTHOR} — ${DATE_FORMATTED}"
  echo ">"

  # Prefix every line with "> "
  # Empty lines become ">" (Obsidian needs continuation)
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ -z "$line" ]]; then
      echo ">"
    else
      echo "> $line"
    fi
  done < "$TMPDIR/body.txt"

  echo ">"
  echo "> Engagement: ${LIKES} likes | ${RETWEETS} retweets | ${REPLIES} replies"
  echo "> [Original post](${URL})"
} > "$OUTPUT"

# --- Step 5: Output metadata JSON to stdout ---
jq -n \
  --arg author "@${AUTHOR}" \
  --arg name "$NAME" \
  --arg date "$DATE_FORMATTED" \
  --argjson likes "$LIKES" \
  --argjson retweets "$RETWEETS" \
  --argjson replies "$REPLIES" \
  --arg url "$URL" \
  --arg article_title "$ARTICLE_TITLE" \
  '{author: $author, name: $name, date: $date, likes: $likes, retweets: $retweets, replies: $replies, url: $url, article_title: $article_title}'
