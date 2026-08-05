---
name: cymbal-ops-runbook
description: Incident-triage runbook for Cymbal Cloud services. Use when assessing a service's health, classifying error-rate severity, and deciding next steps and escalation for an ops incident.
license: Apache-2.0
---

# Cymbal Ops Incident-Triage Runbook

A compact runbook Nimbus loads on demand to triage a Cymbal Cloud service incident
consistently. Cymbal services include `checkout`, `payments`, `search`, and `recommendations`.

## 1. Gather the signals
For the service in question, collect:
- **status** and **error_rate_pct** (last 1h) via `get_service_health`;
- **severity** via `get_error_rate`;
- **p95_latency_ms**, **owner_team**, and **last_deploy**.

## 2. Classify severity (from error rate, last 1h)
| error_rate_pct | severity |
| --- | --- |
| `>= 2.0` | **high** |
| `1.0 – 1.99` | **elevated** |
| `< 1.0` | **normal** |

A service is **degraded** if status is `degraded` OR severity is `high`.

## 3. Triage steps
1. Confirm the service name against the known fleet; if unknown, list known services.
2. Read current health + error rate; note whether it is in `prod`.
3. If severity is **high** in prod → treat as an active incident (step 4).
4. Correlate with **last_deploy**: a recent deploy (< 2h before onset) is the prime suspect —
   recommend inspecting that rollout first.
5. Check whether latency (**p95_latency_ms**) is also elevated (dependency/timeout signal).

## 4. Escalation
- **high** severity in **prod** → page the **owner_team**; recommend a rollback of the suspect
  deploy if one is implicated.
- **elevated** → notify the owner_team; monitor for trend.
- **normal** → no action; record the check.

## 5. Output
Summarize: service, status, error_rate_pct, severity, p95_latency_ms, owner_team, the most likely
cause, and the single recommended next step.
