"""Exercise the actual Streamlit decision callback without live services."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("available", [True, False])
def test_human_feedback_required_only_for_completed_review(available):
    check = {"result": "issue", "reason": "Kontrol edilmeli", "evidence": ["cust_id"]}
    review = {
        "status": "completed" if available else "unavailable",
        "producer_model": "producer",
        "judge_model": "reviewer",
        "independent_assessment": {"expected_field": "customer_id"},
        "checks": {
            key: check
            for key in ("problem_alignment", "solution_adequacy", "behavior_preservation")
        },
    }
    incident = {
        "id": 7,
        "state": "proposed",
        "judge_review": review,
        "model_contents_before": "select customer_id from raw.customers",
        "model_contents_after": "select cust_id as customer_id from raw.customers",
        "target_model_path": "models/staging/stg_customers.sql",
    }
    source = (ROOT / "streamlit_app/app.py").read_text().rsplit("\nmain()", 1)[0]
    source = source.replace("from __future__ import annotations", "")
    bootstrap = f"import sys\nsys.path.insert(0, {str(ROOT / 'streamlit_app')!r})\n"
    harness = """
class FakeStore:
    def record_decision(self, **kwargs):
        st.session_state['saved'] = kwargs
        return True
proposal_panel(INCIDENT, FakeStore())
_show_notice()
"""
    app = AppTest.from_string(
        bootstrap + source + "\nINCIDENT = " + repr(incident) + harness, default_timeout=15
    )
    app.run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    if available:
        assert "saved" not in app.session_state
        app.selectbox[0].select("Katılmıyorum").run()
        app.button[0].click().run()
        assert app.session_state["saved"]["judge_feedback"] == "disagree"
    else:
        assert app.session_state["saved"]["judge_feedback"] is None
        assert len(app.selectbox) == 0
    assert app.session_state["saved"]["decision"] == "approved"
    assert not app.exception


def test_unfixable_history_explains_why_without_offering_approval():
    source = (ROOT / "streamlit_app/app.py").read_text().rsplit("\nmain()", 1)[0]
    source = source.replace("from __future__ import annotations", "")
    row = dict(id=1, state="unfixable", opened_at=None, failing_task_id="dbt_run",
               conclusion_note="dbt executable not found: /demo-fault/dbt-unavailable")
    bootstrap = f"import sys\nsys.path.insert(0, {str(ROOT / 'streamlit_app')!r})\n"
    app = AppTest.from_string(bootstrap + source + f"\nhistory_panel([{row!r}])", default_timeout=15).run()
    assert not app.exception
    content = "\n".join(str(element.value) for element in app.markdown)
    assert "unfixable" in content
    assert row["conclusion_note"] in content
    assert not app.button


@pytest.mark.parametrize("same_run", [True, False])
def test_recorded_failure_is_not_reported_as_unrecorded(same_run):
    source = (ROOT / "streamlit_app/app.py").read_text().rsplit("\nmain()", 1)[0]
    source = source.replace("from __future__ import annotations", "")
    row = dict(id=1, state="unfixable", opened_at=None, failing_task_id="dbt_run",
               failing_run_id="failed-1", conclusion_note="3 candidates; validator unavailable")
    bootstrap = f"import sys\nsys.path.insert(0, {str(ROOT / 'streamlit_app')!r})\n"
    harness = f'''
from types import SimpleNamespace
store = SimpleNamespace(in_flight=lambda: None, history=lambda: [{row!r}])
pipeline.health = lambda _: ("failing", {{"dag_run_id": {('failed-1' if same_run else 'failed-2')!r}}}, "last run failed")
render(SimpleNamespace(), store, None, refreshing=False)
'''
    app = AppTest.from_string(bootstrap + source + harness, default_timeout=15).run()
    assert not app.exception
    content = "\n".join(str(element.value) for element in app.markdown)
    assert ("Nothing has been recorded for this failure yet" in content) is not same_run
