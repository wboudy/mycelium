# Specs

Engineering specifications for major Mycelium components. These are the authoritative design documents — code in `src/mycelium/` is the implementation.

## Structure

One subdirectory per component, each with `main.md` as entry point:

```
specs/
  {component-name}/
    main.md              # entry point: purpose, architecture summary, sub-spec index
    {sub-spec}.md        # specific aspects (data contracts, algorithms, integrations)
    research/            # raw investigation outputs (source material, not polished)
```

## Current Specs

| Spec | Status | Description |
|------|--------|-------------|
| [`vault-augmented-reasoning/`](vault-augmented-reasoning/main.md) | Draft | Make the vault function as live context augmentation for Claude during conversation (not traditional RAG — agentic sift) |
| [`frontier-v2/`](frontier-v2/main.md) | Draft | Replace rule-based frontier scoring with Opus-reasoning over the vault knowledge graph |

## Relationship to Root Documents

- **`SPEC.md`** (root) — pipeline spec (capture → normalize → fingerprint → extract → compare → delta → propose_queue). Authoritative for the ingestion pipeline.
- **`CURRENT_STATE.md`** (root) — system overview and what's built.
- **`TARGET_VISION.md`** (root) — product vision and goals.
- **`ROADMAP.md`** (root) — development phases.
- **`AGENTS.md`** (root) — agent workflow rules.

The specs here extend these root documents with detailed designs for specific components. When a root document and a spec contradict, the **spec is authoritative for implementation**, the root document is authoritative for scope and priorities.

## Relationship to Code

Specs describe what to build. Code in `src/mycelium/` is the implementation. When implementation diverges from a spec, **update the spec to reflect reality** rather than letting them drift apart.

## Research Outputs

Each spec may have a `research/` subdirectory for raw outputs from deep research or design investigations. These are source material, not polished documents. Claims in `research/` files should be verified before entering the spec proper.

## Principle: Spec Is Code

Before executing, write the spec. This prevents:
- Coding agents making up interfaces that conflict with other components
- Scope creep ("while I was there, I also changed X...")
- Silent design drift between sessions

A good spec answers: what's the contract, what's the failure mode, what's the test that proves it works.
