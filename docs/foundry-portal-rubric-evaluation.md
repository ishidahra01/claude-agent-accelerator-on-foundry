# Foundry Portal Rubric Evaluation Guide

This guide shows how to run the Part B Evaluate demo from the Microsoft Foundry portal. It focuses on a portal-first flow: create a Rubric evaluator with Autogenerate, run the deployed Hosted Agent against the bad-config dataset, and inspect the cloud evaluation report.

Use this when you want to show that evaluation happens in Foundry, not only in the local `evaluation.py` smoke test.

## What This Proves

This flow proves that:

- Foundry can run the deployed Hosted Agent as the evaluation target.
- A Foundry Rubric evaluator can judge the agent response with weighted domain-specific criteria.
- The report is stored in the Foundry project and can be reviewed from the portal.
- Local assets under `evals/` can seed cloud evaluation without being packaged into the Hosted Agent container.

This flow does not replace the local deterministic policy checks. Use both:

| Layer | Use |
| --- | --- |
| Foundry Rubric evaluator | LLM-as-judge quality scoring with dimension reasons. |
| Local `evaluation.py` | Deterministic schema, required-field, expected-signal, and policy checks. |

## Prerequisites

- The Hosted Agent is deployed in the Foundry project.
- You can open the Foundry project in `https://ai.azure.com`.
- Your user has the Foundry User role or higher on the project.
- The project has a GPT model deployment available as the judge model. Prefer a strong judge model for rubric scoring.
- The local repo has these files:
  - `evals/datasets/bad-config.queries.jsonl`
  - `evals/rubric-autogenerate-context.md`
  - `evals/rubrics/analysis-quality.rubric.yaml`

For your azd environment, confirm the target values before creating the evaluation:

| Setting | Value |
| --- | --- |
| Project | The Foundry project created or selected by your azd environment. |
| Agent | The deployed Hosted Agent name, for example `my-claude-agent`. |
| Agent version | The deployed version you want to evaluate. |

Confirm the exact values with `azd env get-values` from your generated azd project root if needed.

## Step 1: Open the Foundry Project

1. Open `https://ai.azure.com`.
2. Select the Foundry project that contains the deployed Hosted Agent.
3. Open the agent list and confirm your Hosted Agent is present.
4. Confirm the deployed version you want to evaluate.

If the agent is not visible, redeploy or check the azd environment first. Do not create a rubric against the wrong project because evaluator and dataset assets are project-scoped.

## Step 2: Create a Rubric Evaluator with Autogenerate

In the portal, the exact navigation can change slightly, but the common path is:

```text
Evaluation
  -> Evaluators, Evaluator catalog, or Testing criteria
  -> Create
  -> Rubric evaluator
  -> Autogenerate
```

If you do not see a standalone evaluator catalog, start from:

```text
Evaluation
  -> Create
  -> Select testing criteria
  -> Add rubric or create rubric evaluator
```

Rubric evaluators are preview. If the UI labels differ, look for `Rubric`, `Custom criteria`, or `Autogenerate rubric`.

### Judge Model

Choose the strongest available GPT judge model in the project. For a demo, use the best model available in your quota. Avoid tiny judge models when possible because rubric score consistency depends on judge quality.

Recommended order:

```text
Best available GPT-5.x judge model
gpt-4.1
gpt-4o
```

Avoid `gpt-4o-mini` for rubric judging unless it is the only available option.

### Autogenerate Instruction

Paste this instruction into the rubric generation prompt or description field:

```text
Generate a rubric evaluator for an Azure Well-Architected Review Agent. The rubric should score single-turn responses for risk coverage, remediation quality, evidence accuracy, severity prioritization, and schema compliance. The response should be grounded in the provided Azure resource export and follow the required summary/security/cost/architecture JSON schema. Penalize missed public exposure, missed internet-exposed administrative access, vague recommendations, hallucinated resources, incorrect severity, missing remediation, inconsistent summary counts, and malformed JSON.
```

### Context / Reference File

Upload or paste `evals/rubric-autogenerate-context.md` as the reference context.

If the portal lets you select the existing agent as context, also select your deployed Hosted Agent. For a Hosted Agent, the portal may use the agent description rather than every project instruction, so the reference file is still important.

### Optional Additional Context

If the portal accepts multiple files, add these as supporting references:

- `backend/src/agent/runtime_contracts.py`
- `evals/rubrics/analysis-quality.rubric.yaml`
- `evals/policies/security.policy.yaml`
- `evals/policies/cost.policy.yaml`
- `evals/policies/waf.policy.yaml`

Do not upload secrets, `.env` files, azd environment files, or customer data.

## Step 3: Review and Edit the Generated Rubric

After Autogenerate finishes, review the generated dimensions before saving.

The rubric should include dimensions equivalent to these:

| Dimension | What It Should Measure | Suggested Weight |
| --- | --- | --- |
| `risk_coverage` | Finds key security, cost, and architecture risks present in the input. | 9 |
| `evidence_accuracy` | Grounds findings in the provided Azure configuration and avoids hallucination. | 8 |
| `remediation_quality` | Gives concrete, implementable remediation or recommendation steps. | 7 |
| `severity_prioritization` | Assigns High or Critical severity to public exposure and internet-exposed admin access. | 6 |
| `schema_compliance` | Follows the required JSON contract and keeps summary counts consistent. | 5 |

Set `schema_compliance` to always applicable if the UI supports it.

Start with this pass threshold:

```text
0.7
```

Use `0.75` or `0.8` when you want a stricter demo.

### Fix Common Autogenerate Problems

Edit the generated rubric if it has these issues:

| Problem | Fix |
| --- | --- |
| It focuses only on security. | Add cost and architecture coverage to `risk_coverage`. |
| It rewards generic Azure advice. | Require resource-specific findings grounded in input evidence. |
| It ignores JSON shape. | Add or strengthen `schema_compliance`. |
| It does not mention hallucination. | Add hallucinated resources/settings/metrics as explicit penalties. |
| It treats all severities equally. | Require public exposure and open admin access to be High or Critical. |
| It omits remediation. | Add remediation quality as a separate dimension. |

Save the rubric evaluator after review. Give it a recognizable name such as:

```text
azure-waf-analysis-quality-rubric
```

## Step 4: Create an Agent Evaluation

Open:

```text
Evaluation
  -> Create
```

Choose:

| Field | Value |
| --- | --- |
| Target | Agent |
| Agent | Your deployed Hosted Agent, for example `my-claude-agent` |
| Version | The deployed version you want to evaluate |
| Scope | Individual turns |
| Data source | Existing dataset |

Use `Individual turns` for the first demo. Full conversation evaluation is useful later, but this B2 flow is about one bad-config review request and one structured response.

## Step 5: Upload or Select the Dataset

Upload `evals/datasets/bad-config.queries.jsonl` as a JSONL dataset if it is not already present in the project.

The row shape is:

```json
{"id":"bad_config_fixture_review","query":"samples/bad-config/azure-export.json ...","expected":{}}
```

For Agent target evaluation, the key field is `query`. Foundry sends `query` to the Hosted Agent during the evaluation run and then scores the generated response.

Name the dataset something clear, for example:

```text
azure-waf-bad-config-queries
```

Use version `1` for the first run.

## Step 6: Configure Agent Prompt Mapping

In the agent configuration step, keep the user prompt mapping simple:

```text
{{item.query}}
```

This sends the dataset row's `query` field directly to the Hosted Agent.

Use the default system prompt unless you intentionally want to test a prompt variant. For this accelerator, the deployed agent already carries the runtime output contract through `backend/main.py` and `backend/src/agent/runtime_contracts.py`.

## Step 7: Configure Field Mapping

For an Agent target evaluation, Foundry runs the agent and exposes the generated answer to evaluators.

Map fields like this:

| Evaluator Input | Mapping |
| --- | --- |
| Query | `{{item.query}}` |
| Response | Agent generated output / `{{sample.output_text}}` |

If the portal shows dropdowns instead of template text, map:

- `query` to the dataset `query` field.
- `response` to the generated agent response.

For Task Adherence or other agent evaluators, use the full generated output when offered by the UI.

## Step 8: Select Testing Criteria

Add the Rubric evaluator you created in Step 2.

For the first run, also add a small supporting set:

| Evaluator | Why |
| --- | --- |
| Rubric evaluator | Domain-specific WAF quality score and dimension reasons. |
| Task Adherence | Checks whether the agent followed the request constraints. |
| Coherence | Basic quality sanity check. |
| Violence | Small safety smoke check. |

Keep the first run small. More evaluators increase cost and make early troubleshooting noisier.

## Step 9: Submit and Monitor the Run

Review the configuration, then submit the evaluation.

The run usually moves through:

```text
In Progress -> Completed
```

Open the evaluation result when it completes.

If the run stays in progress for a long time, check judge model quota or reduce the dataset size.

## Step 10: Interpret the Rubric Result

In the result view, focus on:

| Result Field | Meaning |
| --- | --- |
| Overall score | Weighted normalized score, typically 0-1. |
| Label / passed | Whether the score meets the threshold. |
| Reason | Judge explanation for the score. |
| Dimension scores | Per-dimension 1-5 scores and reasons. |

For this demo, a strong result should say the response:

- found public blob access;
- found weak TLS or HTTPS-only issues;
- found internet-exposed RDP;
- identified dev VM and SQL cost opportunities;
- identified zone redundancy, backup redundancy, or diagnostics gaps;
- used concrete resource names;
- gave concrete remediation or recommendations;
- returned the required JSON shape.

If the rubric score is low, use the dimension reasons to decide whether to improve prompt instructions, Skills, output controls, or the rubric wording itself.

## Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| Rubric option is not visible | Preview UI or region availability differs. | Look for `Custom criteria`, `Testing criteria`, or create the rubric during evaluation setup. |
| Dataset upload fails | JSONL format issue. | Validate one JSON object per line and UTF-8 encoding. |
| Agent cannot read `samples/bad-config/azure-export.json` | Wrong agent version or container package. | Confirm the evaluated Hosted Agent version includes `backend/samples/`. |
| Field mapping error | Required evaluator fields are unassigned. | Map `query` to `{{item.query}}` and `response` to generated agent output. |
| Rubric gives strange scores | Rubric is too vague or judge model is weak. | Tighten descriptions, add hallucination penalties, use a stronger judge model. |
| Run is slow or fails with quota errors | Judge model capacity is low. | Use a smaller dataset, retry later, or use another judge deployment. |

## What to Capture for the Demo

Capture these screenshots or notes:

1. Rubric evaluator dimensions and threshold.
2. Agent evaluation target showing your Hosted Agent name and version.
3. Dataset preview for `bad-config.queries.jsonl`.
4. Evaluation result summary.
5. Rubric dimension scores and reasons.

These artifacts make the demo story clear: the agent is not only hosted in Foundry; Foundry also evaluates its output quality with a domain-specific rubric.
