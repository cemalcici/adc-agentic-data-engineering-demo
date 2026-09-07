"""The operator console.

Reads the pipeline's health from the orchestrator and everything else from the
incident record, and writes the decision and human feedback on the judge review.

It never asks the warehouse whether the pipeline is working. A failed run leaves
the previous output in place, so data would report green throughout an incident
— the silent failure this system exists to reveal, reproduced inside the screen
built to reveal it.
See adr/0026-read-pipeline-health-from-the-run-not-the-data.md

It needs no agent. The record is the channel, and this side of it works when the
other is not running.
See adr/0015-the-incident-record-is-the-channel-between-agent-and-operator.md
"""

from __future__ import annotations

import html
import json
import time
from typing import Any

import streamlit as st

NOTICE_SECONDS = 20

import difference
import pipeline
import theme

import config
from incidents import IncidentStore

st.set_page_config(page_title="Self-Healing Pipeline", page_icon="◆", layout="wide")


@st.cache_resource
def _wiring() -> tuple[config.Settings, IncidentStore, pipeline.Orchestrator]:
    settings = config.load()
    store = IncidentStore(
        settings.postgres_host,
        settings.warehouse_db,
        settings.postgres_user,
        settings.postgres_password,
    )
    orchestrator = pipeline.Orchestrator(
        settings.airflow_url,
        settings.airflow_username,
        settings.airflow_password,
        settings.dag_id,
    )
    return settings, store, orchestrator


def _when(value: Any) -> str:
    return value.strftime("%d %b %H:%M:%S") if value else "—"


def _diagnosis(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        return dict(json.loads(raw))
    except (ValueError, TypeError):
        return None


# --- panels ------------------------------------------------------------------


def status_header(state: pipeline.Health, detail: str, run: dict[str, Any] | None) -> None:
    label = {"healthy": "PIPELINE HEALTHY", "failing": "PIPELINE FAILING"}.get(
        state, f"PIPELINE {state.upper()}"
    )
    left, right = st.columns([3, 2])
    with left:
        st.markdown(theme.badge(label, theme.HEALTH_COLOURS[state]), unsafe_allow_html=True)
    with right:
        run_id = (run or {}).get("dag_run_id", "")
        st.markdown(
            f'<div class="muted" style="text-align:right">{detail}'
            + (f'<br/><span class="mono">{run_id}</span>' if run_id else "")
            + "</div>",
            unsafe_allow_html=True,
        )


def nothing_recorded_yet() -> None:
    """A failed run with no incident is a real state, not an empty one."""
    st.markdown(
        '<div class="panel"><b>Nothing has been recorded for this failure yet.</b>'
        '<div class="muted" style="margin-top:6px">'
        "Either the agent has not looked at it yet, or it is not running. The "
        "console reads the incident record and does not depend on the agent, so "
        "this page stays accurate either way.</div></div>",
        unsafe_allow_html=True,
    )


def diagnosis_panel(incident: dict[str, Any]) -> None:
    """One panel, rendered in one call.

    Streamlit puts every markdown call in its own container, so a div opened in
    one and closed in another does not wrap what is between them. Panels are
    built as a single string for that reason.
    """
    found = _diagnosis(incident.get("diagnosis"))
    state = incident["state"]

    if found:
        body = (
            f"<div style=\"margin-top:10px\">{html.escape(str(found.get('explanation', '')))}</div>"
            f'<div class="mono muted" style="margin-top:10px">'
            f"expected <b>{html.escape(str(found.get('expected_field', '?')))}</b> &middot; "
            f"found <b>{html.escape(str(found.get('replacing_field', '?')))}</b> &middot; "
            f"in {html.escape(str(found.get('failing_model', '?')))} &middot; "
            f"confidence {html.escape(str(found.get('confidence', '?')))}</div>"
        )
    else:
        body = '<div class="muted" style="margin-top:10px">No diagnosis recorded.</div>'

    trace = incident.get("trace_url")
    link = (
        f'<div style="margin-top:12px"><a href="{html.escape(str(trace))}" target="_blank">'
        "How did the agent arrive at that? &rarr;</a></div>"
        if trace
        else ""
    )

    st.markdown(
        '<div class="panel">'
        + theme.badge(
            theme.STATE_LABELS.get(state, state).upper(),
            theme.STATE_COLOURS.get(state, "text-muted"),
        )
        + '<div style="margin-top:12px"><b>What the agent found</b></div>'
        + body
        + link
        + "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("What the pipeline printed"):
        st.code(incident.get("failure_output") or "—", language="text")


def judge_panel(incident: dict[str, Any]) -> None:
    review = incident.get("judge_review") or {}
    st.markdown("#### LLM-as-Judge")
    st.text(f"Üretici: {review.get('producer_model', '—')} · Judge: {review.get('judge_model', '—')}")
    if review.get("status") != "completed":
        st.warning("Judge değerlendirmesi alınamadı. Öneriyi inceleyip karar verebilirsiniz.")
        return
    labels = {"problem_alignment": "Sorunla uyum", "solution_adequacy": "Çözümün yeterliliği",
              "behavior_preservation": "Davranışın korunması"}
    results = {"appropriate": "Uygun", "issue": "Sorun var",
               "insufficient_evidence": "Kanıt yetersiz"}
    for key, label in labels.items():
        check = review["checks"][key]
        st.text(f"{label}: {results[check['result']]}")
        st.write(check["reason"])
        st.code("\n".join(check["evidence"]), language="text")
    with st.expander("Judge'ın öneriyi görmeden yaptığı kanıt incelemesi"):
        st.json(review["independent_assessment"])


def proposal_panel(incident: dict[str, Any], store: IncidentStore) -> None:
    before = incident.get("model_contents_before") or ""
    after = incident.get("model_contents_after") or ""
    path = incident.get("target_model_path") or "?"
    added, removed = difference.counts(before, after)

    st.markdown(
        f'<div class="panel"><b>Proposed change</b>'
        f'<div class="mono muted" style="margin-top:4px">{path} · '
        f'<span style="color:var(--state-success)">+{added}</span> '
        f'<span style="color:var(--state-error)">−{removed}</span></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(difference.unified(before, after, path), unsafe_allow_html=True)

    st.markdown(
        '<div class="muted" style="margin:12px 0 6px">'
        "The agent has already built this successfully. What is left is whether "
        "it means the right thing — which is yours to judge.</div>",
        unsafe_allow_html=True,
    )

    judge_panel(incident)
    if (incident.get("judge_review") or {}).get("status") == "completed":
        st.selectbox(
            "Judge değerlendirmesine ilişkin görüşünüz",
            ["Seçiniz", "Katılıyorum", "Kısmen katılıyorum", "Katılmıyorum"],
            key=f"judge_feedback_{incident['id']}",
        )
        st.text_area("Açıklama (isteğe bağlı)", key=f"judge_note_{incident['id']}")

    # Callbacks rather than `if st.button(...)`. A click reruns the script, and
    # by the time it reruns the incident may have moved — in which case this
    # panel is not rendered at all, the button is never created, and the branch
    # that would have explained what happened never runs. Measured: the decision
    # was silently dropped and the operator was shown nothing.
    #
    # A callback fires before the rerun, on the incident the page was actually
    # showing, which is the whole point of writing the decision conditionally.
    approve, reject, _ = st.columns([1, 1, 4])
    with approve:
        st.button(
            "Approve",
            type="primary",
            use_container_width=True,
            on_click=_decide,
            args=(store, incident, "approved"),
        )
    with reject:
        st.button(
            "Reject",
            use_container_width=True,
            on_click=_decide,
            args=(store, incident, "rejected"),
        )


def _decide(store: IncidentStore, incident: dict[str, Any], decision: str) -> None:
    """Record a decision against the incident as the page last saw it."""
    feedback = None
    if (incident.get("judge_review") or {}).get("status") == "completed":
        feedback = {"Katılıyorum": "agree", "Kısmen katılıyorum": "partly_agree",
                    "Katılmıyorum": "disagree"}.get(
            st.session_state.get(f"judge_feedback_{incident['id']}")
        )
        if feedback is None:
            _notify("missing", "Önce judge değerlendirmesine ilişkin görüşünüzü seçin.")
            return
    recorded = store.record_decision(
        incident_id=int(incident["id"]),
        decision=decision,
        expected_state=incident["state"],
        judge_feedback=feedback,
        judge_feedback_note=(st.session_state.get(f"judge_note_{incident['id']}") or None)
        if feedback else None,
    )
    if recorded:
        _notify("ok", f"Recorded: {decision}.")
    else:
        _notify(
            "moved",
            "This incident moved on while it was open in front of you, so "
            "nothing was recorded. The page below shows where it is now.",
        )
    # No rerun here: Streamlit reruns of its own accord once a callback returns,
    # and calling for one from inside a callback is refused.


def _notify(kind: str, message: str) -> None:
    """Leave a message for the next render, with a life of its own.

    The page refreshes itself, so a message cleared on the next render would
    last one refresh interval. It expires on a clock instead, which is long
    enough to read and short enough not to linger over a later state.
    """
    st.session_state["notice"] = (kind, message, time.monotonic() + NOTICE_SECONDS)


def _show_notice() -> None:
    notice = st.session_state.get("notice")
    if not notice:
        return
    kind, message, expires = notice
    if time.monotonic() > expires:
        del st.session_state["notice"]
        return
    (st.success if kind == "ok" else st.warning)(message)


def applying_panel(incident: dict[str, Any]) -> None:
    run = incident.get("verifying_run_id")
    st.markdown(
        '<div class="panel"><b>Applying your approval</b>'
        '<div class="muted" style="margin-top:6px">'
        + (
            f'The fix was written and a run started to check it.<br/><span class="mono">{run}</span>'
            if run
            else "The fix is being written."
        )
        + "</div></div>",
        unsafe_allow_html=True,
    )


def history_panel(rows: list[dict[str, Any]]) -> None:
    st.markdown("#### History")
    if not rows:
        st.markdown('<span class="muted">Nothing recorded yet.</span>', unsafe_allow_html=True)
        return
    for row in rows:
        state = row["state"]
        trace = row.get("trace_url")
        link = (
            f' · <a href="{trace}" target="_blank">trace</a>' if trace else ""
        )
        st.markdown(
            f'<div class="row"><span class="when">{_when(row["opened_at"])}</span>'
            f'{theme.badge(theme.STATE_LABELS.get(state, state), theme.STATE_COLOURS.get(state, "text-muted"))}'
            f'<span class="muted mono">#{row["id"]} · {row["failing_task_id"]}'
            f'{link}</span></div>',
            unsafe_allow_html=True,
        )

        if row.get("conclusion_note"):
            with st.expander(f"#{row['id']} — Neden durdu?", expanded=True):
                st.write(row["conclusion_note"])
                if state == "unfixable":
                    st.caption("Bu incident için doğrulanmış bir öneri sunulmadı; dbt dosyası değiştirilmedi.")

        if row.get("judge_review"):
            with st.expander(f"#{row['id']} — Judge değerlendirmesi ve insan görüşü"):
                st.code(row.get("model_contents_after") or "", language="sql")
                judge_panel(row)
                feedback = {"agree": "Katılıyorum", "partly_agree": "Kısmen katılıyorum",
                            "disagree": "Katılmıyorum"}.get(row.get("judge_feedback"), "—")
                st.text(f"İnsan görüşü: {feedback}")
                if row.get("judge_feedback_note"):
                    st.write(row["judge_feedback_note"])


# --- the page ----------------------------------------------------------------


def render(settings: config.Settings, store: IncidentStore, orchestrator: pipeline.Orchestrator, refreshing: bool) -> None:
    """The whole page. Called directly, or by a fragment that repeats it."""
    incident = store.in_flight()

    # A proposal has appeared while the page was refreshing itself. Restart the
    # whole script so it takes the path that does not refresh — the operator is
    # about to read a difference, and the page should stop moving before they
    # start rather than after.
    if refreshing and incident is not None and incident["state"] == "proposed":
        st.rerun(scope="app")

    _show_notice()

    state, run, detail = pipeline.health(orchestrator)
    status_header(state, detail, run)

    history = store.history()
    if incident is None:
        if state == "failing":
            recorded = any(row.get("failing_run_id") == (run or {}).get("dag_run_id") for row in history)
            if not recorded:
                nothing_recorded_yet()
    elif incident["state"] == "open":
        diagnosis_panel(incident)
    elif incident["state"] == "proposed":
        diagnosis_panel(incident)
        proposal_panel(incident, store)
    elif incident["state"] == "approved":
        diagnosis_panel(incident)
        applying_panel(incident)

    st.divider()
    history_panel(history)

    st.markdown(
        '<div class="muted" style="font-size:0.75rem;margin-top:18px">'
        + (
            f"refreshing every {settings.refresh_seconds}s"
            if refreshing
            else "paused while you decide"
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    settings, store, orchestrator = _wiring()
    st.markdown(theme.css(), unsafe_allow_html=True)

    # Refresh while the system is moving; hold still once a decision is due.
    # That is the only state in which nothing can change without the operator —
    # and the only screen where they are reading closely enough to lose their
    # place.
    #
    # A fragment rather than a sleeping loop: the script has to finish for
    # Streamlit to clear what the previous render left behind, and a script that
    # sleeps never finishes. Measured, after getting it wrong: the page kept
    # both renders on screen at once, buttons included.
    incident = store.in_flight()
    if incident is not None and incident["state"] == "proposed":
        render(settings, store, orchestrator, refreshing=False)
    else:
        repeat = st.fragment(run_every=f"{settings.refresh_seconds}s")(render)
        repeat(settings, store, orchestrator, refreshing=True)


main()
