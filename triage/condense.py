"""Turn a long, noisy CI log into a short failure summary with Gemma.

CI logs are mostly setup noise (installs, caches, timestamps). Sending all of
it to the diagnosing model wastes tokens and makes diagnosis worse, so a cheap
model reads it first and returns only what matters.
"""

import json
import re

from triage.llm import generate

SIGNAL = re.compile(
    r"(error|fail|failed|traceback|exception|assert|expected|raise|exit code|\.py:\d+)",
    re.IGNORECASE,
)
CONTEXT_LINES = 3
TAIL_LINES = 60
MAX_CHARS = 40_000
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.]+Z\s?")

PROMPT = """You are reading a CI log from a failing build.
Return ONLY a JSON object with these keys:
  "failing_tests": list of failing test names,
  "error_type": short error class, e.g. "AssertionError",
  "error_message": the most important assertion or error line, verbatim,
  "suspect_files": list of source files (not test files) most likely to contain the bug,
  "summary": 2-3 sentences describing what failed and the likely cause.
Do not invent files that are not mentioned in the log.

CI log:
{log}
"""


def prefilter(raw_log):
    """Keep lines near errors plus the end of the log, without any model call."""
    lines = [TIMESTAMP.sub("", line) for line in raw_log.splitlines()]
    keep = set(range(max(0, len(lines) - TAIL_LINES), len(lines)))
    for i, line in enumerate(lines):
        if SIGNAL.search(line):
            keep.update(range(max(0, i - CONTEXT_LINES), min(len(lines), i + CONTEXT_LINES + 1)))
    text = "\n".join(lines[i] for i in sorted(keep))
    return text[-MAX_CHARS:]


def _extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"Gemma did not return JSON:\n{text[:500]}")
    return json.loads(match.group(0))


def condense(client, models, raw_log):
    filtered = prefilter(raw_log)
    response, used = generate(client, models, contents=PROMPT.format(log=filtered))
    summary = _extract_json(response.text)
    summary["model"] = used
    summary["summary_chars"] = len(json.dumps(summary))
    summary["log_chars_in"] = len(raw_log)
    return summary
