# Lab 07 (bonus). Register a deployed agent to Gemini Enterprise

**Presenter demo, not attendee hands-on** · ~10 minutes reading, plus one 5-minute local detour
that genuinely is hands-on.

> ### Scope and cost
>
> The publish flow needs a chain of things no attendee will have in the room: a GCP project
> with billing, the **Discovery Engine API** enabled, the **Gemini Enterprise Admin** role, an
> **already-deployed** ADK agent on Agent Runtime, and an **existing Gemini Enterprise app**.
> Registration itself is a metadata write and is effectively free. ⚠️ The **Agent Runtime
> behind it is not** — you pay for a deployed agent 24/7 before you can register anything, and
> un-registering does **not** delete it. [§3](#3-the-part-you-can-actually-run-the-a2a-agent-card)
> needs none of that; it costs a ~785 MB scaffold install and nothing else.

## 1. What you are registering into

"Gemini Enterprise" is two things wearing one name. The **web app** is the employee-facing front door: chat, search over company
data, and an **Agent Gallery**. **Gemini Enterprise Agent Platform** is
the developer platform underneath — Agent Runtime, Sessions, Memory Bank, Sandboxes, Agent
Registry, Skill Registry. Labs 02-04 deploy to the second; registering publishes into the
first, on the "From your organization" shelf.

A Gemini Enterprise app's resource name looks like
`projects/{project_number}/locations/{location}/collections/{collection}/engines/{engine_id}`.
Per Google's [agents overview](https://docs.cloud.google.com/gemini/enterprise/docs/agents-overview),
an admin can register ADK agents hosted on Agent Runtime (what lab 04 builds), **A2A agents**
— anything that speaks the [Agent2Agent protocol](https://a2a-protocol.org/) and publishes an
agent card, wherever it runs — Dialogflow agents, and no-code Agent Designer agents. A2A agents
already in Agent Registry can be discovered and added directly: the payoff for lab 03's
governed identity.

> **"Agent Runtime" and "reasoning engine" are the same thing.** The API resource is still
> named `ReasoningEngine` for backwards compatibility. Everybody trips on this exactly once.

## 2. Publishing

`agents-cli publish gemini-enterprise --list` resolves your project number via `gcloud` and
returns the apps you can publish into — or `{"apps": []}` with `HTTP 403` warnings if you have
no entitlement. The command works; the API says no.

```bash
agents-cli publish gemini-enterprise \
  --registration-type adk \
  --agent-runtime-id "projects/PROJECT_NUMBER/locations/LOCATION/reasoningEngines/ENGINE_ID" \
  --gemini-enterprise-app-id "projects/PROJECT_NUMBER/locations/global/collections/default_collection/engines/APP_ID" \
  --display-name "Nimbus - Cymbal Cloud Ops Copilot" \
  --description "Answers on-call questions about Cymbal Cloud service health." \
  --tool-description "Use for service health, error rates, latency, ownership and recent deploys."
```

If you deployed with `agents-cli`, `--agent-runtime-id` can be omitted — it is read from
`deployment_metadata.json`. For an A2A agent, swap in `--registration-type a2a` and
`--agent-card-url "https://YOUR-SERVICE.run.app/a2a/app/.well-known/agent-card.json"`. That is
the interesting case for a mixed estate: the agent does not have to be on Agent Runtime, or
Python, or ADK. It has to publish a card. That is the whole contract.

> **Teardown.** Un-registering from the Gemini Enterprise console does **not** delete the Agent
> Runtime. Delete the reasoning engine separately or it keeps billing.

## 3. The part you can actually run: the A2A agent card

No Gemini Enterprise, no deployment.

```bash
agents-cli create my-agent -a adk -d cloud_run -p --session-type in_memory -y
cd my-agent
agents-cli install
```

> ⚠️ **Billing warning — the trap in this whole toolchain.** Note `--session-type in_memory`.
> Scaffold with **`--session-type agent_platform_sessions`** instead and the generated session
> service will **silently create a billed Vertex Agent Engine in your project the first time
> you run `agents-cli playground`** — no prompt, no confirmation. You did not deploy anything;
> you started a local UI. Use `in_memory` unless you mean it.

`agents-cli playground` does **not** serve the A2A routes — `/a2a/...` returns 404 there. The
agent card comes from the project's own `app/fast_api_app.py`, which calls
`attach_a2a_routes(...)` at startup. (A2A is not an add-on you go and find: the generated
`pyproject.toml` pins `a2a-sdk[http-server]` as a default dependency.) So run the real app —
this is what the generated Dockerfile runs:

```bash
gcloud auth application-default login
uv run uvicorn app.fast_api_app:app --host 127.0.0.1 --port 8080
```

Then, in another terminal:

```bash
curl -s http://127.0.0.1:8080/a2a/app/.well-known/agent-card.json | python3 -m json.tool
```

Unlike `playground`, this app needs credentials just to *start*: `fast_api_app.py` calls
`google.auth.default()` and creates a Cloud Logging client at import time. Simply starting it makes no model
calls simply by starting.

## Next

[**Lab 08 — AX and Agent Substrate**](../08-bonus-ax-substrate/) is the runtime underneath the
agent. [**Lab 06 — The long-horizon harness**](../06-bonus-long-horizon-harness/) is what a
production-shaped agent looks like inside.
