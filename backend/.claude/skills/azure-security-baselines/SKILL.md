---
name: azure-security-baselines
description: Azure security review guidance for exported resources. Use when checking network exposure, encryption, secrets, identity boundaries, and public access risks.
user-invocable: false
---

Apply this skill when analyzing Azure infrastructure definitions or exported resource lists.

Focus on evidence-driven checks such as:

- Public endpoints, public network access, and open inbound rules
- Weak TLS settings, HTTP allowed, or insecure protocol configurations
- Shared key access, local auth, broad RBAC, or missing managed identity usage
- Missing encryption, key management gaps, and data exfiltration risk
- Internet-facing databases, storage accounts, or admin surfaces

When reporting findings:

1. Reference the exact resource name and type.
2. Explain the risk in plain language.
3. Recommend the most direct remediation.
4. Distinguish confirmed misconfiguration from likely concern.