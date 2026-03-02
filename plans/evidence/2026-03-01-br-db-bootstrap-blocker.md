# Blocker Catalog Entry

- component/source ID: `br-ready-default-db`
- blocker class: `env_block`
- blocked phase/workstep: Orchestrator bootstrap verification step (`br ready --json`)
- move-on decision: `proceed`
- linked bead IDs: `mycelium-1`, `mycelium-2`
- denominator/gate treatment: `excluded` (readiness gate deferred until blocker beads are resolved)
- next retry owner/time: `CaptainRusty`, `2026-03-01T20:30:00Z`

## Evidence

- Command: `br ready --json`
- Result: fails with "no beads database found" while `.beads/issues.jsonl` exists.
- Temporary workaround: use `br --no-db ready` in JSONL-only clones until runtime fix lands.
