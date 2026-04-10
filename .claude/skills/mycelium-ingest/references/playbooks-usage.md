# Playbooks CLI Reference

`npx playbooks get` fetches any public URL and converts it to clean markdown.
Works with client-side rendered pages (SPAs, React apps, etc.).

## Basic Usage

```bash
# Fetch a URL as markdown (printed to stdout)
npx playbooks get "<url>"
```

Output includes a YAML frontmatter block with title, description, and URL,
followed by the page content as markdown.

## JSON Mode

```bash
npx playbooks get "<url>" --json
```

Returns a JSON object:
```json
{
  "markdown": "---\ntitle: ...\n---\n\nPage content...",
  "title": "Page Title",
  "description": "Page meta description",
  "finalUrl": "https://final-url-after-redirects.com",
  "report": {
    "strategy": "readability",
    "trimmedLength": 4725,
    "isSparse": false,
    "wasHeadless": false
  }
}
```

Use JSON mode when you need structured metadata (title, description) separately
from content, or to check the `finalUrl` for redirects.

## When to Use

| Source | Tool |
|--------|------|
| Tweet or Twitter/X thread | `bird read/thread <url>` |
| Any other URL (articles, docs, GitHub, blogs) | `npx playbooks get "<url>"` |

Use the `detect-url-type.sh` script to classify URLs deterministically.

## Notes

- First run may install the package (adds a few seconds)
- Handles client-rendered pages automatically
- Output is clean markdown suitable for vault notes
- For very large pages, content may be trimmed (check `report.trimmedLength`)
