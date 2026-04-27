---
name: azure-cost-patterns
description: Azure cost optimization guidance for exported resources. Use when checking oversizing, always-on services, premium SKUs, and missing elasticity controls.
user-invocable: false
---

Use this skill for Azure cost reviews.

Look for:

- Oversized VM SKUs relative to the surrounding architecture
- Premium storage or networking tiers without clear justification
- Public IPs, gateways, or managed services that are always allocated
- Missing autoscale, auto-pause, serverless, or burst-friendly patterns
- HA, backup, or geo-redundancy choices that may be more expensive than needed

When writing recommendations:

1. Identify the costly configuration.
2. State why it may be wasteful.
3. Offer a lower-cost alternative or validation path.
4. Note uncertainty when utilization data is unavailable.