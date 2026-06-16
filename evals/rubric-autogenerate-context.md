# Azure WAF Review Agent Rubric Autogenerate Context

Use this file as reference context when creating a Foundry Rubric evaluator with Autogenerate.

## Purpose

The evaluator scores an Azure Well-Architected Review Agent. The agent reads Azure resource export JSON and returns a structured review covering security, cost, and architecture risks.

The rubric should judge whether the response is useful, grounded, complete, and operationally actionable for an Azure operator.

## Expected Output Contract

The response must be a JSON object with these top-level keys:

- `summary`
- `security`
- `cost`
- `architecture`

The `summary` object must include:

- `resourcesAnalyzed`
- `securityFindings`
- `costSavingsOpportunities`

Each `security` finding must include:

- `severity`
- `resource`
- `finding`
- `remediation`

Each `cost` finding must include:

- `resource`
- `recommendation`
- `estimatedSavings`

Each `architecture` finding must include:

- `pillar`
- `finding`
- `recommendation`

## What Good Looks Like

A good response:

- identifies important Azure Well-Architected risks present in the input;
- names the affected resources;
- grounds every finding in the provided configuration;
- gives concrete, implementable remediation or recommendations;
- assigns severity according to risk impact;
- prioritizes public exposure and administrative access as High or Critical;
- includes cost opportunities when resources appear oversized or always-on without justification;
- includes architecture findings for reliability, operational excellence, observability, and backup gaps;
- keeps summary counts consistent with the returned arrays;
- avoids generic Azure best-practice advice that is not tied to a resource in the input;
- avoids inventing resources, settings, telemetry, utilization, or savings not present in the input.

## Important Security Signals

The response should detect:

- storage accounts with public blob access enabled;
- storage accounts that do not enforce HTTPS-only traffic;
- weak TLS versions such as TLS 1.0;
- NSG rules that allow inbound administrative access from the internet, such as RDP 3389 or SSH 22;
- Key Vault public network exposure when visible in the input;
- disabled soft delete or purge protection when visible in the input;
- missing encryption or weak identity controls when visible in the configuration.

Public exposure and internet-exposed administrative access should normally be High or Critical severity.

## Important Cost Signals

The response should detect:

- oversized VMs;
- always-on development or test resources;
- database capacity that appears overprovisioned;
- premium SKUs or capacity choices that should be reviewed;
- resources where savings estimates require utilization data.

Cost recommendations should include a concrete action, such as right-sizing, scheduling shutdown, reviewing vCore utilization, or changing SKU. If exact savings are not known, the response should state what data is needed to estimate savings.

## Important Architecture Signals

The response should detect:

- missing zone redundancy for production resources;
- local-only backup redundancy where geo-redundancy is expected;
- disabled or missing backups;
- empty diagnostic settings;
- missing logs or metrics;
- reliability and operational excellence gaps that affect production readiness.

Architecture recommendations should map to Azure Well-Architected pillars such as Reliability, Security, Cost Optimization, and Operational Excellence.

## Scoring Guidance

The generated rubric should include these dimensions:

1. Risk coverage
   Measures whether the response finds the important security, cost, and architecture risks present in the input.

2. Evidence accuracy
   Measures whether findings are grounded in the provided Azure configuration and avoid hallucination.

3. Remediation quality
   Measures whether findings include concrete, implementable remediation or recommendations.

4. Severity prioritization
   Measures whether the response prioritizes high-impact risks appropriately.

5. Schema compliance
   Measures whether the response follows the required JSON structure and keeps summary counts consistent.

Risk coverage and evidence accuracy should have the highest weights. Schema compliance should be always applicable.

## Failure Examples

A response should be penalized if it:

- misses public blob access;
- misses internet-exposed RDP or SSH;
- reports generic best practices without naming affected resources;
- omits remediation for security findings;
- invents resources or settings;
- assigns public exposure as Low severity;
- returns prose instead of the required JSON object when JSON-only output is requested;
- has summary counts that do not match the arrays;
- reports cost savings without evidence or assumptions.

## Demo Fixture Signals

For the included bad-config fixture, examples of expected signals include:

- public blob access on the storage account;
- weak TLS or HTTPS-only configuration on the storage account;
- internet-exposed RDP on the NSG;
- oversized or always-on development VM cost opportunity;
- SQL capacity right-sizing opportunity;
- missing zone redundancy or weak backup redundancy;
- empty diagnostic settings.

Treat these as examples from the demo fixture, not as the only valid Azure Well-Architected review criteria.