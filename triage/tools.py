"""Workspace tools the agent is allowed to use.

Every path is resolved inside one workspace folder, and test files are
read-only, so the agent can only make a build green by fixing source code.
"""

import difflib
import subprocess
import sys
from pathlib import Path

PROTECTED_DIRS = ("tests", ".github")
MAX_READ_CHARS = 20_000
MAX_TEST_OUTPUT_CHARS = 6_000


class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.originals = {}  # path -> text before the agent's first edit, used for the diff

    def _resolve(self, rel_path):
        path = (self.root / rel_path).resolve()
        if path != self.root and self.root not in path.parents:
            raise ValueError(f"{rel_path} is outside the workspace")
        return path

    def list_files(self):
        """List source and test files in the repository."""
        files = []
        for path in sorted(self.root.rglob("*")):
            rel = path.relative_to(self.root)
            if path.is_file() and not any(p.startswith(".") or p == "__pycache__" for p in rel.parts):
                files.append(rel.as_posix())
        return {"files": files}

    def read_file(self, path):
        """Return the contents of one file."""
        target = self._resolve(path)
        if not target.is_file():
            return {"error": f"{path} does not exist"}
        text = target.read_text(encoding="utf-8")
        return {"path": path, "content": text[:MAX_READ_CHARS], "truncated": len(text) > MAX_READ_CHARS}

    def replace_in_file(self, path, old_text, new_text):
        """Replace one exact snippet in a source file."""
        rel = Path(path).as_posix()
        if rel.split("/")[0] in PROTECTED_DIRS:
            return {"error": f"{path} is protected. Fix the source code, not the tests or CI config."}
        target = self._resolve(path)
        if not target.is_file():
            return {"error": f"{path} does not exist"}
        text = target.read_text(encoding="utf-8")
        count = text.count(old_text)
        if count != 1:
            return {"error": f"old_text must match exactly once in {path}, found {count} matches"}
        self.originals.setdefault(rel, text)
        target.write_text(text.replace(old_text, new_text), encoding="utf-8")
        return {"ok": True, "path": path}

    def diff(self):
        """Unified diff of every file the agent changed."""
        chunks = []
        for rel, before in sorted(self.originals.items()):
            after = (self.root / rel).read_text(encoding="utf-8")
            chunks.extend(
                difflib.unified_diff(
                    before.splitlines(keepends=True),
                    after.splitlines(keepends=True),
                    fromfile=f"a/{rel}",
                    tofile=f"b/{rel}",
                )
            )
        return "".join(chunks)

    def run_tests(self):
        """Run the test suite and report whether it passed."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        output = (result.stdout + result.stderr).strip()
        return {
            "passed": result.returncode == 0,
            "exit_code": result.returncode,
            "output": output[-MAX_TEST_OUTPUT_CHARS:],
        }
