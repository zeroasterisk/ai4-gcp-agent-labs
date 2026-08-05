# Lab 03. MCP over HTTP

Deploy the ops tools as a Streamable HTTP MCP server on Cloud Run, catalogue it in Agent Registry, and point the same graph at it instead of a stdio subprocess.

## Run it

```bash
cd labs/03-mcp-servers
uv pip install -r requirements.txt
./test.sh
bash ./scripts/deploy_cloud_run.sh
bash ./scripts/register_in_registry.sh
python run_local.py "Is checkout healthy? What's its error rate?"
```

`deploy_cloud_run.sh` writes `.ops_mcp_url`; the agent reads it, and `OPS_MCP_URL` overrides it. Registration is long-running; the catalogue takes about a minute to show it.

This lab creates billable resources. Run [`scripts/teardown.sh`](../../scripts/teardown.sh) from the repo root when you are finished with the labs.

## Cannot deploy?

Some orgs block `--allow-unauthenticated` on Cloud Run. Run the server locally instead and skip both scripts — the agent already defaults to `http://localhost:8080/mcp/`.

```bash
python mcp_server/server.py &
sleep 3
python run_local.py "Is checkout healthy? What's its error rate?"
kill %1
```

## Read the code

| Where | Why it matters |
| - | - |
| `mcp_server/server.py:295-325` | `Mount("/mcp", ...)` over `StreamableHTTPSessionManager`, served by uvicorn. |
| `mcp_server/server.py:205-290` | `@server.list_tools()` and `@server.call_tool()` — the two handlers that make it MCP. |
| `src/nimbus/agent/agent.py:98-102` | `McpToolset(StreamableHTTPConnectionParams(url=...))` — the whole change from Lab 01. |
| `src/nimbus/agent/agent.py:55-73` | URL precedence: `OPS_MCP_URL`, the `.ops_mcp_url` marker, then localhost. Resolved offline, so the graph builds with no network. |
| `scripts/register_in_registry.sh:20-38` | The catalogue entry: an interface URL plus a tool spec. This is what makes the server discoverable rather than hardcoded. |

## Next
[Lab 04, Deployments](../04-deployments/) puts the graph itself on Agent Engine.
