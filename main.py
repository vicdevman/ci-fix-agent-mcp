"""CI triage agent: failing build in, verified fix and evidence report out.

Local demo (no GitHub needed):
    python main.py --local sample_repo

Against a real failing GitHub Actions run:
    python main.py --repo your-name/your-repo            # dry run, prints the report
    python main.py --repo your-name/your-repo --post     # also comments on the PR

In CI, the ci-triage.yml workflow runs the --repo --post form automatically
whenever the test workflow fails.
"""

import argparse
import asyncio
import os
import shutil
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from triage.agent import call_mcp_tool, run_agent
from triage.condense import condense
from triage.github_api import GitHub
from triage.llm import make_client
from triage.report import build_report
from triage.tools import Workspace

PROJECT_DIR = Path(__file__).resolve().parent
WORK_DIR = PROJECT_DIR / ".work"


async def main():
    parser = argparse.ArgumentParser(description="Diagnose and fix a failing CI build.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--local", help="Path to a local repo whose tests fail")
    source.add_argument("--repo", help="GitHub repo (owner/name) with a failed Actions run")
    parser.add_argument("--run-id", help="Specific workflow run id (default: latest failed run)")
    parser.add_argument("--post", action="store_true", help="Post the report as a PR comment")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")  # the report contains emoji; Windows consoles default to cp1252
    load_dotenv(PROJECT_DIR / ".env")
    gemini = make_client(os.environ["GEMINI_API_KEY"])
    # First model is preferred; the next ones are used only if it stays busy.
    triage_models = [os.getenv("TRIAGE_MODEL", "gemma-4-26b-a4b-it"), "gemma-4-31b-it", "gemini-3.5-flash-lite"]
    fix_models = [os.getenv("FIX_MODEL", "gemini-3.8-flash"), "gemini-3.6-flash", "gemini-3.5-flash-lite"]

    workdir = WORK_DIR / time.strftime("%Y%m%d-%H%M%S")
    github, pr_number = None, None

    print("1. Getting the failing build")
    if args.local:
        shutil.copytree(args.local, workdir, ignore=shutil.ignore_patterns(".work", "__pycache__", ".venv"))
        before = Workspace(workdir).run_tests()
        raw_log = before["output"]
        print(f"   local copy at {workdir}")
    else:
        github = GitHub(os.environ["GITHUB_TOKEN"], args.repo)
        run = github.get_run(args.run_id)
        print(f"   run #{run['run_number']} '{run['display_title']}' on {run['head_branch']} ({run['html_url']})")
        raw_log = github.get_run_log(run["id"])
        pr_number = github.find_pull_request(run)
        github.clone_at(run["head_sha"], workdir)
        before = Workspace(workdir).run_tests()

    if before["passed"]:
        sys.exit("   The tests pass on this commit, so there is nothing to fix here.")

    print(f"2. Condensing the log with {triage_models[0]}")
    summary = condense(gemini, triage_models, raw_log)
    print(f"   {summary['log_chars_in']:,} chars of log -> {summary['summary_chars']:,} char summary ({summary['model']})")
    print(f"   {summary.get('summary', '')}")

    print(f"3. Diagnosing and fixing with {fix_models[0]}, using tools from our MCP server")
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(PROJECT_DIR / "mcp_server.py")],
        env={"WORKSPACE": str(workdir.resolve())},
        cwd=str(PROJECT_DIR),
    )
    async with Client(server) as mcp:
        result = await run_agent(gemini, fix_models, mcp, summary)
        diff = (await call_mcp_tool(mcp, "get_diff", {}))["diff"]

    print("4. Verifying independently (outside the agent and the MCP server)")
    after = Workspace(workdir).run_tests()
    print(f"   tests {'PASS' if after['passed'] else 'STILL FAIL'}")

    report = build_report(summary, result, diff, before, after)
    report_path = workdir / "triage-report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"5. Report written to {report_path}")

    if args.post:
        if not github or not pr_number:
            print("   --post skipped: no pull request is linked to this run.")
        else:
            print(f"   posted: {github.comment(pr_number, report)}")
    else:
        print()
        print(report)


if __name__ == "__main__":
    asyncio.run(main())
