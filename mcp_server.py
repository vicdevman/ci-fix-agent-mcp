"""The toolkit: CI triage tools as an MCP server.

Our own agent (main.py) connects to this server, and so can any other MCP
client: Claude Desktop, Gemini CLI, VS Code, or someone else's agent.

    WORKSPACE=path/to/repo python mcp_server.py
"""

import os

from dotenv import load_dotenv
from google import genai
from mcp.server.mcpserver import MCPServer

from triage.condense import condense
from triage.github_api import GitHub
from triage.tools import Workspace

load_dotenv()
workspace = Workspace(os.getenv("WORKSPACE", "."))
server = MCPServer("ci-triage-tools", instructions="Tools for diagnosing and fixing failing CI builds.")


@server.tool()
def summarize_failed_run(repo: str, run_id: str = "") -> dict:
    """Fetch a failed GitHub Actions run and return a short Gemma-written failure summary."""
    github = GitHub(os.environ["GITHUB_TOKEN"], repo)
    run = github.get_run(run_id or None)
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    summary = condense(client, os.getenv("TRIAGE_MODEL", "gemma-4-26b-a4b-it"), github.get_run_log(run["id"]))
    summary["run_url"] = run["html_url"]
    return summary


@server.tool()
def list_files() -> dict:
    """List the files in the workspace repository."""
    return workspace.list_files()


@server.tool()
def read_file(path: str) -> dict:
    """Read one file from the workspace repository."""
    return workspace.read_file(path)


@server.tool()
def replace_in_file(path: str, old_text: str, new_text: str) -> dict:
    """Replace one exact snippet in a source file. Tests and CI config are protected."""
    return workspace.replace_in_file(path, old_text, new_text)


@server.tool()
def run_tests() -> dict:
    """Run the test suite and report whether it passed."""
    return workspace.run_tests()


@server.tool()
def get_diff() -> dict:
    """Return a unified diff of every file changed through this server."""
    return {"diff": workspace.diff()}


if __name__ == "__main__":
    server.run()
