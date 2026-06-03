# Azure Well-Architected Review Agent Accelerator on Foundry

This repository is a reference accelerator for running a **Claude Agent SDK** based Azure resource review agent as a **Microsoft Foundry Hosted Agent**.

The sample scenario is an Azure Well-Architected review workflow. The agent reads Azure exports, ARM-style JSON, or resource configuration snapshots, then returns security findings, cost recommendations, and architecture guidance through a stable output contract.

The current implementation focuses on **Part A: Harness Deep Dive**, which shows how to build and host the agent while preserving the Claude Agent SDK runtime model. Start with [docs/harness-deepdive.md](docs/harness-deepdive.md) if you want the detailed implementation walkthrough.

## What This Repository Demonstrates

- Claude Agent SDK as the inner harness for agent loop, SubAgents, Skills, built-in tools, and context handling
- Microsoft Agent Framework as the bridge that exposes the Claude agent to the Hosted Agent runtime
- Microsoft Foundry Hosted Agent as the outer managed harness for endpoint hosting, sandbox execution, state boundaries, telemetry, and future identity / guardrail integration
- A fixed Azure analysis output schema that Part B can later use for evaluation, control, optimization, and ROI
- A deliberately weak Azure export under `backend/samples/bad-config/` for repeatable demos

## Current Architecture

```text
User / client
  -> Microsoft Foundry Hosted Agent responses endpoint
  -> backend/main.py
  -> Microsoft Agent Framework adapter
  -> Claude Agent SDK loop
  -> .claude Main Agent instructions
  -> explore-agent, security-analyzer, cost-optimizer, architecture-reviewer
  -> Azure WAF / security / cost Skills
  -> stable JSON analysis contract
```

The architecture is described in more detail in [docs/architecture.md](docs/architecture.md). Part A is documented in [docs/harness-deepdive.md](docs/harness-deepdive.md).

## Repository Layout

```text
backend/
  main.py                         # Hosted Agent entrypoint and MAF bridge
  agent.yaml                      # azd / Hosted Agent manifest
  CLAUDE.md                       # Main Agent project instructions
  src/agent/
    runtime_contracts.py          # Stable output schema and prompt contract
    workspaces.py                 # Hosted workspace root helper
  .claude/
    agents/                       # Explore, security, cost, architecture SubAgents
    skills/                       # Azure WAF, security, and cost guidance
  .foundry/
    agent-metadata.yaml           # Design metadata for Hosted Agent behavior
  samples/
    bad-config/azure-export.json  # Demo input included in the hosted container
docs/
  architecture.md
  harness-deepdive.md
  deploy-hosted-agent.md
```

## Agent Design

The Main Agent coordinates four specialist SubAgents:

| SubAgent | Responsibility |
| --- | --- |
| `explore-agent` | Inventories files, resource types, and high-signal configuration facts before deeper review. |
| `security-analyzer` | Reviews public exposure, encryption, identity, authentication, and network controls. |
| `cost-optimizer` | Reviews oversized resources, always-on spend, premium SKUs, and elasticity gaps. |
| `architecture-reviewer` | Reviews reliability, operational readiness, observability, and Well-Architected alignment. |

Skills under `backend/.claude/skills/` provide progressive context loading for Azure WAF, security baselines, and cost patterns.

## Expected Analysis Output

Azure analysis should preserve this contract:

```json
{
  "summary": { "resourcesAnalyzed": 25, "securityFindings": 12, "costSavingsOpportunities": 8 },
  "security": [ { "severity": "Critical", "resource": "...", "finding": "...", "remediation": "..." } ],
  "cost": [ { "resource": "...", "recommendation": "...", "estimatedSavings": "$15/month" } ],
  "architecture": [ { "pillar": "Operational Excellence", "finding": "...", "recommendation": "..." } ]
}
```

The contract is centralized in `backend/src/agent/runtime_contracts.py` and appended to the runtime prompt in `backend/main.py`.

## Local Development

From the repository root:

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Configure Foundry access through `backend/.env` or environment variables:

```env
CLAUDE_CODE_USE_FOUNDRY=1
ANTHROPIC_FOUNDRY_BASE_URL=https://<resource>.services.ai.azure.com/anthropic
ANTHROPIC_FOUNDRY_API_KEY=<your-key>
ANTHROPIC_DEFAULT_SONNET_MODEL=<deployment-name>
CLAUDE_MODEL=sonnet
AGENT_WORKSPACE_ROOT=work
```

Start the local responses server:

```powershell
python main.py
```

The default endpoint is `http://localhost:8088/responses`.

## Demo Prompt

Use the included weak Azure export. The path is relative to the backend working directory used by the agent:

```text
samples/bad-config/azure-export.json を分析して、security / cost / architecture の固定JSONスキーマで結果を返してください。必要なら explore-agent で先に棚卸ししてください。
```

## Deployment

Deploy the backend as a Foundry Hosted Agent with `azd ai agent init`, `azd provision`, and `azd deploy`. See [docs/deploy-hosted-agent.md](docs/deploy-hosted-agent.md).

After deployment, validate both input paths: the bundled fixture smoke test and the inline JSON request test. See [docs/hosted-agent-test-plan.md](docs/hosted-agent-test-plan.md) for the Hosted Agent verification checklist and concrete prompts.

## Status and Roadmap

| Area | Status |
| --- | --- |
| Part A inner harness | Implemented: Claude Agent SDK loop, SubAgents, Skills, built-in tools. |
| Part A outer harness | Implemented: MAF bridge, responses manifest, telemetry setup, workspace contract. |
| Part A next steps | Approval checkpoint, Invocations protocol, MAF workflow sample, identity hardening. |
| Part B | Planned: tracing helpers, ASSERT/Rubric assets, ACS policy, ROI metrics. |
| Frontend | Planned. |

## References

- [Claude Agent SDK Documentation](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Claude in Microsoft Foundry](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry)
- [Microsoft Foundry Documentation](https://learn.microsoft.com/en-us/azure/foundry/)
- [Microsoft Foundry Hosted Agents](https://learn.microsoft.com/azure/ai-foundry/agents/concepts/hosted-agents?view=foundry)
- [Model Context Protocol](https://modelcontextprotocol.io/)

## License

MIT License. See [LICENSE](LICENSE) for details.
