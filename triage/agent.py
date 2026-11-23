"""The specialised agent: Gemini decides, our MCP server's tools act.

The agent does not import the tools. It connects to the MCP server, asks it
which tools exist, hands those to Gemini, and sends Gemini's tool calls back
to the server. Any other MCP server with the same tools would work too.
"""

import json

from google.genai import types

from triage.llm import agenerate

SYSTEM_PROMPT = """You are a CI triage engineer. A build is failing and you must fix it.

Rules:
- Start from the failure summary, then read the relevant source and test files.
- Make the smallest change to SOURCE code that fixes the root cause.
- Never edit tests or CI config; the tools will refuse.
- After every change, call run_tests. Only stop when the tests pass,
  or when you are sure you cannot fix it.
- When you stop, reply with exactly two lines:
  ROOT CAUSE: <one sentence>
  FIX: <one sentence>
"""

# The server also offers tools for other clients (fetching runs, diffs).
# This agent only needs the ones that touch the code.
AGENT_TOOLS = {"list_files", "read_file", "replace_in_file", "run_tests"}


async def gemini_tools_from_mcp(mcp):
    """Turn the MCP server's tool list into Gemini function declarations."""
    listed = await mcp.list_tools()
    return [
        types.FunctionDeclaration(
            name=tool.name,
            description=tool.description,
            parameters_json_schema=tool.input_schema,
        )
        for tool in listed.tools
        if tool.name in AGENT_TOOLS
    ]


async def call_mcp_tool(mcp, name, args):
    """Call a tool on the MCP server and return its result as a dict."""
    result = await mcp.call_tool(name, args)
    if result.structured_content:
        return result.structured_content
    text = "".join(getattr(part, "text", "") for part in result.content)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error" if result.is_error else "result": text}


async def run_agent(gemini, models, mcp, failure_summary, max_steps=12, on_event=print):
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=await gemini_tools_from_mcp(mcp))],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text="Failure summary from CI:\n" + json.dumps(failure_summary, indent=2))],
        )
    ]

    for step in range(1, max_steps + 1):
        response, _ = await agenerate(gemini, models, contents=contents, config=config)
        # Send the model's full turn back, so any thought signatures are kept.
        contents.append(response.candidates[0].content)

        if not response.function_calls:
            return {"final_message": (response.text or "").strip(), "steps": step}

        results = []
        for call in response.function_calls:
            args = dict(call.args or {})
            on_event(f"  [{step}] {call.name}({_short(args)})")
            if call.name not in AGENT_TOOLS:
                result = {"error": f"{call.name} is not available to this agent"}
            else:
                result = await call_mcp_tool(mcp, call.name, args)
            if call.name == "run_tests":
                on_event(f"      tests {'PASSED' if result.get('passed') else 'FAILED'}")
            results.append(types.Part.from_function_response(name=call.name, response=result))
        contents.append(types.Content(role="user", parts=results))

    return {"final_message": "Stopped: step limit reached without a passing build.", "steps": max_steps}


def _short(args):
    text = ", ".join(f"{k}={v!r}" for k, v in args.items())
    return text if len(text) <= 90 else text[:87] + "..."
