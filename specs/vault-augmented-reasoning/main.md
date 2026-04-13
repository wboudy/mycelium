# Vault-Augmented Reasoning

**Status:** Draft
**Date:** 2026-04-12
**Goal:** Make the Mycelium vault function as a persistent extension of Claude's working memory during conversation, so responses are informed by canonical vault knowledge when relevant.
**Related tasks:** #9 (design), #10 (recall skill), #13 (conversational wiring)

---

## Context

As of 2026-04-12, the vault contains 55 canonical source notes in `vault/Sources/` covering:

- AI/ML foundations (RL, diffusion, attention, world models)
- Agent orchestration and coding agents (Beads, Gas Town, AGENTS.md impact)
- Forecasting and calibration (Tetlock, frozen snapshots, RAG forecasting)
- Harness engineering practice (portfolio-derived domain notes)
- Speech synthesis detection, deep learning theory, philosophy of emergence

The `vault/MOCs/moc - Vault.md` organizes these by domain with wikilinks. Every note has claim-based titles, typed atomic claims with polarities, and inline wikilinks to related notes.

**The problem this spec solves:** Claude has access to the vault on disk but doesn't systematically use it during conversation. When the user asks about a topic covered in the vault, Claude should recognize the overlap and incorporate the relevant canonical knowledge into its response — with explicit citations to vault notes.

**Key design choice: agentic sift, not traditional RAG.** Traditional RAG chunks the corpus, embeds the chunks, retrieves top-K by vector similarity, and stuffs them into the prompt. That's the wrong model for this vault because:

1. Notes are already claim-structured and wiki-linked — the graph carries signal that embeddings flatten.
2. The vault is small (~55 notes, will grow to hundreds, not millions) — brute retrieval is overkill.
3. The user wants Claude to *reason* over the vault, not mechanically retrieve from it.

Instead: Claude decides when vault lookup is warranted, picks the right entry points (MOC traversal, grep by topic, or explore agent for broader sifts), reads the relevant notes in full, and weaves their claims into its response. The vault becomes an agentic capability, not a retrieval pipeline.

---

## Goals

1. **Recall on demand.** When the user asks about a topic covered in the vault, Claude uses vault content to ground its response and cites the source notes via wikilinks.
2. **Cross-reference.** When Claude ingests new content or discusses a new topic, it identifies how that relates to existing vault knowledge (supports, contradicts, extends).
3. **Transparency.** The user knows when Claude is drawing on vault knowledge vs. parametric knowledge. Citations are explicit.
4. **Graceful absence.** When the vault has nothing relevant, Claude says so and falls back to parametric reasoning cleanly.

## Non-Goals

1. Not building an embedding index. The vault is too small and too structured for brute vector retrieval to outperform targeted grep + LLM reading.
2. Not replacing the ingestion pipeline. This spec is about *using* the vault, not building it.
3. Not building a general chatbot interface. Vault augmentation is for knowledge work within Claude Code sessions.

---

## Architecture Overview

Three layers:

1. **Discovery** — Claude identifies relevant notes for a given topic or question. Entry points: the MOC, grep by keywords, or dispatching an Explore agent for broad sifts.
2. **Reading** — Claude reads the Key Takeaways and Claims sections of matched notes. Optionally reads the full Original Content callout for primary source quotes.
3. **Weaving** — Claude incorporates relevant claims into its response with explicit wikilink citations.

```
User query/topic
      ↓
[Discovery] → MOC section traversal OR grep vault/Sources OR Explore agent
      ↓
  matched notes (N ≤ 10 typically)
      ↓
[Reading] → read Key Takeaways + Claims sections
      ↓
  claim set with provenance
      ↓
[Weaving] → response with [[wikilink]] citations
```

---

## Interfaces

### Skill: `/mycelium-recall`

Explicit invocation: user asks for relevant vault context on a topic.

**Input:** topic description (free text).
**Behavior:**
1. Read `vault/MOCs/moc - Vault.md` to identify which domain sections are relevant.
2. For each relevant domain, read the linked notes' frontmatter and Key Takeaways.
3. For notes that appear highly relevant (based on description match), read the full Claims section.
4. Output: a structured context block with matched notes, their core claims, and suggested wikilink citations.

**Output format:**
```
Vault knowledge on [topic]:

**[[Note title 1]]** ([[topic-area]])
- Key insight: ...
- Relevant claims: ...

**[[Note title 2]]** ([[topic-area]])
- ...

Potential contradictions: ...
Related threads: [[note X]], [[note Y]]
```

### Behavioral hook (eventual): automatic recall

When the user raises a topic covered in the vault without explicitly invoking recall, Claude should proactively surface relevant vault knowledge. This is a CLAUDE.md behavioral rule, not a skill invocation.

**Heuristic for when to auto-recall:**
- The user asks a question in a domain with ≥2 notes in the MOC.
- The user proposes an approach that relates to a documented claim (support or contradiction).
- The user plans new work in a domain where vault notes inform the approach.

**When NOT to auto-recall:**
- Trivial questions (syntax, one-line fact lookups).
- The user explicitly says "don't pull from the vault right now."
- The topic is far outside vault coverage.

---

## Failure Modes

1. **False negatives (missed relevance).** Claude fails to recognize that a question overlaps with vault content and answers from parametric knowledge only. Mitigation: explicit `/mycelium-recall` skill for when the user wants to force a lookup.
2. **False positives (irrelevant recall).** Claude surfaces vault content that doesn't actually apply. Mitigation: relevance filtering by reading Key Takeaways before deciding to cite.
3. **Stale vault content.** The vault contains outdated claims that contradict current understanding. Mitigation: frontier will eventually flag stale areas; for now, Claude treats vault content as "what I knew then" and can note when current evidence updates it.
4. **Citation without reading.** Claude cites a note based on the title without actually reading it. Mitigation: the skill contract requires reading the Key Takeaways section before citing.
5. **Circular reference.** Vault note A cites B cites A cites B... Mitigation: Claude's context window limits depth automatically; explicit rule not to follow a citation chain past 2 hops without user direction.

---

## Acceptance Criteria

- AC-1: `/mycelium-recall "topic"` returns relevant notes with their core claims in under 30 seconds for a 55-note vault.
- AC-2: When relevant notes exist, the recall output includes at least one wikilink-formatted citation.
- AC-3: When no relevant notes exist, the recall output clearly says so without fabricating citations.
- AC-4: Claude cites vault notes using `[[exact title]]` syntax that resolves to actual files in `vault/Sources/`.
- AC-5: Recall does not read more than 10 full notes per invocation (keeps context manageable).
- AC-6: Cross-reference detection: if two retrieved notes have contradicting claims on the same topic, the recall output flags this explicitly.

---

## Open Questions

1. **Should recall include draft notes (`Inbox/Sources/`) or only canonical (`Sources/`)?** Default: canonical only, since drafts are pre-review and may contain errors.
2. **How aggressive should auto-recall be?** Err toward surfacing too little rather than too much. The user can always ask.
3. **Should recall operate on claim level or note level?** Note level for now; claim-level cross-referencing is the separate spec in `frontier-v2/` that depends on a claim index.
4. **Should there be a max-depth parameter for wikilink traversal?** Default: depth 1 (follow wikilinks from matched notes, but don't recurse further).

---

## Sub-Specs

- [`discovery.md`](discovery.md) — details on note matching and ranking (TBD)
- [`skill-contract.md`](skill-contract.md) — full input/output contract for `/mycelium-recall` (TBD)
- [`behavioral-rules.md`](behavioral-rules.md) — CLAUDE.md additions for auto-recall (TBD)

---

## Dependencies

- **Vault in canonical state.** All graduated notes in `vault/Sources/` with proper frontmatter and wikilinks. ✅ (as of 2026-04-12)
- **MOC kept current.** `vault/MOCs/moc - Vault.md` lists all canonical notes grouped by domain. ✅
- **Grep/read tooling.** Claude Code's Grep and Read tools operate over the vault. ✅
