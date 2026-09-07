"""Column-rename review integration tests; no network or running stack required."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
import judge
from proposal import Candidate

import config
import graph
from diagnosis import Diagnosis

EVIDENCE = {
    "failing_task": "dbt_run",
    "failure_output": "column customer_id does not exist",
    "model_path": "models/staging/stg_customers.sql",
    "model_sql": "select customer_id, lower(email) as email from raw.customers",
    "source_columns": ["cust_id", "email"],
}
SQL = "select cust_id as customer_id, lower(email) as email from raw.customers"
DIAGNOSIS = Diagnosis(
    failing_task="dbt_run",
    failing_model=EVIDENCE["model_path"],
    expected_field="customer_id",
    replacing_field="cust_id",
    confidence=0.9,
    explanation="producer-only-explanation",
)


def client(result="appropriate", fail_at=None):
    calls = []
    independent = judge.EvidenceReview(
        expected_field="customer_id",
        replacing_field="cust_id",
        expected_correction="cust_id as customer_id",
        preserved_behaviors=["lower(email)"],
        evidence=["column customer_id does not exist"],
        uncertainties=[],
    )
    check = judge.Check(result=result, reason="Review reason", evidence=["cust_id as customer_id"])
    review = judge.ProposalReview(
        problem_alignment=check, solution_adequacy=check, behavior_preservation=check
    )

    def structured(schema):
        def invoke(messages):
            calls.append(messages)
            if len(calls) == fail_at:
                raise TimeoutError("must not leak this detail")
            return independent if schema is judge.EvidenceReview else review

        return SimpleNamespace(invoke=invoke)

    return SimpleNamespace(with_structured_output=structured), calls


def test_independent_assessment_has_no_producer_content():
    llm, calls = client()
    review = judge.evaluate(llm, EVIDENCE, DIAGNOSIS, SQL, "producer-only-summary")
    assert len(calls) == 2
    assert json.loads(calls[0][1][1]) == EVIDENCE
    assert "producer-only" not in json.dumps(calls[0])
    payload = json.loads(calls[1][1][1])
    assert payload["candidate_sql"] == SQL
    assert payload["independent_assessment"] == review["independent_assessment"]


@pytest.mark.parametrize(
    "result,fail_at",
    [
        ("appropriate", None),
        ("issue", None),
        ("insufficient_evidence", None),
        ("appropriate", 1),
        ("appropriate", 2),
    ],
)
def test_graph_reviews_only_validated_candidate_and_stops_for_human(monkeypatch, result, fail_at):
    llm, calls = client(result, fail_at)
    store = Mock()
    store.in_flight.return_value = None
    store.open_incident.return_value = 7
    orchestrator = Mock()
    orchestrator.latest_run.return_value = {"state": "failed", "dag_run_id": "run-1"}
    orchestrator.failed_task.return_value = "dbt_run"
    orchestrator.task_log.return_value = EVIDENCE["failure_output"]
    validator = Mock()
    validator.validate.side_effect = [
        SimpleNamespace(built=False, output="invalid SQL"),
        SimpleNamespace(built=True, output=""),
    ]
    settings = SimpleNamespace(
        dbt_project_dir="/dbt",
        postgres_host="",
        source_db="",
        postgres_user="",
        postgres_password="",
        dag_id="customer_elt",
        phoenix_ui_url="",
        phoenix_endpoint="",
        max_fix_attempts=3,
        llm_model="producer",
        judge_model="reviewer",
    )
    monkeypatch.setattr(graph.sandbox, "resolve_target", lambda *args: None)
    monkeypatch.setattr(graph.evidence, "failing_model_path", lambda _: EVIDENCE["model_path"])
    monkeypatch.setattr(graph.evidence, "read_model", lambda *args: EVIDENCE["model_sql"])
    monkeypatch.setattr(graph.evidence, "source_columns", lambda *args: EVIDENCE["source_columns"])
    monkeypatch.setattr(graph, "diagnose", lambda *args: DIAGNOSIS)
    propose = Mock(
        side_effect=[
            Candidate(model_sql="bad SQL", summary="first"),
            Candidate(model_sql=SQL, summary="final"),
        ]
    )
    monkeypatch.setattr(graph.proposal, "propose", propose)
    write = Mock()
    monkeypatch.setattr(graph.sandbox, "write_model", write)
    result_state = graph.build_graph(settings, orchestrator, store, validator, Mock(), llm).invoke(
        {}
    )
    assert validator.validate.call_count == 2
    assert len(calls) == (fail_at or 2)
    saved = store.record_proposal.call_args.kwargs
    assert saved["model_contents_after"] == SQL
    assert saved["judge_review"]["status"] == ("unavailable" if fail_at else "completed")
    assert "must not leak" not in json.dumps(saved)
    assert result_state["attempts"] == 2
    store.conclude_unfixable.assert_not_called()
    orchestrator.trigger_run.assert_not_called()
    write.assert_not_called()


def test_same_judge_model_is_configuration_error(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "producer")
    monkeypatch.setenv("JUDGE_MODEL", " Producer ")
    with pytest.raises(RuntimeError, match="different model"):
        config.load()


def test_missing_judge_model_is_configuration_error(monkeypatch):
    monkeypatch.delenv("JUDGE_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="JUDGE_MODEL"):
        config.load()


@pytest.mark.parametrize("separate_endpoint", [False, True])
def test_judge_connection_reuses_producer_unless_overridden(monkeypatch, separate_endpoint):
    for name in (
        "POSTGRES_HOST",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_SOURCE_DB",
        "POSTGRES_WAREHOUSE_DB",
        "AIRFLOW_API_URL",
        "AIRFLOW_ADMIN_USERNAME",
        "AIRFLOW_ADMIN_PASSWORD",
    ):
        monkeypatch.setenv(name, "test")
    monkeypatch.setenv("OPENAI_MODEL", "producer")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://producer.invalid/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-producer-key")
    monkeypatch.setenv("JUDGE_MODEL", "reviewer")
    monkeypatch.setenv("JUDGE_BASE_URL", "https://judge.invalid/v1" if separate_endpoint else "")
    monkeypatch.setenv("JUDGE_API_KEY", "test-judge-key" if separate_endpoint else "")
    settings = config.load()
    assert settings.judge_model == "reviewer"
    assert settings.judge_base_url == (
        "https://judge.invalid/v1" if separate_endpoint else settings.llm_base_url
    )
    assert settings.judge_api_key == (
        "test-judge-key" if separate_endpoint else settings.llm_api_key
    )
