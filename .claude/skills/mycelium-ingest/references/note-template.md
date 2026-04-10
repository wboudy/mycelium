# Note Template for URL Captures

Exact structure for vault notes created from URLs. Adapt each section to the content.

## Template

```markdown
---
created: YYYY-MM-DD
description: One sentence elaborating the title claim
source: https://original-url.com
type: framework
---

## Key Takeaways

Original analysis paragraph with [[Related Note]] woven inline. Each takeaway should
stand alone — a reader arriving via any wiki link understands the insight without
needing other context. Dense linking is expected: aim for at least one wiki link per
takeaway paragraph connecting to existing vault knowledge.

Second takeaway paragraph exploring a different angle. This connects to
[[Another Note]] because the underlying pattern is shared. Write in your own voice,
not copied text from the source.

## External Resources

- [Resource Title](https://url) — one-sentence description of what this links to
- [Another Resource](https://url) — brief description

Only include resources found within or referenced by the source content.

## Original Content

[Use one of the two formats below depending on source type]
```

## Format: Tweets (short content)

Use standard blockquotes with attribution:

```markdown
> @handle — YYYY-MM-DD
>
> Full tweet text here. For threads, include all tweets
> in the thread as a continuous blockquote with blank
> lines between each tweet.
>
> Engagement: 260 likes | 12 retweets | 18 replies
> [Original post](https://x.com/handle/status/id)
```

## Format: Web pages (long content)

Use a collapsible Obsidian callout:

```markdown
> [!quote]- Source Material
> Full article/page content here.
> Preserve headings and structure from the markdown.
> This collapses by default in Obsidian so it does not
> clutter the reading view but remains available for reference.
>
> [Original page](https://url)
```

## Format: PDFs (local or remote)

Use the same collapsible callout as web pages:

```markdown
> [!quote]- Source Material
> Full extracted text from the PDF.
> pdftotext preserves reading order but not rich formatting.
>
> [Source: filename.pdf](/path/to/filename.pdf)
```

Notes:
- `source` frontmatter field: use the PDF filename, not the full path
- Text extraction quality varies — tables and multi-column layouts may need manual cleanup

## Images

When the source contains images (diagrams, tables, screenshots, charts):

1. Images are saved to the vault's `_media/` folder at the root
2. Naming convention: `{author}-{last6digits_of_id}-{NNN}.{ext}`
   - Example: `nicbstme-617652-001.png`
3. Embed in the note using Obsidian wiki syntax: `![[nicbstme-617652-001.png]]`
4. Place image embeds in the **Original Content** section near the text they accompany
5. Add a brief caption line above or below each image embed:
   ```markdown
   *Pricing comparison: cached vs uncached inputs*
   ![[nicbstme-617652-001.png]]
   ```
6. Also reference key images in **Key Takeaways** when they contain data not in the text
   (e.g., a pricing table whose numbers are missing from the article text)

Images are extracted using:
```bash
bash scripts/extract-tweet-images.sh "<tweet_url>" "<slug>" /path/to/vault/_media/
```

The script returns a JSON array of filenames. Map them to the article by visual order
(image 001 = first image in the article, 002 = second, etc.).

## Rules

- Title is a claim, not a topic: "onboarding drives 70% of retention" not "onboarding-notes"
- Wiki links go inline in sentences, never in a "Related:" section at the bottom
- Description must be one sentence making the note discoverable without opening it
- The note must stand alone — a reader arriving from any wiki link understands it
- No emoji in headings or body
- Always include link to original URL in the Original Content section
- When source has images, always run the image extraction script and embed them
