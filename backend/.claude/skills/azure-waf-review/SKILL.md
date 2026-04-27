---
name: azure-waf-review
description: Azure Well-Architected and reliability review guidance for exported resources. Use when assessing resiliency, fault domains, operational readiness, and architectural fit.
user-invocable: false
---

Use this skill to review architecture and reliability.

Check for:

- Single points of failure such as single-instance compute or disabled HA
- Missing zone redundancy or insufficient resilience for data services
- Weak segmentation or resource coupling that hurts operability
- Architecture mismatches with Well-Architected pillars such as reliability and operational excellence
- Missing observability, backup, lifecycle, or recovery considerations that can be inferred from the resource set

When reporting:

1. Separate confirmed issues from architecture assumptions.
2. Explain the likely failure mode.
3. Suggest a pragmatic next step, not just an idealized target state.