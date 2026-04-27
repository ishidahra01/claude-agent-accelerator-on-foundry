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
- An Anthropic Claude deployment on Microsoft Foundry, and its API key

## Repository Layout Used by the Walkthrough

- `backend/` — Hosted agent source: `Dockerfile`, `main.py`, `requirements.txt`, and `agent.yaml`
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

## 3. Set the Anthropic Foundry API Key in the azd Environment

> **Don't skip this step.** The hosted agent reads `ANTHROPIC_FOUNDRY_API_KEY` from the `azd` environment at deploy time. The key is intentionally **not** committed to `backend/agent.yaml` — only the variable reference is.

Open the generated `.azure/<env-name>/.env` and add your key:

```env
ANTHROPIC_FOUNDRY_API_KEY=<your-foundry-anthropic-api-key>
```

Other values in this `.env` file (project endpoint, App Insights connection string, ACR endpoint, etc.) are populated automatically by `azd provision`.

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

## Typical Iteration Loop

Once initial provisioning is done, day-to-day iteration is just:

1. Edit code under `backend/`
2. `azd deploy`
