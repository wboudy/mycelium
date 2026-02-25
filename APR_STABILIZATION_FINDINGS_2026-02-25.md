# APR Execution Stabilization Findings (2026-02-25)

## Scope Split
- Mycelium repo is kept for workflow/config/context only.
- APR/tooling debugging is now prepared in `~/Desktop/apr` (fresh clone + local patch applied from `tools/apr/apr`).

## What Was Reproduced

1. `mycelium_spec` round 2 stalls with `--wait`.
- Command:
  - `tools/apr/apr run 2 --workflow mycelium_spec --include-impl --wait --verbose --no-retry`
- Behavior:
  - Oracle launches browser mode and sends prompt.
  - `oracle status` stays `running` with fixed `Chars=985`.
  - `.apr/rounds/mycelium_spec/round_2.md` remains old timeout stub unless run is manually interrupted.

2. Same stall reproduced with Oracle directly (no APR wrapper).
- Command (equivalent payload):
  - `oracle --engine browser -m gpt-5.2-pro --file TARGET_VISION.md --file CURRENT_STATE.md --file SPEC.md --browser-attachments never ...`
- Result:
  - Same `running` + fixed `Chars=985` state.
- Conclusion:
  - This is not APR orchestration logic; it reproduces in Oracle browser automation itself for this prompt/UI state.

3. Short direct probes succeed.
- Command:
  - `oracle --engine browser -m gpt-5.2-pro --remote-chrome 127.0.0.1:62151 --browser-model-strategy current -p "Reply with exactly OK."`
- Result:
  - Completes in ~7s and writes output.

4. Disabling remote-chrome fails in this environment.
- Command path:
  - `APR_ORACLE_AUTO_REMOTE_CHROME=0 APR_ORACLE_REMOTE_CHROME= tools/apr/apr run ...`
- Result:
  - `ERROR: connect ECONNREFUSED 127.0.0.1:55238`
- Implication:
  - Current profile/session setup effectively depends on remote-chrome reuse.

## Browser/DOM Evidence During Stall

- In the active tab, body text includes:
  - Full user prompt + inlined files.
  - `ChatGPT said:` + `Heavy thinking` + `ChatGPT is still generating a response...`.
- Oracle extractor returns empty assistant snapshot on the same tab:
  - `readAssistantSnapshot(Runtime)` => `len=0`.
- This strongly suggests a selector/extraction mismatch for this ChatGPT UI state, which prevents completion capture.

## Known Secondary Issue

- APR Oracle patch step uses `sed -i` syntax that is not macOS/BSD-sed portable.
- This explains the preflight sed warnings when `APR_NO_ORACLE_PATCH` is not set.

## Immediate Operator Guidance (Mycelium)

1. Keep using remote-chrome attach path for now.
- `source ~/.zshrc`
- `apr_oracle_attach_current || true`

2. If a run appears stuck (`oracle status` fixed chars for minutes):
- Check session state quickly:
  - `oracle status --hours 1`
- If needed, clear stale sessions before re-run:
  - `ORACLE_HOME_DIR="$PWD/.oracle-profile" oracle session --all --clear`

3. Keep APR patch disabled unless needed:
- `APR_NO_ORACLE_PATCH=1`

## Upstream Follow-Up (APR/Oracle tooling side)

1. Oracle assistant extraction/completion detection for heavy-thinking ChatGPT states where current selectors miss the assistant turn.
2. APR macOS-portable in-place edit helper (replace raw `sed -i` calls).
