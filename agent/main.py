"""The agent's entry point: instrument, check, then loop.

Watches for a failed pipeline run, explains it, proposes a correction, proves
that correction builds, and — once an operator has approved it — applies it and
re-triggers the pipeline until the run that follows says whether it worked.

Everything that acts is reachable only from an approved incident. The agent does
not check whether it may proceed; it arrives at those steps only by a route that
starts at a decision.
"""

from __future__ import annotations

import sys
import time

from langchain_openai import ChatOpenAI
from opentelemetry import trace
from validation import Validator

import config
import diagnosis
from graph import build_graph
from incidents import IncidentStore
from orchestrator import Orchestrator


def start_tracing(endpoint: str) -> None:
    """Export spans to the trace collector, if there is one.

    Best effort by design: an observability layer that can break the thing it
    observes has made the system less reliable in exchange for insight into it.

    Batched, and that is not a preference. Sending each span as it ends means
    each one waits for the collector — and with nothing listening, each retries
    with backoff before giving up. Measured with the collector stopped: a pass
    that normally takes about two seconds took roughly ninety. The agent kept
    working, so the requirement that it must not stall looked met while it was
    being broken by an order of magnitude. Batching moves the export off the
    path the agent's work runs on.
    """
    if not endpoint:
        print("no trace collector configured; continuing without tracing")
        return
    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from phoenix.otel import register

        provider = register(
            project_name="self-healing-pipeline",
            endpoint=f"{endpoint.rstrip('/')}/v1/traces",
            batch=True,
        )
        LangChainInstrumentor().instrument(tracer_provider=provider)
        print(f"tracing to {endpoint}")
    except Exception as error:  # noqa: BLE001 - tracing must never be fatal
        print(f"tracing unavailable ({type(error).__name__}); continuing without it")


def main() -> int:
    settings = config.load()
    start_tracing(settings.phoenix_endpoint)

    llm = diagnosis.build_model(
        settings.llm_base_url, settings.llm_api_key, settings.llm_model
    )

    # Ask the endpoint one trivial question now rather than discovering a wrong
    # model id in the middle of an incident. Reported, never fatal — a container
    # that restarts on a bad variable drowns the demo in noise.
    status, detail = diagnosis.check_endpoint(llm)
    print(f"language model endpoint: {status} ({settings.llm_model}) — {detail}")

    orchestrator = Orchestrator(
        settings.airflow_url,
        settings.airflow_username,
        settings.airflow_password,
        settings.dag_id,
    )
    store = IncidentStore(
        settings.postgres_host,
        settings.warehouse_db,
        settings.postgres_user,
        settings.postgres_password,
    )
    validator = Validator(
        project_dir=settings.dbt_project_dir,
        scratch_dir=settings.scratch_dir,
        dbt_executable=settings.dbt_executable,
        schema_prefix=settings.validation_schema_prefix,
        warehouse={
            "host": settings.postgres_host,
            "dbname": settings.warehouse_db,
            "user": settings.postgres_user,
            "password": settings.postgres_password,
        },
    )
    judge_llm = ChatOpenAI(
        base_url=settings.judge_base_url, api_key=settings.judge_api_key,
        model=settings.judge_model, temperature=0, timeout=30, max_retries=0,
    )
    graph = build_graph(settings, orchestrator, store, validator, llm, judge_llm)

    print(f"watching {settings.dag_id} every {settings.poll_interval_seconds}s")
    tracer = trace.get_tracer("agent")
    while True:
        try:
            # Each pass gets one span of its own, so the whole pass shares a
            # trace id the incident can point at. The instrumentation's spans
            # nest under it; without this there is no single span that
            # represents "the work that produced this incident".
            with tracer.start_as_current_span("agent_pass"):
                result = graph.invoke({})
                outcome = result.get("outcome")
                if outcome and outcome != "no failed run":
                    print(f"pass complete: {outcome}")
                if result.get("incident_id") and result.get("diagnosis"):
                    found = result["diagnosis"]
                    print(
                        f"incident {result['incident_id']}: "
                        f"{found.expected_field} -> {found.replacing_field} "
                        f"in {found.failing_model} (confidence {found.confidence})"
                    )
        except Exception as error:  # noqa: BLE001 - a bad pass must not end the loop
            print(f"pass failed ({type(error).__name__}): {error}")
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    sys.exit(main())
