# Lab 06 (bonus). The long-horizon harness

**Read-only in the room** · ~10 minutes reading · entirely optional.

> ### Scope and cost
>
> This chapter is a guided tour of somebody else's code. There is nothing here you can type in
> 40 minutes on conference wifi. Reading costs nothing. Scaffolding the sample costs **~1.2 GB**
> of disk and a long download. *Running* it needs `uv`, `google-agents-cli`, the Google Cloud
> SDK, `make`, Node.js 20.19+/22.12+ for the web UI, and a **GCP project with billing enabled**
> — and **every turn is billed per token**. ⚠️ `make deploy` stands up **always-on Cloud SQL
> and Cloud Scheduler**: Cloud Run scales to zero between turns, Cloud SQL does not. On
> Windows, use WSL.

## Why you would care

[**`google/adk-samples` → `core/python/long-horizon-harness`**](https://github.com/google/adk-samples/tree/main/core/python/long-horizon-harness)
calls itself *"a reference implementation of an agent harness on ADK and Google's Agent
Platform."* Labs 01-04 walk one agent from a laptop to Agent Runtime. Long Horizon answers the
next question: **what does the machinery around that agent look like when it has to run for
hours or days, across many sessions, for many users, without falling over?**

It answers with:

- cross-session memory from Memory Bank, through the same `PreloadMemoryTool` that Lab 01
  points at `InMemoryMemoryService`
- a per-user, JWT-routed sandbox kept warm between turns
- resumable sessions with turn compaction
- iteration-budget, no-progress and repeated-failure guardrails
- blocking and fire-and-forget sub-agents, and an A2A surface
- a nightly "dream" pass that consolidates memories off the critical path

The reason to read it is that **the agent graph is the same shape as lab 01's**. Every
difference — memory service, code executor, session store, model per node — is a slot, and a
slot is a configuration decision, not a rewrite.

It is **not an officially supported Google product**. Lift the patterns, don't ship the repo.

## Scaffolding it

Scaffold it with the full GitHub tree URL:

```bash
agents-cli create my-horizon \
  -a https://github.com/google/adk-samples/tree/main/core/python/long-horizon-harness
```

> ⚠️ **Silent billing trap.** Never add `--session-type agent_platform_sessions` to an
> `agents-cli create` unless you mean it. A project scaffolded that way **creates a billed
> Vertex Agent Engine in your GCP project the first time you run `agents-cli playground`** —
> no prompt, no confirmation, no obvious log line. Use `--session-type in_memory` for anything
> exploratory. This applies to every chapter in this repo.

⚠️ From the sample's own README: a sparse clone plus `make dev-local` runs tools on your host
with in-memory sessions and provisions nothing in GCP. The trade-off: no cross-session memory
and no sandbox isolation. Inference still goes to Agent Platform
either way — `local` moves *tool execution* to your host, not the model.
`uv run pytest tests/unit tests/integration` is the only part the sample describes as free;
`make dev-sandbox`, `make deploy` and `agents-cli eval run` all bill.

## Read next

- [The sample](https://github.com/google/adk-samples/tree/main/core/python/long-horizon-harness)
  — `README.md`, then `AGENTS.md`, then `docs/architecture.md` and `docs/security-model.md`.
- [Agents CLI documentation](https://google.github.io/agents-cli/) ·
  [install `uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Agent Platform primitives it builds on:
  [Sessions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sessions) ·
  [Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank) ·
  [Sandbox](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sandbox)

## Next

[**Lab 07 — Register to Gemini Enterprise**](../07-bonus-register-to-gemini-enterprise/) is the
other end of the same story: once an agent is deployed, how users and other agents reach it.
[**Lab 08 — AX and Agent Substrate**](../08-bonus-ax-substrate/) is the infrastructure-layer
answer to the durability problem Long Horizon solves in application code.
