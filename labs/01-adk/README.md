# Lab 01. ADK primitives, running locally

Run Nimbus — a four-stage ADK graph with a skill, MCP tools, a code executor and memory — entirely on your laptop.

Do [setup](../../docs/setup.md) first; an AI Studio key is enough here. The service data is fixtures, not a real fleet.

## Run it

```bash
cd labs/01-adk
./test.sh
python run_local.py "Is checkout healthy? What's its error rate?"
adk web src --allow_origins="*"
```

Open <http://127.0.0.1:8000>, pick `nimbus`, and read the Events panel: one row per stage.
In Cloud Shell use **Web Preview** on port 8000; `--allow_origins` is what makes that work.
Copy `.env.example` to `.env` if you would rather not re-export on every new shell.

## Read the code

| Where | Why it matters |
| - | - |
| `src/nimbus/agent/agent.py:189-196` | The whole graph. `edges=[("START", load_history, investigate, analyze, report)]` — topology is data. |
| `src/nimbus/agent/agent.py:44-49` | `SkillToolset(skills=[load_skill_from_dir(...)])`. The runbook is a directory on disk; Lab 02 swaps it for the registry. |
| `src/nimbus/agent/agent.py:69-78` | `StdioConnectionParams` launches `mcp_server/server.py` as a subprocess. Lab 03 points this at HTTP. |
| `src/nimbus/agent/agent.py:81-83` | `UnsafeLocalCodeExecutor()` — model-written Python runs in your interpreter, unsandboxed. |
| `src/nimbus/agent/agent.py:187`, `src/nimbus/harness/memory_manager.py:43-51` | `after_agent_callback=auto_save_memories`. The broad `except` means a lost memory never breaks a turn. |
| `src/nimbus/agent/agent.py:88-123` | `load_history` is a plain function node. Not every stage needs a model. |

## Try these in `adk web`

Each one lights up a different part of the graph. Watch the Events panel as it answers.

```text
Is checkout healthy? What's its error rate?
Compare all four services and rank them by error rate.
Checkout is degraded — what does the runbook say I should do?
What did I ask you first?
```

One MCP tool call; then several plus the code stage; then the runbook skill; then session history.

## Next
[Lab 02, Skills](../02-skills/) moves the runbook into the managed Skill Registry.
