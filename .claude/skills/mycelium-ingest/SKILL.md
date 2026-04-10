---
name: mycelium-ingest
description: Capture knowledge from any URL, PDF, or text into the Mycelium vault. Use when the user says "ingest this", "capture this URL", "add to vault", "save this", "capture this article", "capture this PDF", or provides a URL/file path to process.
user-invocable: true
argument-hint: "<url-or-path-or-text>"
allowed-tools:
  - Bash
  - Read
  - Write
  - Agent
---

# Mycelium Ingest

Capture knowledge from a URL and create a linked vault note in draft scope.

**Vault location**: `./vault`
**Media folder**: `./vault/_media/`
**Draft target**: `./vault/Inbox/Sources/` (notes land here, NOT in canonical scope)

## Workflow

### 1. Classify and fetch content

Classify the input:
```bash
bash .claude/skills/mycelium-ingest/scripts/detect-url-type.sh "<url-or-path>"
# Outputs: "pdf", "twitter", or "web"
```

**If pdf** (local file path or URL ending in `.pdf`):
```bash
bash .claude/skills/mycelium-ingest/scripts/fetch-pdf.sh "<path-or-url>" /tmp/content.md
# File output: collapsible callout with full extracted text
# Stdout: JSON metadata { title, filename, description, url }
```
For `source` frontmatter: use the PDF filename (e.g., `Framework.pdf`), not the full path.

**If twitter**:
```bash
# Single tweet
bird read <url> --plain

# If output shows it is part of a thread, re-fetch the full thread
bird thread <url> --plain
```

**If web**:
```bash
npx playbooks get "<url>"
```

See `references/playbooks-usage.md` for detailed options and JSON output mode.

### 1b. Extract images (twitter and web)

For **twitter** URLs, extract all content images from the post:
```bash
bash .claude/skills/mycelium-ingest/scripts/extract-tweet-images.sh "<url>" "<slug>" ./vault/_media/
```

**Slug convention**: `{author_handle}-{last_6_digits_of_tweet_id}`

For **web** URLs with important images, use agent-browser manually:
```bash
agent-browser open "<url>"
agent-browser eval '<JS to extract content image URLs>'
# Download with curl, save to ./vault/_media/
agent-browser close
```

For **PDFs**, skip image extraction (text-only capture via pdftotext).

**Image embedding convention**:
- All images live in `_media/` at the vault root
- Embed with Obsidian wiki syntax: `![[slug-001.png]]`
- Add a brief italic caption above each embed

### 2. Analyze content

From the fetched content, extract:
1. **Core claim** — a single assertive sentence capturing the main insight. This becomes the note title.
2. **Key takeaways** — 3-7 insights in your own words (not copied text).
3. **Atomic claims** — falsifiable assertions from the source, each with:
   - `claim_text`: the assertion
   - `claim_type`: empirical, definition, causal, normative, or procedural
   - `polarity`: supports, opposes, or neutral
4. **External links** — URLs found in the content.
5. **Domain/topic** — what knowledge area this belongs to.

### 3. Determine note title

Write a claim-based title in readable prose:
- GOOD: `onboarding is 70 percent of app success.md`
- BAD: `playbooks-notes.md`

The title should be an assertion a reader can evaluate as true or false.

### 4. Find related vault notes

Search the vault for related existing notes:
```bash
# Search canonical scope for related content
grep -rl "<key terms>" vault/Sources/ vault/Claims/ vault/Concepts/ 2>/dev/null | head -10
```

Or dispatch an Explore agent to search more broadly.

Use the returned note titles as `[[wiki link]]` targets in step 6.

### 5. Determine folder placement

Notes go into **draft scope** — `Inbox/Sources/`:
```
vault/Inbox/Sources/[claim-based-title].md
```

This is non-negotiable. Notes enter draft scope first and only reach canonical scope (Sources/, Claims/, etc.) through the review + graduation process.

### 6. Create the note

Write the note to `vault/Inbox/Sources/[title].md` with this structure:

```markdown
---
created: YYYY-MM-DD
description: One sentence elaborating the title claim
source: https://original-url.com
status: draft
type: source
tags: []
---

## Key Takeaways

Original analysis with [[Related Note]] woven inline.

## Claims

- **[empirical]** Claim text here (supports)
- **[causal]** Another claim (supports)
- **[definition]** A definition claim (neutral)

## External Resources

- [Resource Title](https://url) — one-sentence description

## Original Content

> [!quote]- Source Material
> Full content here in collapsible callout.
>
> [Original page](https://url)
```

Key rules:
- `status: draft` — always. Never `canon`.
- Claims section lists the atomic claims you extracted in step 2.
- Wiki links go inline in sentences, never in a "Related:" section.
- No emoji in headings or body.

### 7. Update the vault MOC

Update `vault/MOCs/moc - Vault.md` with a link to the new note under the relevant section.

### 8. Report

Output a summary:
```
Ingested: [note title]
Location: vault/Inbox/Sources/[filename]
Source: [URL]
Claims extracted: N
Related notes linked: [[note1]], [[note2]], ...
Status: draft (pending review)
```

## Quality Checks

Before finishing, verify:
- [ ] Title is a claim (readable prose assertion, not keywords)
- [ ] YAML frontmatter has `created`, `description`, `source`, `status: draft`
- [ ] Key Takeaways contains original analysis, not copied text
- [ ] Claims section lists atomic claims with types and polarities
- [ ] Wiki links woven inline into sentences
- [ ] Original content preserved in collapsible callout
- [ ] Note is in `vault/Inbox/Sources/`, NOT in canonical scope
- [ ] MOC updated
