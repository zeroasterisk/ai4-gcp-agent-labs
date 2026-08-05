# Setup — everything that is not the happy path

**The copy-paste blocks live in the [README](../README.md#setup).** This file is the rest:
choosing a path, starting from no Google Cloud project, corporate networks, the variables, and
troubleshooting. `python check_prereqs.py --setup` walks the gcloud steps interactively.

## Which path should I pick?

| Your situation | Go here |
| - | - |
| A GCP project with billing | [Cloud Shell or local laptop](../README.md#setup) — either block works |
| No project, but you can create one | [From zero](#from-zero-create-a-gcp-project) (~10 minutes), then those blocks |
| No project and no way to get one | [AI Studio key](../README.md#no-gcp-project--ai-studio-key-lab-01-only) — Lab 01 only, ~3 minutes |

Labs 02-04 need a real project: the Skill and Agent registries and Agent Runtime are managed
services an API key cannot reach. Vertex AI + ADC is the default; the key works for Lab 01 and
is a dead end at Lab 02.

## From zero: create a GCP project

1. **Google account.** A personal `@gmail.com` is often *easier*: org policies routinely block
   ADC logins, billing changes and project creation.
2. **Free trial:** [cloud.google.com/free](https://cloud.google.com/free). The card is identity
   verification; nothing auto-charges at the end.
3. **Create a project** — [Console](https://console.cloud.google.com/) project picker → *New
   Project*. Note the project **ID**, not the display name. Or:

   ```bash
   gcloud projects create my-ai4-labs-project --name="AI4 Agent Labs"
   ```

4. **Link billing** — Console → *Billing* → *Link a billing account*. Vertex AI serves nothing
   without it, even with free credits. The most common blocker.
5. **Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install)** (Cloud Shell has it),
   then run the [local block](../README.md#local-laptop-with-a-gcp-project--the-default), which
   enables the one API Labs 01-02 need.

Labs 03 and 04 need more APIs — enable them when you get there:

<details>
<summary>All of labs 01-04 in one command</summary>

```bash
gcloud services enable \
  aiplatform.googleapis.com run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com agentregistry.googleapis.com \
  storage.googleapis.com logging.googleapis.com monitoring.googleapis.com \
  cloudtrace.googleapis.com cloudresourcemanager.googleapis.com
```

</details>

Enabling is not instant: allow a minute or two, and the first call can still 403 while it
propagates. It needs `serviceusage.services.enable`, which many corporate projects withhold —
use a personal project or the AI Studio key rather than fighting your admin.

## Corporate laptops and networks

Two different failures, two different fixes, both in the table below. A system-wide
`/etc/pip.conf` or `/etc/uv/uv.toml` pointing at a **private mirror** without `google-adk` needs
`UV_DEFAULT_INDEX`; a **TLS-inspecting proxy** needs a CA bundle, and the index fix will not
help it. `python check_prereqs.py` prints which index you are on.

## Variables

| Variable | Default | What it controls |
| - | - | - |
| `GOOGLE_CLOUD_PROJECT` | *(none — you set it)* | Your project ID. Vertex path only. |
| `GOOGLE_CLOUD_LOCATION` | `global` | Where the **model** is served. `global` carries the most models. |
| `GOOGLE_CLOUD_AGENT_ENGINE_LOCATION` | `GOOGLE_CLOUD_LOCATION` if that is a real region, else `us-central1` | Where **Agent Engine and the Skill Registry** live (Labs 02, 04). Regional, never `global`. The SDK's own variable. |
| `GEMINI_MODEL` | `gemini-flash-latest` | The model. Escape hatch when the default is unavailable. |
| `GOOGLE_GENAI_USE_ENTERPRISE` | `True` | `True` = Vertex, `False` = AI Studio. Replaces the deprecated `GOOGLE_GENAI_USE_VERTEXAI`. |
| `GOOGLE_API_KEY` | *(none)* | AI Studio key. Used only when the line above is not true. |
| `REGISTRY_LOCATION` | `global` | Where the **Agent Registry** entry lives (Lab 03). MCP registration is not supported in the `us`/`eu` multi-regions. |
| `CLOUD_RUN_REGION` | `us-central1` | Where the MCP server runs (Lab 03). |

A `.env` works instead of exports — `cp labs/01-adk/.env.example labs/01-adk/.env`. The lab's
`.env` loads first, then the root's; real environment variables win, and placeholders like
`your-project-id` count as unset.

## Troubleshooting

| Symptom | Cause | Fix |
| - | - | - |
| `Could not find a version that satisfies the requirement google-adk ... (from versions: none)`, or a 401 from an unfamiliar host | A private mirror, set by system-wide config that beats project config. | `export UV_DEFAULT_INDEX=https://pypi.org/simple` (PowerShell: `$env:UV_DEFAULT_INDEX="https://pypi.org/simple"`). |
| `SSLError` / `CERTIFICATE_VERIFY_FAILED` | TLS-inspecting proxy. The index fix will not help. | `export SSL_CERT_FILE=/path/to/corp-ca.pem` and `export REQUESTS_CA_BUNDLE=/path/to/corp-ca.pem`. |
| `USER_PROJECT_DENIED` in Cloud Shell | You are on Cloud Shell's throwaway default project. | `gcloud config set project "$GOOGLE_CLOUD_PROJECT"`. |
| `ADC quota project (X) is not GOOGLE_CLOUD_PROJECT (Y)`, or an unexplained 403 | ADC was written before the project was set, so it bills elsewhere. | `gcloud auth application-default set-quota-project "$GOOGLE_CLOUD_PROJECT"`. |
| `UREQ_PROJECT_BILLING_NOT_FOUND`, or `FAILED_PRECONDITION` / "Billing must be enabled" | No billing account linked. Free credits still need one. | Link at `https://console.cloud.google.com/billing/linkedaccount?project=YOUR_PROJECT_ID`. At a workshop, ask the instructor for credits first. |
| `SERVICE_DISABLED` / 403 naming `aiplatform.googleapis.com` | Vertex AI API not enabled here. | `gcloud services enable aiplatform.googleapis.com --project "$GOOGLE_CLOUD_PROJECT"`, wait a minute. |
| `404 NOT_FOUND` / `Publisher Model ... was not found` | Regional endpoints carry fewer models than `global`. | `export GOOGLE_CLOUD_LOCATION=global`. Still failing: `python check_prereqs.py --probe-models`, then `export GEMINI_MODEL=<result>`. |
| `Your default credentials were not found` / `invalid_grant` | ADC missing or expired. | `gcloud auth login --update-adc`, then re-run the quota-project line. |
| `ERROR: GOOGLE_CLOUD_PROJECT is not set.` | Nothing exported, or `.env` still has the placeholder. | Export it, or fill in `.env`. |
| `this lab needs a Google Cloud project. You are in AI Studio mode` | API key path in Lab 02, 03 or 04. | Use a real project; a key cannot reach the registries or Agent Runtime. |
| `this lab's dependencies are missing from the Python you are running` | Installed into one interpreter, running another. | Re-activate the venv: `python -c "import sys; print(sys.executable)"`. |
| `ImportError` naming `mcp.shared.session` or `mcp.server.fastmcp` | You have `mcp` 2.x; the labs pin `mcp>=1.24,<2`. | `uv pip install "mcp>=1.24,<2"`. |
| Windows: `.venv/bin/activate: No such file or directory`, or "running scripts is disabled" | Windows venvs use `Scripts\`; PowerShell blocks unsigned scripts. | `.venv\Scripts\Activate.ps1`, after `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. |
| `UserWarning: [EXPERIMENTAL] feature FeatureName.PLUGGABLE_AUTH is enabled.` | ADK flagging experimental features. | **Cosmetic. Ignore it.** |
| `adk web` loads but chatting fails with 403 on `/sessions` | You are on Cloud Shell Web Preview or another proxied host; the dev UI blocks cross-origin writes. | Start it as `adk web src --allow_origins="*"`. |
