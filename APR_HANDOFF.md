# APR Handoff (Mycelium)

> Update (2026-02-25): see `APR_STABILIZATION_FINDINGS_2026-02-25.md` for latest reproduction results and run guidance. Some statements below are historical and no longer reflect current stall behavior on `mycelium_spec` round 2.

## 1. Current Status

- Oracle + APR browser execution is working with real runs (not `--render`).
- Stable path is:
  - manual-login profile mode
  - cookie sync disabled
  - attach to existing Chrome DevTools target when available
  - model strategy `current` (uses whatever mode is already selected in the active ChatGPT tab)
- Full `mycelium_spec` round has not been successfully completed yet in this session.
- Toy workflows (`oracle_probe`, `toy_tiny`) succeeded and proved end-to-end GPT execution + file output.

## 2. Required Environment

These are already added to `~/.zshrc` for this machine:

```bash
export ORACLE_HOME_DIR="$HOME/Desktop/mycelium/.oracle-profile"
export ORACLE_BROWSER_PROFILE_DIR="$ORACLE_HOME_DIR/browser-profile"
export APR_ORACLE_FORCE_MANUAL_LOGIN=1
export APR_ORACLE_NO_COOKIE_SYNC=1
export APR_ORACLE_BROWSER_MODEL_STRATEGY=current
export APR_NO_ORACLE_PATCH=1
```

Helper function in `~/.zshrc`:

```bash
apr_oracle_attach_current
```

It reads `DevToolsActivePort` from Oracle’s profile and sets `APR_ORACLE_REMOTE_CHROME=127.0.0.1:<port>`.

## 3. APR Script Changes

Patched file: `tools/apr/apr`

Added/extended behavior:

- `APR_ORACLE_FORCE_MANUAL_LOGIN`
- `APR_ORACLE_NO_COOKIE_SYNC`
- `APR_ORACLE_BROWSER_MODEL_STRATEGY`
- `APR_ORACLE_REMOTE_CHROME`
- `APR_ORACLE_AUTO_REMOTE_CHROME` (default on)
- Auto-detect remote Chrome target from:
  - `DevToolsActivePort` in `ORACLE_BROWSER_PROFILE_DIR`
  - fallback process scan for `--remote-debugging-port`

This removes the need to manually pass remote target each run.

## 4. Proven Working Runs (Real GPT Browser Runs)

### Oracle probe outputs

- `.apr/rounds/oracle_probe/round_1.md`
- `.apr/rounds/oracle_probe/round_2.md`
- `.apr/rounds/oracle_probe/round_3.md`
- `.apr/rounds/oracle_probe/round_5.md`
- `.apr/rounds/oracle_probe/round_6.md`

Each contains: `ORACLE_APR_PROBE_OK`

### Toy tiny spec outputs

- `.apr/rounds/toy_tiny/round_1.md`
- `.apr/rounds/toy_tiny/round_2.md`
- `.apr/rounds/toy_tiny/round_3.md`
- `.apr/rounds/toy_tiny/round_4.md`

These contain real generated tiny specs.

## 5. Main Workflow to Continue

From repo root:

```bash
source ~/.zshrc
apr_oracle_attach_current || true
tools/apr/apr run 1 --workflow mycelium_spec --include-impl --wait --verbose --no-retry
```

Notes:

- Use `--no-retry` when debugging to reduce extra `about:blank` tabs.
- `modelStrategy=current` means the active ChatGPT tab mode is reused.
- If user wants a specific mode, set it in the active tab before run starts.

## 6. Known Failure Modes + Fixes

### A) Duplicate prompt guard

Symptom:
- Oracle says identical prompt session already running.

Fix:

```bash
ORACLE_HOME_DIR="$PWD/.oracle-profile" oracle session --all --clear
```

### B) Extra `about:blank` tabs

Cause:
- retries / aborted runs / fresh target creation.

Fix:
- run with `--no-retry` while stabilizing
- close `about:blank` tabs via DevTools endpoint if needed

### C) APR “Output file is suspiciously small (<2048 bytes)”

This is APR’s validator threshold and can be a false positive for intentionally short outputs.
The output file can still be valid; inspect file content directly.

### D) Intermittent `ECONNREFUSED` without remote attach

Fix:
- ensure `APR_ORACLE_REMOTE_CHROME` is set via `apr_oracle_attach_current`
- rerun using remote attach path

## 7. Recommendation for Parallel Agent Handoff

Yes, hand off to another agent now.

Minimum context they must receive:

1. This file (`APR_HANDOFF.md`)
2. `tools/apr/apr` includes local patches
3. `~/.zshrc` exports + helper function are required
4. Run command in section 5
5. If blocked, use section 6 recovery commands

## 8. Skill Recommendation

A dedicated APR skill is useful but not required to continue today.

If created later, include:

- env bootstrap checks
- remote attach detection
- stale session cleanup
- “real run” verification checklist (session status + output file + content sanity)
