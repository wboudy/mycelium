# Handoff: Extended Pro Capture Failure (Round 2/3 Tiny Outputs)

Date: 2026-02-25
Primary repo context: `/Users/williamboudy/Desktop/mycelium`

## Executive Summary
`mycelium_spec` round runs in **GPT-5.2 Pro + Extended Pro** intermittently produce tiny output files (~241-242 bytes) containing only an interim preamble ("I'll rewrite/update...") instead of the full SPEC.

### Bottom line on ownership
- **Primary defect appears to be Oracle browser-capture/completion behavior** in Extended Pro mode.
- **APR has a secondary bug/UX gap**: it can continue to later rounds even when a round output is invalid/truncated (non-fatal flow with `rc=0`).

## Current State (files)
Path: `/Users/williamboudy/Desktop/mycelium/.apr/rounds/mycelium_spec/`

- `round_1.md` -> valid full output (33,461 bytes)
- `round_2.md` -> invalid tiny output (242 bytes)
- `round_3.md` -> invalid tiny output (241 bytes)
- `round_4.md` -> old full output (32,741 bytes)
- `round_5.md` -> timeout stub (46 bytes)

Tiny file contents prove preamble-only capture:
- `round_2.md`: "I’ll rewrite SPEC.md ..."
- `round_3.md`: "I’ll update SPEC.md ..."

## Repro Evidence
Session logs show Oracle accepted/saved the interim preamble as final answer:
- `/Users/williamboudy/Desktop/mycelium/.oracle-profile/sessions/apr-mycelium-spec-round-2-2/output.log`
- `/Users/williamboudy/Desktop/mycelium/.oracle-profile/sessions/apr-mycelium-spec-round-3/output.log`

Both logs include:
- `Answer:` followed by the short preamble sentence
- then `Saved assistant output to .../round_2.md` or `round_3.md`

Observed UI pattern during failures:
- ChatGPT tab shows `Stop streaming` for long periods.
- Final assistant turn often remains an interim/prelude string, not full document.
- In some stalled tabs, assistant turn was only "ChatGPT said: Pro thinking".

## Why we think it is mostly Oracle
Oracle completion/capture path seems to treat an interim assistant turn as complete under Extended Pro, then writes output before final body arrives (or despite stalled state).

Relevant Oracle internals checked locally:
- File: `/Users/williamboudy/.nvm/versions/node/v20.14.0/lib/node_modules/@steipete/oracle/dist/src/browser/actions/assistantResponse.js`
- Completion/capture logic: `waitForAssistantResponse`, `pollAssistantCompletion`, `parseAssistantEvaluationResult`, `normalizeAssistantSnapshot`.
- Existing APR patch already increased stability thresholds (minStableMs/settle windows/cycles), but issue persists.

## Why APR also needs a fix
APR currently treats truncated output as warning/recovery path but can still finish run and continue later rounds.

APR behavior observed:
- Marks output invalid (too small), tries recovery, recovery fails.
- Still returns overall round success path in loop context (allowed progress to next round in my batch loop).

APR location:
- `/Users/williamboudy/Desktop/mycelium/tools/apr/apr`

## Recommended Investigation Plan
1. Reproduce in Oracle directly (without APR loop) using browser mode + Extended Pro.
2. Instrument capture timing in `assistantResponse.js`:
   - log text length deltas, stop-button presence, completion markers, and turn IDs.
3. Harden capture acceptance criteria for Extended Pro:
   - reject obvious interim preamble-only answers (`/^I('|’)ll\s+(rewrite|update|refine|revise)/i`) as non-final,
   - require either finished action controls on latest assistant turn OR stronger post-stop stability for non-trivial output,
   - if captured text is tiny and matches preamble pattern, continue waiting instead of finalizing.
4. APR mitigation (independent of Oracle patch):
   - fail the round hard (non-zero) when output validation fails after recovery,
   - block auto-advance to next round when output invalid.

## Desktop Clone Guidance for New Agent
You can clone either/both repos under Desktop for isolated work:

```bash
cd ~/Desktop

# APR
git clone https://github.com/Dicklesworthstone/automated_plan_reviser_pro apr

# Oracle
git clone https://github.com/steipete/oracle oracle
```

Local APR copies already present:
- `/Users/williamboudy/Desktop/mycelium/tools/apr`
- `/Users/williamboudy/Desktop/apr`

## Useful Commands
### Validate current tiny outputs
```bash
cd /Users/williamboudy/Desktop/mycelium
wc -c .apr/rounds/mycelium_spec/round_{2,3}.md
cat .apr/rounds/mycelium_spec/round_2.md
cat .apr/rounds/mycelium_spec/round_3.md
```

### Inspect relevant Oracle logs
```bash
sed -n '1,160p' .oracle-profile/sessions/apr-mycelium-spec-round-2-2/output.log
sed -n '1,160p' .oracle-profile/sessions/apr-mycelium-spec-round-3/output.log
```

### Check active oracle browser processes
```bash
ps aux | rg -i 'node .*/oracle --engine browser' | rg -v rg
```

## Notes on Runtime State
`oracle status` may still list historical sessions as `running` even when no oracle process is active; trust `ps` for actual live runner checks.

## Proposed Ownership Split
- **Oracle agent**: fix completion/capture correctness for Extended Pro thinking flows.
- **APR agent**: enforce fail-fast on invalid outputs and prevent downstream round progression on broken artifacts.

