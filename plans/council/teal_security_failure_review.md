# TealPeak Council Review: Security, Privacy, Egress, and Failure Recovery

Date: 2026-03-01  
Reviewer: TealPeak (Security + Failure Modes Auditor)

## Scope and Method
Primary spec reviewed in full:
- `mycelium-apr-spec/docs/plans/mycelium_refactor_plan_apr_round5.md`

Repository evidence reviewed:
- `mycelium-apr-spec/src/mycelium/llm.py`
- `mycelium-apr-spec/src/mycelium/mcp/server.py`
- `mycelium-apr-spec/src/mycelium/orchestrator.py`
- `mycelium-apr-spec/src/mycelium/tools.py`
- `mycelium-apr-spec/src/mycelium/cli.py`
- `mycelium-apr-spec/tests/test_llm.py`
- `mycelium-apr-spec/tests/test_mcp.py`
- `mycelium-apr-spec/tests/test_orchestrator.py`
- `mycelium-apr-spec/tests/test_cli.py`
- `mycelium-apr-spec/tests/test_tools.py`

Comparison references used to resolve policy gaps:
- `mycelium-apr-spec/SPEC.round5.md`
- `mycelium-apr-spec/SPEC.md`
- `mycelium-apr-spec/SPEC.orchestrator-handoff.md`

Key audit conclusion:
- The Round 5 refactor plan has solid high-level requirements for security/failure, but leaves critical defaults and threat controls unresolved (notably TODO-Q-SEC-1).
- Current implementation in `src/mycelium` does not implement the vault ingestion/promotion security model yet; most security/failure controls in the refactor spec are **missing in code**.

---

## 1. Requirement Traceability (Security + Failure)

| Requirement | Spec Evidence | Repo Evidence | Status | Gap / Decision Needed |
|---|---|---|---|---|
| AUD-001 append-only audit logs for ingest/promotion | `docs/plans/mycelium_refactor_plan_apr_round5.md:607-620` | No audit event schema/writer in `src/mycelium/*`; `save_progress` rewrites YAML in place (`src/mycelium/orchestrator.py:98-113`); search for required audit events returned no matches (`rg ... ingest_started|egress_blocked ... -> NO_MATCHES`) | Missing | Define audit subsystem now; cannot defer to MVP2 if promotion decisions rely on attributable audit.
| SEC-001 egress policy (allowlist/blocklist + sanitization) | `...round5.md:623-627` | No allowlist/blocklist/redaction code in `src`/`tests` (`rg ... allowlist|blocklist|redact|ERR_EGRESS_POLICY_BLOCK -> NO_MATCHES`); outbound call happens directly in `llm.complete` (`src/mycelium/llm.py:319`) | Missing | TODO-Q-SEC-1 must be resolved into concrete defaults and enforcement points.
| SEC-002 log what was sent (or digest) and why | `...round5.md:629-633` | No payload digesting, reason capture, destination logging around LLM egress (`src/mycelium/llm.py`, `src/mycelium/orchestrator.py`) | Missing | Add canonical egress event schema and mandatory reason fields before enabling external send paths for vault data.
| ERR-001 stage-scoped recoverable failures | `...round5.md:639-643` | Current runtime errors are generic strings without stage+deterministic code (`src/mycelium/orchestrator.py:489-493`, `579-582`); no pipeline stages implemented for vault ingest | Missing | Introduce typed error model (`code`, `stage`, `retryable`) at command boundary before pipeline build-out.
| ERR-002 quarantine partial/invalid artifacts | `...round5.md:646-650` | No quarantine subsystem/sidecar diagnostics in code; no fixtures for quarantine behavior under current tests | Missing | Define quarantine path contract and atomic movement semantics now; this is required for safe failure recovery.
| INV-002 / VLT-001 no canon writes without promotion | `...round5.md:63-69`, `110-114` | Existing `write_file` can write arbitrary filesystem paths if approval checks pass (`src/mycelium/mcp/server.py:352-397`); no canonical boundary enforcement | Missing | Add path policy guardrails independent of HITL; approval is not equivalent to scope control.
| PIPE-002 no partial canonical writes on failure | `...round5.md:531-535` | No draft staging transaction model exists in code; direct file writes used (`src/mycelium/mcp/server.py:391`) | Missing | Stage + atomic rename/quarantine workflow required; direct writes violate intended safety model.
| Failure tolerance primitives (partial) | Spec expects recoverability and retries (`...round5.md:639-643`) | LLM retries/backoff exist (`src/mycelium/llm.py:288-408`), command timeout exists (`src/mycelium/mcp/server.py:457-462`), CLI circuit breakers exist (`src/mycelium/cli.py:272-286`) | Partial | Keep these primitives, but they are generic orchestrator controls and do not satisfy vault pipeline recovery requirements.
| Fail-closed approval gate for unreadable agent state (partial positive) | Related to safe control behavior | `_requires_approval` fails closed when `current_agent` unreadable (`src/mycelium/mcp/server.py:100-107`); tests validate this (`tests/test_mcp.py:423-440`, `528-543`) | Partial (good) | Preserve this behavior; extend fail-closed semantics to egress policy and path ambiguity.

---

## 2. Cross-Plan Conflict Resolution

### Conflict A: TODO-Q-SEC-1 unresolved in refactor plan, but concrete defaults already exist elsewhere
- Refactor plan leaves default path policy/redaction undefined (`...round5.md:635`, `788`).
- Prior spec already defines baseline defaults:
  - Allowlist: `/Inbox/Sources/`, `/Inbox/ReviewQueue/`, `/Reports/Delta/`, explicit canonical opt-in (`SPEC.round5.md:436-442`).
  - Blocklist: `/Logs/Audit/`, credential patterns, wildcard vault export blocked (`SPEC.round5.md:443-447`).
- Decision: adopt prior defaults as baseline, then harden with path canonicalization, symlink checks, and explicit policy precedence (defined below).

### Conflict B: Threat model present in `SPEC.round5.md`, absent in refactor plan
- Threats THR-001..THR-005 and tamper-evident logging are explicitly defined in `SPEC.round5.md:452-460`.
- Refactor plan security section lacks explicit threat table and no tamper-evidence requirement.
- Decision: reintroduce threat model section into refactor plan before implementation freeze; include audit tamper detection as MUST.

### Conflict C: Current runtime allows broad command/file operations
- `run_command` executes with `shell=True` (`src/mycelium/mcp/server.py:442-444`) and only gates by HITL state.
- `write_file` has no canonical/draft scope restriction (`src/mycelium/mcp/server.py:385-397`).
- Decision: enforce policy scope controls at tool layer even when HITL approved; HITL and policy are separate controls.

---

## 3. Threat-Model and Auditability Gaps

1. **Egress policy has no default deny implementation path.**
- There is no policy engine in `src/mycelium` and no rejection code `ERR_EGRESS_POLICY_BLOCK` in code/tests.

2. **No provenance for outbound payload decisions.**
- Outbound LLM calls do not capture why content is sent, what file set was included, or payload digest.

3. **No tamper-evident audit chain.**
- Existing persisted runtime state is YAML rewrite (`orchestrator.save_progress`), not append-only event log.

4. **Path boundary is not enforced by filesystem policy.**
- `write_file` and `run_command` can target arbitrary paths once approval is granted; this violates intended vault scope control.

5. **Command injection blast radius is broad by default.**
- `subprocess.run(..., shell=True)` with unrestricted command text is high-risk in tool-call loops.

6. **Failure recovery is under-specified operationally.**
- Spec says recoverable/stage-scoped, but no concrete retry class matrix, no stage journal schema, no rollback checkpoint protocol.

7. **Redaction failure behavior is unspecified.**
- No fail-closed rule when sanitization fails; this is a critical exfiltration risk.

---

## 4. Concrete Decisions for TODO-Q-SEC-1 (and Related TODOs)

## 4.1 Decision Set: Default Egress Policy (TODO-Q-SEC-1 / TODO-Q5)

Adopt policy `egress_policy.v1` with **default deny** outside explicit allow scopes.

### 4.1.1 Allowlist (default)
- `Inbox/Sources/**`
- `Inbox/ReviewQueue/**`
- `Reports/Delta/**`
- `Logs/Audit/**` is **not egressable** (see blocklist)
- Canonical note paths (`Sources/**`, `Claims/**`, `Concepts/**`, `Questions/**`, `Projects/**`, `MOCs/**`) require explicit per-request opt-in:
  - explicit file list (no directory wildcards)
  - user reason string
  - audit event `egress_attempted` with `canon_opt_in=true`

### 4.1.2 Blocklist (default)
- `Logs/Audit/**`
- `Quarantine/**`
- `Indexes/**`
- `.git/**`
- `**/.env*`
- `**/*.{pem,key,p12,pfx,der,crt,csr,kdbx}`
- `**/id_rsa*`, `**/id_ed25519*`
- `**/secrets/**`, `**/credentials/**`
- Full-vault wildcard exports (`**/*`) unless explicit elevated override is present and logged.

### 4.1.3 Path normalization and traversal controls
- Resolve real path before policy evaluation.
- Reject any path outside vault root.
- Reject symlink escapes.
- Evaluate policy on normalized vault-relative path only.

## 4.2 Decision Set: Sanitization/Redaction Policy (TODO-Q-SEC-1)

### 4.2.1 Always-on redaction before external send
Redact values matching case-insensitive keys/patterns:
- `token`, `secret`, `password`, `api_key`, `authorization`, `cookie`, `session`, `private_key`
- Bearer/Basic auth headers and URI credential segments
- High-confidence secret regexes (provider keys, JWT-like, PEM headers)

### 4.2.2 Metadata minimization
- Strip absolute home paths to `<HOME>` outside vault.
- Strip local machine identifiers unless explicitly required.

### 4.2.3 Failure mode
- If redaction fails, **block egress** and emit:
  - `event_type=egress_blocked`
  - `details.error_class=redaction_failed`
  - `retryable=false`

## 4.3 Decision Set: Egress Audit Event Contract (SEC-002)

For every external send attempt, require append-only event fields:
- `event_id`, `timestamp`, `actor`, `run_id`, `event_type`
- `destination` (provider/model)
- `reason` (command + user context)
- `source_paths` (normalized)
- `payload_sha256`
- `bytes_sent`
- `redaction_applied` (bool)
- `redaction_summary` (counts/categories)
- `policy_version`
- `decision` (`allowed`/`blocked`)

Policy: store digest + path list by default; raw payload archival only behind explicit debug flag and local encryption requirement.

## 4.4 Related TODO Decisions

### TODO-Q2 (provenance locator minimum granularity)
Decision:
- URL: include section heading + paragraph index + snippet hash.
- PDF: include page number + block index + snippet hash.
- DOI/arXiv text: include section heading + paragraph index + snippet hash.
Rationale: supports forensic traceability without full source export.

### TODO-Q4 (authoritative review UX and approval recording)
Decision:
- CLI remains source-of-truth for promotion approval records.
- Obsidian/plugin UX is allowed only as frontend to same approval API.
- Every approval writes an immutable record: actor, queue_id, target hash, timestamp, reason.

### TODO-Q1 (ID strategy, security-relevant collision handling)
Decision:
- Use slug+hash hybrid IDs for canonical notes (`<slug>--h-<8-12hex>`).
- Keep human readability while reducing collision and spoofing risk.

---

## 5. Remediation Plan (Dependency-Ordered)

## 5.1 Milestone S0: Spec Closure (must happen first)

### T-S0-1 (Owner: Security Architect)
- Update `mycelium_refactor_plan_apr_round5.md` to include concrete egress default policy and redaction rules from Section 4.
- Done when TODO-Q-SEC-1/TODO-Q5 are removed and replaced by normative text + ACs.

### T-S0-2 (Owner: Security Architect)
- Add threat-model table (THR-001 style) and policy precedence/fail-closed rules.
- Done when each threat has mitigation + testable AC.

### T-S0-3 (Owner: Platform Architect)
- Add explicit egress/audit event schemas and deterministic error code catalog (`ERR_EGRESS_POLICY_BLOCK`, `ERR_REDACTION_FAILED`, etc.).
- Done when IF-001 envelope references these codes and tests are specified.

## 5.2 Milestone S1: Control Plane Implementation

### T-S1-1 (Owner: Backend Engineer)
- Add `src/mycelium/security/policy.py` for path normalization + allow/block evaluation.
- Depends on T-S0-1.

### T-S1-2 (Owner: Backend Engineer)
- Add `src/mycelium/security/redaction.py` for always-on sanitization pipeline.
- Depends on T-S0-1.

### T-S1-3 (Owner: Backend Engineer)
- Add `src/mycelium/security/audit.py` for append-only JSONL writer with hash-chain support.
- Depends on T-S0-3.

### T-S1-4 (Owner: Orchestrator Engineer)
- Integrate egress gate before any external model call (entry point around `llm.complete` call path).
- Depends on T-S1-1/T-S1-2/T-S1-3.

### T-S1-5 (Owner: MCP Engineer)
- Enforce path scope policy in `write_file`/`read_file`/`run_command` wrappers; require mission context or explicit non-mission policy token.
- Depends on T-S1-1.

### T-S1-6 (Owner: Pipeline Engineer)
- Implement quarantine sidecar contract and staged write model for vault pipeline artifacts.
- Depends on T-S0-2/T-S0-3.

## 5.3 Milestone S2: Verification and Gating

### T-S2-1 (Owner: Test Engineer)
- Add unit tests for policy matching, redaction, path traversal/symlink escape handling.

### T-S2-2 (Owner: Test Engineer)
- Add integration tests for blocked egress, redaction failure fail-closed, audit event emission.

### T-S2-3 (Owner: Release Engineer)
- Add CI gate: any security regression blocks release candidate.

Parallelization:
- `T-S1-1`, `T-S1-2`, `T-S1-3` can run in parallel after S0.
- `T-S2-1` can start once module contracts stabilize; `T-S2-2` waits for S1 integration.

---

## 6. Verification Matrix (Concrete)

| Command | Purpose | Expected Output | Artifact |
|---|---|---|---|
| `PYTHONPATH=src pytest -q tests/test_llm.py tests/test_mcp.py tests/test_orchestrator.py` | Baseline regression check | Pass on existing tests; confirms retry/HITL behavior remains stable | CI logs |
| `PYTHONPATH=src pytest -q tests/security/test_egress_policy.py` | Validate allow/block defaults and traversal rejection | Blocked paths return `ERR_EGRESS_POLICY_BLOCK`; allowlisted paths pass | `tests/security/test_egress_policy.py` results |
| `PYTHONPATH=src pytest -q tests/security/test_redaction.py` | Validate redaction coverage and failure behavior | Sensitive tokens redacted; redaction failure blocks send | `tests/security/test_redaction.py` results |
| `PYTHONPATH=src pytest -q tests/security/test_audit_events.py` | Validate append-only + required fields | Event schema complete; hash-chain/tamper checks pass | `Logs/Audit/*.jsonl` test fixtures |
| `PYTHONPATH=src pytest -q tests/integration/test_quarantine_recovery.py` | Validate failure recovery and quarantine sidecars | Failed stage yields quarantine artifact + diagnostic; no canonical mutation | `Quarantine/<run_id>/` fixture outputs |

Current state note:
- Security-specific test files above do not yet exist and must be added.

---

## 7. Risk Register, Mitigations, and Rollback

| Risk | Impact | Mitigation | Rollback |
|---|---|---|---|
| Over-blocking policy disrupts workflows | Medium | Introduce `report-only` policy mode first; compare block logs for one release | Toggle `policy_mode=report-only` while retaining audit logging |
| Under-redaction leaks sensitive data | High | Fail-closed on sanitizer errors; add regression fixtures for known secret patterns | Disable external egress route except local provider until fixed |
| Audit performance overhead | Medium | Buffered append writer with bounded flush intervals | Fallback to synchronous append-only path with reduced throughput |
| Policy bypass via symlink/path tricks | High | Normalize real paths and reject out-of-root or unresolved symlink policies | Temporary hard-disable egress for suspicious path patterns |
| Shell command abuse via MCP tooling | High | Enforce mission-scoped policy and command allowlist modes; require explicit approvals | Disable `run_command` tool for non-maintainer roles via config |

---

## 8. Final Council Position

1. The Round 5 refactor plan is directionally strong but not security-complete until TODO-Q-SEC-1 is concretized and threat/audit requirements are upgraded from implicit to explicit controls.
2. Existing `src/mycelium` runtime has useful reliability primitives (retry/backoff, timeout, fail-closed unreadable HITL state), but does not implement the required vault egress/audit/quarantine model.
3. Proceed only with a security-first ordering: **spec closure (S0) -> control implementation (S1) -> security gating (S2)**.

