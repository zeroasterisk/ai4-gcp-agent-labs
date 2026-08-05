# Lab 05. agents-cli — how you'll actually work

Assuming you use a coding agent, this is how you'll probably build, deploy and
customize agents from here on. `agents-cli` installs skills that make your coding
agent an expert in Agent Platform, so you don't have to learn every CLI and
service yourself.

Labs 01-04 walked you through the primitives by hand so you'd have a feel for
what is happening underneath. This lab is how to be fast.

Start in an **empty directory** — nothing from this repo is used here.

## Run it

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/getting-started/installation/), and [Node.js](https://nodejs.org/en/download).

```bash
mkdir ~/my-first-agent && cd ~/my-first-agent
uvx google-agents-cli setup
```

That installs the CLI and adds the skills to whichever coding agent you have —
[Antigravity](https://antigravity.google/), Claude Code, Codex, Cursor and others
are detected automatically.

Then open your coding agent in that directory and ask it for something:

> use agents-cli to build a caveman-style agent that compresses verbose text
> into terse, technical grunts. run it locally so I can try it, and explain what
> you are doing as you go.

When you want it deployed, ask for that too:

> now deploy it to agent platform runtime and give me the resource name, then
> tell me what it costs and how to tear it down.

## What the skills give it

| Skill | What your coding agent can now do |
| - | - |
| `scaffold` | create a project, add a deployment target, upgrade an existing one |
| `adk-code` | write ADK agents, tools, callbacks and sub-agents correctly |
| `deploy` | ship to Agent Runtime, Cloud Run or GKE |
| `eval` | generate eval cases, run them, grade the traces |
| `observability` | wire up tracing and read it back |
| `publish` | register a deployed agent to Gemini Enterprise |
| `workflow` | tie the above into a loop you can repeat |

Run `agents-cli --help` to see the commands directly, though the point is that
you mostly won't need to.

## Clean up

Anything you deploy here bills while it exists. Ask your coding agent to tear it
down, or run `agents-cli deploy --list` to find it and delete it in the console.

## Docs
[google.github.io/agents-cli](https://google.github.io/agents-cli) ·
[github.com/google/agents-cli](https://github.com/google/agents-cli)

## Next
Optional bonus tracks: [06](../06-bonus-long-horizon-harness/),
[07](../07-bonus-register-to-gemini-enterprise/), [08](../08-bonus-ax-substrate/).
