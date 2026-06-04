# Deploying the Backend as a Microsoft Foundry Hosted Agent

This document gives a high-level walkthrough for deploying the `backend/` agent in this repository as a **Microsoft Foundry Hosted Agent** using the **Azure Developer CLI (`azd`)** and its `azure.ai.agents` extension.

For the latest options, parameters, regional availability, and troubleshooting, always refer to the official documentation:

- [Quickstart: Create a hosted agent (azd)](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent?pivots=azd)
- [Microsoft Foundry Hosted Agents (concepts)](https://learn.microsoft.com/azure/ai-foundry/agents/concepts/hosted-agents?view=foundry)

This file only describes the rough end-to-end flow, in the order you typically run it.

## Prerequisites

- Azure subscription with permission to create AI Foundry resources
- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) installed
- Docker Desktop (or another OCI-compatible builder) running locally — required for building the hosted agent container image
- An Anthropic Claude deployment on Microsoft Foundry, and either an API key for development or an Entra / Managed Identity path for production hardening

## Repository Layout Used by the Walkthrough

- `backend/` — Hosted agent source: `Dockerfile`, `main.py`, `requirements.txt`, `agent.yaml`, `.claude/`, `src/agent/`, and `.foundry/agent-metadata.yaml`
- A working directory (e.g. `work-foundry-init/`) created and managed by `azd ai agent init` — this is where `azure.yaml`, `infra/`, and `.azure/` live

You will run all `azd` commands from inside this working directory.

## 1. Prepare the `azd` Environment

Make sure `azd` and the AI Agents extension are up to date, then sign in.

```powershell
azd version
azd ext list
azd ext upgrade azure.ai.agents
azd auth login
```

## 2. Initialize the Hosted Agent Project

From the working directory you want `azd` to manage (for example `work-foundry-init/`), point `azd ai agent init` at the agent definition under `backend/`:

```powershell
azd ai agent init -m ..\backend\agent.yaml
```

This scaffolds `azure.yaml`, the Bicep templates under `infra/`, and the `.azure/<env-name>/` folder that holds environment values.

## 3. Set Runtime Values in the azd Environment

> **Don't skip this step.** The hosted agent reads `ANTHROPIC_FOUNDRY_API_KEY` from the `azd` environment at deploy time. The key is intentionally **not** committed to `backend/agent.yaml` — only the variable reference is.

Open the generated `.azure/<env-name>/.env` and add your key if you are using API-key authentication during development:

```env
ANTHROPIC_FOUNDRY_API_KEY=<your-foundry-anthropic-api-key>
```

Other values in this `.env` file (project endpoint, App Insights connection string, ACR endpoint, etc.) are populated automatically by `azd provision`.

The manifest also sets `CLAUDE_WORKSPACE_ROOT=$HOME/work`. Hosted Agents persist session state under `$HOME` and `/files`, so this keeps normalized exports, intermediate summaries, and generated reports in the same filesystem surface that the Foundry Portal Files view exposes. Local `.env` files can still use `CLAUDE_WORKSPACE_ROOT=work`, which resolves under the backend project directory.

Custom environment variables in `agent.yaml` must not use the `AGENT_` or `FOUNDRY_` prefixes. Those prefixes are reserved by the Hosted Agent container image specification, and Foundry rejects deployments that try to set them.

For production hardening, move Azure resource access toward Entra ID, Managed Identity, or OBO. The current API key is only the development fallback for Claude-on-Foundry model access.

## 4. Provision Azure Resources

Create the AI Foundry account, project, container registry, and supporting resources:

```powershell
azd provision
```

## 5. Deploy the Hosted Agent

Build the agent container image, push it to the provisioned ACR, and register / update the hosted agent on Foundry:

```powershell
azd deploy
```

Re-run `azd deploy` whenever you change code under `backend/` or values in `agent.yaml`.

## 6. Invoke the Agent

After a successful deploy, the agent endpoint is written to `.azure/<env-name>/.env` as `AGENT_<NAME>_ENDPOINT`. Use `azd ai agent run`, the Foundry portal, or call the `/responses` endpoint directly to test it.

See the [official quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent?pivots=azd) for current invocation samples.

For a repeatable Part A smoke prompt, use `samples/bad-config/azure-export.json` and ask the agent to return the fixed `summary`, `security`, `cost`, and `architecture` JSON contract. The sample lives under `backend/` so it is included in the hosted container.

For the main Hosted Agent acceptance test, pass the Azure export JSON in the Portal, API, or SDK request body instead of only asking the agent to read the bundled sample file. The bundled file proves container packaging and file-tool behavior; inline JSON proves the Hosted Agent request boundary. See [hosted-agent-test-plan.md](hosted-agent-test-plan.md) for the full verification matrix and concrete prompts.

## Runtime Notes

- `backend/main.py` keeps the process working directory at `backend/` so Claude Code project settings, `.claude` agents, and Skills remain discoverable.
- `CLAUDE_WORKSPACE_ROOT` controls where the agent should write intermediate artifacts. Local `work` resolves under the backend project directory; hosted deployments should use `$HOME/work` so artifacts are session-persisted and visible under the portal's HOME file tree.
- `APPINSIGHTS_CONNECTION_STRING` or `AZURE_MONITOR_CONNECTION_STRING` is normalized to `APPLICATIONINSIGHTS_CONNECTION_STRING` so the telemetry layer can export consistently.
- `backend/.foundry/agent-metadata.yaml` is a design metadata file. The deployment source of truth for `azd ai agent init` remains `backend/agent.yaml`.

## Typical Iteration Loop

Once initial provisioning is done, day-to-day iteration is just:

1. Edit code under `backend/`
2. `azd deploy`
3. Re-run the Part A smoke test, inline JSON acceptance test, explore-agent routing test, and trace check from [hosted-agent-test-plan.md](hosted-agent-test-plan.md)
