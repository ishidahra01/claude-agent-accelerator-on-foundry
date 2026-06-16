# Evaluation Assets

This directory contains the Part B Evaluate assets for the Azure Well-Architected review agent.

The MVP evaluation design deliberately uses three lanes:

| Lane | Assets | Purpose |
| --- | --- | --- |
| ASSERT-like policy | `policies/*.policy.yaml` | Check explicit obligations such as public exposure detection, remediation, cost findings, and architecture coverage. |
| Rubric | `rubrics/analysis-quality.rubric.yaml` | Define weighted quality dimensions that can be scored locally now and mapped to Foundry Rubric evaluator later. |
| Datasets | `datasets/*.jsonl` | Provide repeatable local smoke rows and Foundry cloud evaluation inputs. |
| Rubric autogenerate context | `rubric-autogenerate-context.md` | Reference context for creating a Foundry Rubric evaluator from the portal. |

No Foundry Custom Evaluator is included in the MVP. JSON parseability, required fields, and severity enum checks are deterministic gates. They are checked locally by `src/agent/observability/evaluation.py` today and should move to the ACS output checkpoint in B3.

Run the local scorecard from the repository root:

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m src.agent.observability.evaluation `
  --responses evals/datasets/bad-config.sample-responses.jsonl `
  --policy "evals/policies/*.policy.yaml" `
  --rubric evals/rubrics/analysis-quality.rubric.yaml `
  --output .foundry/results/local-policy-scorecard.json
```

Use `bad-config.queries.jsonl` for Hosted Agent target evaluation from the Foundry portal or through `scripts/run_foundry_agent_eval.py`. Use `rubric-autogenerate-context.md` when creating the portal Rubric evaluator with Autogenerate. Use `bad-config.conversations.jsonl` as the seed for future conversation or trace evaluation.

Portal-first instructions are in [../docs/foundry-portal-rubric-evaluation.md](../docs/foundry-portal-rubric-evaluation.md).