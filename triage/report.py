"""Build the Markdown evidence report posted on the pull request."""


def _tail(text, lines=15):
    return "\n".join(text.strip().splitlines()[-lines:])


def build_report(summary, agent_result, diff, before, after):
    verified = after["passed"]
    status = "✅ Fix verified: tests pass" if verified else "❌ Not fixed: tests still failing"
    failing = ", ".join(f"`{t}`" for t in summary.get("failing_tests", [])) or "unknown"
    return f"""## CI triage report: {status}

**What failed:** {failing}
**Error:** `{summary.get('error_message', 'unknown')}`

{agent_result['final_message']}

### Proposed patch
```diff
{diff.strip() or '(no changes made)'}
```

### Evidence
<details><summary>Tests before the fix (exit code {before['exit_code']})</summary>

```
{_tail(before['output'])}
```
</details>

<details><summary>Tests after the fix (exit code {after['exit_code']})</summary>

```
{_tail(after['output'])}
```
</details>

<sub>Gemma condensed a {summary.get('log_chars_in', 0):,}-character CI log into a {summary.get('summary_chars', 0):,}-character summary before Gemini diagnosed it. Agent steps: {agent_result['steps']}.</sub>
"""
