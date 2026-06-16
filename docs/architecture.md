# Architecture Overview

This repository is evolving from a backend-only Claude Agent SDK sample into an Azure Well-Architected Review Agent accelerator on Microsoft Foundry. The design target is a production lifecycle that can grow from Build and Host into Observe, Evaluate, Control, Optimize, and ROI.

The current implementation covers Part A, the harness layer that lets a Claude Agent SDK application run as a Microsoft Foundry Hosted Agent, and starts Part B with Observe and Evaluate foundations for accelerator-specific tracing context, policy checks, rubrics, and Foundry cloud evaluation handoff.

## Two Harness Layers

The accelerator treats harness as two cooperating layers.

| Layer | Primary runtime | Responsibility | Current repository surface |
| --- | --- | --- | --- |
| Inner harness | Claude Agent SDK | Agent loop, built-in tools, SubAgents, Skills, sessions, context handling | `backend/main.py`, `backend/.claude/`, `backend/src/agent/runtime_contracts.py` |
| Outer managed harness | Microsoft Foundry Hosted Agent through Microsoft Agent Framework | Hosted endpoint, sandbox, filesystem persistence, state boundary, telemetry bridge, identity, scale | `backend/agent.yaml`, `backend/.foundry/agent-metadata.yaml`, `docs/deploy-hosted-agent.md` |

The implementation intentionally keeps the Claude Agent SDK loop intact. Microsoft Agent Framework wraps that agent so it can be exposed through the Hosted Agent responses protocol and connected to Foundry operations.

## Runtime Flow

```text
User / client
  -> Foundry Hosted Agent responses endpoint
  -> backend/main.py
  -> Microsoft Agent Framework adapter
  -> ClaudeAgent query loop
  -> .claude Main Agent instructions
  -> explore-agent, security-analyzer, cost-optimizer, architecture-reviewer
  -> Azure WAF / security / cost Skills
  -> stable analysis output contract
  -> Part B observability attributes and traces
```

The agent keeps `.claude` definitions, source code, and demo samples under `backend/` so the hosted container has a self-contained project directory. Local generated artifacts can use `backend/work/`, while Hosted Agent deployment sets `CLAUDE_WORKSPACE_ROOT=$HOME/work` so generated files live in the session-persisted home filesystem.

## Stable Output Contract

Azure analysis responses are expected to preserve these top-level keys:

```json
{
  "summary": { "resourcesAnalyzed": 25, "securityFindings": 12, "costSavingsOpportunities": 8 },
  "security": [ { "severity": "Critical", "resource": "...", "finding": "...", "remediation": "..." } ],
  "cost": [ { "resource": "...", "recommendation": "...", "estimatedSavings": "$15/month" } ],
  "architecture": [ { "pillar": "Operational Excellence", "finding": "...", "recommendation": "..." } ]
}
```

This contract is not just presentation. Part B will use it as the shared input for ASSERT policies, ACS output controls, rubric scoring, and ROI calculations.

## Part B Operational Loop

Part B keeps operational concerns outside the agent's reasoning prompts.

| Stage | Current or Planned Surface | Purpose |
| --- | --- | --- |
| Observe | `backend/src/agent/observability/tracing.py`, `backend/main.py`, Hosted Agent/App Insights traces | Attach agent identity, workspace, schema, and runtime context to traces. |
| Evaluate | `evals/`, `backend/src/agent/observability/evaluation.py`, `scripts/run_foundry_agent_eval.py` | Turn ASSERT-like policies and rubric criteria into repeatable local checks and optional Foundry cloud eval runs without packaging evaluation assets into the Hosted Agent image. |
| Control | Future `backend/control/acs.policy.yaml` and `acs_runtime.py` | Apply deterministic input, LLM, state, tool, and output controls. |
| Optimize | Future scorecards and trace-derived datasets | Identify changes that improve quality or reduce waste. |
| ROI | Future `roi.py` | Calculate completion rate, time saved, and cost efficiency. |

See [trust-roi-deepdive.md](trust-roi-deepdive.md) for the full Part B guide.

## Current Part A Status

| Capability | Status | Notes |
| --- | --- | --- |
| Claude SDK agent loop | Implemented | `ClaudeAgent` runs through MAF in `backend/main.py`. |
| SubAgent definitions | Implemented | Explore, security, cost, and architecture reviewers live under `backend/.claude/agents/`. |
| Skills | Implemented | Security, cost, and WAF guidance live under `backend/.claude/skills/`. |
| Responses protocol entry | Implemented | `backend/agent.yaml` declares the hosted responses protocol. |
| Filesystem workspace contract | Implemented | Local `CLAUDE_WORKSPACE_ROOT=work`; Hosted Agent manifest uses `$HOME/work`. |
| Fixed analysis output schema | Implemented | `backend/src/agent/runtime_contracts.py` centralizes the contract. |
| Part B Observe helper | Implemented | `backend/src/agent/observability/tracing.py` defines common trace attributes and startup context. |
| Part B Evaluate helper | Implemented | `backend/src/agent/observability/evaluation.py` scores JSONL responses against ASSERT-like policy and rubric assets. |
| Approval checkpoint | Planned | Part A design includes it; Part B ACS will provide the policy layer. |
| Invocations protocol | Planned | Useful for batch JSON-in / JSON-out workflows after the responses path is stable. |

## Roadmap

1. Part A completion: add approval checkpoint behavior, optional Invocations support, and a MAF workflow example that wraps the Claude agent as one node.
2. Part B foundation: expand request/run tracing, connect trace evaluation, add ACS policy/runtime, and ROI calculation helpers.
3. Demo hardening: add more sample exports, replayable scripts, and dashboard screenshots or setup notes.
