"""Where the console learns whether the pipeline is working.

From the orchestrator's record of the latest run, and from nowhere else. Not
from the warehouse: a failed run leaves the previous output in place, so
anything reading the data reports green for exactly as long as the pipeline is
broken — which is the silent failure this whole system exists to make visible.

Not from the agent either. The agent might be stopped, and a console that
learned health from it would then display a confident stale green.

See adr/0026-read-pipeline-health-from-the-run-not-the-data.md
"""

from __future__ import annotations

from typing import Any, Literal

import requests

Health = Literal["healthy", "failing", "unknown", "never run"]

# Which run states count as the pipeline currently working. Anything in flight
# is neither: reporting it as healthy would be premature and as failing would be
# alarming, so it gets its own answer.
SUCCEEDED = "success"
FAILED = "failed"


class Orchestrator:
    """A read-only client. Its credential cannot start a run; this cannot ask."""

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
            timeout=15,
        )
        response.raise_for_status()
        return str(response.json()["access_token"])

    def _get(self, path: str) -> dict[str, Any]:
        """GET, refreshing the token once if the request is rejected."""
        for attempt in (1, 2):
            if self._token is None:
                self._token = self._fetch_token()
            response = requests.get(
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=15,
            )
            if response.status_code in (401, 403) and attempt == 1:
                self._token = None
                continue
            response.raise_for_status()
            return dict(response.json())
        raise RuntimeError(f"could not read {path} after refreshing the token")

    def latest_run(self) -> dict[str, Any] | None:
        payload = self._get(
            f"/api/v2/dags/{self._dag_id}/dagRuns?order_by=-run_after&limit=1"
        )
        runs = payload.get("dag_runs") or []
        return dict(runs[0]) if runs else None


def health(orchestrator: Orchestrator) -> tuple[Health, dict[str, Any] | None, str]:
    """The pipeline's state, the run it was read from, and something to show.

    Returns `unknown` rather than guessing when the orchestrator cannot be
    reached. A console that fell back to optimism here would be wrong in the one
    direction that matters.
    """
    try:
        run = orchestrator.latest_run()
    except Exception as error:  # noqa: BLE001 - unreachable is a state, not a crash
        return "unknown", None, f"the orchestrator could not be reached ({type(error).__name__})"

    if run is None:
        return "never run", None, "the pipeline has not run yet"

    state = str(run.get("state") or "")
    if state == SUCCEEDED:
        return "healthy", run, "the last run succeeded"
    if state == FAILED:
        return "failing", run, "the last run failed"
    return "unknown", run, f"a run is {state}"
