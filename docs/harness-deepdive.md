# Part A Harness Deep Dive

This document is the standalone Part A guide for this repository. It explains how the accelerator is built, where the important code lives, how to run it, and what to look for when you demo or extend it.

Part A is about the build-and-host layer: **Claude Agent SDK as the inner harness** and **Microsoft Foundry Hosted Agent as the outer managed harness**. Part B will later add evaluation, control, optimization, and ROI. You do not need any external design note to understand the current Part A implementation.

## Who This Is For

Use this guide if you want to:

- Understand why this repository combines Claude Agent SDK, Microsoft Agent Framework, and Foundry Hosted Agent.
- Read the code in a useful order instead of jumping between files.
- Run the backend locally against Claude on Foundry.
- Deploy the same backend as a Foundry Hosted Agent.
- Explain the demo story to a customer, teammate, or reviewer.
- Extend the runtime without mixing hosting concerns into agent reasoning logic.

## The Core Idea

An agent needs two different kinds of runtime support.

| Layer | What It Solves | Runtime Used Here | Repository Surface |
| --- | --- | --- | --- |
| Inner harness | How the agent thinks, uses tools, delegates work, and manages context. | Claude Agent SDK through `agent-framework-claude`. | `backend/main.py`, `backend/CLAUDE.md`, `backend/.claude/agents/`, `backend/.claude/skills/`. |
| Outer managed harness | Where the agent runs, how it is hosted, how state and telemetry connect to enterprise operations. | Microsoft Foundry Hosted Agent through Microsoft Agent Framework. | `backend/agent.yaml`, `backend/Dockerfile`, `backend/.foundry/agent-metadata.yaml`, `docs/deploy-hosted-agent.md`. |

The repository deliberately keeps these responsibilities separate. Claude Agent SDK remains responsible for the agent loop and SubAgent behavior. Foundry Hosted Agent remains responsible for hosting the custom backend as a managed endpoint.

## Architecture at a Glance

```text
User or client
  -> Foundry Hosted Agent responses endpoint
  -> backend/main.py
  -> Microsoft Agent Framework adapter
  -> ClaudeAgent from agent-framework-claude
  -> Claude Agent SDK project runtime
  -> backend/CLAUDE.md plus appended runtime instructions
  -> SubAgents under backend/.claude/agents/
  -> Skills under backend/.claude/skills/
  -> stable Azure analysis output contract
```

The same backend can be run locally or packaged into a Hosted Agent container. Local mode is useful for development and debugging. Hosted mode is useful for demonstrating managed endpoint hosting, sandbox execution, deployment lifecycle, and telemetry integration.

## Repository Map for Part A

Read these files in this order when you are learning the implementation.

| Step | File | Why It Matters |
| --- | --- | --- |
| 1 | `backend/main.py` | The runtime entrypoint. Builds the `ClaudeAgent`, configures Foundry model access, appends runtime instructions, and exposes the agent through Microsoft Agent Framework. |
| 2 | `backend/CLAUDE.md` | The Main Agent's project instructions: role, delegation behavior, output structure, and tool guidance. |
| 3 | `backend/.claude/agents/explore-agent.md` | The first specialist for large or unfamiliar Azure exports. It inventories files and resources before deeper review. |
| 4 | `backend/.claude/agents/security-analyzer.md` | Security specialist for exposure, encryption, identity, network controls, and policy gaps. |
| 5 | `backend/.claude/agents/cost-optimizer.md` | Cost specialist for sizing, always-on spend, premium tiers, and elasticity gaps. |
| 6 | `backend/.claude/agents/architecture-reviewer.md` | Architecture specialist for reliability, operations, and Well-Architected alignment. |
| 7 | `backend/.claude/skills/` | Progressive domain guidance that the agent can load only when useful. |
| 8 | `backend/src/agent/runtime_contracts.py` | The stable output contract used by prompts today and by evaluation, control, and ROI later. |
| 9 | `backend/src/agent/workspaces.py` | The filesystem persistence contract for generated artifacts and intermediate analysis files. |
| 10 | `backend/agent.yaml` | The Hosted Agent manifest consumed by `azd ai agent init`. |
| 11 | `backend/.foundry/agent-metadata.yaml` | Human-readable metadata for the intended Hosted Agent behavior and implementation status. |
| 12 | `backend/samples/bad-config/azure-export.json` | A deliberately weak Azure export for repeatable demos. It lives under `backend/` so the Hosted Agent container includes it. |

## Request Flow in Detail

A typical Azure export review follows this path.

1. A user asks the backend to analyze an Azure export or resource configuration.
2. `backend/main.py` creates a `ClaudeAgent` with `cwd` set to `backend/` so Claude Code project settings, SubAgents, and Skills are discoverable.
3. The appended runtime prompt tells the agent it is hosted behind Microsoft Agent Framework and Azure AI Agent Server.
4. The appended runtime prompt also injects the workspace root and stable JSON output contract.
5. `backend/CLAUDE.md` tells the Main Agent to prefer local files, use Skills for Azure review, and delegate to SubAgents.
6. For broad or unfamiliar inputs, the Main Agent calls `explore-agent` first.
7. The Explore Agent uses only `Read`, `Grep`, and `Glob` to inventory files and summarize high-signal facts.
8. The Main Agent delegates deeper review to security, cost, and architecture specialists when useful.
9. The Main Agent synthesizes the final response using stable `summary`, `security`, `cost`, and `architecture` keys.
10. Microsoft Agent Framework streams the response through the Hosted Agent-compatible responses endpoint.

## Why the Explore Agent Exists

Azure exports can be large, uneven, and noisy. Jumping directly into security or cost review often causes the parent context to carry too much raw configuration.

`explore-agent` gives the workflow a cheap first pass:

- Count resource types and providers.
- Identify files that matter.
- Extract facts that specialists can use.
- Call out missing context before the final report becomes overconfident.

This is a practical use of Claude Agent SDK SubAgents: the exploration context can be detailed, while the Main Agent receives a compact summary.

## SubAgent Boundaries

SubAgents are defined as Markdown files under `backend/.claude/agents/`. They are not Python classes in this implementation. That is intentional: the Claude Agent SDK project format keeps specialist behavior declarative and close to the instructions that shape it.

| SubAgent | Allowed Tools | Expected Output Style |
| --- | --- | --- |
| `explore-agent` | `Read`, `Grep`, `Glob` | Compact inventory and high-signal facts. |
| `security-analyzer` | `Read`, `Grep`, `Glob`, `WebSearch`, `WebFetch` | Evidence-based risks and remediation. |
| `cost-optimizer` | `Read`, `Grep`, `Glob`, `WebSearch`, `WebFetch` | Resource-specific savings opportunities and assumptions. |
| `architecture-reviewer` | `Read`, `Grep`, `Glob`, `WebSearch`, `WebFetch` | Reliability, operations, and Well-Architected recommendations. |

The Main Agent remains the coordinator. Specialists should not own final synthesis unless the user asks for one narrow perspective.

## Skills and Progressive Context Loading

Skills live under `backend/.claude/skills/`. They hold reusable domain guidance without forcing all of it into the always-loaded system prompt.

Current Skills:

- `azure-security-baselines`: public exposure, encryption, identity, and network security checks.
- `azure-cost-patterns`: oversizing, always-on services, SKU choices, and elasticity checks.
- `azure-waf-review`: reliability, operational excellence, observability, backup, and recovery considerations.

This is one of the main reasons to use Claude Agent SDK for this sample. The domain knowledge can grow while the Main Agent prompt stays focused.

## The Stable Output Contract

The final Azure analysis should preserve this shape:

```json
{
  "summary": { "resourcesAnalyzed": 25, "securityFindings": 12, "costSavingsOpportunities": 8 },
  "security": [ { "severity": "Critical", "resource": "...", "finding": "...", "remediation": "..." } ],
  "cost": [ { "resource": "...", "recommendation": "...", "estimatedSavings": "$15/month" } ],
  "architecture": [ { "pillar": "Operational Excellence", "finding": "...", "recommendation": "..." } ]
}
```

The contract appears in two places:

- `backend/CLAUDE.md` gives the agent a human-readable version.
- `backend/src/agent/runtime_contracts.py` defines the schema and generates prompt text appended by `backend/main.py`.

This contract matters even before Part B exists. It makes demo output easier to compare across runs, and it gives future evaluation and control code something stable to validate.

## Workspace and Filesystem Contract

`backend/src/agent/workspaces.py` resolves and creates the workspace root, controlled by `CLAUDE_WORKSPACE_ROOT`. For local development, `work` resolves under `backend/`. For Hosted Agent deployment, the manifest sets `CLAUDE_WORKSPACE_ROOT=$HOME/work` so generated artifacts land in the session-persisted `$HOME` filesystem that appears in the Foundry Portal Files view.

The workspace is for:

- Normalized input exports.
- Intermediate summaries.
- Generated reports.
- Session-specific scratch files when a request includes a thread, run, or session identifier.

The workspace is not for:

- API keys.
- Tokens.
- Secrets.
- Long-lived customer data that should be stored in a governed system.

The local default workspace is ignored by Git. In Hosted Agent sessions, files under `$HOME/work` are session-scoped and can persist across turns and idle resume.

## The Runtime Entry Point

`backend/main.py` does five important things.

1. Loads environment variables with `python-dotenv`.
2. Normalizes App Insights connection string environment variables.
3. Validates Claude-on-Foundry configuration.
4. Builds a telemetry-enabled `ClaudeAgent` with Claude Agent SDK options.
5. Exposes that agent through `from_agent_framework(...).run(port=port)`.

The important implementation details are:

- `PROJECT_ROOT` is `backend/`.
- `cwd` is set to `backend/` so `.claude` project files are available.
- `setting_sources` is set to `project` so project-level Claude settings apply.
- `allowed_tools` centralizes the built-in tools that the Main Agent can use.
- `permission_mode` defaults to `dontAsk` for hosted execution.
- `ClaudeAgent` includes Microsoft Agent Framework telemetry support through `AgentTelemetryLayer`.
- `_patch_foundry_agent_identity()` fills trace identity fields when the request does not provide an agent reference.

The server defaults to `http://localhost:8088/responses`.

## Environment Variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `CLAUDE_CODE_USE_FOUNDRY` | Yes | Enables Claude Code / Claude Agent SDK model calls through Foundry. Defaults to `1`. |
| `ANTHROPIC_FOUNDRY_RESOURCE` | One of resource or base URL | Foundry resource name. |
| `ANTHROPIC_FOUNDRY_BASE_URL` | One of resource or base URL | Explicit Anthropic-on-Foundry endpoint. Takes precedence in many setups. |
| `ANTHROPIC_FOUNDRY_API_KEY` | Development fallback | API-key authentication for local development. Leave unset when using Entra-compatible auth. |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | Recommended | Deployment pin for Sonnet. Missing pins produce warnings. |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | Recommended | Deployment pin for Opus. |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | Recommended | Deployment pin for Haiku. |
| `CLAUDE_MODEL` | No | Which model family the agent asks Claude Code to use. Defaults to `sonnet`. |
| `CLAUDE_MAX_TURNS` | No | Maximum agent turns. Defaults to `12`. |
| `CLAUDE_EFFORT` | No | Effort level: `low`, `medium`, `high`, `max`, or `auto`. Defaults to `high`. |
| `CLAUDE_PERMISSION_MODE` | No | Claude tool permission mode. Defaults to `dontAsk`. |
| `CLAUDE_CODE_USE_POWERSHELL_TOOL` | No | Uses PowerShell-oriented shell behavior on Windows. Defaults to `1`. |
| `CLAUDE_WORKSPACE_ROOT` | No | Workspace root for artifacts. Local examples use `work`; Hosted Agent manifests use `$HOME/work` so files are under the session-persisted home directory. |
| `PORT` | No | Local HTTP port. Defaults to `8088`. |
| `APPINSIGHTS_CONNECTION_STRING` | No | App Insights export connection string. |
| `AZURE_MONITOR_CONNECTION_STRING` | No | Alternative connection string name normalized at startup. |

Use `backend/.env.example` as the starting point for local development.

## Local Development Walkthrough

From the repository root:

```powershell
Set-Location backend
python -m venv ..\.venv
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and fill at least one Foundry target plus your model deployment values.

For API-key development, the minimum useful values are:

```env
CLAUDE_CODE_USE_FOUNDRY=1
ANTHROPIC_FOUNDRY_BASE_URL=https://<resource>.services.ai.azure.com/anthropic
ANTHROPIC_FOUNDRY_API_KEY=<your-key>
ANTHROPIC_DEFAULT_SONNET_MODEL=<deployment-name>
CLAUDE_MODEL=sonnet
CLAUDE_WORKSPACE_ROOT=work
```

Run static checks that do not require a live Foundry call:

```powershell
..\.venv\Scripts\python.exe -m compileall main.py src
..\.venv\Scripts\python.exe -c "import main; print(main.FOUNDRY_AGENT_NAME)"
```

Start the local server:

```powershell
..\.venv\Scripts\python.exe main.py
```

Expected startup behavior:

- The server logs the Foundry target and authentication mode.
- The `work/` directory is created if it does not already exist.
- The server listens on `http://localhost:8088/responses` unless `PORT` is set.
- Startup can take 30 to 60 seconds while Azure credentials, project connections, and telemetry exporters initialize.
- If App Insights is not configured, telemetry export is disabled but the server can still run.

Check readiness before sending prompts:

```powershell
curl.exe --silent --show-error --fail --retry 40 --retry-connrefused --retry-delay 2 http://localhost:8088/readiness
```

## Running the Demo

The demo input is `backend/samples/bad-config/azure-export.json`. It intentionally contains issues that should trigger all three review dimensions.

When calling the running agent, use `samples/bad-config/azure-export.json` because `backend/main.py` sets the agent working directory to `backend/`.

Security signals include:

- Public blob access.
- TLS drift.
- HTTPS-only disabled.
- Open RDP from the Internet.

Cost signals include:

- A development VM using a relatively large SKU.
- Always-on capacity without utilization context.
- SQL capacity that should be validated against workload needs.

Architecture signals include:

- Missing availability configuration.
- Zone redundancy disabled.
- Local backup redundancy.
- Empty diagnostic settings.

A useful prompt is:

```text
samples/bad-config/azure-export.json を分析して、security / cost / architecture の固定JSONスキーマで結果を返してください。必要なら explore-agent で先に棚卸ししてください。
```

For a quick local smoke test, call the non-streaming responses endpoint and read the last output text. The response can contain multiple assistant messages because Claude may emit a short preface before the final answer.

```powershell
$prompt = 'samples/bad-config/azure-export.json を Read で読み、WebSearch と WebFetch と Agent ツールは使わず、見えているJSONだけを根拠に summary/security/cost/architecture の固定JSONだけを返してください。説明文は不要です。'
$body = @{ input = $prompt; stream = $false } | ConvertTo-Json -Depth 8
$response = Invoke-RestMethod -Uri http://localhost:8088/responses -Method Post -ContentType 'application/json' -Body $body
$texts = @($response.output | ForEach-Object { $_.content } | ForEach-Object { $_.text } | Where-Object { $_ })
$texts[-1]
```

To verify SubAgent routing without running a full review, use a smaller exploration prompt:

```powershell
$prompt = 'samples/bad-config/azure-export.json を explore-agent で棚卸ししてください。最終回答は resource count by provider/type だけを JSON で返してください。'
```

When reviewing the result, check for:

- A `summary` object with counts.
- Security findings with non-empty `severity`, `resource`, `finding`, and `remediation`.
- Cost findings tied to specific resources rather than generic advice.
- Architecture findings mapped to a Well-Architected pillar.
- Clear uncertainty when utilization data or workload intent is missing.

## What to Look For in a Live Demo

A strong Part A demo shows the harness behavior, not only the final answer.

| Moment | What to Explain |
| --- | --- |
| Startup | The backend is a custom Python service, but it is exposed through Microsoft Agent Framework for Hosted Agent compatibility. |
| Prompt | The user asks for an Azure export review, not a scripted workflow. |
| Exploration | `explore-agent` gives the Main Agent a compact inventory before specialist review. |
| Specialist review | Security, cost, and architecture concerns stay in separate contexts. |
| Synthesis | The Main Agent merges specialist output into the fixed schema. |
| Workspace | Intermediate and generated artifacts belong under `CLAUDE_WORKSPACE_ROOT`. |
| Telemetry | `ClaudeAgent` and the Part B tracing helper are ready for MAF telemetry export when App Insights is configured. |

## Deploying as a Hosted Agent

Deployment is covered in [deploy-hosted-agent.md](deploy-hosted-agent.md). The short version is:

```powershell
# If missing: azd ext install azure.ai.agents
azd ext upgrade azure.ai.agents
azd auth login
azd ai agent init -m ..\backend\agent.yaml
azd provision
azd deploy
```

Use `azure.ai.agents` `0.1.40-preview` or later when continuing into the Agent Optimizer B4 flow.

The manifest `backend/agent.yaml` declares:

- Hosted agent kind.
- Responses protocol support.
- Foundry and Claude environment variables.
- Model deployment pins.
- `CLAUDE_WORKSPACE_ROOT=$HOME/work` for Hosted Agent session-persisted files.

The metadata file `backend/.foundry/agent-metadata.yaml` is not the deployment source of truth. It records design intent and implementation status for reviewers.

## Current Implementation Status

| Capability | Status | Where to Look |
| --- | --- | --- |
| Claude SDK agent loop | Implemented | `backend/main.py`. |
| Microsoft Agent Framework bridge | Implemented | `from_agent_framework(...)` in `backend/main.py`. |
| Responses protocol entry | Implemented | `backend/agent.yaml`. |
| Explore, security, cost, architecture SubAgents | Implemented | `backend/.claude/agents/`. |
| Azure review Skills | Implemented | `backend/.claude/skills/`. |
| Fixed output contract | Implemented | `backend/src/agent/runtime_contracts.py`. |
| Workspace root contract | Implemented | `backend/src/agent/workspaces.py`. |
| App Insights connection normalization | Implemented | `_configure_observability_environment()` in `backend/main.py`. |
| Hosted Agent trace identity patch | Implemented | `_patch_foundry_agent_identity()` in `backend/main.py`. |
| Approval checkpoint | Planned | Part B ACS runtime or MAF middleware. |
| Invocations protocol | Planned | Useful for batch JSON-in / JSON-out scenarios. |
| Managed Identity / OBO hardening | Planned | Production Azure access path. |

## Troubleshooting

| Symptom | Likely Cause | What to Check |
| --- | --- | --- |
| `Microsoft Foundry is not configured` | No Foundry target was provided. | Set `ANTHROPIC_FOUNDRY_RESOURCE` or `ANTHROPIC_FOUNDRY_BASE_URL`. |
| Model calls use the wrong deployment | Model pins are missing or mismatched. | Check `ANTHROPIC_DEFAULT_SONNET_MODEL` and related model variables. |
| SubAgents are not found | Process working directory is wrong or `.claude` files are missing from the container. | Confirm `cwd` is `backend/` and Docker copies the full backend directory. |
| No telemetry appears | App Insights connection string is missing. | Set `APPINSIGHTS_CONNECTION_STRING` or `AZURE_MONITOR_CONNECTION_STRING`. |
| Generated files are hard to find | Workspace root is different from expected. | Check `CLAUDE_WORKSPACE_ROOT`; local relative paths resolve under `backend/`, while Hosted Agent files should be under `$HOME/work`. |
| Agent gives generic recommendations | Input lacks evidence or prompt did not point at the sample file. | Use the bad-config prompt and ask for resource-specific findings. |
| Local request appears to return only a preface | The responses payload can include multiple output messages. | Inspect all `response.output[*].content[*].text` values or read the last text item. |
| Readiness fails immediately after startup | Azure credential and project connection discovery is still running. | Retry `/readiness`; local startup often takes 30 to 60 seconds. |
| Server import fails with missing packages | Dependencies are not installed in the active environment. | Run `pip install -r backend/requirements.txt` in the selected virtual environment. |

## How to Extend Part A Safely

Keep the two harness layers separate when extending the repository.

Good Part A extensions:

- Add a new SubAgent definition under `backend/.claude/agents/` for a focused review area.
- Add a new Skill under `backend/.claude/skills/` for reusable Azure guidance.
- Add request preprocessing in a runtime adapter while preserving the Claude Agent SDK loop.
- Add a MAF workflow sample that treats the Claude agent as one node.
- Add a Hosted Agent invocation path for batch-style input.
- Add better workspace artifact conventions under `CLAUDE_WORKSPACE_ROOT`.

Avoid these moves unless there is a strong reason:

- Reimplementing the tool-use loop in Python.
- Hardcoding Azure policy knowledge directly into `backend/main.py`.
- Mixing evaluation or guardrail logic into the Main Agent's reasoning instructions.
- Giving every SubAgent every tool by default.
- Writing secrets or credentials into the workspace.

## Path Toward Part B

Part A intentionally leaves clean attachment points for Part B.

| Part B Need | Part A Attachment Point |
| --- | --- |
| Tracing | `ClaudeAgent`, MAF telemetry, and `backend/src/agent/observability/tracing.py`. |
| Evaluation | Stable output contract from `runtime_contracts.py`. |
| Control | Tool permissions today, ACS or middleware checkpoint later. |
| ROI | `summary`, `cost[].estimatedSavings`, execution duration, and token data later. |
| Trace replay | Consistent run, SubAgent, and tool boundaries. |

The important design rule is that Part B should observe and control the agent from the side, not bury operational policy inside the specialist prompts.

## Quick Review Checklist

Before you demo or open a pull request for Part A, check:

- `backend/main.py` imports successfully.
- `python -m compileall backend/main.py backend/src` passes from the repository root.
- `backend/.env.example` includes every environment variable referenced by the docs.
- `backend/agent.yaml` includes Hosted Agent runtime values that must exist in deployment.
- The bad-config prompt produces resource-specific findings.
- The response preserves `summary`, `security`, `cost`, and `architecture`.
- No generated files under `backend/work/` are committed.
- README links point to this guide rather than to external planning notes.
