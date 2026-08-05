# Lab 04. Deployments on Agent Engine

Ship the same graph to Agent Engine and query it as a managed endpoint.

## Run it

```bash
cd labs/04-deployments
uv pip install -r requirements.txt
./test.sh
export OPS_MCP_URL="$(cat ../03-mcp-servers/.ops_mcp_url)"
python deploy.py
python query_deployed.py "Is checkout healthy?"
python delete_deployed.py
```

Lab 03 must have run first: `OPS_MCP_URL` comes from the marker it writes, and an empty
value only surfaces minutes into the deploy.

A deploy takes about three minutes. Always finish with `delete_deployed.py`, or
run [`scripts/teardown.sh`](../../scripts/teardown.sh) from the repo root —
Agent Engine bills for as long as it exists.

## Read the code

| Where | Why it matters |
| - | - |
| `src/nimbus/runtime/deploy.py:116` | `AdkApp(agent=build_root_agent(), enable_tracing=True)` — the whole graph ships. |
| `src/nimbus/runtime/deploy.py:50-56` | `register_pickle_by_value` per nimbus module, or the engine fails with "No module named nimbus". |
| `src/nimbus/runtime/deploy.py:70-80` | `REQUIREMENTS` pins the local versions — the engine unpickles against the pickling stack. |
| `src/nimbus/runtime/deploy.py:132-143` | Staging bucket, `extra_packages=["src/nimbus"]`, env vars. |
| `src/nimbus/runtime/deploy.py:155-158` | Creates the engine, writes its name to `.agent_engine`. |
| `src/nimbus/runtime/client.py:43-49`, `:90-95` | Reads the marker back to query, and to delete. Deleting stops billing. |

## Next
[Lab 05, agents-cli](../05-agents-cli/) — how you'll actually do this day to day.
