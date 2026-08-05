# Lab 08 (bonus). AX and Agent Substrate — the runtime under the agent

> **A pointer, not a lab.** Nothing here needs typing. It exists for people who finish labs
> 01-04 early and want to know what sits *underneath* an agent; it is discussed from slides
> during the session.

## ▶ Watch the demo first

**[AX + Agent Substrate demo (MP4, ~410 MB)](https://storage.googleapis.com/alanblount-demo-public/ax/ax-substrate-demo2.mp4)**

The video is the explanation. Large file — download it rather than stream it in a hall.

## The one-paragraph version

Labs 01-04 run model-generated Python with `UnsafeLocalCodeExecutor`, in your own interpreter,
with your own credentials. Fine for a laptop workshop, indefensible anywhere else. Three
projects sit under that slot:

- **[GKE Agent Sandbox](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/agent-sandbox)**
  — Kubernetes-native isolation for untrusted model-generated code: gVisor/Kata kernels,
  default-deny networking, pod snapshots. Generally available.
- **[Agent Substrate](https://github.com/agent-substrate/substrate)** — a control plane
  *beside* Kubernetes that multiplexes a large set of mostly-idle "actors" onto a small set of
  ready "workers"; its published demo runs ~250 stateful actors across 8 pods. Its README says
  plainly that it is **"not an officially supported Google product"** and **"not ready for
  production use."**
- **[Agent Executor (AX)](https://github.com/google/ax)** — a Go runtime that makes a
  long-running agent *resumable* by replaying a durable event log. Early development, Apache
  2.0; its README leads with a 🚧 breaking-changes warning.

Together they are the durable-execution half of the story.

## Three things the coverage gets wrong

1. **AX is not an agentic framework.** In its own words it is "agnostic of the framework used
   to build agents," and it is not a managed service either.
2. **AX does not claim ADK / LangChain / A2A support.** That compatibility list — ADK,
   LangChain, Claude Code / Codex, MCP servers-as-actors — belongs to **Agent Substrate**.
   Neither project's README claims A2A.
3. **Trajectory forking is roadmap, not shipped.** "Forking from event log and snapshots" and
   "trajectory exposition" are listed as upcoming, not shipped.

Also: AX itself is Go, but its built-in Antigravity harness runs as a **Python sidecar** that
AX bootstraps for you.

## If you want to try it yourself

The CLI installs with `go install github.com/google/ax/cmd/ax@latest`; getting past the first
prompt needs Gemini credentials (`GEMINI_API_KEY`, or Vertex ADC plus a project), and the
built-in Python harness needs `export PYTHONPATH=$HOME/.ax/python`.

⚠️ Everything on GKE is out of scope here: Agent Sandbox and Agent Substrate need a
**Kubernetes cluster that bills continuously** — control plane, nodes, and any warm pool you
keep hot — and warm pools trade money for latency by design. If you have a cluster to burn,
start from the
[install guide](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/how-install-agent-sandbox)
and the
[announcement](https://cloud.google.com/blog/products/containers-kubernetes/bringing-you-agent-sandbox-on-gke-and-agent-substrate).

## Next

[**Lab 06 — The long-horizon harness**](../06-bonus-long-horizon-harness/) solves the same
durability problem one layer up, in application code on a managed runtime.
[**Lab 07 — Register to Gemini Enterprise**](../07-bonus-register-to-gemini-enterprise/) is
about who gets to reach the agent once it runs.
