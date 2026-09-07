"""Reading the incident record, and writing the decision and judge feedback the operator owns.

The console connects as a role that may select from this table and update the
decision and feedback columns. Nothing in this module enforces that — the grants do, and
an UPDATE naming any other column is refused by the server rather than by a
check here.

See adr/0027-bound-the-consoles-authority-by-grant.md
See adr/0015-the-incident-record-is-the-channel-between-agent-and-operator.md
"""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

TERMINAL_STATES = ("resolved", "rejected", "unfixable", "verification_failed")

IN_FLIGHT = f"""
    SELECT * FROM ops.incidents
    WHERE state NOT IN {TERMINAL_STATES}
    ORDER BY opened_at DESC
    LIMIT 1
"""

HISTORY = """
    SELECT * FROM ops.incidents
    ORDER BY opened_at DESC
    LIMIT %(limit)s
"""

# Conditional on the state the page was rendered from. The operator's click
# reflects what they saw, which may be seconds old, and the incident can move
# while it is read. The lifecycle trigger would refuse anything illegal anyway;
# this is what lets the console explain rather than raise.
RECORD_DECISION = """
    UPDATE ops.incidents
    SET state = %(decision)s,
        judge_feedback = %(judge_feedback)s,
        judge_feedback_note = %(judge_feedback_note)s
    WHERE id = %(incident_id)s AND state = %(expected_state)s
"""


class IncidentStore:
    """Reads the record; writes the decision and human judge feedback."""

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
        """The incident currently in flight, if there is one."""
        connection = self._connection()
        try:
            with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(IN_FLIGHT)
                row = cursor.fetchone()
                return dict(row) if row else None
        finally:
            connection.close()

    def history(self, limit: int = 25) -> list[dict[str, Any]]:
        """Everything recorded, most recent first."""
        connection = self._connection()
        try:
            with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(HISTORY, {"limit": limit})
                return [dict(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def record_decision(
        self, incident_id: int, decision: str, expected_state: str,
        judge_feedback: str | None = None, judge_feedback_note: str | None = None,
    ) -> bool:
        """Record the operator's decision, if the incident is still where it was.

        Returns False when it is not, so the page can say what happened rather
        than surface a database error. Which decisions are legal at all is the
        schema's business, not this module's.
        """
        connection = self._connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    RECORD_DECISION,
                    {
                        "incident_id": incident_id,
                        "decision": decision,
                        "expected_state": expected_state,
                        "judge_feedback": judge_feedback,
                        "judge_feedback_note": judge_feedback_note,
                    },
                )
                moved = cursor.rowcount == 1
            connection.commit()
            return moved
        finally:
            connection.close()
