---
created: 2026-04-11
description: Decomposing agent workflows into role-separated stages (scientist, implementer, verifier, maintainer) with explicit human-gated handoffs produces more auditable and reliable output than single-agent autonomy
source: portfolio-derived
status: canon
type: source
tags: [multi-agent, role-separation, human-in-the-loop, orchestration, original-concept]
---

## Key Takeaways

The Mycelium project's 4-agent workflow embodies a design principle that [[multi-agent coordination degrades performance on sequential tasks by 39 to 70 percent despite helping on parallelizable ones]] partially validates: the value of multi-agent systems depends on whether agents are working in parallel (coordination helps) or in sequence (coordination hurts). The role-separated pipeline is deliberately sequential — but each agent has a *different* capability constraint rather than multiple agents doing the same thing.

Scientist (read-only, planning): creates the Definition of Done and implementation plan without writing any code. This separation prevents the common failure mode of agents that start coding before understanding the problem. Implementer (write-capable): executes the plan, with the human doing this role in practice. Verifier (run-only): validates the implementation against the DoD using test execution and code inspection, without the ability to modify code — preventing the verifier from "fixing" issues and hiding them. Maintainer (refactor-only): cleanup and commit, explicitly prohibited from changing behavior.

The human gates at each handoff serve a dual purpose: quality control (the human can redirect if an agent went off track) and auditability (each transition is an explicit decision point with documented rationale). This is the antithesis of [[orchestrating 20 to 30 parallel coding agents requires Kubernetes-like infrastructure not just a better IDE]] — Gas Town optimizes for throughput with chaotic parallelism, while the role-separated pipeline optimizes for correctness with structured sequential handoffs. Both are valid for different contexts.

The key insight from practice: agents perform better when given narrow, well-defined roles with explicit constraints on what they *cannot* do. A verifier that can also edit code will edit code instead of reporting issues honestly. A scientist that can implement will skip planning and start coding. Constraints are features, not limitations.

## Claims

- **[causal]** Role separation with capability constraints (read-only scientist, run-only verifier, refactor-only maintainer) prevents agents from circumventing their designated function (supports)
- **[causal]** Human-gated handoffs between agent stages provide both quality control and auditability, creating documented decision points at each transition (supports)
- **[empirical]** Agents perform better with narrow, well-defined roles than with broad autonomous mandates because constraints prevent common failure modes like premature implementation or self-fixing verification (supports)
- **[causal]** A verifier that can also edit code will edit rather than report honestly, and a scientist that can implement will skip planning — capability constraints are features not limitations (supports)
- **[normative]** Role-separated sequential pipelines optimize for correctness in high-stakes work, while parallel agent swarms optimize for throughput in high-volume work — both are valid for different contexts (supports)

## External Resources

- [Mycelium AGENTS.md](portfolio-derived) — role separation rules in project configuration
- [Antigravity Crew](portfolio-derived) — earlier name for the 4-agent workflow pattern

## Original Content

> [!quote]- Source Material
> Role-Separated Agent Pipelines — domain knowledge from practice
>
> Developed through the Mycelium project's Antigravity Crew workflow: scientist (planning, read-only), implementer (execution, write-capable), verifier (validation, run-only), maintainer (cleanup, refactor-only). Each role has explicit capability constraints and human gates at handoffs.
>
> [Portfolio-derived knowledge]
