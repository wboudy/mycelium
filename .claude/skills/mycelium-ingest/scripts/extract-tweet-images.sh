#!/usr/bin/env bash
# extract-tweet-images.sh — Download all content images from an X/Twitter post
#
# Usage:
#   extract-tweet-images.sh <tweet_url> <slug> [output_dir]
#
# Arguments:
#   tweet_url   — Full X/Twitter URL
#   slug        — Short identifier for filenames (e.g., "nicbstme-617652")
#   output_dir  — Where to save images (default: current directory)
#
# Output:
#   Downloads images to output_dir as {slug}-{NNN}.{ext}
#   Prints JSON array of downloaded filenames to stdout
#
# Requires: agent-browser, curl, python3

set -euo pipefail

TWEET_URL="${1:?Usage: extract-tweet-images.sh <tweet_url> <slug> [output_dir]}"
SLUG="${2:?Usage: extract-tweet-images.sh <tweet_url> <slug> [output_dir]}"
OUTPUT_DIR="${3:-.}"

mkdir -p "$OUTPUT_DIR"

# ── 1. Open the tweet in agent-browser ────────────────────────────────
echo "[images] Opening $TWEET_URL" >&2
agent-browser open "$TWEET_URL" --wait 3000 >/dev/null 2>&1

# ── 2. Scroll to load all lazy images ────────────────────────────────
echo "[images] Scrolling to load images..." >&2
for i in $(seq 1 8); do
  agent-browser scroll down 2000 >/dev/null 2>&1
  sleep 1
done
# Return to top and scroll again for anything missed
agent-browser eval "window.scrollTo(0, 0)" >/dev/null 2>&1
sleep 1
for i in $(seq 1 6); do
  agent-browser scroll down 3000 >/dev/null 2>&1
  sleep 0.8
done

# ── 3. Extract image URLs via JS ─────────────────────────────────────
echo "[images] Extracting image URLs..." >&2
RAW_URLS=$(agent-browser eval '
(() => {
  const urls = Array.from(document.querySelectorAll("img"))
    .map(img => img.src)
    .filter(src => src && src.includes("pbs.twimg.com/media/"))
    .map(src => src.replace(/name=\w+/, "name=large"))
    .filter((v, i, a) => a.indexOf(v) === i);
  return JSON.stringify(urls);
})()
' 2>/dev/null || echo '[]')

# ── 4. Close browser ─────────────────────────────────────────────────
agent-browser close >/dev/null 2>&1

# ── 5. Clean the output ──────────────────────────────────────────────
# agent-browser eval wraps output in double quotes and escapes inner quotes
# Strip outer quotes: "\"[...]\"" → [...]
CLEAN_URLS=$(echo "$RAW_URLS" | python3 -c "
import sys, json
raw = sys.stdin.read().strip()
# Handle double-encoded JSON: \"[...]\"
if raw.startswith('\"') and raw.endswith('\"'):
    try:
        raw = json.loads(raw)
    except:
        pass
# Now parse the actual array
try:
    urls = json.loads(raw)
    print(json.dumps(urls))
except:
    print('[]')
")

# ── 6. Download images ───────────────────────────────────────────────
echo "[images] Downloading to $OUTPUT_DIR..." >&2

FILENAMES=$(echo "$CLEAN_URLS" | python3 -c "
import json, sys, subprocess, os

raw = sys.stdin.read().strip()
urls = json.loads(raw)
slug = os.environ.get('SLUG', 'img')
output_dir = os.environ.get('OUTPUT_DIR', '.')
filenames = []

for i, url in enumerate(urls, 1):
    # Determine extension from format param
    ext = 'png'
    if 'format=jpg' in url or 'format=jpeg' in url:
        ext = 'jpg'
    elif 'format=webp' in url:
        ext = 'webp'

    filename = f'{slug}-{i:03d}.{ext}'
    filepath = os.path.join(output_dir, filename)

    try:
        result = subprocess.run(
            ['curl', '-sL', '-o', filepath, '--max-time', '30', url],
            timeout=35,
            capture_output=True
        )
        filesize = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        if result.returncode == 0 and filesize > 1000:
            filenames.append(filename)
            print(f'  ✓ {filename} ({filesize:,} bytes)', file=sys.stderr)
        else:
            if os.path.exists(filepath):
                os.remove(filepath)
            print(f'  ✗ {filename} (failed, {filesize} bytes)', file=sys.stderr)
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        print(f'  ✗ {filename} (error: {e})', file=sys.stderr)

print(json.dumps(filenames))
" 2>&2)

echo "[images] Done: $(echo "$FILENAMES" | python3 -c "import json,sys; print(len(json.loads(sys.stdin.read())))")/$(echo "$CLEAN_URLS" | python3 -c "import json,sys; print(len(json.loads(sys.stdin.read())))")  images downloaded" >&2
echo "$FILENAMES"
