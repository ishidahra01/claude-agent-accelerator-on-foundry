from __future__ import annotations

import json


EXPECTED_ANALYSIS_OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["summary", "security", "cost", "architecture"],
    "properties": {
        "summary": {
            "type": "object",
            "required": ["resourcesAnalyzed", "securityFindings", "costSavingsOpportunities"],
            "properties": {
                "resourcesAnalyzed": {"type": "integer", "minimum": 0},
                "securityFindings": {"type": "integer", "minimum": 0},
                "costSavingsOpportunities": {"type": "integer", "minimum": 0},
            },
        },
        "security": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["severity", "resource", "finding", "remediation"],
                "properties": {
                    "severity": {"type": "string"},
                    "resource": {"type": "string"},
                    "finding": {"type": "string"},
                    "remediation": {"type": "string"},
                },
            },
        },
        "cost": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["resource", "recommendation", "estimatedSavings"],
                "properties": {
                    "resource": {"type": "string"},
                    "recommendation": {"type": "string"},
                    "estimatedSavings": {"type": "string"},
                },
            },
        },
        "architecture": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["pillar", "finding", "recommendation"],
                "properties": {
                    "pillar": {"type": "string"},
                    "finding": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
            },
        },
    },
}


def analysis_output_instructions() -> str:
    schema = json.dumps(EXPECTED_ANALYSIS_OUTPUT_SCHEMA, indent=2)
    return f"""
For Azure resource analysis tasks, synthesize the final answer around this stable contract:

```json
{{
  "summary": {{ "resourcesAnalyzed": 25, "securityFindings": 12, "costSavingsOpportunities": 8 }},
  "security": [{{ "severity": "Critical", "resource": "...", "finding": "...", "remediation": "..." }}],
  "cost": [{{ "resource": "...", "recommendation": "...", "estimatedSavings": "$15/month" }}],
  "architecture": [{{ "pillar": "Operational Excellence", "finding": "...", "recommendation": "..." }}]
}}
```

Use Japanese prose around the report when helpful, but keep these keys stable because evaluation,
control, and ROI calculations depend on them. If evidence is incomplete, return an empty array for
that category and explain the uncertainty outside the JSON contract.

Reference schema for validators and future ACS controls:

```json
{schema}
```
""".strip()