"""The GitHub side: find the failing run, download its log, comment on the PR."""

import io
import subprocess
import zipfile

import requests

API = "https://api.github.com"


class GitHub:
    def __init__(self, token, repo):
        self.repo = repo
        self.token = token
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _get(self, path, **params):
        response = self.session.get(f"{API}/repos/{self.repo}{path}", params=params, timeout=30)
        response.raise_for_status()
        return response

    def get_run(self, run_id=None):
        """Return one workflow run: the given id, or the most recent failed run."""
        if run_id:
            return self._get(f"/actions/runs/{run_id}").json()
        runs = self._get("/actions/runs", status="failure", per_page=1).json()["workflow_runs"]
        if not runs:
            raise RuntimeError(f"No failed workflow runs found in {self.repo}")
        return runs[0]

    def get_run_log(self, run_id):
        """Download the run's log archive and join every step into one text."""
        archive = zipfile.ZipFile(io.BytesIO(self._get(f"/actions/runs/{run_id}/logs").content))
        parts = []
        for name in sorted(archive.namelist()):
            if name.endswith(".txt"):
                parts.append(f"===== {name} =====\n" + archive.read(name).decode("utf-8", errors="replace"))
        return "\n".join(parts)

    def find_pull_request(self, run):
        """Return the PR number for a run, or None if it was not on a PR."""
        if run.get("pull_requests"):
            return run["pull_requests"][0]["number"]
        pulls = self._get(f"/commits/{run['head_sha']}/pulls").json()
        return pulls[0]["number"] if pulls else None

    def comment(self, number, body):
        response = self.session.post(
            f"{API}/repos/{self.repo}/issues/{number}/comments", json={"body": body}, timeout=30
        )
        response.raise_for_status()
        return response.json()["html_url"]

    def clone_at(self, sha, dest):
        """Clone the repo and check out the exact commit that failed."""
        url = f"https://x-access-token:{self.token}@github.com/{self.repo}.git"
        subprocess.run(["git", "clone", "--quiet", "--no-checkout", url, str(dest)], check=True)
        subprocess.run(["git", "-C", str(dest), "checkout", "--quiet", sha], check=True)
