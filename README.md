# Production Agent Labs

Build **Nimbus, the Cymbal Cloud Ops Copilot** — an ADK agent — from a laptop prototype to a
deployed agent on the Gemini Enterprise Agent Platform. One service per lab.

| Lab | Focus | Needs a GCP project? |
|-----|-------|----------------------|
| [01-adk](./labs/01-adk/) | The Nimbus agent graph with ADK | No — an AI Studio API key is enough |
| [02-skills](./labs/02-skills/) | Skills the agent can call (Skill Registry) | Yes |
| [03-mcp-servers](./labs/03-mcp-servers/) | MCP servers on Cloud Run + Agent Registry | Yes |
| [04-deployments](./labs/04-deployments/) | Deploying to Agent Runtime | Yes |
| [05-agents-cli](./labs/05-agents-cli/) | Building agents with `agents-cli` and your coding agent | Yes |
| [06-bonus-long-horizon-harness](./labs/06-bonus-long-horizon-harness/) | *Bonus.* Durable sessions, cross-session memory, sandboxed execution | Yes |
| [07-bonus-register-to-gemini-enterprise](./labs/07-bonus-register-to-gemini-enterprise/) | *Bonus.* Gemini Enterprise Apps, agent cards, A2A | Yes — presenter demo |
| [08-bonus-ax-substrate](./labs/08-bonus-ax-substrate/) | *Bonus, pointer only.* AX + Agent Substrate as a durable, sandboxed runtime — [**watch the demo**](https://storage.googleapis.com/alanblount-demo-public/ax/ax-substrate-demo2.mp4) | No |

---

## Setup

**Prerequisites: [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and Python
3.10+.** `uv` is the only installer documented here, and it can install Python for you. Get the
code and an environment:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
git clone https://github.com/zeroasterisk/ai4-gcp-agent-labs
cd ai4-gcp-agent-labs
uv venv .venv
source .venv/bin/activate
uv pip install -r labs/01-adk/requirements.txt
```

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv python install 3.12
git clone https://github.com/zeroasterisk/ai4-gcp-agent-labs
cd ai4-gcp-agent-labs
uv venv .venv
.venv\Scripts\Activate.ps1
uv pip install -r labs/01-adk/requirements.txt
```

In PowerShell `export NAME=value` becomes `$env:NAME = "value"`, and `test.sh` needs Git Bash
or WSL.

</details>

Now authenticate. Pick **one** block — **the first line is the only thing you edit**; the rest
reuses it. Rather be walked through it? **`python check_prereqs.py --setup`** runs the same
gcloud steps interactively: shows each command, asks first, verifies, then checks everything.

### Local laptop with a GCP project — the default

Needs the [gcloud CLI](https://cloud.google.com/sdk/docs/install).
`gcloud auth login --update-adc` signs gcloud in **and** writes your Python code's Application
Default Credentials in one browser popup. It runs before the project is set, so
`set-quota-project` realigns them.

```bash
export GOOGLE_CLOUD_PROJECT="my-id-here"
export GOOGLE_CLOUD_LOCATION=global
gcloud auth login --update-adc
gcloud config set project "$GOOGLE_CLOUD_PROJECT"
gcloud auth application-default set-quota-project "$GOOGLE_CLOUD_PROJECT"
gcloud services enable aiplatform.googleapis.com --project "$GOOGLE_CLOUD_PROJECT"
python check_prereqs.py
```

### Cloud Shell

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://shell.cloud.google.com/cloudshell/open?cloudshell_git_repo=https://github.com/zeroasterisk/ai4-gcp-agent-labs)

The button clones the repo. Cloud Shell is **already authenticated** — no `gcloud auth login`,
**no ADC login**. `uv` is not preinstalled, so this block replaces the one above.

```bash
cd ai4-gcp-agent-labs
export GOOGLE_CLOUD_PROJECT="my-id-here"
export GOOGLE_CLOUD_LOCATION=global
gcloud config set project "$GOOGLE_CLOUD_PROJECT"
gcloud services enable aiplatform.googleapis.com --project "$GOOGLE_CLOUD_PROJECT"
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv venv .venv
source .venv/bin/activate
uv pip install -r labs/01-adk/requirements.txt
python check_prereqs.py
```

### No GCP project — AI Studio key, Lab 01 only

A free [AI Studio key](https://aistudio.google.com/apikey) needs no project, billing or APIs.
Lab 01 works completely on it; Labs 02-04 do not.

```bash
export GOOGLE_API_KEY="my-key-here"
export GOOGLE_GENAI_USE_ENTERPRISE=False
python check_prereqs.py
```

Expect `RESULT: all checks passed.` Then start Lab 01: `cd labs/01-adk && ./test.sh` should
print `ALL PASSED`.

**Everything else** — picking a path, creating a GCP project from zero, corporate mirrors and
TLS, all the variables, troubleshooting — is in **[`docs/setup.md`](./docs/setup.md)**.

---

## Prefer to work through a coding agent?

[Lab 05](./labs/05-agents-cli/) is `agents-cli`: it installs skills that make
Antigravity, Claude Code, Codex or Cursor an expert in Agent Platform, so you
describe what you want instead of learning every CLI. Labs 01-04 teach the
primitives by hand first, which is what makes the shortcut legible.

## Tests

`./test.sh` runs the offline tests and needs no credentials.
`RUN_LIVE=1` additionally runs the live tests against your project.

```bash
cd labs/01-adk/
./test.sh
```

```bash
RUN_LIVE=1 ./test.sh
```

Each lab's `./test.sh` checks its own imports first and tells you exactly what to install if
something is missing.

## Clean up

Labs 03 and 04 create billable resources. One script removes them, and it skips whatever is not there:

```bash
bash scripts/teardown.sh
```

## What's next

Three optional bonus chapters cover the parts that don't fit in a hands-on hour:
[**06 — long-horizon harness**](./labs/06-bonus-long-horizon-harness/) (durable sessions,
cross-session memory, sandboxed execution),
[**07 — register to Gemini Enterprise**](./labs/07-bonus-register-to-gemini-enterprise/)
(Gemini Enterprise Apps, agent cards, A2A), and
[**08 — AX + Agent Substrate**](./labs/08-bonus-ax-substrate/) (durable execution and
sandboxed isolation as a runtime — a pointer with a
[demo video](https://storage.googleapis.com/alanblount-demo-public/ax/ax-substrate-demo2.mp4),
not something to type). They are presented from slides rather than typed; each
chapter opens with a scope box saying what you can run today and what it costs.
