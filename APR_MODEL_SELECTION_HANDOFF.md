# APR Model Persistence Handoff

## Objective
Ensure APR browser runs do NOT change ChatGPT model mode between rounds once user manually sets `Extended / Pro` in the already-open browser session.

## Primary Symptom
User reports APR run switches to `heavy thinking` instead of keeping their manually selected `Extended / Pro` mode.

## Environment
- Repo: `/Users/williamboudy/Desktop/mycelium`
- APR source (local clone): `/Users/williamboudy/Desktop/mycelium/tools/apr`
- Oracle CLI: `0.8.6`
- Active remote Chrome target observed: `127.0.0.1:62151`

## Current Local Changes Already Applied
### 1) APR script enhancements (`tools/apr/apr`)
- Round-aware templates added:
  - `template_round_N`
  - `template_with_impl_round_N`
- Browser persistence/config resolution added from workflow:
  - `keep_browser`
  - `browser_model_strategy`
  - `remote_chrome`
  - `browser_profile_dir`
- Remote Chrome autodetect helper added (`DevToolsActivePort` / process inspection).
- `run_round` and `robot_run` updated to pass these options to Oracle.

### 2) Workflow updates
- `mycelium_spec.yaml`, `toy_tiny.yaml`, `toy_spec.yaml` updated to:
  - `model: gpt-5.2-pro`
  - `keep_browser: true`
  - `browser_model_strategy: "current"`
  - `browser_profile_dir: "/Users/williamboudy/Desktop/mycelium/.oracle-profile"`
- Removed `thinking_time: heavy` from these updated workflows.

## Verified Behavior So Far
### Works
- Round-aware prompt selection works (`run 1` and `run 5` produce different prompt tasks).
- Browser persistence flags now appear in dry-run output for updated workflows.
- Real toy run produced output file:
  - `.apr/rounds/toy_tiny/round_5.md`

### Still Problematic
- User still observed mode drifting to heavy thinking in some runs.
- Oracle status for recent toy runs showed sessions labeled `gpt-5.2-thinking`.

## Important Log Evidence
1. Toy runs before workflow hardening used:
- `model: "5.2 Thinking"`
- `thinking_time: heavy`
This definitely nudged model behavior.

2. Even after remote-chrome pinning, Oracle output line showed:
- `Launching browser mode (gpt-5.2-thinking)`
for toy rounds that were still configured with `5.2 Thinking` + heavy.

3. APR preflight Oracle patch step is noisy/broken (separate issue):
- `sed: illiamboudy/...assistantResponse.js: No such file or directory`
- This is likely a path manipulation bug in APR’s `patch_oracle_stability_thresholds` and is unrelated to model switching, but worth fixing.

## Reproduction Commands
### A) Check current workflow config
```bash
sed -n '1,220p' .apr/workflows/mycelium_spec.yaml
sed -n '1,220p' .apr/workflows/toy_tiny.yaml
```

### B) Verify what APR will pass to Oracle
```bash
tools/apr/apr run 2 --workflow mycelium_spec --include-impl --dry-run --verbose
```
Expectations:
- includes `--browser-keep-browser`
- includes `--browser-model-strategy "current"`
- does NOT include `--browser-thinking-time heavy`

### C) Force reuse of already-open browser target (diagnostic)
```bash
APR_ORACLE_REMOTE_CHROME=127.0.0.1:62151 \
APR_ORACLE_AUTO_REMOTE_CHROME=0 \
APR_ORACLE_BROWSER_MODEL_STRATEGY=current \
tools/apr/apr run 3 --workflow mycelium_spec --include-impl --wait --verbose --no-retry
```

## Suggested Investigation Plan (for fresh agent)
1. Run controlled A/B with same remote Chrome target:
- Variant 1: `--browser-model-strategy current`
- Variant 2: `--browser-model-strategy ignore`
Compare if mode still changes.

2. Validate whether Oracle model string itself causes switching even with `current`:
- Test workflow `model: gpt-5.2-pro`
- Test workflow `model: 5.2 Thinking`
- Test whether omitting `-m` in Oracle call is possible/safer for preserving current UI model.

3. Confirm if Oracle’s status label (`gpt-5.2-thinking`) reflects:
- requested target model, or
- actual final selected UI model.
(Need direct browser observation plus Oracle logs.)

4. Inspect Oracle upstream behavior for browser model picker logic:
- How `current` interacts with provided `-m` value.
- Whether `current` still normalizes to thinking mode under some conditions.

5. Consider a workflow-level strict mode option:
- `preserve_current_model: true` -> APR passes `--browser-model-strategy ignore` and avoids model/think-time forcing.

## Upstream Context
- APR upstream (`origin/main`) currently has no round-aware template feature or workflow-level browser persistence keys.
- This local branch includes those patches only.

## Success Criteria
1. User sets `Extended / Pro` once in the active browser session.
2. APR round N+1 executes without model mode changing.
3. APR rounds 2..5 run unattended with stable mode.
4. Round outputs are written normally in `.apr/rounds/<workflow>/`.
