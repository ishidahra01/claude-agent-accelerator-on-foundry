# Foundry Agent Optimizer Concepts

This document explains what Agent Optimizer uses as input, what happens during an optimization run, what it produces, and what must be prepared for this repository's Claude Hosted Agent.

Use [foundry-agent-optimizer.md](foundry-agent-optimizer.md) for the command-by-command runbook. Use this document to understand the moving parts before running it.

## The Short Version

Agent Optimizer is an evaluation-driven improvement loop for Hosted Agents.

For this accelerator, the loop is:

```text
baseline agent config
  + evaluation dataset
  + evaluators
  + eval model
  + optimization model
  -> baseline run
  -> candidate instruction overlays
  -> candidate evaluation runs
  -> ranked recommendation
  -> local apply
  -> diff review
  -> redeploy
```

Optimizer does not edit the main Claude project instructions or Skills directly in this repo. It improves a thin instruction overlay under `.claude/optimizer_configs/` and the runtime appends that overlay to the ClaudeAgent system prompt.

The official quickstart now uses the standard `.agent_configs/` layout and `azure.ai.agents` CLI extension `0.1.40-preview` or later. This repo still keeps `.claude/optimizer_configs/` as the reviewed source of truth; generated `.agent_configs/` files are treated as staging artifacts.

## What Optimizer Tries to Improve

Agent Optimizer can improve several target types in the Foundry preview, but this repo enables only the safest one by default.

| Target | This Repo | Why |
| --- | --- | --- |
| Instruction tuning | Enabled | Improves coordinator planning and synthesis without changing the core Claude project files. |
| Skill improvement | Not enabled by default | `.claude/skills/` is the Claude Code source of truth. Directly optimizing a copy would require manual merge discipline. |
| Tool optimization | Not enabled | The app uses Claude Code built-in tools, not OpenAI function tool definitions. |
| Model selection | Not enabled | ClaudeAgent runtime uses Claude aliases such as `sonnet`; Foundry GPT deployments are used for optimization/evaluation, not runtime model switching. |

The optimized surface is:

```text
.claude/optimizer_configs/baseline/instructions.md
```

The long-lived surfaces remain:

```text
CLAUDE.md
.claude/agents/
.claude/skills/
backend/src/agent/runtime_contracts.py
```

## Inputs

### 1. `eval.yaml`: The Optimization Job Spec

`eval.yaml` tells `azd ai agent optimize` what job to run.

Checked-in template path:

```text
backend/eval.yaml
```

Current shape:

```yaml
name: azure-waf-review-optimizer
agent:
  name: my-claude-agent
  kind: hosted
  version: "<deployed-agent-version>"
  model: <existing-eval-model-deployment>
  config: <relative-agent-root>/.claude/optimizer_configs/baseline/metadata.yaml
dataset_file: <relative-repo-root>/evals/datasets/bad-config.queries.jsonl
evaluators:
  - builtin.task_adherence
  - builtin.coherence
  - builtin.violence
```

The important fields are:

| Field | Purpose |
| --- | --- |
| `agent.name` | Hosted Agent to optimize. |
| `agent.version` | Baseline version for the optimization run. |
| `agent.model` | Foundry model deployment used by the optimizer job contract. It is not the Claude runtime model. |
| `agent.config` | Points to the baseline metadata file. The updated CLI resolves this from the azd project root. |
| `dataset_file` | JSONL tasks sent to the Hosted Agent during optimization. |
| `evaluators` | Metrics used to score baseline and candidates. |

`agent.config` and `dataset_file` are resolved by azd from the azd project root, not from the folder that contains `eval.yaml`. Replace the placeholder paths with paths relative to your generated azd project root.

With the updated CLI, `azd ai agent optimize` can auto-detect the agent and generated `eval.yaml` from the current azd environment. Explicit targeting is clearer for repeatable demos:

```powershell
azd ai agent optimize `
  --agent <hosted-agent-name> `
  --config <path-to-backend>\eval.yaml `
  --eval-model <existing-eval-model-deployment> `
  --optimize-model <existing-supported-optimization-model-deployment>
```

### 2. `metadata.yaml`: Baseline Config Metadata

`metadata.yaml` describes the local baseline config that Optimizer can rewrite.

Current path:

```text
.claude/optimizer_configs/baseline/metadata.yaml
```

Current shape:

```yaml
temperature: 0.2
instruction_file: instructions.md
```

The important fields are:

| Field | Purpose |
| --- | --- |
| `instruction_file` | Relative path to the instruction overlay Optimizer can rewrite. |
| `temperature` | Baseline generation setting for the optimizer config. |
| `skill_dir` | Omitted in this repo to avoid duplicating `.claude/skills/`. |
| `tool_file` | Omitted because Claude Code built-in tools are not OpenAI function definitions. |
| `model` | Omitted here to avoid confusing optimizer metadata with Claude runtime model. The optimizer job still gets `agent.model` from `eval.yaml`. |

The SDK accepts this metadata without `model`; `load_config(config_dir=...)` returns a config with `model=None`. Runtime model selection stays in `main.py`.

### 3. `instructions.md`: Optimizer Overlay

Current path:

```text
.claude/optimizer_configs/baseline/instructions.md
```

This file is intentionally short. It tells Optimizer what kind of coordinator behavior should improve:

- better Azure review planning;
- stronger evidence-grounded synthesis;
- fewer vague recommendations;
- preserved Japanese response behavior;
- preserved delegation to existing subagents.

It does not duplicate the stable JSON schema, workspace boundary, or hosted runtime constraints. Those are appended by application code so optimizer candidates cannot accidentally remove them.

### 4. Dataset JSONL

Current path:

```text
evals/datasets/bad-config.queries.jsonl
```

The dataset contains query rows. Optimizer invokes the Hosted Agent with each query and captures the generated response.

For this repo, the dataset asks the agent to review the bad-config Azure export fixture:

```text
backend/samples/bad-config/azure-export.json
```

The first dataset should stay small. Larger datasets make better optimization signals, but they also cost more and make failure analysis noisier.

### 5. Evaluators

Current built-in evaluator set:

```yaml
evaluators:
  - builtin.task_adherence
  - builtin.coherence
  - builtin.violence
```

These are intentionally simple first-pass evaluators:

| Evaluator | Purpose |
| --- | --- |
| `builtin.task_adherence` | Checks whether the response follows the request. |
| `builtin.coherence` | Checks basic response quality. |
| `builtin.violence` | Safety smoke check. |

For richer quality scoring, use the Foundry Portal Rubric flow in [foundry-portal-rubric-evaluation.md](foundry-portal-rubric-evaluation.md), then decide whether to add a stable Rubric evaluator to `eval.yaml` later.

### 6. Eval and Optimization Models

The command provides these models:

```powershell
azd ai agent optimize `
  --eval-model <existing-eval-model-deployment> `
  --optimize-model <existing-supported-optimization-model-deployment>
```

| Model | Role |
| --- | --- |
| Eval model | Judges baseline and candidate outputs against evaluators. |
| Optimization model | Generates improved candidate configs. |

Both deployment names must exist in the Foundry account that owns the Hosted Agent being optimized.

These are not Claude runtime models. Claude runtime remains controlled by `CLAUDE_MODEL` or the `sonnet` default in `main.py`.

## What Happens During an Optimization Run

When you run `azd ai agent optimize`, the service performs this loop.

### 1. Resolve the Agent and Config

azd reads the azd project and selected service, then reads `eval.yaml`.

It resolves:

- Hosted Agent name and version;
- dataset file;
- evaluator list;
- baseline config metadata;
- instruction file path;
- eval model;
- optimization model.

### 2. Save a Baseline Snapshot

azd may create a generated `.agent_configs/baseline/` cache while building the request. In this repo, that cache is ignored and is not the source of truth.

Source of truth remains:

```text
.claude/optimizer_configs/baseline/
```

### 3. Invoke the Hosted Agent on the Dataset

Optimizer sends each dataset query to the deployed Hosted Agent.

For this accelerator, the Hosted Agent still runs:

```text
ClaudeAgent
  -> CLAUDE.md
  -> .claude/agents/
  -> .claude/skills/
  -> optimizer overlay from .claude/optimizer_configs/
  -> runtime output schema appended by main.py
```

### 4. Score the Baseline

The eval model scores the baseline responses with the configured evaluators. This creates the baseline score.

### 5. Generate Candidate Configs

The optimization model reads the baseline config, dataset tasks, and evaluation results, then generates candidate config changes.

In this repo, candidates should primarily change the instruction overlay. The updated CLI applies those files to staging first:

```text
.agent_configs/<candidate-id>/instructions.md
```

After review, merge approved instruction changes into:

```text
.claude/optimizer_configs/baseline/instructions.md
```

Candidates should not be allowed to silently change the durable Claude project Skills, subagent definitions, schema contract, or runtime code.

### 6. Evaluate Candidates

Optimizer invokes temporary candidate versions of the agent against the same dataset and scores them with the same evaluators.

### 7. Rank and Recommend

The service ranks candidates by score and marks a recommended candidate. Treat the score as a signal, not an automatic deployment decision.

Small score improvements can be noise. Review the candidate diff and compare with the Portal Rubric reasons before deploying.

### 8. Apply Locally

When you run:

```powershell
azd ai agent optimize apply --candidate <candidate-id>
```

azd writes the selected candidate config locally. In the standard quickstart layout, this lands under `.agent_configs/<candidate-id>/` and `load_config()` reads it automatically on the next deployment.

This repo intentionally does not make `.agent_configs/` authoritative. Review the applied candidate under `.agent_configs/`, then merge the approved instruction changes into `.claude/optimizer_configs/baseline/instructions.md` before deploying.

### 9. Deploy After Review

After validation, deploy with:

```powershell
azd deploy
```

This keeps optimized changes reviewable in source control.

## What Optimizer Produces

An optimization run can produce:

| Output | Purpose |
| --- | --- |
| Operation/job ID | Used to monitor or cancel the run. |
| Portal URL | Used to review results in Foundry. |
| Baseline score | Quality score before changes. |
| Candidate scores | Quality scores for generated alternatives. |
| Candidate config files | Local instructions/config after `apply`. |
| Recommended candidate | The service's best-scoring candidate. |

Do not treat the recommended candidate as automatically production-ready. It still needs diff review, local smoke checks, and B2 evaluation comparison.

In this repo, candidate files under `.agent_configs/` are generated staging outputs. Reviewed optimizer source remains under `.claude/optimizer_configs/`.

## Required Preparation

Before running Optimizer, prepare these items.

| Preparation | Why |
| --- | --- |
| Hosted Agent deployed | Optimizer evaluates the deployed Hosted Agent, not only local code. |
| Agent version known | Baseline needs a stable version reference. |
| Foundry eval model deployment | Required to score responses. |
| Foundry optimization model deployment | Required to generate candidate configs. |
| Dataset JSONL | Defines the tasks Optimizer uses. |
| Evaluators | Define what better means. |
| Baseline optimizer config | Defines what can be rewritten. |
| Runtime loader | Makes baseline/candidate overlay affect the Hosted Agent. |
| Review workflow | Prevents a high score from bypassing engineering review. |

The CLI preparation step should include:

```powershell
azd ext list
azd ext upgrade azure.ai.agents
azd ai agent optimize --help
```

Use `azure.ai.agents` `0.1.40-preview` or later for the quickstart behavior described in [foundry-agent-optimizer.md](foundry-agent-optimizer.md).

## Current Repo Boundary

This repo intentionally separates four layers:

| Layer | Source of Truth | Notes |
| --- | --- | --- |
| Claude runtime behavior | `CLAUDE.md`, `.claude/agents/`, `.claude/skills/` | Long-lived Claude Agent SDK project config. |
| Optimizer overlay | `.claude/optimizer_configs/` | Thin, reviewable improvement surface. |
| CLI staging cache | `.agent_configs/` | Generated by `azd ai agent optimize` and `optimize apply`; ignored by git in this repo. |
| Evaluation job spec | `eval.yaml` | Dataset, evaluators, target agent, and optimizer-visible model. |
| Runtime constraints | `main.py`, `runtime_contracts.py`, `workspaces.py` | Schema and workspace constraints stay outside Optimizer edits. |

This boundary keeps the demo clear: Optimizer can improve behavior, but evaluation/control contracts remain stable and inspectable.

## Common Misunderstandings

### Is the optimizer model replacing Claude Sonnet?

No.

The eval and optimization model deployment names are used by Agent Optimizer in Foundry. ClaudeAgent still uses `CLAUDE_MODEL` or `sonnet` at runtime.

### Why does `eval.yaml` have `agent.model`?

The Optimizer job contract expects a Foundry model deployment name. It is not the Claude SDK alias. Use a deployment that exists in the Hosted Agent's Foundry account.

### Why does `metadata.yaml` omit `model`?

The installed SDK can load baseline metadata without `model`, returning `model=None`. This avoids implying that optimizer metadata controls Claude runtime model selection. `eval.yaml` still carries the optimizer-visible model deployment.

### Does Optimizer improve `.claude/skills/`?

Not in the default repo setup. Skill improvement can be added later with a staging copy under `.claude/optimizer_configs/baseline/skills/`, but those changes should be manually reviewed and merged into `.claude/skills/`.

### Why not deploy the recommended candidate directly?

The score is only one signal. Candidate instructions can become longer, overfit to a tiny dataset, or conflict with domain expectations. Apply locally, inspect the diff, rerun evaluation, then deploy.

The updated CLI also has `azd ai agent optimize deploy --candidate <id>`, but that path deploys through the API without updating local source. It is useful for quick testing, not for this repo's reviewable accelerator workflow.
