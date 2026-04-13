# Handoff: APR Execution Stabilization (Feb 25, 2026)

## Current Status
- No toy Oracle run is currently active.
- Progressive prompt selection check was completed using `toy_tiny_progressive`:
  - Round-specific prompt markers validated: `R1`, `R2`, `R3`.
  - Workflow is configured for `thinking_time: "extended"` (Standard was briefly used then corrected).
- Ready to proceed to `mycelium_spec` runs.

## What Was Updated

### 1) Shell override defaults fixed (no forced manual login globally)
- File: `~/.zshrc`
- Defaults now:
  - `APR_ORACLE_FORCE_MANUAL_LOGIN=0`
  - `APR_ORACLE_NO_COOKIE_SYNC=0`
  - `APR_ORACLE_BROWSER_MODEL_STRATEGY=select`
  - `APR_NO_ORACLE_PATCH` unset
- Added toggles:
  - `apr_oracle_auth_mode_on`
  - `apr_oracle_auth_mode_off`
- Existing helper retained:
  - `apr_oracle_attach_current`

### 2) APR script patched (Mycelium copy + separate APR clone)
- Files:
  - `/Users/williamboudy/Desktop/mycelium/tools/apr/apr`
  - `/Users/williamboudy/Desktop/apr/apr`
- Changes made:
  - Cross-platform `sed -i` handling (macOS/BSD vs GNU).
  - Oracle 0.8.6 `assistantResponse.js` pattern support in stability patcher.
  - Added automatic remote tab pruning support:
    - env: `APR_ORACLE_PRUNE_TABS`
    - workflow key: `oracle.prune_tabs`
    - prunes stale `about:blank` and root `https://chatgpt.com` pages pre-run.
  - Reduced false-positive output truncation threshold:
    - `MIN_OUTPUT_SIZE_BYTES` from `2048` to `768`.
  - Fixed `set -u` edge case by renaming `command` local var to `subcommand` in main dispatch.

### 3) Workflow config updates
- `/Users/williamboudy/Desktop/mycelium/.apr/workflows/mycelium_spec.yaml`
  - `model: gpt-5.2-pro`
  - `keep_browser: true`
  - `prune_tabs: true`
  - `browser_model_strategy: "select"`
  - `thinking_time: "extended"`
  - `browser_profile_dir: /Users/williamboudy/Desktop/mycelium/.oracle-profile`
  - includes progressive prompts: `template_round_1` ... `template_round_5`
- `/Users/williamboudy/Desktop/mycelium/.apr/workflows/toy_tiny.yaml`
  - `prune_tabs: true`
  - `thinking_time: "extended"`
  - still uses single `template` (same prompt each round)

### 4) Local Oracle install patched for current ChatGPT model-picker UI
- File (global npm install, local machine only):
  - `/Users/williamboudy/.nvm/versions/node/v20.14.0/lib/node_modules/@steipete/oracle/dist/src/browser/actions/modelSelection.js`
- Added/adjusted behavior:
  - better matching for Pro-family options in newer UI states.
  - fallback menu scanning.
  - `switched-best-effort` status when click confidence is high but top-left label does not change.

## What Has Been Validated
- Direct Oracle browser run with `select + extended` succeeds and returns expected output.
- APR toy run with `select + extended` succeeded (`round_9` completed, real output written).
- Auto tab pruning executes in APR run path (visible in verbose logs).

## Remaining Risk / Notes
- Pro/Extended runs can legitimately take 15-60 minutes.
- Oracle status metadata can become stale after aborted runs; duplicate-prompt guard may require session cleanup.
- Local Oracle patch (`modelSelection.js`) is not upstream and can be overwritten by Oracle reinstall/update.

## Next Agent Runbook (after toy round 10 completes)
1. `source ~/.zshrc`
2. `cd /Users/williamboudy/Desktop/mycelium`
3. `apr_oracle_attach_current`
4. Start with a mycelium round:
   - `tools/apr/apr run 5 --workflow mycelium_spec --include-impl --wait --verbose --no-retry`
   - or next round if you do not want to overwrite: `tools/apr/apr run 6 --workflow mycelium_spec --include-impl --wait --verbose --no-retry`
5. Verify output is non-timeout and contains substantive model content.

## If You Need to Prune Tabs Manually
- Safe prune target class is now automated in APR.
- Manual fallback (same criteria): close only `about:blank` and root `https://chatgpt.com` tabs, keep `https://chatgpt.com/c/...` conversation tabs.

## Commit / Sharing Guidance
- If another agent is running in this exact same local workspace and paths, they can use changes immediately without commit.
- If another agent uses a separate clone/worktree or another machine, you must commit/push repo changes and separately transfer local-machine changes:
  - `~/.zshrc` edits
  - Oracle global install patch (`modelSelection.js`)
- Recommended for reproducibility:
  - Commit Mycelium repo changes (workflow + `tools/apr/apr`) to `apr-spec`.
  - Commit APR clone changes in `~/Desktop/apr` on a branch or export a patch.
  - Keep a patch file for local Oracle install edits.
