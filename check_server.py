"""Connect to the MCP server the way an AI app would, and try its tools.

    python check_server.py sample_repo
"""

import asyncio
import os
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters


async def main(repo_path):
    server = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"],
        env={"WORKSPACE": os.path.abspath(repo_path)},
    )
    async with Client(server) as mcp:
        print("Tools this server offers:")
        for tool in (await mcp.list_tools()).tools:
            print(f"  - {tool.name}: {tool.description}")

        print("\nCalling run_tests:")
        result = await mcp.call_tool("run_tests", {})
        print(result.content[0].text[:400])

        print("\nTrying to edit a test file (should be refused):")
        result = await mcp.call_tool(
            "replace_in_file",
            {"path": "tests/test_pagination.py", "old_text": "assert", "new_text": "pass"},
        )
        print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "sample_repo"))
