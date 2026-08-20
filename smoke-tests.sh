#!/usr/bin/env bash
#
# The two claims the demo rests on, checked mechanically.
#
#   1. The drift trigger really breaks the pipeline.
#   2. An approved fix really turns it green again.
#
# Neither check consults a language model. Breaking the pipeline involves no
# agent at all, and applying an approved fix makes no model call — so neither
# assertion can fail because a model answered differently today.
#
# Not quite free, and worth being exact about: the agent is running alongside,
# and a broken pipeline is work, so it will diagnose and propose while this runs
# even though nothing here reads its answer. A run costs a fraction of a cent
# rather than nothing.
#
# What these deliberately DO NOT cover: whether the agent's diagnosis reads well
# aloud, whether the proposed change is small enough to take in at a glance, and
# whether the beats fit the time available. Those are judgements. A green run
# here is not a rehearsed demo, and is not meant to substitute for one — see
# DEMO.md.
#
# Destructive: runs the drift trigger and applies a fix, so it leaves the stack
# mid-scenario. Reset afterwards the way DEMO.md describes.
#
# Usage:  ./smoke-tests.sh
# Exits 0 only if both claims hold.

set -uo pipefail

cd "$(dirname "$0")"

if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
else
    echo "no .env found — copy .env.example to .env first" >&2
    exit 1
fi

PASSED=0
FAILED=0
AIRFLOW_URL="http://localhost:${AIRFLOW_PORT:-8080}"
DAG_ID="customer_elt"
# A pipeline run takes about ten seconds; this is generous by a wide margin and
# short enough that a genuinely stuck run is reported rather than waited on.
RUN_TIMEOUT_SECONDS=180

pass() {
    printf '  \033[32mPASS\033[0m  %s\n' "$1"
    PASSED=$((PASSED + 1))
}

fail() {
    printf '  \033[31mFAIL\033[0m  %s\n' "$1"
    if [[ -n "${2:-}" ]]; then
        printf '        %s\n' "$2"
    fi
    FAILED=$((FAILED + 1))
}

info() { printf '        %s\n' "$1"; }

psql_query() {
    local database="$1" query="$2"
    docker compose exec -T postgres \
        psql -U "${POSTGRES_USER}" -d "${database}" -tAc "${query}" 2>/dev/null | tr -d '[:space:]'
}

psql_run() {
    local database="$1" statement="$2"
    docker compose exec -T postgres \
        psql -U "${POSTGRES_USER}" -d "${database}" -v ON_ERROR_STOP=1 -q -c "${statement}" >/dev/null 2>&1
}

airflow_token() {
    curl -fsS --max-time 15 -X POST "${AIRFLOW_URL}/auth/token" \
        -H 'Content-Type: application/json' \
        -d "{\"username\":\"${AIRFLOW_ADMIN_USERNAME}\",\"password\":\"${AIRFLOW_ADMIN_PASSWORD}\"}" \
        2>/dev/null | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p'
}

# Start a run and print its identifier. The identifier matters: the state of
# "the latest run" is not the state of the run this asked for.
trigger_run() {
    local token="$1"
    curl -fsS --max-time 15 -X POST "${AIRFLOW_URL}/api/v2/dags/${DAG_ID}/dagRuns" \
        -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' \
        -d '{"logical_date": null}' 2>/dev/null \
        | sed -n 's/.*"dag_run_id":"\([^"]*\)".*/\1/p'
}

# Wait for one specific run to finish, and print how it finished.
await_run() {
    local token="$1" run_id="$2" encoded state elapsed=0
    encoded="$(printf '%s' "${run_id}" | sed 's/:/%3A/g; s/+/%2B/g')"
    while (( elapsed < RUN_TIMEOUT_SECONDS )); do
        state="$(curl -fsS --max-time 15 \
            "${AIRFLOW_URL}/api/v2/dags/${DAG_ID}/dagRuns/${encoded}" \
            -H "Authorization: Bearer ${token}" 2>/dev/null \
            | sed -n 's/.*"state":"\([^"]*\)".*/\1/p')"
        case "${state}" in
            success|failed) printf '%s' "${state}"; return 0 ;;
        esac
        sleep 5
        elapsed=$((elapsed + 5))
    done
    printf 'did-not-finish'
}

echo
echo "Demo smoke tests"
echo "================"
echo

TOKEN="$(airflow_token)"
if [[ -z "${TOKEN}" ]]; then
    fail "the orchestrator issues a token" "check that the stack is up: ./verify-stack.sh"
    echo
    exit 1
fi

# --- 1. The failure is real ------------------------------------------------
echo "The drift trigger breaks the pipeline"

IDENTIFIER="$(psql_query source_db "
    SELECT a.attname FROM pg_index i
    JOIN pg_class c ON c.oid = i.indrelid
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
    WHERE c.relname = 'customers' AND i.indisprimary")"

if [[ "${IDENTIFIER}" == "customer_id" ]]; then
    info "applying the upstream change"
    if ! docker compose --profile drift run --rm --build drift >/dev/null 2>&1; then
        fail "the drift trigger runs" "see: docker compose --profile drift run --rm --build drift"
    fi
elif [[ "${IDENTIFIER}" == "cust_id" ]]; then
    info "the upstream change is already applied; continuing"
else
    fail "the source has a recognised identifier" "found '${IDENTIFIER}'"
fi

info "running the pipeline"
RUN_ID="$(trigger_run "${TOKEN}")"
if [[ -z "${RUN_ID}" ]]; then
    fail "a pipeline run can be started" "the orchestrator returned no run identifier"
else
    OUTCOME="$(await_run "${TOKEN}" "${RUN_ID}")"
    if [[ "${OUTCOME}" == "failed" ]]; then
        pass "the pipeline fails once the upstream column is renamed"
    else
        fail "the pipeline fails once the upstream column is renamed" \
            "the run ended as '${OUTCOME}' — the demo has nothing to show"
    fi
fi

# --- 2. The recovery is real -----------------------------------------------
echo
echo "An approved fix turns it green again"

# The proposal is written straight into the record rather than produced by the
# agent. That is what keeps this check free of a model: everything downstream of
# a decision — writing the file, re-triggering, verifying — makes no model call.
info "recording a fix and approving it"

CORRECTED="$(sed 's/^    customer_id,$/    cust_id                                 as customer_id,/' \
    dbt/models/staging/stg_customers.sql)"

if ! grep -q 'cust_id' <<<"${CORRECTED}"; then
    fail "a corrected transformation can be prepared" \
        "dbt/models/staging/stg_customers.sql does not look like the demo's starting state"
else
    # Do not fight the agent for the in-flight slot. While the pipeline is
    # broken the agent keeps opening incidents, so inserting one races with it —
    # measured, by losing that race. Instead: take whatever is in flight, put
    # the known-good contents on it, and approve that.
    psql_run warehouse_db "
        UPDATE ops.incidents
        SET state='verification_failed',
            conclusion_note='closed by a smoke test run'
        WHERE state='approved';"

    if [[ "$(psql_query warehouse_db "
            SELECT count(*) FROM ops.incidents
            WHERE state IN ('open','proposed')")" == "0" ]]; then
        psql_run warehouse_db "
            INSERT INTO ops.incidents (dag_id, failing_run_id, failing_task_id, failure_output, diagnosis)
            VALUES ('customer_elt', '${RUN_ID:-smoke}', 'dbt_run',
                    'recorded by a smoke test, not by the agent',
                    '{\"explanation\": \"recorded by a smoke test, not by the agent\"}');"
    fi

    # psql substitutes :'NAME' from -v, not from the environment. Passing these
    # as environment variables silently produced nothing — which is how the
    # first version of this test failed.
    docker compose exec -T postgres \
        psql -U "${POSTGRES_USER}" -d warehouse_db -v ON_ERROR_STOP=1 -q \
        -v before="$(cat dbt/models/staging/stg_customers.sql)" \
        -v after="${CORRECTED}" <<'SQL' >/dev/null 2>&1
UPDATE ops.incidents SET
    state = 'proposed',
    target_model_path = 'models/staging/stg_customers.sql',
    model_contents_before = :'before',
    model_contents_after  = :'after'
WHERE state IN ('open', 'proposed');

UPDATE ops.incidents SET state = 'approved' WHERE state = 'proposed';
SQL

    if [[ "$(psql_query warehouse_db "SELECT count(*) FROM ops.incidents WHERE state='approved'")" != "1" ]]; then
        fail "a fix can be recorded and approved" "no incident reached the approved state"
    else
        info "waiting for the agent to apply it and verify"
        CONCLUDED=""
        for _ in $(seq 1 60); do
            CONCLUDED="$(psql_query warehouse_db "
                SELECT state FROM ops.incidents ORDER BY id DESC LIMIT 1")"
            case "${CONCLUDED}" in
                resolved|verification_failed) break ;;
            esac
            sleep 5
        done

        if [[ "${CONCLUDED}" == "resolved" ]]; then
            pass "an approved fix restores the pipeline"
        else
            fail "an approved fix restores the pipeline" \
                "the incident ended as '${CONCLUDED:-still in flight}'"
        fi
    fi
fi

# --- Summary ---------------------------------------------------------------
echo
echo "================"
if (( FAILED == 0 )); then
    printf '\033[32m%d passed, 0 failed\033[0m\n' "${PASSED}"
    printf 'The stack is now mid-scenario. Reset it before rehearsing — see DEMO.md.\n\n'
    exit 0
fi
printf '\033[31m%d passed, %d failed\033[0m\n\n' "${PASSED}" "${FAILED}"
exit 1
