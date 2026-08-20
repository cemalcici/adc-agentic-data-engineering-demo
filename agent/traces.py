"""Building a link an operator can actually follow.

The trace address cannot be assembled from what the agent knows. Phoenix
addresses a project by an identifier it assigns, not by the name the agent
registered under, so the identifier has to be asked for. It is asked for once
and remembered.

Getting this wrong is invisible from here: a malformed address is still a
string, still stored, and still rendered as a link. It only shows up when
somebody clicks it — which is how this was found, one change after it was
written.
"""

from __future__ import annotations

import requests

PROJECT_NAME = "self-healing-pipeline"

# What Phoenix's own interface uses. Not `/traces/<id>`, which loads the
# project's trace list and drops the selection, and not the project's name,
# which its API refuses as an unknown node.
TRACE_PATH = "{ui}/projects/{project}/spans/{trace}"

_project_id: str | None = None


def project_id(api_base_url: str) -> str | None:
    """Phoenix's identifier for the agent's project, asked once.

    Read from where the agent exports rather than from where an operator
    browses: one is a service on the compose network, the other a host address
    that means nothing inside this container.

    Returns None when Phoenix cannot be reached or has not seen the project
    yet — it is created by the first trace, so early passes can legitimately
    find nothing. Nothing is cached in that case, so a later pass tries again.
    """
    global _project_id
    if _project_id is not None:
        return _project_id
    if not api_base_url:
        return None
    try:
        response = requests.get(f"{api_base_url.rstrip('/')}/v1/projects", timeout=10)
        response.raise_for_status()
        for project in response.json().get("data", []):
            if project.get("name") == PROJECT_NAME:
                _project_id = str(project["id"])
                return _project_id
    except Exception:  # noqa: BLE001 - a missing link is not an incident
        return None
    return None


def trace_url(ui_base_url: str, api_base_url: str, trace_id: str) -> str | None:
    """The address of one trace, or None if it cannot be built truthfully."""
    if not ui_base_url or not trace_id:
        return None
    identifier = project_id(api_base_url)
    if identifier is None:
        return None
    return TRACE_PATH.format(
        ui=ui_base_url.rstrip("/"), project=identifier, trace=trace_id
    )
