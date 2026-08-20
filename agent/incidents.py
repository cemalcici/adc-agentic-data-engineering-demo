"""Writing to the incident record.

The record is the channel between the agent and the operator, and the place the
approval gate lives. Its lifecycle is enforced by the database, so this module
does not re-check what the schema already refuses.

See adr/0015-the-incident-record-is-the-channel-between-agent-and-operator.md
"""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

TERMINAL_STATES = ("resolved", "rejected", "unfixable", "verification_failed")

OPEN_INCIDENT = f"""
    SELECT * FROM ops.incidents
    WHERE state NOT IN {TERMINAL_STATES}
    ORDER BY opened_at DESC
    LIMIT 1
"""

RECORD_PROPOSAL = """
    UPDATE ops.incidents
    SET state = 'proposed',
        target_model_path = %(target_model_path)s,
        model_contents_before = %(model_contents_before)s,
        model_contents_after = %(model_contents_after)s
    WHERE id = %(incident_id)s AND state = 'open'
"""

CONCLUDE_UNFIXABLE = """
    UPDATE ops.incidents
    SET state = 'unfixable',
        conclusion_note = %(conclusion_note)s
    WHERE id = %(incident_id)s AND state = 'open'
"""

RECORD_VERIFYING_RUN = """
    UPDATE ops.incidents
    SET verifying_run_id = %(verifying_run_id)s
    WHERE id = %(incident_id)s AND state = 'approved' AND verifying_run_id IS NULL
"""

RESOLVE = """
    UPDATE ops.incidents
    SET state = 'resolved'
    WHERE id = %(incident_id)s AND state = 'approved'
"""

CONCLUDE_VERIFICATION_FAILED = """
    UPDATE ops.incidents
    SET state = 'verification_failed',
        conclusion_note = %(conclusion_note)s
    WHERE id = %(incident_id)s AND state = 'approved'
"""

INSERT_INCIDENT = """
    INSERT INTO ops.incidents (
        dag_id, failing_run_id, failing_task_id, failure_output,
        diagnosis, trace_url
    ) VALUES (
        %(dag_id)s, %(failing_run_id)s, %(failing_task_id)s, %(failure_output)s,
        %(diagnosis)s, %(trace_url)s
    )
    RETURNING id
"""


class IncidentStore:
    """Reads and writes the incident record."""

    def __init__(self, host: str, database: str, user: str, password: str) -> None:
        self._connect_args = {
            "host": host,
            "dbname": database,
            "user": user,
            "password": password,
        }

    def _connection(self) -> psycopg2.extensions.connection:
        return psycopg2.connect(**self._connect_args)

    def in_flight(self) -> dict[str, Any] | None:
        """The incident currently in flight, if there is one.

        At most one can exist — the database enforces that, so this returns a
        single row rather than a list.
        """
        connection = self._connection()
        try:
            with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(OPEN_INCIDENT)
                row = cursor.fetchone()
                return dict(row) if row else None
        finally:
            connection.close()

    def open_incident(
        self,
        dag_id: str,
        failing_run_id: str,
        failing_task_id: str,
        failure_output: str,
        diagnosis: str,
        trace_url: str | None,
    ) -> int:
        """Record a newly diagnosed failure."""
        connection = self._connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    INSERT_INCIDENT,
                    {
                        "dag_id": dag_id,
                        "failing_run_id": failing_run_id,
                        "failing_task_id": failing_task_id,
                        "failure_output": failure_output,
                        "diagnosis": diagnosis,
                        "trace_url": trace_url,
                    },
                )
                incident_id = int(cursor.fetchone()[0])
            connection.commit()
            return incident_id
        finally:
            connection.close()

    def _advance(self, statement: str, parameters: dict[str, Any]) -> None:
        """Move an incident along, or fail loudly if the store refuses.

        The refusal is the schema's, not this module's. Nothing here re-checks
        what the lifecycle trigger already enforces — a second opinion about the
        approval gate is a second place for it to be wrong.
        """
        connection = self._connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                if cursor.rowcount != 1:
                    raise RuntimeError(
                        f"incident {parameters['incident_id']} was not where it was "
                        f"expected to be; {cursor.rowcount} rows moved"
                    )
            connection.commit()
        finally:
            connection.close()

    def record_proposal(
        self,
        incident_id: int,
        target_model_path: str,
        model_contents_before: str,
        model_contents_after: str,
    ) -> None:
        """Record a validated fix and stop.

        The contents are stored whole rather than as a difference, so what the
        operator approves and what would be written cannot diverge.
        See adr/0017-carry-proposed-fixes-as-file-contents.md
        """
        self._advance(
            RECORD_PROPOSAL,
            {
                "incident_id": incident_id,
                "target_model_path": target_model_path,
                "model_contents_before": model_contents_before,
                "model_contents_after": model_contents_after,
            },
        )

    def conclude_unfixable(self, incident_id: int, conclusion_note: str) -> None:
        """End an incident the agent could not write a working fix for.

        Nothing is offered for a decision. The note is what the operator gets
        instead: an outcome that says only "unfixable" explains nothing.
        """
        self._advance(
            CONCLUDE_UNFIXABLE,
            {"incident_id": incident_id, "conclusion_note": conclusion_note},
        )

    def record_verifying_run(self, incident_id: int, verifying_run_id: str) -> None:
        """Note which run is the one being watched.

        The incident stays approved; this is bookkeeping within a state, which
        the lifecycle permits. Recorded separately from the run that failed, so
        "this broke on run A and was confirmed fixed on run D" stays answerable.

        Refuses to overwrite a run already recorded: a second trigger after a
        crash must not make the agent abandon the run it is already watching.
        """
        self._advance(
            RECORD_VERIFYING_RUN,
            {"incident_id": incident_id, "verifying_run_id": verifying_run_id},
        )

    def resolve(self, incident_id: int) -> None:
        """The pipeline recovered."""
        self._advance(RESOLVE, {"incident_id": incident_id})

    def conclude_verification_failed(
        self, incident_id: int, conclusion_note: str
    ) -> None:
        """The fix was applied and the pipeline did not recover.

        Distinct from the operator rejecting a proposal and from the agent
        failing to write one, because those are three different stories about
        whether any of this works. The file stays as it was applied — see
        adr/0025-an-applied-fix-is-not-unapplied.md
        """
        self._advance(
            CONCLUDE_VERIFICATION_FAILED,
            {"incident_id": incident_id, "conclusion_note": conclusion_note},
        )
