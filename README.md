# Claude Agent SDK on Microsoft Foundry Hosted Agent

A reference implementation for running agents built with the **Claude Agent SDK** as **Microsoft Foundry Hosted Agents**.

This repository uses an Azure resource analysis agent as the sample scenario. It demonstrates how to build agentic AI workflows that take advantage of the Claude Agent SDK's core strengths: **SubAgents, Skills, built-in tools, context management, and MCP integration**, while running the agent on Microsoft Foundry.

> The initial scope is **backend only**. The frontend, docs, and example directories are planned for later. To make the agent easy to host as a Foundry Hosted Agent, the Python backend, source code, and `.claude` agent definitions are kept together under `backend/`.

## What This Repository Builds

This sample builds an **Azure Resource Analysis Agent** that analyzes Azure infrastructure configurations and returns security, cost, and architecture recommendations.

The agent is designed to:

- Read Azure resource definitions, ARM templates, and configuration JSON
- Identify security risks and propose remediation steps
- Find cost optimization opportunities and estimate potential savings
- Evaluate configurations against the Azure Well-Architected Framework
- Delegate exploration, security analysis, and cost analysis to specialized SubAgents
- Run as a Microsoft Foundry Hosted Agent, using Foundry as the hosting layer for a custom-framework agent

## Why Microsoft Foundry Hosted Agent?

Microsoft Foundry Hosted Agent lets you host agents implemented with arbitrary frameworks on Foundry.

In this repository, a custom agent backend built with the Claude Agent SDK is hosted as a **Foundry Hosted Agent**.

This approach is intended to provide:

- **Framework flexibility**: Run a Claude Agent SDK agent as a Foundry Hosted Agent
- **Integrated operations**: Bring agent execution, evaluation, observability, and lifecycle management into Foundry
- **Unified model and runtime platform**: Combine Claude model deployments on Microsoft Foundry with Hosted Agent execution
- **A simple path for future expansion**: Add frontend, docs, and example assets later without changing the backend boundary
- **Enterprise-ready operations**: Integrate more naturally with Azure identity, networking, monitoring, and governance

## Target Architecture

```text
User / Client
    |
    | request
    v
Microsoft Foundry Hosted Agent
    |
    | hosts custom Python backend
    v
backend/
  Python Agent API / runtime adapter
  Claude Agent SDK application
  .claude agent definitions
  Skills and MCP tools
    |
    | model calls
    v
Microsoft Foundry Claude model deployment
```

The Hosted Agent hosts the custom backend. The backend is responsible for running the Claude Agent SDK application, including the `query()` execution flow, SubAgent definitions, Skills, and MCP tools.

## Planned Project Structure

The long-term goal is a simple repository structure that is easy to understand at a glance.

```text
backend/
  src/
    agent/
      main_agent.py
    skills/
      azure_waf.py
    observability/
      tracing.py
      evaluation.py
    server.py
  .claude/
    CLAUDE.md
    agents/
      explore-agent.md
      security-analyzer.md
      cost-optimizer.md
    skills/
      azure-well-architected/
        SKILL.md
  .foundry/
    agent-metadata.yaml
  pyproject.toml

frontend/      # future: interactive UI
docs/          # future: architecture, demo, and deployment notes
example/       # future: sample Azure exports and test inputs
```

The first implementation target is `backend/` only. To make the project easy to host as a Foundry Hosted Agent, Python source code, Claude Agent SDK agent definitions, skills, and Foundry metadata are grouped under `backend/`.

## Sample Agent Design

The sample agent design intentionally highlights the value of the Claude Agent SDK.

```text
Main Agent
  |
  +-- Explore Agent
  |     - Explores input files and Azure resource configurations
  |     - Reads large JSON files and configuration data, then returns concise summaries
  |
  +-- Security Analyzer
  |     - Reviews security settings, exposure, authentication, and encryption
  |     - Produces severity, evidence, and remediation guidance
  |
  +-- Cost Optimizer
        - Reviews sizing, unused resources, and over-provisioning
        - Produces savings opportunities and estimates

Skills / MCP
  - Azure Well-Architected Framework guidance
  - Future integration with the MS Learn Docs MCP server
```

The Main Agent plans the overall analysis and delegates specialized work to SubAgents when appropriate. Each SubAgent works in an isolated context and returns only summarized findings to the parent agent.

## Why Claude Agent SDK?

### Built on the Same Runtime as Claude Code

The Claude Agent SDK is **the same agent runtime that powers Claude Code**, packaged as a library for Python and TypeScript. Anthropic explicitly describes it as providing "the same tools, agent loop, and context management that power Claude Code, programmable in Python and TypeScript."

This matters because Claude Code is one of the most heavily used agentic products in the world, and its agent loop, tool design, context management, and SubAgent model are continuously refined against real developer workloads. By adopting the Claude Agent SDK, you can bring that proven agent design directly into your own agent without reinventing the core loop.

In practice this means:

- The agent loop, tool routing, SubAgent boundaries, and context handling are battle-tested in Claude Code, not built from scratch in your project.
- Patterns that work well in Claude Code (CLAUDE.md, SubAgents, Skills, MCP servers) transfer directly to your agent.
- New SDK improvements (model support, context handling, tool behavior) flow into your agent through SDK upgrades.

This significantly raises the chance of building a successful, production-quality agent, because you start from a runtime that is already proven to work for autonomous, multi-step, tool-using workflows.

### Context as a First-Class Concern

The Claude Agent SDK is not just another agent orchestration framework. It is an agent runtime designed around one of the hardest problems in agentic AI: **managing LLM context effectively**.

Many frameworks, such as LangGraph or AutoGen, are strong at state transitions and graph orchestration. The Claude Agent SDK focuses on the operational problems that appear when agents handle long inputs, large tool outputs, SubAgent boundaries, and domain knowledge that should only be loaded when needed.

### Key Differentiators

| Feature | Claude Agent SDK | Typical Orchestration Frameworks |
|---------|------------------|----------------------------------|
| Agent loop | Claude autonomously plans, calls tools, and iterates inside the SDK | The tool-call loop is often implemented by the application |
| Context isolation | SubAgents can work in separate contexts | State and context management often need custom design |
| Automatic compaction | Large tool outputs are easier to handle through the runtime | Truncation and chunking are often implemented manually |
| Built-in tools | Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, AskUserQuestion, and more are available out of the box | Tool handlers are often implemented one by one |
| Progressive context loading | Skills can be loaded only when needed | Domain knowledge is often packed into the system prompt upfront |
| MCP native | MCP servers are easy to connect | Integrations are often custom-built |
| Hooks | Lifecycle hooks let you observe and intercept agent execution events | Cross-cutting concerns are often bolted on |
| Permissions | Tool access can be controlled declaratively (`allowed_tools`, etc.) | Access control is often implemented per tool |
| Sessions | Conversations can be resumed and continued across turns | Session and history handling is often custom |

## Claude Agent SDK Capabilities Demonstrated

### 1. Autonomous Agent Loop

With the Anthropic Client SDK, the application is responsible for implementing the tool-use loop: send a prompt, parse the response, execute tool calls, send the results back, and repeat.

With the Claude Agent SDK, this loop is provided by the runtime. The application calls `query()` and the SDK drives the planning, tool selection, tool execution, and iteration until the agent finishes the task. This is the same agent loop that powers Claude Code.

For this sample, that means the Main Agent can autonomously decide when to delegate to a SubAgent, when to call a Skill, and when to read input files, without the backend implementing a custom orchestration loop.

### 2. Context Isolation with SubAgents

Azure resource analysis mixes many kinds of information: input JSON, resource configuration, security posture, cost signals, and architectural guidance.

With Claude Agent SDK SubAgents, exploration, security analysis, and cost analysis can run in separate contexts. Each SubAgent can go deep in its own area, while the Main Agent receives summarized results and synthesizes the final report.

This helps keep the parent agent's context lean and preserves analysis quality as the input grows.

### 3. Built-in Tools

The Claude Agent SDK provides a set of built-in tools that work without any handler implementation on the application side. The most relevant ones for this sample include:

| Tool | Purpose |
|------|---------|
| `Read` | Read files in the working directory (input JSON, configurations, ARM templates) |
| `Write` | Create new files (analysis output, intermediate artifacts) |
| `Edit` | Make precise edits to existing files |
| `Bash` | Run shell commands and scripts |
| `Glob` | Find files by pattern, useful for navigating large input sets |
| `Grep` | Search file contents with regex |
| `WebSearch` | Look up current information on the web |
| `WebFetch` | Fetch and parse a specific web page |
| `AskUserQuestion` | Ask the user a clarifying question with multiple-choice options |

In this sample, the Explore Agent is expected to use Read, Glob, and Grep to navigate input files and configuration data, then extract only the information needed for downstream analysis. This reduces tool-handler implementation work and keeps the focus on agent instructions and analysis logic.

### 4. Progressive Context Loading with Skills

Domain knowledge such as the Azure Well-Architected Framework can quickly bloat a system prompt if it is always loaded upfront.

By defining this knowledge as Skills, the agent can load relevant guidance only when needed, such as security, cost, reliability, operational excellence, or performance guidance.

### 5. MCP Integration

The Claude Agent SDK is designed to work naturally with MCP, making it easier to connect agents to external tools and knowledge sources.

This sample treats Azure Well-Architected Framework guidance as MCP-accessible tooling. In the future, it can be extended with the MS Learn Docs MCP server so the agent can reference the latest Azure documentation during analysis.

### 6. Hooks

The Claude Agent SDK exposes lifecycle hooks for agent execution events, such as tool calls, SubAgent transitions, and message turns.

This sample uses hooks as the integration point for tracing and evaluation, so observability concerns can be implemented as cross-cutting concerns rather than being scattered through the agent code.

### 7. Permissions

Tool access in the Claude Agent SDK is explicitly controlled, for example through `allowed_tools` (Python) or the equivalent option in TypeScript.

For a Hosted Agent that runs in an enterprise environment, this gives a clear way to limit what the agent can do, scope tool usage to what each SubAgent actually needs, and reduce the blast radius of unexpected tool invocations.

### 8. Sessions

The Claude Agent SDK supports session continuation, so a conversation can be resumed across multiple turns rather than always starting from scratch.

This is important when running as a Foundry Hosted Agent, where a client may issue multiple related requests against the same logical conversation, and the backend needs to preserve agent state in a consistent way.

### 9. Large Context Handling

Azure subscription exports can become large quickly as the number of resources grows.

By combining Claude Agent SDK context management, SubAgents, and automatic compaction, the agent can process larger inputs while keeping the Main Agent's working context organized.

## Why Claude Models?

Claude models are well suited for agentic workflows that require structured data understanding, long-context reasoning, and multi-step analysis.

| Capability | Why It Matters |
|------------|----------------|
| Long context | Helps process large Azure resource exports and ARM templates |
| Technical accuracy | Important when reading JSON, infrastructure settings, and cloud configurations |
| Multi-step reasoning | Supports exploration, classification, analysis, prioritization, and remediation generation |
| Structured output | Makes it easier to produce JSON or report-style analysis results |
| Low hallucination tendency | Important because incorrect infrastructure recommendations can be costly |

## When To Use This Pattern

This pattern is a good fit when you need to:

- Analyze large configuration files, logs, or exported infrastructure data
- Split analysis across multiple specialized perspectives
- Let an agent investigate autonomously using tools
- Centralize model hosting, agent hosting, evaluation, and observability in Microsoft Foundry
- Prioritize LLM context management over graph orchestration mechanics

For simple question-answering scenarios or fixed API workflows, this architecture may be more than you need.

## Microsoft Foundry Integration

This sample uses Microsoft Foundry for:

- **Claude model deployment**: Use Claude models deployed on Foundry
- **Hosted Agent**: Host the Python backend as a custom-framework agent
- **Agent lifecycle**: Manage deployment, updates, invocation, evaluation, and monitoring through Foundry
- **Observability**: Connect tracing, evaluation, and monitoring workflows

The backend hosted as a Foundry Hosted Agent is implemented as a Python service with a clear request/response boundary for the Foundry agent runtime.

## Backend First Implementation Plan

The first implementation target is backend only.

1. Create the minimal Python backend scaffold
2. Implement the Claude Agent SDK Main Agent
3. Place `.claude/CLAUDE.md` and SubAgent definitions under `backend/`
4. Add an Azure Well-Architected Framework skill
5. Support analysis of a sample Azure resource export
6. Provide an entrypoint suitable for Foundry Hosted Agent hosting
7. Add the foundation for tracing and evaluation

The frontend will be added later. Initially, backend behavior will be validated through an API or Hosted Agent invocation.

## Expected Analysis Output

The final analysis result is expected to follow a structure like this:

```json
{
  "summary": {
    "resourcesAnalyzed": 25,
    "securityFindings": 12,
    "costSavingsOpportunities": 8
  },
  "security": [
    {
      "severity": "Critical",
      "resource": "Storage Account: proddata001",
      "finding": "Public blob access is enabled.",
      "remediation": "Disable public blob access and restrict network access."
    }
  ],
  "cost": [
    {
      "resource": "VM: dev-webserver-01",
      "recommendation": "Downsize or schedule shutdown for non-production workloads.",
      "estimatedSavings": "$15/month"
    }
  ],
  "architecture": [
    {
      "pillar": "Operational Excellence",
      "finding": "Monitoring configuration is incomplete.",
      "recommendation": "Enable diagnostic settings and centralize logs."
    }
  ]
}
```

## Configuration

To use Claude on Microsoft Foundry, the backend needs configuration for the Claude deployment hosted in Foundry.

```env
CLAUDE_CODE_USE_FOUNDRY=1
ANTHROPIC_FOUNDRY_API_KEY=your_foundry_api_key_here
ANTHROPIC_FOUNDRY_RESOURCE=your-resource-name
ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-4-5
```

For configurations that do not use an API key, this can be extended to use Microsoft Entra ID authentication or Managed Identity.

## Deployment

For a high-level walkthrough of deploying the `backend/` agent as a Microsoft Foundry Hosted Agent with `azd`, see [docs/deploy-hosted-agent.md](docs/deploy-hosted-agent.md). Detailed parameters and the latest options are covered in the [official quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent?pivots=azd).

## Roadmap

- [ ] Python backend scaffold
- [ ] Claude Agent SDK Main Agent implementation
- [ ] Main Agent, SubAgent, and Skill definitions under `.claude`
- [ ] Azure Well-Architected Framework skill
- [ ] Local analysis using sample Azure resource exports
- [ ] Foundry Hosted Agent entrypoint
- [ ] Initial tracing and evaluation implementation
- [ ] Frontend
- [ ] Expanded docs and example assets
- [ ] MS Learn Docs MCP server integration

## Use Cases

| Audience | Use Case |
|----------|----------|
| Solution Architects | Demonstrate the value of Claude Agent SDK and Microsoft Foundry Hosted Agent |
| Developers | Use as a reference for hosting arbitrary-framework agents on Foundry |
| Technical Decision Makers | Evaluate the combination of Claude models, Foundry, and Hosted Agent |
| Customer Success / PoC Teams | Use as a PoC accelerator for Azure + Claude agent scenarios |

## References

- [Claude Agent SDK Documentation](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Claude in Microsoft Foundry](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry)
- [Microsoft Foundry Documentation](https://learn.microsoft.com/en-us/azure/foundry/)
- [Microsoft Foundry Hosted Agents](https://learn.microsoft.com/azure/ai-foundry/agents/concepts/hosted-agents?view=foundry)
- [Microsoft Foundry Agent Runtime Components](https://learn.microsoft.com/azure/ai-foundry/agents/concepts/runtime-components?view=foundry)
- [Model Context Protocol](https://modelcontextprotocol.io/)

## License

MIT License. See [LICENSE](LICENSE) for details.

---

**Built with Claude Agent SDK. Hosted by Microsoft Foundry. Designed for enterprise agent workflows.**
