"""Talking to the orchestrator.

Almost all reads. The one method that acts — starting a run — exists because a
fix an operator approved has to be proved against a run that read it, and it is
reachable only from a graph branch an approval opens.
See adr/0024-verify-a-fix-against-a-run-you-started.md

The token expires (a day, measured during CH1), which is longer than a demo and
shorter than a stack left running. Rather than reasoning about when that
happens, the client fetches a token when it has none and fetches a fresh one
whenever a request is rejected.
"""

from __future__ import annotations

import re
from typing import Any

import requests

# Task logs come back ANSI-coloured — measured in CH3. Anything reading them for
# meaning has to strip the escape sequences first.
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


class Orchestrator:
    """A client for the pipeline orchestrator's API."""

    def __init__(self, base_url: str, username: str, password: str, dag_id: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._dag_id = dag_id
        self._token: str | None = None

    def _fetch_token(self) -> str:
        response = requests.post(
            f"{self._base_url}/auth/token",
            json={"username": self._username, "password": self._password},
            timeout=30,
        )
        response.raise_for_status()
        return str(response.json()["access_token"])

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Call the API, refreshing the token once if the request is rejected."""
        for attempt in (1, 2):
            if self._token is None:
                self._token = self._fetch_token()
            response = requests.request(
                method,
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {self._token}"},
                json=payload,
                timeout=60,
            )
            if response.status_code in (401, 403) and attempt == 1:
                self._token = None
                continue
            response.raise_for_status()
            return dict(response.json())
        raise RuntimeError(f"could not {method} {path} after refreshing the token")

    def _get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def latest_run(self) -> dict[str, Any] | None:
        """The most recent pipeline run, or None if there has never been one."""
        payload = self._get(
            f"/api/v2/dags/{self._dag_id}/dagRuns?order_by=-run_after&limit=1"
        )
        runs = payload.get("dag_runs") or []
        return dict(runs[0]) if runs else None

    def failed_task(self, run_id: str) -> str | None:
        """Which task failed in a run, if any did."""
        payload = self._get(
            f"/api/v2/dags/{self._dag_id}/dagRuns/{requests.utils.quote(run_id, safe='')}"
            f"/taskInstances"
        )
        for task in payload.get("task_instances", []):
            if task.get("state") == "failed":
                return str(task["task_id"])
        return None

    def task_log(self, run_id: str, task_id: str, try_number: int = 1) -> str:
        """The failing task's output, with its colouring removed."""
        payload = self._get(
            f"/api/v2/dags/{self._dag_id}/dagRuns/{requests.utils.quote(run_id, safe='')}"
            f"/taskInstances/{task_id}/logs/{try_number}"
        )
        parts = [
            chunk.get("event", "") if isinstance(chunk, dict) else str(chunk)
            for chunk in payload.get("content", [])
        ]
        return ANSI_ESCAPE.sub("", "\n".join(parts))

    def run(self, run_id: str) -> dict[str, Any]:
        """One specific run, by the identifier this agent recorded for it.

        Verification reads this and nothing else. Asking for the latest run
        instead would sooner or later read one that started before the fix was
        written, whose outcome describes a project it never saw.
        See adr/0024-verify-a-fix-against-a-run-you-started.md
        """
        return self._get(
            f"/api/v2/dags/{self._dag_id}/dagRuns/{requests.utils.quote(run_id, safe='')}"
        )

    def trigger_run(self) -> str:
        """Start a run and return which one it is.

        The only method here that acts. It does not look for a run already in
        progress: one may have started before the fix was written, and adopting
        it would be verifying the fix against a project it never read. The
        pipeline permits one active run, so a trigger issued while another is
        going queues rather than conflicting.
        """
        created = self._request(
            "POST",
            f"/api/v2/dags/{self._dag_id}/dagRuns",
            {"logical_date": None},
        )
        return str(created["dag_run_id"])
