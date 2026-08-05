# Lab 02. Skills, registered and discovered

Move the runbook out of a local directory into the managed Skill Registry, and let Nimbus find it by semantic search.

## Run it

```bash
cd labs/02-skills
uv pip install -r requirements.txt
./test.sh
python skill_admin.py register
python skill_admin.py list
python skill_admin.py retrieve "how do I triage a checkout incident"
python demo.py "Is checkout healthy? Triage it."
```

`register` is long-running, and the skill ID stays reserved for 24 hours after a delete.

## Read the code

| Where | Why it matters |
| - | - |
| `skills/cymbal-ops-runbook/SKILL.md:1-5` | The whole artifact: front matter plus Markdown. `description` is what search reads. |
| `src/nimbus/agent/skills.py:143-148` | `skills.create(config={"local_path": ...})` zips the directory; returns an operation. |
| `src/nimbus/agent/skills.py:174` | `skills.retrieve` — the same lookup the agent makes at runtime. |
| `src/nimbus/agent/skills.py:253-257` | `SkillToolset(registry=...)` replaces Lab 01's `load_skill_from_dir`. Lazy project, so the graph still builds offline. |
| `src/nimbus/agent/agent.py:146-153` | The investigate node's tool list is the only place the swap shows. |

## Next
[Lab 03, MCP servers](../03-mcp-servers/) serves the ops tools over HTTP.
