# Frontier V2 — Opus-Reasoning Over the Vault Graph

**Status:** Draft
**Date:** 2026-04-12
**Goal:** Replace the rule-based frontier scoring engine (`src/mycelium/commands/frontier.py`) with an Opus-powered reasoning system that identifies knowledge gaps, contradictions, and high-value reading targets through LLM analysis of the vault graph.
**Related tasks:** #11 (redesign), #12 (claim cross-referencing)
**Prereq:** [`vault-augmented-reasoning/`](../vault-augmented-reasoning/main.md) — frontier is a specific query pattern on top of vault augmentation.

---

## Context

The current frontier implementation (`src/mycelium/commands/frontier.py`) is a deterministic weighted scoring engine:

```
score = 100 * (0.35 * conflict_factor
             + 0.25 * support_gap
             + 0.20 * goal_relevance
             + 0.10 * novelty
             + 0.10 * staleness)
```

It's arithmetic over metadata — count contradictions, count support, check timestamps, compute weighted sum. The `execute_frontier` function currently returns empty lists because vault queries to populate `TargetData` aren't wired in.

**The problem:** a rule-based score can rank existing targets but cannot *reason* about why something is worth reading. It can tell you note X has 3 contradictions and was last reviewed 50 days ago, but it cannot tell you *what* the contradictions are, *why* they matter, or *what specific resources* would resolve them.

The frontier is fundamentally a reasoning task: given a user's knowledge graph, identify the places where understanding is thin, conflicted, or stale — and recommend what to explore next, with reasoning grounded in the actual content of the notes.

**Key design choice: Opus reasons over the graph, the scoring engine becomes optional sub-component.** The reasoning system reads the MOC, samples notes, identifies patterns, and produces recommendations. The deterministic scoring can still be used as one signal among many, but the primary engine is LLM analysis.

---

## Goals

1. **Identify gaps.** Domains in the vault with thin evidence (few claims, few sources) where more reading would materially improve understanding.
2. **Surface contradictions.** Claims across notes that conflict with each other, with an analysis of whether they're resolvable or represent genuine open questions.
3. **Detect staleness.** Topics where recent external developments likely supersede vault claims, even if the vault hasn't been updated.
4. **Recommend concretely.** Output specific reading targets — either existing vault notes to re-read, or external resources (URLs, papers, people to follow) that would address identified gaps.
5. **Prioritize by user context.** Weight recommendations by the user's current projects and interests (from memory + CLAUDE.md).

## Non-Goals

1. Not replacing the scoring engine entirely. Deterministic scores are useful as one signal for the reasoning layer.
2. Not automating the reading itself. Frontier recommends; the user decides what to pursue.
3. Not generating new knowledge. Frontier identifies gaps; filling them requires ingestion.

---

## Architecture Overview

```
[Trigger] → user invokes /mycelium-frontier or scheduled review
      ↓
[Graph Summary] → read MOC + sample claims across all domains
      ↓
[Analysis] → Opus reasons about gaps, contradictions, stale areas
      ↓
[Scoring Signal] → optional: rule-based factors (conflict_count, staleness_days)
      ↓
[Recommendations] → ranked reading targets with rationale + citations
      ↓
[Persistence] → frontier report written to vault/Reports/Frontier/
```

Stages:

1. **Graph summary.** Read the MOC to understand domain coverage. For each domain, sample representative note titles and key claims. Build a compact graph summary that fits in Opus's context.
2. **Analysis.** Opus examines the summary looking for: domains with ≤N notes (thin coverage), conflicting claims (text-level contradictions), claims without recent support (stale), interesting cross-domain connections (e.g., two unrelated domains converging on the same idea).
3. **Scoring signal.** The deterministic scoring from frontier.py still runs in parallel and provides quantitative signals (exact conflict counts, review dates). Opus incorporates these into its analysis.
4. **Recommendations.** Opus produces a ranked list of reading targets with: what to read, why it matters to this user's knowledge graph, what gap it fills, estimated effort (paper, blog, book).
5. **Persistence.** The report is written to `vault/Reports/Frontier/YYYY-MM-DD.md` as a dated artifact the user can reference later.

---

## Interfaces

### Skill: `/mycelium-frontier`

**Input (optional):**
- `project`: focus recommendations on a specific project context (e.g., "pizza_at_the_pentagon" or "mycelium")
- `domain`: limit analysis to one vault domain (e.g., "Reinforcement Learning")
- `limit`: max number of recommendations (default 10)

**Behavior:**
1. Read `vault/MOCs/moc - Vault.md`.
2. For each domain, read 3-5 representative notes' Key Takeaways and Claims sections.
3. Run deterministic scoring in parallel (optional) for quantitative signals.
4. Opus analyzes the combined input, produces a ranked list of reading targets.
5. Write report to `vault/Reports/Frontier/YYYY-MM-DD.md`.
6. Return a summary to the user with the top N recommendations.

**Output format:**
```markdown
# Frontier Report — 2026-04-12

## Top Recommendations

### 1. [Priority: HIGH] Read more on process reward models vs outcome rewards
**Gap:** The vault has 3 notes on outcome-based RL (DeepSeek-R1, Atari DQN, A3C) but only 1 on PRMs (Lightman et al.).
**Why it matters:** Your forecasting project uses judge models, which are essentially PRMs. The single PRM note is light on training details.
**Suggested sources:** PRM800K dataset paper, Rewarding Progress (Setlur et al. 2025), R-PRM (Luo et al. 2025).
**Citations:** [[pure reinforcement learning without human demonstrations...]], [[process reward models that verify each reasoning step...]]

### 2. [Priority: MEDIUM] Resolve contradiction on multi-agent coordination
**Contradiction:** [[Gato]] claims one architecture works for all modalities; [[modality-specific experts]] claims dedicated components are needed for time series.
**Analysis:** These are not directly contradictory — Gato is about breadth across domains, modality-specific experts is about depth within time series. But the reconciliation is not documented.
**Suggested resolution:** Write a concept note explaining the breadth-vs-depth tradeoff in multimodal architectures.

...
```

---

## Failure Modes

1. **Hallucinated gaps.** Opus invents a gap that doesn't actually exist in the vault. Mitigation: require every claim in the report to cite specific notes by title; those titles must resolve to real files.
2. **Biased by sample size.** Opus sees 3 RL notes and 1 PRM note, concludes PRM is under-covered, but actually the user genuinely cares more about RL. Mitigation: user project/interest context is input to the analysis, not inferred from vault proportions.
3. **Too generic recommendations.** "Read more on X" without specifics. Mitigation: require every recommendation to propose specific resources (papers, URLs, people) by name.
4. **Recommendations drift over time.** Same gaps flagged repeatedly even after they're addressed. Mitigation: frontier reports are dated; each report can reference the previous one to track progress.
5. **LLM context limit.** Vault grows beyond what fits in Opus's context window. Mitigation: frontier analyzes domains sequentially, aggregating at the end; MOC is always loaded, full notes are sampled not exhaustive.

---

## Acceptance Criteria

- AC-1: `/mycelium-frontier` completes within 5 minutes for a 55-note vault.
- AC-2: Every recommendation in the report cites specific vault notes by title, and those titles resolve to files in `vault/Sources/`.
- AC-3: Every recommendation includes: what to read, why it matters, and suggested external resources.
- AC-4: Contradiction detection correctly identifies ≥1 real contradiction when the vault contains known contradictory claims.
- AC-5: Reports are persisted to `vault/Reports/Frontier/YYYY-MM-DD.md` and reference prior reports when applicable.
- AC-6: User-provided `project` context measurably changes the ranking of recommendations.

---

## Open Questions

1. **Should frontier propose specific ingestion candidates?** E.g., "read this arXiv paper: 2501.12948." Yes, but only if Opus has verifiable source info. Avoid fabricating arXiv IDs.
2. **Should the deterministic scorer be removed entirely or kept as a signal?** Keep as optional signal. The math is cheap and provides quantitative backup for qualitative analysis.
3. **How often should frontier run?** Manual for now. Eventual: after every batch ingestion (5+ new notes) and/or weekly scheduled review.
4. **Should frontier update the MOC with annotations?** E.g., marking domains as "under-explored" or "stale." Not in v1 — keep frontier output separate from the MOC to avoid polluting the canonical index.

---

## Dependencies

- **Vault-augmented reasoning (prereq).** Frontier uses the same discovery and reading patterns. See [`../vault-augmented-reasoning/main.md`](../vault-augmented-reasoning/main.md).
- **Claim-level cross-referencing (optional enhancement).** For more precise contradiction detection. See task #12 — if implemented first, frontier can reason over claim pairs directly.
- **MOC kept current.** Frontier's graph summary step starts at the MOC.

---

## Sub-Specs

- [`analysis-prompt.md`](analysis-prompt.md) — the prompt template for Opus's frontier analysis (TBD)
- [`report-format.md`](report-format.md) — full schema for frontier report markdown files (TBD)
- [`scheduling.md`](scheduling.md) — when/how frontier should run automatically (TBD)
