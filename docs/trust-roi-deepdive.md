# Part B Trust to ROI Deep Dive

This document is the standalone Part B guide for this repository. It explains how the accelerator grows from a hosted Azure review agent into an operational system that can be observed, evaluated, controlled, optimized, and tied back to business value.

Part A explains how the agent is built and hosted. Part B starts after that: **once the agent can answer, how do we prove that it is trustworthy, improve it over time, and explain the value it creates?** You do not need any external design note to understand the Part B direction. The repository code and this guide are the source of truth.

## Who This Is For

Use this guide if you want to:

- Understand the operational lifecycle around the Azure Well-Architected review agent.
- See where traces, evaluation assets, policy controls, and ROI calculations should live in the repository.
- Run the current B1 Observe implementation locally or in a Hosted Agent deployment.
- Explain how ASSERT, rubric evaluation, ACS, Agent Optimizer, and Agent ROI fit together without mixing them into the agent prompts.
- Extend the accelerator in small, testable steps.

## The Core Idea

A useful agent is not finished when the endpoint returns an answer. For an enterprise workload, the runtime needs a feedback loop:

```text
Observe -> Evaluate -> Control -> Optimize -> ROI
```

| Stage | Question It Answers | Repository Surface |
| --- | --- | --- |
| Observe | What happened during this run, and where did the answer come from? | `backend/src/agent/observability/tracing.py`, `backend/main.py`, App Insights / Foundry traces. |
| Evaluate | Did the output satisfy policy, quality, coverage, and safety expectations? | `evals/`, `backend/src/agent/observability/evaluation.py`, and `scripts/run_foundry_agent_eval.py`. |
| Control | What should be deterministically allowed, blocked, redacted, or approved? | Future `backend/control/acs.policy.yaml` and `backend/src/agent/control/acs_runtime.py`. |
| Optimize | Which changes improve quality or reduce waste according to evidence? | Future scorecards, trace datasets, and optimizer recommendations. |
| ROI | How much time, cost, and review effort did the agent save? | Future `backend/src/agent/observability/roi.py`, output contract, and trace metrics. |

The design rule is simple: Part B observes and controls the agent from the side. It should not bury operational policy inside `backend/CLAUDE.md` or specialist SubAgent prompts.

## Architecture at a Glance

```text
User or client
  -> Foundry Hosted Agent responses endpoint
  -> backend/main.py
  -> ClaudeAgent through Microsoft Agent Framework
  -> Claude Agent SDK loop, SubAgents, Skills, tools
  -> stable Azure analysis output contract
        |
        | B1 Observe
        v
     OpenTelemetry spans and logs
     Foundry traces / Application Insights
        |
        | B2 Evaluate
        v
    ASSERT-like policies, rubric scorecards, multi-turn scenarios
        |
        | B3 Control
        v
     ACS checkpoints for input, LLM, state, tool, output
        |
        | B4 Optimize and ROI
        v
     optimizer recommendations, completion rate, time saved, cost efficiency
```

The stable output contract from Part A is the bridge between agent reasoning and operational checks:

```json
{
  "summary": { "resourcesAnalyzed": 25, "securityFindings": 12, "costSavingsOpportunities": 8 },
  "security": [ { "severity": "Critical", "resource": "...", "finding": "...", "remediation": "..." } ],
  "cost": [ { "resource": "...", "recommendation": "...", "estimatedSavings": "$15/month" } ],
  "architecture": [ { "pillar": "Operational Excellence", "finding": "...", "recommendation": "..." } ]
}
```

This shape is intentionally stable because evaluation, ACS output validation, and ROI calculations all need a predictable input.

## Repository Map for Part B

Read or build these files in this order.

| Step | File | Why It Matters |
| --- | --- | --- |
| 1 | `docs/trust-roi-deepdive.md` | This guide. It defines the Part B lifecycle and current implementation status. |
| 2 | `backend/src/agent/observability/tracing.py` | B1 Observe foundation: OpenTelemetry helpers, common trace attributes, startup/server spans, and future hook-event conversion. |
| 3 | `backend/src/agent/observability/evaluation.py` | B2 Evaluate foundation: JSON extraction, schema validation, policy checks, and deterministic rubric scoring. |
| 4 | `evals/` | Local evaluation assets: policy YAML, rubric YAML, query JSONL, and sample response JSONL. Kept outside `backend/` so they are not packaged into the Hosted Agent image. |
| 5 | `docs/foundry-portal-rubric-evaluation.md` | Portal-first guide for creating a Foundry Rubric evaluator with Autogenerate and running Hosted Agent evaluation. |
| 6 | `docs/foundry-agent-optimizer.md` | Agent Optimizer execution guide for the B4 Optimize loop. |
| 7 | `scripts/run_foundry_agent_eval.py` | Microsoft Foundry cloud evaluation runner for Hosted Agent target evaluation automation. |
| 8 | `backend/main.py` | Wires B1 tracing and B4 optimizer config into startup and server hosting without changing agent reasoning logic. |
| 9 | `backend/src/agent/runtime_contracts.py` | Stable output schema that evaluation, control, and ROI depend on. |
| 10 | `backend/src/agent/optimization.py` | Loads Agent Optimizer baseline/candidate config at runtime. |
| 11 | `backend/.claude/optimizer_configs/baseline/` | Agent Optimizer baseline overlay. |
| 12 | `backend/eval.yaml` | Local optimization intent and bad-config dataset binding. |
| 13 | `backend/agent.yaml` | Hosted Agent telemetry environment flags and App Insights connection mapping. |
| 14 | `docs/hosted-agent-test-plan.md` | Deployment verification path, including trace visibility checks. |
| 15 | Future `backend/control/acs.policy.yaml` | Portable ACS checkpoint contract. |
| 16 | Future `backend/src/agent/observability/roi.py` | Completion, time saved, and cost efficiency calculations. |

## Current Implementation Status

| Capability | Status | Where to Look |
| --- | --- | --- |
| B1 common trace attributes | Implemented | `backend/src/agent/observability/tracing.py`. |
| B1 startup/server spans | Implemented | `backend/main.py` calls `create_observability()` and `trace_server_startup()`. |
| B1 App Insights connection normalization | Implemented | `_configure_observability_environment()` in `backend/main.py`. |
| B1 GenAI tracing environment flags | Implemented | `backend/agent.yaml`. |
| B1 ClaudeAgent built-in telemetry | Implemented by dependency | `agent-framework-claude`'s `ClaudeAgent` includes `AgentTelemetryLayer`. |
| B1 hook event model | Implemented as a helper surface | `record_hook_event()` can be used when SDK hook callbacks are added. |
| B2 ASSERT-like policy evaluation | Implemented | `backend/src/agent/observability/evaluation.py` and `evals/policies/`. |
| B2 local rubric scoring | Implemented | `evals/rubrics/analysis-quality.rubric.yaml`. |
| B2 seed datasets | Implemented | `evals/datasets/bad-config.queries.jsonl`, `bad-config.sample-responses.jsonl`, and `bad-config.conversations.jsonl`. |
| B2 Foundry portal Rubric guide | Implemented | `docs/foundry-portal-rubric-evaluation.md` and `evals/rubric-autogenerate-context.md`. |
| B2 Foundry cloud eval runner | Implemented as optional automation | `scripts/run_foundry_agent_eval.py` uses `azure-ai-projects>=2.2.0`. |
| B3 ACS policy/runtime | Planned | Add under future `backend/control/` and `backend/src/agent/control/`. |
| B4 Agent Optimizer readiness | Implemented | `backend/src/agent/optimization.py`, `backend/.claude/optimizer_configs/baseline/`, `backend/eval.yaml`, and `docs/foundry-agent-optimizer.md`. |
| B4 ROI helpers | Planned | Add after evaluation and trace metrics are stable. |

## B1 Observe

### What Observe Means Here

Observe is not only "send logs somewhere." For this accelerator, Observe means every important run should answer five questions:

1. Which hosted agent and version handled the request?
2. Which workspace boundary was used for generated artifacts?
3. Was the request local or hosted, and which Foundry telemetry settings were active?
4. Did Microsoft Agent Framework and Claude Agent telemetry emit model/tool spans?
5. Can future evaluation and ROI code connect the final output to the run that produced it?

The current implementation gives the repository an accelerator-specific tracing layer while leaving model/tool tracing to the framework components that already know those internals.

### Runtime Responsibilities

`backend/main.py` owns runtime setup:

- Loads `.env` values.
- Normalizes `APPINSIGHTS_CONNECTION_STRING` and `AZURE_MONITOR_CONNECTION_STRING` into `APPLICATIONINSIGHTS_CONNECTION_STRING`.
- Builds the `ClaudeAgent`.
- Starts the Hosted Agent-compatible responses server.
- Emits a startup span through `trace_server_startup()`.

`backend/src/agent/observability/tracing.py` owns observability conventions:

- The tracer name: `claude_agent_accelerator.part_b`.
- Shared attributes for agent name, version, workspace root, schema name, and runtime mode.
- A startup/server span around the host startup boundary.
- A hook event recording helper for future Claude SDK hook callbacks.
- Low-cardinality event attributes that are safe for production telemetry.

### Span Shape

The intended trace tree for a full future run is:

```text
hosted_agent.server
  -> agent_framework request spans
    -> gen_ai agent/model spans from ClaudeAgent telemetry
      -> future hook events for SubAgent and tool boundaries
```

Today, `ClaudeAgent` already includes Microsoft Agent Framework telemetry. The accelerator tracing code adds the outer repository-specific context so traces can be filtered and explained consistently in demos.

### Attribute Contract

Part B uses these attribute names as the stable observability vocabulary.

| Attribute | Meaning |
| --- | --- |
| `service.name` | Logical service name for this backend. |
| `gen_ai.agent.name` | Hosted Agent name or local agent name. |
| `gen_ai.agent.version` | Hosted Agent version when provided by the platform. |
| `azure.accelerator.part` | Current lifecycle part, currently `part-b-observe`. |
| `azure.accelerator.schema` | Output contract name, currently `azure-analysis-output-v1`. |
| `azure.accelerator.workspace_root` | Resolved workspace path used for artifacts. |
| `azure.accelerator.hosted` | Whether the process appears to run inside Hosted Agent platform injection. |
| `azure.accelerator.app_insights.configured` | Whether an App Insights connection string is present. |
| `azure.accelerator.genai_tracing.enabled` | Whether GenAI tracing environment flags are enabled. |

Keep attributes low-cardinality. Do not put full prompts, Azure export JSON, keys, tokens, or customer data into trace attributes.

### Local Smoke Test

From the repository root:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m compileall main.py src
..\.venv\Scripts\python.exe -c "from pathlib import Path; from src.agent.observability.tracing import create_observability; o = create_observability(agent_name='local', agent_version='', workspace_root=Path('work')); print(o.base_attributes()['azure.accelerator.schema'])"
```

Expected output:

```text
azure-analysis-output-v1
```

Start the local server as usual:

```powershell
..\.venv\Scripts\python.exe main.py
```

Expected startup behavior:

- Logs still show Foundry target and authentication mode.
- Logs include the resolved workspace root.
- If App Insights is configured, the OpenTelemetry provider used by the host/framework can export spans.
- If App Insights is not configured, the tracing helper still runs but acts as a no-op provider through OpenTelemetry API defaults.

### Hosted Agent Trace Check

After `azd deploy`, run a smoke prompt from the Portal or responses endpoint, then inspect Foundry traces or Application Insights.

Use this prompt for a small run:

```text
samples/bad-config/azure-export.json を Read で読み、summary/security/cost/architecture の固定JSONだけを返してください。WebSearch と WebFetch と Agent ツールは使わないでください。
```

Passing signals:

- A Hosted Agent request completes.
- App Insights or Foundry traces show the agent/server activity.
- Trace attributes include the deployed agent name.
- GenAI tracing spans appear when the platform and extension version support them.
- The final response preserves the fixed output contract.

### What Not To Trace

Do not trace:

- Full Azure exports.
- API keys or bearer tokens.
- Customer names, email addresses, tenant IDs, or subscription IDs unless explicitly needed and approved.
- Full prompt or response bodies by default.
- High-cardinality file paths for every temporary artifact.

For local demos, `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` can be useful. For customer or production environments, treat message-content capture as a deliberate data-handling decision.

## B2 Evaluate

Evaluate turns expectations into repeatable checks. This repository now has a B2 foundation with two paths:

| Path | Use It When | Current Asset |
| --- | --- | --- |
| Local portable evaluation | You want fast inner-loop checks without calling Foundry services. | `backend/src/agent/observability/evaluation.py` plus YAML/JSONL under `evals/`. |
| Foundry portal Rubric evaluation | You want to create a Rubric evaluator with Autogenerate, run the Hosted Agent as the target, and review dimension scores in the portal. | `docs/foundry-portal-rubric-evaluation.md` plus `evals/rubric-autogenerate-context.md`. |
| Foundry cloud evaluation automation | You want service-backed evaluator runs from shell or CI/CD after the portal flow is proven. | `scripts/run_foundry_agent_eval.py` using `azure-ai-projects>=2.2.0`. |

Evaluation assets intentionally live at the repository root. The `backend/` folder is the Hosted Agent deployment context, and its Dockerfile copies that folder into the runtime image. Keeping datasets, rubrics, policy fixtures, optional evaluator dependencies, and cloud-eval scripts outside `backend/` prevents test assets from becoming part of the deployed agent container while preserving a clean contract between runtime output and evaluation.

The local path is intentionally deterministic and inspectable. It is not a replacement for Foundry evaluators, ASSERT, or Rubric evaluator. It gives the accelerator a runnable policy/rubric contract today, and the same assets can later seed ASSERT scenarios, Foundry evaluator catalog entries, and cloud evaluation datasets.

### B2 MVP Decision

For this demo, B2 does **not** add a Foundry Custom Evaluator. The cleaner MVP is:

| Concern | MVP Owner | Why |
| --- | --- | --- |
| WAF review quality | Rubric evaluator and `analysis-quality.rubric.yaml` | Quality is nuanced and benefits from weighted criteria. |
| Missed policy obligations | ASSERT-like YAML policies and `evaluation.py` | Policy failures should be concrete and reproducible. |
| JSON validity, required fields, severity enum | Local schema checks now; ACS output checkpoint in B3 | These are runtime controls more than judge-style evaluation. |
| Foundry-managed reporting | Optional cloud eval runner | Use the service when you need portal reports, hosted-agent target runs, or CI scale. |

Custom evaluator remains a future option only if the team wants a deterministic proprietary score surfaced as a first-class Foundry Evaluation metric. For the current Build 2026 story, Rubric + ASSERT-like policy + future ACS keeps the roles clear.

For the main demo, use the portal-first Rubric flow in [foundry-portal-rubric-evaluation.md](foundry-portal-rubric-evaluation.md). It shows how to create a Foundry Rubric evaluator with Autogenerate, upload or select the `bad-config` dataset, run the deployed Hosted Agent as the evaluation target, and inspect dimension scores and reasons in Foundry. The local evaluator remains the fast deterministic gate; the portal Rubric evaluator is the cloud-side quality story.

### Official API Shape Checked

The latest Microsoft Foundry cloud evaluation docs describe three concepts that shape this implementation:

- Evaluation data is JSONL. Existing-output evaluation uses `query` and `response`; agent target evaluation can use query-only rows and generate responses at run time.
- Cloud evaluation with the Microsoft Foundry SDK uses `azure-ai-projects>=2.2.0`, `AIProjectClient`, `project_client.get_openai_client()`, `openai_client.evals.create()`, and `openai_client.evals.runs.create()`.
- Hosted Agent target evaluation uses `data_source.type = azure_ai_target_completions`, `target.type = azure_ai_agent`, and data mappings such as `{{item.query}}`, `{{sample.output_text}}`, and `{{sample.output_items}}`.

For trace evaluation later, Foundry expects GenAI semantic convention spans such as `gen_ai.operation.name = invoke_agent`, `gen_ai.agent.id`, `gen_ai.input.messages`, and `gen_ai.output.messages`. That is why B1 keeps agent identity and trace context explicit.

### ASSERT Track

ASSERT is the policy-driven track. It should answer: **did the agent violate an explicit rule?**

Implemented local path:

```text
evals/policies/security.policy.yaml
evals/policies/cost.policy.yaml
evals/policies/waf.policy.yaml
backend/src/agent/observability/evaluation.py
```

Example policy shape:

```yaml
policy:
  id: security-baseline
  intent: Public exposure, authentication, and encryption risks must be detected with remediation.
  requirements:
    - id: public-blob
      must: Public blob access must be reported with severity High or Critical.
    - id: remediation-required
      must: Every security finding must include non-empty remediation.
  generation:
    scenarios_per_requirement: 5
  scoring:
    fail_on:
      - missing_remediation
      - missed_public_blob
```

ASSERT is useful for inner-loop development because policy failures are concrete. If a public blob exposure is missed, the fix is either prompt guidance, a Skill update, a control, or a parsing improvement.

The local policy runner supports these checks today:

| Check | Purpose |
| --- | --- |
| `schema-valid` | Confirms the fixed `summary/security/cost/architecture` contract can be parsed and validated. |
| `require-non-empty` | Requires fields such as `security[].remediation` and `cost[].estimatedSavings`. |
| `expected-keywords` | Checks that expected fixture signals appear in the relevant output category. |
| `minimum-count` | Requires a minimum number of findings for a category. |
| `severity-at-least` | Ensures high-impact security signals are prioritized appropriately. |

Run the local policy smoke test:

```powershell
Set-Location <repo-root>
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m src.agent.observability.evaluation `
  --responses evals/datasets/bad-config.sample-responses.jsonl `
  --policy "evals/policies/*.policy.yaml" `
  --rubric evals/rubrics/analysis-quality.rubric.yaml `
  --output .foundry/results/local-policy-scorecard.json
```

The sample response is hand-authored only to prove the evaluation machinery. For real runs, capture the agent's actual response into the same JSONL shape:

```json
{"id":"case-id","query":"...","response":"...","expected":{"resourcesAnalyzed":5}}
```

### Rubric Track

Rubric evaluation is the quality track. It should answer: **was the answer good enough to trust and use?**

Implemented local path:

```text
evals/rubrics/analysis-quality.rubric.yaml
backend/src/agent/observability/evaluation.py
```

Example rubric shape:

```yaml
rubric:
  dimensions:
    - name: coverage
      weight: 0.35
    - name: actionability
      weight: 0.30
    - name: accuracy
      weight: 0.25
    - name: prioritization
      weight: 0.10
```

Rubrics are useful after the output contract is stable because they can score nuance: whether remediation is specific, whether severity is sensible, and whether the answer explains uncertainty.

The local scorer maps the rubric dimensions to deterministic heuristics:

| Dimension | Local Signal | Foundry/Rubric Intent |
| --- | --- | --- |
| `coverage` | Expected keyword groups found across security, cost, and architecture. | Does the answer cover the important risks? |
| `actionability` | Required recommendation/remediation fields are substantive. | Can an operator act on the result? |
| `accuracy` | Resource count and summary count consistency. | Does the answer match the inspected input and its own arrays? |
| `prioritization` | Public exposure findings are High or Critical. | Are severe risks elevated appropriately? |

When moving this to Foundry Rubric evaluator, use `analysis-quality.rubric.yaml` as the criteria source and `evals/rubric-autogenerate-context.md` as the Autogenerate context. The Rubric evaluator is preview and scores agent/model responses with weighted criteria, returning a normalized 0-1 score with per-dimension reasoning.

### Foundry Portal Rubric Evaluation

The recommended cloud-side B2 demo is the Foundry portal flow documented in [foundry-portal-rubric-evaluation.md](foundry-portal-rubric-evaluation.md).

Use this path when you want to show:

- the deployed Hosted Agent as a Foundry evaluation target;
- a Rubric evaluator generated and reviewed inside Foundry;
- `bad-config.queries.jsonl` as a query-only dataset;
- dimension scores and judge reasons in the portal report.

Portal setup uses these local assets:

| Asset | Portal Use |
| --- | --- |
| `evals/rubric-autogenerate-context.md` | Reference context for Rubric Autogenerate. |
| `evals/datasets/bad-config.queries.jsonl` | Existing dataset for Agent target evaluation. |
| `evals/rubrics/analysis-quality.rubric.yaml` | Local source of desired dimensions and weights. |
| `evals/policies/*.policy.yaml` | Supporting context for policy obligations, not Foundry ASSERT itself. |

The portal-generated Rubric should include dimensions for risk coverage, evidence accuracy, remediation quality, severity prioritization, and schema compliance. Start with a pass threshold around `0.7`; raise it after the rubric matches human judgment on a small sample.

### Foundry Cloud Evaluation Runner

Use the SDK runner when you want automation after proving the portal evaluation flow. The current runner creates Foundry-managed agent-target evaluation runs from shell, but the portal guide is the canonical path for creating and tuning the Rubric evaluator.

Install optional dependencies first:

```powershell
Set-Location <repo-root>
.\.venv\Scripts\python.exe -m pip install -r requirements-eval.txt
```

Then run an agent target evaluation against the deployed Hosted Agent:

```powershell
$env:AZURE_AI_PROJECT_ENDPOINT = "https://<account>.services.ai.azure.com/api/projects/<project>"
$env:FOUNDRY_AGENT_NAME = "<hosted-agent-name>"
$env:FOUNDRY_AGENT_VERSION = "6"
$env:AZURE_AI_MODEL_DEPLOYMENT_NAME = "<gpt-evaluator-deployment>"

.\.venv\Scripts\python.exe scripts/run_foundry_agent_eval.py `
  --dataset evals/datasets/bad-config.queries.jsonl `
  --output .foundry/results/latest-agent-eval.json
```

The runner follows the current Foundry SDK cloud evaluation shape:

- Uploads the JSONL query dataset with `project_client.datasets.upload_file()`.
- Creates an eval with `openai_client.evals.create()`.
- Runs the hosted agent target through `azure_ai_target_completions` and `azure_ai_agent`.
- Uses built-in `coherence`, `task_adherence`, and `violence` evaluators as a small first suite. Add Rubric evaluator support after the portal-generated rubric is stable.
- Polls the run and writes result metadata plus output items under `.foundry/results/`.

Do not treat this runner as the only B2 path. For production monitoring, Foundry also supports response ID evaluation, trace evaluation, synthetic data generation, conversation-level evaluation, conversation simulation, and continuous evaluation. Those belong after B1 traces and B2 seed datasets are stable.

### Evaluation Data Sources

Evaluation should accept three sources:

| Source | Use |
| --- | --- |
| Bundled fixtures under `backend/samples/` | Repeatable smoke tests and demos. |
| `evals/datasets/*.queries.jsonl` | Query-only inputs for Foundry agent target evaluation. |
| `evals/datasets/*.sample-responses.jsonl` | Local policy/rubric smoke tests with known responses. |
| Inline JSON requests captured from realistic tests | Hosted request-boundary validation. Convert to `query/response/expected` JSONL for local evaluation. |
| Trace-to-dataset exports | Production-like regression coverage after observability is active. Use trace evaluation or traces-to-dataset later. |

## B3 Control

Control is where deterministic guardrails live. The agent can reason, but some constraints should be policy, not persuasion.

ACS gives this repository a portable control contract with five checkpoints.

| Checkpoint | Accelerator Examples |
| --- | --- |
| input | Size limits, JSON parseability, PII screening, file type restrictions. |
| LLM | Task adherence checks, jailbreak detection, restricted instruction handling. |
| state | What may persist across sessions, what must be dropped, what must be encrypted elsewhere. |
| tool | Allowed tools, write path boundaries, web access restrictions, approval requirements. |
| output | Schema validation, remediation requirement, severity normalization, sensitive data redaction. |

Planned policy path:

```text
backend/control/acs.policy.yaml
backend/src/agent/control/acs_runtime.py
```

Example control shape:

```yaml
acs:
  version: "1.0"
  checkpoints:
    input:
      - control: max-size
        limit: 5MB
    tool:
      - control: allow-tools
        only: [Read, Glob, Grep, Write, WebSearch]
    output:
      - control: schema-validate
        schema: azure-analysis-output-v1
      - control: require-field
        path: security[].remediation
```

The important design choice is placement. ACS should sit at runtime boundaries and validation points. It should not be copied into every SubAgent prompt.

## B4 Optimize and ROI

Optimize and ROI close the loop.

### Agent Optimizer Track

Agent Optimizer is the optimization track for Hosted Agents. It evaluates a deployed agent against a dataset, generates candidate configurations, ranks them by score, and lets the team apply the winning candidate locally before redeployment.

This repository is now optimizer-ready for the current Claude Hosted Agent:

| Surface | Role |
| --- | --- |
| `backend/.claude/optimizer_configs/baseline/metadata.yaml` | Baseline config loaded by Agent Optimizer. |
| `backend/.claude/optimizer_configs/baseline/instructions.md` | Thin optimizer overlay that can be rewritten. |
| `backend/.claude/skills/` | Long-lived Claude Code Skills; not duplicated in optimizer config. |
| `backend/eval.yaml` | Bad-config dataset and evaluator intent. |
| `backend/src/agent/optimization.py` | Runtime bridge for `azure.ai.agentserver.optimization.load_config()`. |

Generated azd service folders are deployment scaffolding. They should point at `backend/` and stay outside the committed accelerator source.

Use the conceptual guide in [foundry-agent-optimizer-concepts.md](foundry-agent-optimizer-concepts.md) to understand inputs, processing, outputs, and preparation requirements. Use the step-by-step execution guide in [foundry-agent-optimizer.md](foundry-agent-optimizer.md).

For this accelerator, Optimizer is deliberately scoped:

| Target | Decision |
| --- | --- |
| Instruction tuning | Enabled for coordinator guidance. |
| Skill improvement | Not enabled by default to avoid duplicating `.claude/skills/`. |
| Tool optimization | Not enabled because this app uses Claude Code built-in tools, not OpenAI function definitions. |
| Model selection | Not enabled by default because the runtime uses Claude model aliases such as `sonnet`. |

Keep the stable JSON output contract outside the optimizer baseline. It is still appended by `backend/main.py` through `analysis_output_instructions()`, so optimized candidates cannot accidentally remove the schema that B2 evaluation, B3 control, and ROI depend on.

### Optimizer Inputs

Optimizer recommendations should be based on:

- Trace data from B1.
- ASSERT failures from B2.
- Rubric scorecards from B2.
- ACS block/allow/approval events from B3.
- Repeated weaknesses in demo and production-like datasets.

The first useful optimizer demo does not need full automation. It can be:

1. Run bad-config fixture.
2. Evaluate the output.
3. Run Agent Optimizer against the same dataset.
4. Apply the recommended candidate locally after reviewing the diff.
5. Re-run evaluation.
6. Show score improvement and explain the trace difference.

### ROI Metrics

ROI should be calculated from stable, inspectable inputs.

| Metric | Definition | Data Source |
| --- | --- | --- |
| Task completion rate | Runs that satisfy schema and required policies divided by attempted runs. | Evaluation pass/fail and output validation. |
| Time saved | Manual review baseline minus measured agent run duration. | Configured baseline plus trace duration. |
| Cost efficiency | Estimated savings and labor value divided by run cost. | `cost[].estimatedSavings`, token/runtime cost, and configured hourly rate. |

Planned helper path:

```text
backend/src/agent/observability/roi.py
```

Keep assumptions configurable. Manual WAF review time and hourly labor value differ by customer and should not be hardcoded into the agent prompts.

## Demo Story

Part B has a three-moment demo.

| Moment | What To Show | Passing Signal |
| --- | --- | --- |
| Observe | Run the bad-config prompt and open traces. | The run is visible with agent identity, workspace context, and GenAI spans where available. |
| Evaluate and Control | Show a policy failure, add or enable a control, re-run. | The failure becomes a pass or a deterministic block with clear reason. |
| Optimize and ROI | Apply one improvement and calculate value. | Score improves, findings remain resource-specific, ROI numbers are explainable. |

## Implementation Roadmap

| Milestone | Scope | Done When |
| --- | --- | --- |
| B1.1 | Add tracing helper and startup/server spans. | `compileall` passes and startup emits observability context. |
| B1.2 | Add request/run span wrapping if the host exposes a stable middleware point. | Each responses request has an accelerator run span linked to framework spans. |
| B1.3 | Add Claude SDK hook event bridge when hook callbacks are wired. | Tool/SubAgent events can be recorded without prompt changes. |
| B2.1 | Add JSON extraction and schema validation helper. | Bad-config output can be validated offline. |
| B2.2 | Add ASSERT policies. | Policy failures are reproducible from fixtures. |
| B2.3 | Add rubric scorecard. | Quality score can be compared across runs. |
| B3.1 | Add ACS policy and runtime skeleton. | Output schema and remediation controls can allow/block. |
| B4.0 | Make the Hosted Agent optimizer-ready. | `load_config()` reads `.claude/optimizer_configs/baseline/`, and `eval.yaml` points to the bad-config dataset. |
| B4.1 | Add ROI helper. | Completion, time saved, and cost efficiency can be calculated from sample run data. |

## Troubleshooting

| Symptom | Likely Cause | What To Check |
| --- | --- | --- |
| No traces appear in Foundry | Hosted Agent platform or extension did not ingest GenAI traces. | Confirm `agent-framework-foundry-hosting` version, `APPLICATIONINSIGHTS_CONNECTION_STRING`, and deployed agent name. |
| App Insights has traces but Foundry Traces tab is empty | Agent identity attributes do not match the Hosted Agent name. | Confirm `FOUNDRY_AGENT_NAME`, `CLAUDE_HOSTED_AGENT_NAME`, and manifest name alignment. |
| Local tracing appears to do nothing | No OpenTelemetry provider/exporter is configured locally. | This is expected; the API defaults to no-op unless the host configures a provider. |
| Trace content includes too much prompt data | Message capture flags are enabled. | Review `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` and production data policy. |
| Evaluation cannot parse output | The final answer includes prose or Markdown fences. | Add a JSON extraction helper before schema validation. |
| ROI numbers look arbitrary | Baseline assumptions are hidden. | Move manual review time, hourly rate, and run cost assumptions into configuration. |
| Optimizer scores are all zero | Eval model deployment is missing or unavailable. | Confirm the eval model exists in Foundry and pass it to `azd ai agent optimize --eval-model`. |
| Optimizer candidate changes the model unexpectedly | Model selection was enabled for a ClaudeAgent runtime. | Keep model selection disabled unless the runtime is intentionally changed. |

## How to Extend Part B Safely

Good Part B extensions:

- Add low-cardinality attributes or events to `tracing.py`.
- Add fixture-based validation before adding live service dependencies.
- Keep ASSERT, rubric, and ACS assets in YAML so reviewers can inspect policy separately from code.
- Validate the stable output contract before computing ROI.
- Document any preview/private-preview Foundry feature with current status and a fallback path.
- Apply Agent Optimizer candidates locally and review the source diff before deploying.

Avoid these moves unless there is a strong reason:

- Putting policy text directly into every SubAgent prompt.
- Treating non-empty output as evaluation success.
- Capturing full customer inputs in trace attributes.
- Hardcoding customer-specific ROI assumptions.
- Blocking tool use in a way that silently prevents the agent from gathering evidence.
- Deploying an optimizer candidate directly without checking evaluation results and source changes.

## Quick Review Checklist

Before opening a Part B pull request, check:

- `python -m compileall backend/main.py backend/src` passes.
- New telemetry attributes do not include secrets or full customer data.
- README and architecture docs link to this guide.
- The Part A demo prompt still works.
- The stable output contract remains unchanged unless evaluation/control assets are updated with it.
- Any preview feature is labeled as preview and has an explanation of what is implemented today.
