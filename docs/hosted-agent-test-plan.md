# Hosted Agent Deployment and Test Plan

This guide explains how to deploy the Part A harness as a Microsoft Foundry Hosted Agent and how to verify that the harness behavior is working after deployment.

The important testing point is input ownership:

- For a smoke test, you can ask the hosted container to read the bundled fixture at `samples/bad-config/azure-export.json`.
- For a realistic Hosted Agent test, pass the Azure export JSON as request input through Foundry Portal, API, or SDK.

Both tests are useful, but they prove different things.

## Should `azure-export.json` Stay Under `backend/`?

For this repository, keeping `backend/samples/bad-config/azure-export.json` is acceptable as a demo fixture because `backend/Dockerfile` copies the `backend/` directory into the hosted container. That means the deployed agent can read the sample path during smoke testing.

Do not treat the bundled file as the normal user input path. If every hosted test says "read `samples/bad-config/azure-export.json`", you are mostly testing that the container includes the sample. You are not fully testing the Hosted Agent request boundary.

Recommended split:

| Input Mode | What It Tests | When To Use |
| --- | --- | --- |
| Bundled file path: `samples/bad-config/azure-export.json` | Container packaging, Claude Code `Read`, cwd, `.claude` discovery, file-system access | First smoke test after deploy |
| Inline JSON in request input | Hosted Agent API/Portal input flow, prompt handling, harness synthesis, output contract | Main acceptance test |
| External blob or URL | Real-world file handoff pattern, access/auth behavior | Later integration test |

For production demos, keep the sample obviously labeled as a fixture, or move it to a separate branch/demo package. For this Part A accelerator, leaving it under `backend/samples/` is intentional because it gives a repeatable container smoke test.

## Deploy

Run these commands from the azd working directory created for the hosted agent, not from `backend/`.

```powershell
azd ext upgrade azure.ai.agents
azd auth login
azd ai agent init -m ..\backend\agent.yaml
```

Set or confirm runtime values in `.azure/<env-name>/.env`.

```env
ANTHROPIC_FOUNDRY_API_KEY=<your-foundry-anthropic-api-key>
```

Provision and deploy.

```powershell
azd provision
azd deploy
```

After deployment, capture the endpoint values.

```powershell
azd env get-values
```

Look for values such as:

- `AZURE_AI_PROJECT_ENDPOINT`
- `AGENT_<SERVICE_OR_AGENT_NAME>_ENDPOINT`
- `APPLICATIONINSIGHTS_CONNECTION_STRING`
- `AZURE_RESOURCE_GROUP`
- `AZURE_AI_PROJECT_NAME`

The exact agent endpoint variable name depends on the generated azd service name. Use the `AGENT_..._ENDPOINT` value as the base URL for direct API calls.

## Test Option 1: Foundry Portal

Use the portal first when you want a quick human-readable check.

1. Open the Microsoft Foundry project created by `azd provision`.
2. Find the hosted agent registered by `azd deploy`.
3. Open the playground or test panel for the agent.
4. Send the smoke-test prompt below.

Smoke-test prompt:

```text
samples/bad-config/azure-export.json を Read で読み、WebSearch と WebFetch と Agent ツールは使わず、見えているJSONだけを根拠に summary/security/cost/architecture の固定JSONだけを返してください。説明文は不要です。
```

Then run the realistic inline-input prompt. Paste the JSON from `backend/samples/bad-config/azure-export.json` into `<PASTE_JSON_HERE>`.

```text
次の Azure export JSON を分析してください。コンテナ内のサンプルファイルは読まず、このメッセージ内の JSON だけを根拠にしてください。

要件:
- summary/security/cost/architecture の固定JSONだけを返す
- security は severity/resource/finding/remediation を含める
- cost は resource/recommendation/estimatedSavings を含める
- architecture は pillar/finding/recommendation を含める
- WebSearch と WebFetch は使わない

Azure export JSON:
<PASTE_JSON_HERE>
```

## Test Option 2: azd CLI

Use `azd ai agent run` when you want the hosted-agent quickstart path and do not need custom HTTP handling.

```powershell
azd ai agent run
```

Then paste either the smoke-test prompt or inline-input prompt from the portal section.

If the installed `azd` extension exposes non-interactive run flags in your version, prefer those for repeatable CI-style checks. The exact flags can change with extension versions, so verify with:

```powershell
azd ai agent run --help
```

## Test Option 3: Direct Responses API

Use the direct API when you want to inspect the raw response shape and automate verification.

First load the endpoint from azd values.

```powershell
$values = azd env get-values
$endpointLine = $values | Select-String '^AGENT_.*_ENDPOINT='
$endpoint = ($endpointLine -split '=', 2)[1].Trim('"')
```

Authenticate with Azure CLI or Azure Developer CLI according to the hosted agent quickstart for your environment. If your endpoint requires a bearer token, acquire it for the Foundry/Azure AI resource scope used by the quickstart, then send it as `Authorization: Bearer <token>`.

The body shape is the same responses protocol body used locally.

```powershell
$prompt = 'samples/bad-config/azure-export.json を Read で読み、WebSearch と WebFetch と Agent ツールは使わず、見えているJSONだけを根拠に summary/security/cost/architecture の固定JSONだけを返してください。説明文は不要です。'
$body = @{ input = $prompt; stream = $false } | ConvertTo-Json -Depth 8
$response = Invoke-RestMethod -Uri "$endpoint/responses" -Method Post -ContentType 'application/json' -Body $body
$texts = @($response.output | ForEach-Object { $_.content } | ForEach-Object { $_.text } | Where-Object { $_ })
$texts[-1]
```

The final answer may be in the last output item. Do not validate only `output[0]`, because Claude can emit an intermediate message before the final result.

For inline-input testing, load the JSON and embed it in the prompt.

```powershell
$json = Get-Content ..\backend\samples\bad-config\azure-export.json -Raw
$prompt = @"
次の Azure export JSON を分析してください。コンテナ内のサンプルファイルは読まず、このメッセージ内の JSON だけを根拠にしてください。

summary/security/cost/architecture の固定JSONだけを返してください。WebSearch と WebFetch は使わないでください。

Azure export JSON:
$json
"@
$body = @{ input = $prompt; stream = $false } | ConvertTo-Json -Depth 8
$response = Invoke-RestMethod -Uri "$endpoint/responses" -Method Post -ContentType 'application/json' -Body $body
$texts = @($response.output | ForEach-Object { $_.content } | ForEach-Object { $_.text } | Where-Object { $_ })
$texts[-1]
```

## Harness Verification Matrix

Use this matrix to decide whether the implemented harness is functioning, not just whether the model returned a plausible answer.

| Check | How To Verify | Passing Signal |
| --- | --- | --- |
| Hosted outer harness | Portal, `azd ai agent run`, or direct `/responses` returns a completed response | Agent is reachable as a Hosted Agent, not only as local Python |
| Responses protocol | Direct API returns a responses-shaped object with `output` items | `status` is completed and output text is present |
| Container packaging | Smoke prompt can read `samples/bad-config/azure-export.json` | Result reports 5 resources or findings from the bundled sample |
| Claude Code project context | Agent follows `backend/CLAUDE.md` and stable schema instructions | Final answer uses `summary/security/cost/architecture` |
| Built-in tools | Smoke prompt reads the file without asking for permission | File-specific findings appear, not generic Azure advice |
| SubAgent routing | Ask for `explore-agent` inventory | Provider/type counts include Storage, NSG, VM, SQL DB, DiagnosticSettings |
| Specialist intent | Full review prompt produces security, cost, and architecture findings | Findings map to concrete resources and all three dimensions are populated |
| Workspace contract | Ask the agent to write a short report under `work/` | Generated artifact path is under `AGENT_WORKSPACE_ROOT` |
| Telemetry | Inspect Foundry/App Insights traces after a request | Hosted request, agent run, and model/tool spans or events are visible |
| Output contract | Parse the final text as JSON after stripping Markdown fences if present | Required top-level keys exist and arrays contain required fields |

## Acceptance Prompts

### 1. Bundled Fixture Smoke Test

```text
samples/bad-config/azure-export.json を Read で読み、summary/security/cost/architecture の固定JSONだけを返してください。WebSearch と WebFetch と Agent ツールは使わないでください。
```

Expected content:

- `summary.resourcesAnalyzed` is `5`
- Storage account findings include public blob access, TLS 1.0, and HTTPS-only disabled
- NSG finding includes open RDP from Internet
- Cost findings mention the dev VM and/or SQL capacity
- Architecture findings mention missing availability, zone redundancy, local backup redundancy, or empty diagnostics

### 2. Inline JSON Acceptance Test

```text
次の Azure export JSON を分析してください。コンテナ内のファイルは読まず、この入力だけを根拠に summary/security/cost/architecture の固定JSONだけを返してください。

<PASTE_JSON_HERE>
```

Expected content is similar to the smoke test. This test is more important for API/Portal readiness because it proves the Hosted Agent can analyze user-provided request content.

### 3. Explore Agent Routing Test

```text
samples/bad-config/azure-export.json を explore-agent で棚卸ししてください。最終回答は resource count by provider/type だけをJSONで返してください。
```

Expected output:

```json
{
  "Microsoft.Compute/virtualMachines": 1,
  "Microsoft.Insights/diagnosticSettings": 1,
  "Microsoft.Network/networkSecurityGroups": 1,
  "Microsoft.Sql/servers/databases": 1,
  "Microsoft.Storage/storageAccounts": 1
}
```

## Troubleshooting During Hosted Tests

| Symptom | Likely Cause | Action |
| --- | --- | --- |
| Portal works but direct API fails | Missing or wrong auth header | Use the auth method from the hosted-agent quickstart and confirm endpoint URL |
| File path smoke test fails | Sample was not included in the image or cwd is wrong | Confirm `backend/Dockerfile` build context and `backend/main.py` cwd |
| Inline JSON test works but file path test fails | Harness is fine, packaged fixture path is wrong | Fix sample placement or prompt path |
| File path test works but inline JSON is weak | Prompt relies too much on local file workflow | Strengthen request-content instructions and schema contract |
| Output has multiple messages | Responses protocol returned intermediate assistant text | Validate the last non-empty output text |
| Findings are generic | Agent did not inspect the file/input or lacked evidence | Use the smoke prompt with explicit `Read`, or paste the JSON inline |
| No traces appear | App Insights connection was not wired into the hosted environment | Check `APPLICATIONINSIGHTS_CONNECTION_STRING` and `APPINSIGHTS_CONNECTION_STRING` mapping |

## Decision Criteria

Treat the Hosted Agent validation as passed when all of these are true:

1. Hosted endpoint can be invoked from Portal or direct API.
2. Bundled fixture smoke test succeeds.
3. Inline JSON acceptance test succeeds.
4. `explore-agent` routing test succeeds.
5. Final output follows the fixed contract.
6. At least one trace or telemetry signal is visible for the hosted request.

If only the bundled file test passes, the container and tool path are working but Hosted input handling is not fully proven. If only the inline JSON test passes, the harness is usable, but the demo fixture packaging path should be fixed before presenting the Part A demo.
