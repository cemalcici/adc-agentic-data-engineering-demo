"""The agent's graph.

Entered on a fixed interval. Its entry point reads the incident record and
dispatches: to diagnosing when nothing is in flight, to proposing when an
incident is open, and to applying and verifying when one has been approved.

The graph does not suspend and resume. Nothing survives between invocations —
everything an invocation needs, it reads from the record. That is what makes the
approval gate a property of the routing rather than of anything held in memory.


The shape
---------

Sixteen nodes behind one router. This is the only place the graph's shape is
written down; no other document enumerates these nodes, because a second copy is
what let the first one go stale.

                            START
                              │
                       route_on_state
                              │
                       choose_branch()   reads incidents.state
                              │
        ┌──────────────────┬──┴───────────────┬───────────────────────┐
        │ nothing          │ 'open'           │ 'approved'            │ 'proposed',
        │ in flight        │                  │                       │ or anything else
        ▼                  ▼                  ▼                       ▼
  detect_failure     resume_incident    load_approved               idle
        │                  │                  │                       │
  fetch_failure_log        │            ┌─────┴──────┐               END
        │                  │            ▼            ▼
  inspect_schema           │            apply_fix   verify_success
        │                  │            │            │
    diagnose               │          trigger_rerun END
        │                  │            │
  record_incident          │           END
        │                  │
        └────────┬─────────┘
                 ▼
            propose_fix ◀─────┐
                 │            │ it did not build, and
                 ▼            │ attempts < max_fix_attempts
        validate_candidate ───┘
                 │
            ┌────┴────────┐
            ▼             ▼
     record_proposal   give_up
            │             │
           END           END


The vocabulary
--------------

One event can carry three different names, and this table is the only place the
mapping is written down.

  incident state        the node that produces it   the store method
  --------------------  -------------------------   -----------------------------
  open                  record_incident             open_incident()
  proposed              record_proposal             record_proposal()
  unfixable             give_up                     conclude_unfixable()
  approved              none — see The gate         none
  rejected              none — see The gate         none
  resolved              verify_success              resolve()
  verification_failed   verify_success              conclude_verification_failed()

Three of those do not follow from the names. `give_up` writes `unfixable`.
`verify_success` writes either `resolved` or `verification_failed`, so its name
promises one outcome and delivers two. And `proposal.py`, `Candidate`,
`record_proposal` and `proposed` are four words for one idea.

`trigger_rerun` writes to the record as well, through `record_verifying_run()`,
but moves no state: the incident stays `approved` while the run it started is
watched. See adr/0024-verify-a-fix-against-a-run-you-started.md

These names are not an internal detail. They are what appears in the Phoenix
span tree an operator inspects, and in the one shown to an audience during the
demonstration, so they are the words in which this agent's work gets described.


The gate
--------

Two of the seven states have no producing node here, and that absence is the
whole of the human-in-the-loop guarantee:

  - This agent has no code path that writes `approved` or `rejected`. The only
    writer is `streamlit_app/incidents.py`, when an operator decides. Its
    grant permits that column and no other.
    See adr/0027-bound-the-consoles-authority-by-grant.md
  - The branch that writes to the transformation project and starts a run —
    load_approved, apply_fix, trigger_rerun — is entered only by choose_branch()
    reading `approved`.
  - The database will not accept `approved` except from `proposed`, in
    postgres/init/03-incident-store.sql.
    See adr/0016-enforce-the-incident-lifecycle-in-the-database.md

So nothing here leads from `proposed` to anything that acts. The agent does not
decline to continue past a proposal; there is no edge. Approval is read in the
entry router and nowhere else, deliberately: a second check would give the
invariant two enforcement points, and two can disagree.

Nothing waits, either. A pass ends at record_proposal and the process exits; an
operator decides later, in another service; a further pass reads `approved` and
takes the other branch. The waiting is the gap between passes, which is why no
node is named for it.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any, Literal, TypedDict

import proposal
import sandbox
import traces
from langgraph.graph import END, START, StateGraph
from opentelemetry import trace
from validation import Validator

import evidence
from config import Settings
from diagnosis import Diagnosis, diagnose
from incidents import IncidentStore
from orchestrator import Orchestrator


class AgentState(TypedDict, total=False):
    """What one pass through the graph accumulates."""

    run_id: str
    failing_task: str
    failure_output: str
    model_path: str
    model_sql: str
    source_columns: list[str]
    diagnosis: Diagnosis
    incident_id: int

    # The proposing loop.
    attempts: int
    candidate_sql: str
    candidate_summary: str
    build_output: str
    validated: bool
    refusal: str

    # The applying branch.
    contents_to_write: str
    verifying_run_id: str

    outcome: str


def current_trace_url(phoenix_ui_url: str, phoenix_endpoint: str) -> str | None:
    """A link to the trace of the work happening right now, if it is traced.

    Recorded on the incident so the operator console can offer "how did the
    agent arrive at that?" as one click. Returns None when nothing is
    collecting, which is a normal state rather than an error.

    Two addresses, because they are two different things: the operator browses
    Phoenix from the host, and the agent reaches it by service name.
    """
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return None
    return traces.trace_url(phoenix_ui_url, phoenix_endpoint, f"{context.trace_id:032x}")


def _seconds_since_queued(run: dict[str, Any]) -> float | None:
    """How long a run has been in the system, from the orchestrator's own record.

    Measured from when it was queued rather than when it started, so a run that
    never starts is bounded as well as one that never ends. Returns None when
    the orchestrator reports neither, in which case nothing is concluded from
    it — a missing timestamp is not evidence that a run is stuck.
    """
    stamp = run.get("queued_at") or run.get("start_date")
    if not stamp:
        return None
    queued = dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    return (dt.datetime.now(dt.timezone.utc) - queued).total_seconds()


def build_graph(
    settings: Settings,
    orchestrator: Orchestrator,
    store: IncidentStore,
    validator: Validator,
    llm: Any,
) -> Any:
    """Assemble the graph. Nodes are small and named after what they do."""

    def read_model_in_scope(relative_path: str) -> str:
        """Read a transformation, having first refused anything out of scope.

        The refusal comes before the read, so a path that resolves outside the
        model directory is never opened.
        See adr/0023-the-agent-chooses-contents-never-targets.md
        """
        sandbox.resolve_target(settings.dbt_project_dir, relative_path)
        return evidence.read_model(settings.dbt_project_dir, relative_path)

    def live_source_columns() -> list[str]:
        return evidence.source_columns(
            settings.postgres_host,
            settings.source_db,
            settings.postgres_user,
            settings.postgres_password,
        )

    # -- routing -------------------------------------------------------------

    def route_on_state(state: AgentState) -> AgentState:
        """Read the record and decide what this pass is for."""
        return state

    def choose_branch(
        state: AgentState,
    ) -> Literal["detect_failure", "resume_incident", "load_approved", "idle"]:
        # An incident already in flight means this fault is known. Failures
        # repeat on every scheduled run while a fault persists, so treating each
        # as new would bury the operator in copies of one problem.
        incident = store.in_flight()
        if incident is None:
            return "detect_failure"
        # Open means diagnosed and not yet proposed for — the agent restarted,
        # or its last pass ended before it could finish proposing.
        if incident["state"] == "open":
            return "resume_incident"
        # The one branch that writes and triggers. Reachable from here and
        # nowhere else, and only for a state an operator's decision produces.
        if incident["state"] == "approved":
            return "load_approved"
        # Everything else, `proposed` included, waits. There is no branch from
        # a proposal to anything that acts.
        return "idle"

    def idle(state: AgentState) -> AgentState:
        incident = store.in_flight()
        waiting = incident is not None and incident["state"] == "proposed"
        return {
            **state,
            "outcome": (
                "a proposal is waiting for a decision"
                if waiting
                else "an incident is already in flight"
            ),
        }

    # -- diagnosing: a failure nothing has recorded yet ----------------------

    def detect_failure(state: AgentState) -> AgentState:
        run = orchestrator.latest_run()
        if run is None or run.get("state") != "failed":
            return {**state, "outcome": "no failed run"}
        failing = orchestrator.failed_task(run["dag_run_id"])
        if failing is None:
            return {**state, "outcome": "run failed but no task did"}
        return {**state, "run_id": run["dag_run_id"], "failing_task": failing}

    def fetch_failure_log(state: AgentState) -> AgentState:
        if not state.get("failing_task"):
            return state
        return {
            **state,
            "failure_output": orchestrator.task_log(
                state["run_id"], state["failing_task"]
            ),
        }

    def inspect_schema(state: AgentState) -> AgentState:
        """Read both sides of the disagreement: what was expected, what exists."""
        if not state.get("failure_output"):
            return state
        model_path = evidence.failing_model_path(state["failure_output"])
        if model_path is None:
            return {**state, "outcome": "the failure names no transformation"}
        try:
            model_sql = read_model_in_scope(model_path)
        except sandbox.TargetOutsideModelDirectory as refused:
            return {**state, "outcome": f"refused: {refused}"}
        return {
            **state,
            "model_path": model_path,
            "model_sql": model_sql,
            "source_columns": live_source_columns(),
        }

    def diagnose_failure(state: AgentState) -> AgentState:
        if not state.get("model_sql"):
            return state
        result = diagnose(
            llm,
            {
                "failing_task": state["failing_task"],
                "failure_output": state["failure_output"],
                "model_path": state["model_path"],
                "model_sql": state["model_sql"],
                "source_columns": state["source_columns"],
            },
        )
        return {**state, "diagnosis": result}

    def record_incident(state: AgentState) -> AgentState:
        result = state.get("diagnosis")
        if result is None:
            return state
        incident_id = store.open_incident(
            dag_id=settings.dag_id,
            failing_run_id=state["run_id"],
            failing_task_id=state["failing_task"],
            failure_output=state["failure_output"],
            diagnosis=json.dumps(result.model_dump(), indent=2),
            trace_url=current_trace_url(settings.phoenix_ui_url, settings.phoenix_endpoint),
        )
        return {**state, "incident_id": incident_id, "outcome": "incident opened"}

    def after_recording(state: AgentState) -> Literal["propose_fix", "done"]:
        # Proposing continues in the same pass so that one trace covers the
        # whole story: what failed, what the agent concluded, and what it
        # offered. Split across passes there would be no single trajectory to
        # point the operator at.
        return "propose_fix" if state.get("incident_id") else "done"

    # -- resuming an incident nobody proposed for yet ------------------------

    def resume_incident(state: AgentState) -> AgentState:
        """Rebuild what proposing needs from the record, reading the world fresh.

        Nothing is carried over from the pass that opened the incident. The
        model file and the source columns are read again rather than
        remembered — see adr/0020-diagnose-each-incident-from-scratch.md.
        """
        incident = store.in_flight()
        if incident is None or incident["state"] != "open":
            return {**state, "outcome": "nothing to resume"}

        failure_output = incident["failure_output"] or ""
        model_path = evidence.failing_model_path(failure_output)
        if model_path is None:
            return {
                **state,
                "incident_id": int(incident["id"]),
                "refusal": "the recorded failure output names no transformation",
            }
        try:
            diagnosis_json = incident["diagnosis"] or ""
            found = Diagnosis.model_validate_json(diagnosis_json)
            model_sql = read_model_in_scope(model_path)
        except sandbox.TargetOutsideModelDirectory as refused:
            return {
                **state,
                "incident_id": int(incident["id"]),
                "refusal": str(refused),
            }
        except Exception as error:  # noqa: BLE001 - an unreadable diagnosis ends it
            return {
                **state,
                "incident_id": int(incident["id"]),
                "refusal": f"the recorded diagnosis could not be read: {error}",
            }

        return {
            **state,
            "incident_id": int(incident["id"]),
            "run_id": incident["failing_run_id"],
            "failing_task": incident["failing_task_id"],
            "failure_output": failure_output,
            "model_path": model_path,
            "model_sql": model_sql,
            "source_columns": live_source_columns(),
            "diagnosis": found,
        }

    def after_resuming(state: AgentState) -> Literal["propose_fix", "give_up", "done"]:
        if state.get("refusal"):
            return "give_up"
        return "propose_fix" if state.get("model_sql") else "done"

    # -- proposing: a candidate, built before it is offered ------------------

    def propose_fix(state: AgentState) -> AgentState:
        """Ask what the file should contain — never which file."""
        if not state.get("model_sql"):
            return state
        candidate = proposal.propose(
            llm,
            diagnosis=state["diagnosis"],
            model_path=state["model_path"],
            model_sql=state["model_sql"],
            source_columns=state["source_columns"],
            previous_failure=state.get("build_output") or None,
        )
        return {
            **state,
            "candidate_sql": candidate.model_sql,
            "candidate_summary": candidate.summary,
            "attempts": state.get("attempts", 0) + 1,
        }

    def validate_candidate(state: AgentState) -> AgentState:
        """Build it, on a copy, before anybody is asked about it."""
        if not state.get("candidate_sql"):
            return state
        try:
            result = validator.validate(state["model_path"], state["candidate_sql"])
            built, output = result.built, result.output
        except Exception as error:  # noqa: BLE001 - a failed check is a failed attempt
            # A validation that could not run counts against the limit. Telling
            # a database being briefly unreachable apart from a bad candidate is
            # not reliably possible here, and an exemption that cannot be
            # decided correctly is a way back to an unbounded loop.
            built = False
            output = f"the validation build could not run: {type(error).__name__}: {error}"
        return {**state, "validated": built, "build_output": "" if built else output}

    def after_validation(
        state: AgentState,
    ) -> Literal["record_proposal", "propose_fix", "give_up"]:
        if state.get("validated"):
            return "record_proposal"
        if state.get("attempts", 0) < settings.max_fix_attempts:
            return "propose_fix"
        return "give_up"

    def record_proposal(state: AgentState) -> AgentState:
        """Write the proven proposal down, and stop."""
        store.record_proposal(
            incident_id=state["incident_id"],
            target_model_path=state["model_path"],
            model_contents_before=state["model_sql"],
            model_contents_after=state["candidate_sql"],
        )
        return {
            **state,
            "outcome": f"proposal recorded, awaiting a decision: {state['candidate_summary']}",
        }

    def give_up(state: AgentState) -> AgentState:
        """End the incident with a reason, and offer nothing."""
        attempts = state.get("attempts", 0)
        reason = state.get("refusal") or (
            f"{attempts} candidate(s) were written and none of them built. "
            f"The last build reported:\n\n{state.get('build_output', '')}"
        )
        store.conclude_unfixable(state["incident_id"], reason)
        return {**state, "outcome": "concluded as unfixable; nothing was offered"}

    # -- applying, triggering, verifying: the far side of the gate -----------

    def load_approved(state: AgentState) -> AgentState:
        """Read what an approved incident needs, from the record.

        Nothing is carried over from the pass that proposed. What gets written
        is what the operator approved, read back from where they approved it.
        """
        incident = store.in_flight()
        if incident is None or incident["state"] != "approved":
            return {**state, "outcome": "nothing approved to act on"}
        return {
            **state,
            "incident_id": int(incident["id"]),
            "model_path": incident["target_model_path"],
            "contents_to_write": incident["model_contents_after"],
            "verifying_run_id": incident["verifying_run_id"] or "",
        }

    def after_loading(state: AgentState) -> Literal["apply_fix", "verify_success", "done"]:
        if not state.get("incident_id"):
            return "done"
        # Whether this pass applies or watches is decided by one question the
        # record answers. That is what replaces holding a wait in memory, and
        # what makes a restart at any point harmless.
        return "verify_success" if state.get("verifying_run_id") else "apply_fix"

    def apply_fix(state: AgentState) -> AgentState:
        """Write what the operator approved. The first write this agent makes."""
        written = sandbox.write_model(
            settings.dbt_project_dir,
            state["model_path"],
            state["contents_to_write"],
        )
        return {**state, "outcome": f"applied the approved fix to {written}"}

    def trigger_rerun(state: AgentState) -> AgentState:
        """Start a run that has read the fix, and record which one it is.

        Unconditional. A run already in progress may have started before the
        write and would be judged on a project it never read.
        See adr/0024-verify-a-fix-against-a-run-you-started.md
        """
        run_id = orchestrator.trigger_run()
        store.record_verifying_run(state["incident_id"], run_id)
        return {
            **state,
            "verifying_run_id": run_id,
            "outcome": f"fix applied; watching run {run_id}",
        }

    def verify_success(state: AgentState) -> AgentState:
        """Read the recorded run, and conclude if it has finished."""
        run = orchestrator.run(state["verifying_run_id"])
        run_state = run.get("state")

        if run_state == "success":
            store.resolve(state["incident_id"])
            return {**state, "outcome": "the pipeline recovered; incident resolved"}

        if run_state == "failed":
            store.conclude_verification_failed(
                state["incident_id"],
                "The approved fix was applied and the pipeline still did not "
                f"recover. Run {state['verifying_run_id']} failed. The fix has "
                "been left in place as it was applied.",
            )
            return {**state, "outcome": "the fix did not restore the pipeline"}

        # Still going. Bounded by the run's own clock rather than by anything
        # the agent remembers, so a restart does not reset the count.
        waiting_for = _seconds_since_queued(run)
        if waiting_for is not None and waiting_for > settings.verification_timeout_seconds:
            store.conclude_verification_failed(
                state["incident_id"],
                f"Run {state['verifying_run_id']} was still {run_state} after "
                f"{int(waiting_for)} seconds and did not reach an outcome. The "
                "fix has been left in place as it was applied.",
            )
            return {**state, "outcome": "the verifying run did not finish in time"}

        return {**state, "outcome": f"verifying run is {run_state}"}

    graph = StateGraph(AgentState)
    graph.add_node("route_on_state", route_on_state)
    graph.add_node("idle", idle)
    graph.add_node("detect_failure", detect_failure)
    graph.add_node("fetch_failure_log", fetch_failure_log)
    graph.add_node("inspect_schema", inspect_schema)
    graph.add_node("diagnose", diagnose_failure)
    graph.add_node("record_incident", record_incident)
    graph.add_node("resume_incident", resume_incident)
    graph.add_node("propose_fix", propose_fix)
    graph.add_node("validate_candidate", validate_candidate)
    graph.add_node("record_proposal", record_proposal)
    graph.add_node("give_up", give_up)
    graph.add_node("load_approved", load_approved)
    graph.add_node("apply_fix", apply_fix)
    graph.add_node("trigger_rerun", trigger_rerun)
    graph.add_node("verify_success", verify_success)

    graph.add_edge(START, "route_on_state")
    graph.add_conditional_edges("route_on_state", choose_branch)
    graph.add_edge("idle", END)
    graph.add_edge("detect_failure", "fetch_failure_log")
    graph.add_edge("fetch_failure_log", "inspect_schema")
    graph.add_edge("inspect_schema", "diagnose")
    graph.add_edge("diagnose", "record_incident")
    graph.add_conditional_edges(
        "record_incident", after_recording, {"propose_fix": "propose_fix", "done": END}
    )
    graph.add_conditional_edges(
        "resume_incident",
        after_resuming,
        {"propose_fix": "propose_fix", "give_up": "give_up", "done": END},
    )
    graph.add_edge("propose_fix", "validate_candidate")
    graph.add_conditional_edges("validate_candidate", after_validation)

    # Both endings of the proposing branch stop here. Nothing leads from a
    # recorded proposal to anything that writes or triggers: that is the gate.
    graph.add_edge("record_proposal", END)
    graph.add_edge("give_up", END)

    # The other side of the gate. Its only way in is choose_branch reading
    # `approved`, which the database will not accept except from `proposed`.
    graph.add_conditional_edges(
        "load_approved",
        after_loading,
        {"apply_fix": "apply_fix", "verify_success": "verify_success", "done": END},
    )
    graph.add_edge("apply_fix", "trigger_rerun")
    graph.add_edge("trigger_rerun", END)
    graph.add_edge("verify_success", END)

    return graph.compile()
