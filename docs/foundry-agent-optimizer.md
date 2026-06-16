# Foundry Agent Optimizer Guide

This guide shows how to run the Part B Optimize demo with Agent Optimizer in Microsoft Foundry Agent Service.

Agent Optimizer is preview. It evaluates a deployed Hosted Agent against a dataset, generates candidate configurations, scores the candidates, and lets you apply the best candidate locally before redeploying. Use this guide after the B2 evaluation assets are in place.

For a deeper explanation of inputs, internal processing, outputs, and preparation requirements, read [foundry-agent-optimizer-concepts.md](foundry-agent-optimizer-concepts.md).

## What This Adds

This repository is optimizer-ready from the checked-in backend source. Any azd project folder produced by `azd ai agent init` is deployment scaffolding and should stay outside the committed accelerator source.

| Location | Purpose |
| --- | --- |
| `backend/` | Source implementation, Hosted Agent manifest, runtime code, and optimizer baseline. |
| Generated azd project folder | Local deployment scaffold that points at `backend/`; do not commit environment-specific copies. |

Each agent root contains:

| File | Purpose |
| --- | --- |
| `.claude/optimizer_configs/baseline/metadata.yaml` | Baseline optimizer config. |
| `.claude/optimizer_configs/baseline/instructions.md` | Thin optimizer overlay that Optimizer can rewrite. |
| `.claude/skills/` | Long-lived Claude Code Skills. These remain the source of truth and are not duplicated in the optimizer baseline. |
| `eval.yaml` | Local optimization intent and bad-config dataset binding. |
| `src/agent/optimization.py` | Runtime helper that loads Optimizer config. |
| `main.py` | Wires Optimizer instructions/model into `ClaudeAgent`. |

The stable JSON output contract is still appended by application code. Optimizer can improve the coordinator overlay, but it should not silently remove the schema, workspace, or hosted-runtime constraints that B2/B3 depend on. See [foundry-agent-optimizer-concepts.md](foundry-agent-optimizer-concepts.md) for the design rationale.

## Prerequisites

- You have access to the Agent Optimizer preview.
- Your Azure subscription is on the Agent Optimizer preview allow list.
- The hosted agent is deployed and uses the Responses protocol.
- `azd` and Azure CLI are installed.
- `az login` and `azd auth login` are complete.
- The `azure.ai.agents` azd extension is installed at `0.1.40-preview` or later.
- The Foundry project has an eval model deployment.
- The Foundry project has an optimization model deployment from the supported preview list.
- The dataset exists locally at `evals/datasets/bad-config.queries.jsonl`.

Check the CLI and extension before running the optimizer:

```powershell
azd version
azd ext list
# If the extension is missing:
# azd ext install azure.ai.agents
# If the extension is older than 0.1.40-preview:
azd ext upgrade azure.ai.agents
azd ai agent optimize --help
```

If `azd ext list` shows `azure.ai.agents` earlier than `0.1.40-preview`, upgrade before following the rest of this guide. The current quickstart also recommends keeping `azd` itself current; on Windows, `winget upgrade Microsoft.Azd` updates the Azure Developer CLI.

Supported optimization models are preview-dependent. From the referenced docs, use an existing deployment named one of:

```text
GPT-5
GPT-5.1
GPT-5.2
GPT-5.4
GPT-5.5
DeepSeek-V4-Pro
DeepSeek-V-3.2
```

Do not guess model deployment names. Confirm the deployments in the Foundry portal before running optimization.

## CLI Update Summary

The 2026-06 quickstart changed the optimizer flow in a few important ways:

| Area | Updated CLI Behavior | This Repo's Practice |
| --- | --- | --- |
| Extension version | `azure.ai.agents` must be `0.1.40-preview` or later. | The generated `azure.yaml` should require `>=0.1.40-preview`. |
| Agent targeting | `azd ai agent optimize` can auto-detect the deployed agent from the current azd environment and local agent files. | Auto-detection can work, but explicit `--agent <hosted-agent-name>` and `--config <path-to-eval.yaml>` is clearer for repeatable demos. |
| Eval generation | The quickstart can generate an eval config and dataset before optimization. | The bad-config dataset and `eval.yaml` are already committed. Do not regenerate them unless you intentionally want a new suite. |
| Candidate apply | `azd ai agent optimize apply` writes optimized config under `.agent_configs/`. | Treat `.agent_configs/` as generated staging. Review and merge approved instruction changes into `.claude/optimizer_configs/`. |
| Direct deploy | `azd ai agent optimize deploy --candidate <id>` can deploy a candidate directly through the API. | Prefer local `apply`, diff review, manual `.claude` merge, then `azd deploy`. |
| Separate eval run | `azd ai agent eval run` can run evaluation from `eval.yaml`. | Useful after candidate review, but keep Portal Rubric as the quality baseline for B2/B4 demos. |

The official quickstart uses the standard `.agent_configs/` layout. This accelerator intentionally keeps the optimizer source of truth under `.claude/optimizer_configs/` so it does not duplicate the long-lived Claude Code Skills. That means CLI-generated `.agent_configs/` files are not automatically authoritative in this repo.

## Optimizer Boundary for This Agent

This accelerator uses `ClaudeAgent` through Microsoft Agent Framework. The optimizer scaffold is intentionally conservative:

| Optimizer Target | Status | Reason |
| --- | --- | --- |
| Instruction tuning | Enabled | `.claude/optimizer_configs/baseline/instructions.md` is loaded at startup. |
| Skill improvement | Not enabled by default | `.claude/skills/` remains the Claude Code source of truth and is not duplicated into optimizer config. |
| Tool optimization | Not enabled | Built-in Claude Code tools are not OpenAI function definitions in this app. |
| Model selection | Not enabled by default | The runtime uses Claude model aliases such as `sonnet`; do not add GPT model candidates unless the runtime is intentionally changed. |

## Step 1: Verify the Runtime Scaffold

From the repo root:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m compileall main.py src
..\.venv\Scripts\python.exe -c "from pathlib import Path; from azure.ai.agentserver.optimization import load_config; c = load_config(config_dir=Path('.claude/optimizer_configs')); print(c.source, c.model)"
```

Expected signal:

```text
local:.claude\optimizer_configs\baseline None
```

If the import fails, install dependencies:

```powershell
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The runtime logs this line on startup when the config loads:

```text
Agent optimizer config source=local:.claude\optimizer_configs\baseline model=<default> skills=0 enabled=True
```

## Step 2: Confirm Baseline Quality

Before asking Optimizer to improve the agent, run the existing B2 checks so you know the baseline.

Local deterministic scorecard:

```powershell
Set-Location <repo-root>
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m src.agent.observability.evaluation `
  --responses evals/datasets/bad-config.sample-responses.jsonl `
  --policy "evals/policies/*.policy.yaml" `
  --rubric evals/rubrics/analysis-quality.rubric.yaml `
  --output .foundry/results/local-policy-scorecard.json
```

Cloud-side rubric baseline:

1. Run the portal flow in [foundry-portal-rubric-evaluation.md](foundry-portal-rubric-evaluation.md).
2. Capture the baseline score and dimension reasons.
3. Use those scores to decide what Optimizer should improve.

Optional CLI-generated eval suite:

```powershell
Set-Location <azd-project-root>
azd ai agent eval generate `
  --agent <hosted-agent-name> `
  --eval-model <existing-eval-model-deployment>
```

Some preview extension builds expose this command as `azd ai agent eval init` instead of `eval generate`. Use `azd ai agent eval --help` after upgrading the extension and follow the command name shown by your installed CLI.

Do not run this command during the standard bad-config demo unless you want to replace or compare against the committed `eval.yaml` and `evals/datasets/bad-config.queries.jsonl` assets.

## Step 3: Review `eval.yaml`

The checked-in optimization config template is:

```text
backend/eval.yaml
```

Before running Optimizer, replace the template values in `backend/eval.yaml` with values that match your generated azd project and deployed Hosted Agent. The updated CLI resolves `agent.config` and `dataset_file` from the azd project root, not from the folder that contains `eval.yaml`. Use paths relative to that azd project root.

The `agent.model` value must be a model deployment name that exists in the Foundry account where the Hosted Agent is optimized. It is not a Claude SDK alias. Use the deployment name available in your own Foundry project.

For this ClaudeAgent app, runtime model selection is separate: `main.py` uses `CLAUDE_MODEL` or `sonnet` for Claude SDK execution. The baseline `metadata.yaml` intentionally omits `model` to avoid implying that optimizer metadata controls Claude runtime model selection.

This file intentionally omits `options.eval_model` and `options.optimization_model` because model deployment names are project-specific. Pass them on the command line or add them only after confirming the exact deployment names in Foundry.

If your model deployments live in another Foundry project, check whether that project uses the same Foundry account as the Hosted Agent project. Optimizer resolves model deployments in the account that owns the optimized Hosted Agent. If the deployments are in a different account, deploy equivalent eval/optimization model deployments into the Hosted Agent's account or deploy the Hosted Agent into the account where those models already exist.

The current evaluator set is small:

```yaml
evaluators:
  - builtin.task_adherence
  - builtin.coherence
  - builtin.violence
```

After the Portal Rubric evaluator is stable, add it to `eval.yaml` or keep it as a portal-side baseline comparison.

## Step 4: Run Agent Optimizer

Run from the azd project root. This matters because `azd ai agent optimize` resolves `dataset_file` relative to the azd project root even when the selected service's `eval.yaml` is under `src/<service>/`.

Recommended deterministic command for this repo:

```powershell
Set-Location <azd-project-root>
azd ai agent optimize `
  --agent <hosted-agent-name> `
  --config <path-to-backend>\eval.yaml `
  --eval-model <existing-eval-model-deployment> `
  --optimize-model <existing-supported-optimization-model-deployment>
```

With the updated CLI, this shorter command can also work after the agent and `eval.yaml` are auto-detected:

```powershell
Set-Location <azd-project-root>
azd ai agent optimize `
  --eval-model <existing-eval-model-deployment> `
  --optimize-model <existing-supported-optimization-model-deployment>
```

Use the shorter command only after checking the CLI output. It should show the intended agent and config, for example:

```text
Optimizing agent "<hosted-agent-name>"...
  Config: ...\backend\eval.yaml
  Baseline saved to .agent_configs\baseline\metadata.yaml
  Job ID: opt_...
  Portal: <optimization-job-url>
```

The job invokes the deployed Hosted Agent against the dataset. If the agent uses tools with side effects in the future, point those tools to test endpoints before running optimization. The current bad-config fixture uses local file reads and analysis only.

The run usually takes several minutes. Capture:

- operation ID;
- portal result URL;
- baseline score;
- candidate scores;
- recommended candidate ID.

## Step 5: Monitor the Run

Use the operation ID from the optimize command:

```powershell
azd ai agent optimize status <operation-id> --watch
```

You can also list recent runs:

```powershell
azd ai agent optimize list
```

Cancel a run if the dataset or model selection is wrong:

```powershell
azd ai agent optimize cancel <operation-id>
```

In the Foundry portal, open the agent and use the Optimize tab to inspect score comparisons and candidate details.

## Step 6: Interpret Results

Treat small score changes carefully:

| Improvement | Interpretation |
| --- | --- |
| `< 0.03` | Likely noise. Do not deploy based on score alone. |
| `0.03 - 0.10` | Moderate improvement. Review candidate content. |
| `0.10 - 0.20` | Significant improvement. Strong candidate if rubric reasons agree. |
| `> 0.20` | Major improvement or weak baseline. Review closely. |

Also inspect token length. Optimized instructions may be longer, so compare quality improvement against cost and latency.

## Step 7: Apply the Candidate Locally

Do not deploy directly from the optimizer job. Apply the candidate locally so the generated changes are reviewable:

```powershell
Set-Location <azd-project-root>
azd ai agent optimize apply --candidate <candidate-id>
```

The updated CLI writes the applied candidate under `.agent_configs/` in the azd service project. In this repo, `.agent_configs/` is ignored and treated as staging because the runtime source of truth is `.claude/optimizer_configs/`.

Inspect the generated candidate files first:

```powershell
Get-ChildItem -Recurse .agent_configs | Select-Object FullName
```

Then compare the staged candidate with the active optimizer overlay and manually merge only the approved instruction changes:

```powershell
git diff --no-index `
  <path-to-backend>\.claude\optimizer_configs\baseline\instructions.md `
  .agent_configs\<candidate-id>\instructions.md
```

After review, merge the approved instruction changes into:

```text
backend/.claude/optimizer_configs/baseline/instructions.md
```

Then inspect the source diff from the repo root:

```powershell
Set-Location <repo-root>
git diff -- backend/.claude/optimizer_configs
```

Review for:

- preserved Japanese response behavior;
- preserved evidence-grounded Azure review behavior;
- no removal of schema, workspace, or runtime constraints from code-appended instructions;
- no invented customer-specific assumptions;
- no tool or model changes that the ClaudeAgent runtime cannot use.

The CLI also supports direct deployment:

```powershell
azd ai agent optimize deploy --candidate <candidate-id>
```

Use direct deploy only for throwaway testing. It creates a new agent version through the Foundry API without making local source changes, so it is not the recommended path for this accelerator.

## Step 8: Validate the Candidate

Run syntax checks:

```powershell
Set-Location <repo-root>
.\.venv\Scripts\python.exe -m compileall backend/main.py backend/src
```

Run the local evaluator against an actual candidate response when possible:

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m src.agent.observability.evaluation `
  --responses evals/datasets/bad-config.actual-responses.jsonl `
  --policy "evals/policies/*.policy.yaml" `
  --rubric evals/rubrics/analysis-quality.rubric.yaml `
  --output .foundry/results/optimized-policy-scorecard.json
```

Then re-run the Foundry Portal Rubric evaluation and compare dimension reasons against the baseline.

You can also run the updated CLI evaluation path from the azd project root:

```powershell
Set-Location <azd-project-root>
azd ai agent eval run --config <path-to-backend>\eval.yaml
```

## Step 9: Deploy After Review

After reviewing the candidate diff and validating behavior:

```powershell
Set-Location <azd-project-root>
azd deploy
```

After deploy, run the Hosted Agent smoke prompt and repeat B2 evaluation.

## Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `azd ai agent optimize` uses the wrong agent or config | The updated CLI auto-detected another service or `eval.yaml`. | Re-run with `--agent <hosted-agent-name> --config <path-to-backend>\eval.yaml`. |
| `azd ai agent eval generate` is unavailable | Installed `azure.ai.agents` extension still exposes the older `eval init` command. | Upgrade to `0.1.40-preview` or later, or use the command name shown by `azd ai agent eval --help`. |
| Candidate apply changes only `.agent_configs/` | This is the standard CLI apply location. | Treat it as staging and merge approved changes into `.claude/optimizer_configs/baseline/`. |
| `load_config()` cannot find baseline | Command is running from the wrong folder or `.claude/optimizer_configs/baseline` is missing. | Run from the agent root or confirm the scaffold exists beside `agent.yaml`. |
| Optimize scores are all zero | Eval model deployment is missing or unavailable. | Confirm the eval model exists in the Foundry project and pass `--eval-model`. |
| Optimize command rejects the model | Optimization model is not in the preview allowlist or not deployed. | Deploy an allowed optimization model and pass its deployment name. |
| Candidate changes model to unsupported value | Model selection was enabled for a runtime that uses Claude aliases. | Remove model candidates from `eval.yaml`; keep model selection disabled. |
| Candidate gets verbose but not better | Optimizer increased instruction length without useful quality gain. | Reject the candidate or tighten evaluators/rubric dimensions. |
| Portal Rubric disagrees with optimizer score | Evaluator criteria are not aligned. | Use Rubric dimension reasons to refine `eval.yaml` evaluator selection and baseline instructions. |

## Demo Story

Use this sequence for the B4 Optimize narrative:

1. Show B2 baseline score from local evaluator and Foundry Portal Rubric.
2. Show `.claude/optimizer_configs/baseline/` as the optimizer target.
3. Run `azd ai agent optimize` against the bad-config dataset.
4. Show candidate ranking in CLI or portal.
5. Apply the best candidate locally into `.agent_configs/` staging.
6. Review and merge approved instruction changes into `.claude/optimizer_configs/`.
7. Re-run evaluation and show score movement.
8. Deploy only after review.

This keeps the lifecycle evidence-based: Optimize is driven by evaluation results, not by subjective prompt tweaking.
