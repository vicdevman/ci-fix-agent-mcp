# ci-triage-agent

An agent that takes a failing CI build, works out why it broke, fixes the source code, and proves the fix by re-running the tests. It then posts the patch and the before/after test output on the pull request.

It uses two models on purpose:

- **Gemma 4** reads the long, noisy CI log and returns a short failure summary.
- **Gemini** uses that summary to read the code, patch it and run the tests, through function calling.

The tools live in an **MCP server**. The agent connects to that server as a client, and so can any other MCP app (Claude Desktop, VS Code, Gemini CLI). A GitHub Actions workflow starts the agent automatically whenever CI fails.

## What's in the repo

| Path | What it does |
|---|---|
| `main.py` | Entry point. Runs the full pipeline: get failure → condense → fix → verify → report |
| `triage/condense.py` | Pre-filters the log, then asks Gemma for a JSON failure summary |
| `triage/agent.py` | The Gemini function-calling loop |
| `triage/tools.py` | Workspace tools: list, read, patch, run tests. Tests and CI config are read-only |
| `triage/github_api.py` | Finds the failed run, downloads its log, clones the commit, comments on the PR |
| `triage/report.py` | Builds the Markdown evidence report |
| `mcp_server.py` | The toolkit: CI tools served over MCP. The agent and any other MCP client use it |
| `sample_repo/` | A small project with a real bug, its CI workflow, and `ci-triage.yml`, which runs the agent when CI fails |

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # macOS/Linux: cp .env.example .env, then add your keys
```

Local demo, no GitHub needed:

```bash
python main.py --local sample_repo
```

Against a real failing GitHub Actions run (push `sample_repo/` to a new repo and open a PR first):

```bash
python main.py --repo your-name/your-repo          # prints the report
python main.py --repo your-name/your-repo --post   # also comments on the PR
```

MCP server:

```bash
WORKSPACE=path/to/repo python mcp_server.py
```

Built as the companion project for a lablab.ai tutorial.
