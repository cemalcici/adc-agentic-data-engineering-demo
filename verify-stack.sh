#!/usr/bin/env bash
#
# Asserts every readiness claim the stack makes.
#
# Healthchecks prove processes are up; they cannot prove data-level claims like
# "the source dataset holds the expected number of rows". This script checks
# both, and is the single command the specs refer to.
#
# Runs entirely through `docker compose exec`, so it needs no Python, psql, or
# database driver on the host.
#
# Usage:  ./verify-stack.sh
# Exits 0 only if every claim holds.

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

# Run a query against a database as the configured user, stripping whitespace.
psql_query() {
    local database="$1" query="$2"
    docker compose exec -T postgres \
        psql -U "${POSTGRES_USER}" -d "${database}" -tAc "${query}" 2>/dev/null | tr -d '[:space:]'
}

echo
echo "Stack readiness"
echo "==============="
echo

# --- Databases -------------------------------------------------------------
echo "Databases"
for database in source_db warehouse_db airflow; do
    if [[ "$(psql_query postgres "SELECT 1 FROM pg_database WHERE datname='${database}'")" == "1" ]]; then
        pass "${database} exists"
    else
        fail "${database} exists" "not found in pg_database"
    fi
done

# Separation is the point of using databases rather than schemas: a query
# issued against the warehouse must not be able to reach source tables.
if docker compose exec -T postgres \
        psql -U "${POSTGRES_USER}" -d warehouse_db -tAc \
        "SELECT count(*) FROM customers" >/dev/null 2>&1; then
    fail "warehouse cannot read source tables" "customers was readable from warehouse_db"
else
    pass "warehouse cannot read source tables"
fi

# --- Source dataset --------------------------------------------------------
echo
echo "Source dataset"

# The upstream system keeps operating, so the source no longer holds a single
# fixed number of rows. A legitimate count is the seeded figure plus a whole
# number of arrival batches — still exact, and still catching a generator that
# has started producing the wrong amount.
# See adr/0012-let-the-simulated-upstream-keep-operating.md
SEEDED_ROWS="${SEED_ROW_COUNT:-25000}"
BATCH_ROWS="${ARRIVAL_BATCH_SIZE:-25}"
ACTUAL_ROWS="$(psql_query source_db "SELECT count(*) FROM customers")"

if [[ -z "${ACTUAL_ROWS}" ]]; then
    fail "customers holds a legitimate row count" "could not count the source table"
elif (( ACTUAL_ROWS < SEEDED_ROWS )); then
    fail "customers holds a legitimate row count" \
        "found ${ACTUAL_ROWS}, fewer than the seeded ${SEEDED_ROWS}"
elif (( (ACTUAL_ROWS - SEEDED_ROWS) % BATCH_ROWS != 0 )); then
    fail "customers holds a legitimate row count" \
        "found ${ACTUAL_ROWS}: not ${SEEDED_ROWS} plus a whole number of ${BATCH_ROWS}-record batches"
else
    ARRIVALS=$(( (ACTUAL_ROWS - SEEDED_ROWS) / BATCH_ROWS ))
    pass "customers holds ${ACTUAL_ROWS} rows (seeded ${SEEDED_ROWS}, ${ARRIVALS} arrival batch(es) since)"
fi

SEEDER_EXIT="$(docker compose ps -a --format '{{.Service}} {{.ExitCode}}' 2>/dev/null | awk '$1=="seeder"{print $2}')"
if [[ "${SEEDER_EXIT}" == "0" ]]; then
    pass "seeder completed successfully"
else
    fail "seeder completed successfully" "exit code '${SEEDER_EXIT:-unknown}' — see: docker compose logs seeder"
fi

# The identifier column has two legitimate names now: its original one, and the
# one the drift trigger renames it to. Asserting the original would report the
# stack as broken for the whole length of a deliberate demo scenario, which is
# not what a readiness check is for. What must hold is that an identifier exists;
# which name it currently carries is reported.
IDENTIFIER="$(psql_query source_db "
    SELECT a.attname
    FROM pg_index i
    JOIN pg_class c ON c.oid = i.indrelid
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
    WHERE c.relname = 'customers' AND i.indisprimary")"

case "${IDENTIFIER}" in
    customer_id)
        pass "source identifier is 'customer_id' (no drift applied)"
        ;;
    cust_id)
        pass "source identifier is 'cust_id' (drift applied)"
        ;;
    "")
        fail "source has an identifier column" "the customers table has no primary key"
        ;;
    *)
        fail "source has a recognised identifier column" "found '${IDENTIFIER}', expected customer_id or cust_id"
        ;;
esac

# The warehouse is the pipeline's output, so whether that output exists is the
# difference between a pipeline that has run and one that has not. This reports
# which state the stack is in rather than asserting one of them: both are valid,
# and conflating them is how a broken pipeline gets mistaken for a working one.
#
# Note it does NOT report pipeline health. The mart survives a failed run — see
# the stale-output finding in progress-tracker.md — so a populated warehouse is
# evidence the pipeline ran at some point, never evidence it is working now.
MART_EXISTS="$(psql_query warehouse_db "SELECT count(*) FROM information_schema.tables WHERE table_schema='analytics' AND table_name='dim_customers'")"
if [[ "${MART_EXISTS}" == "0" ]]; then
    pass "warehouse holds no transformation output (the pipeline has not run)"
elif [[ "${MART_EXISTS}" == "1" ]]; then
    MART_ROWS="$(psql_query warehouse_db "SELECT count(*) FROM analytics.dim_customers")"
    pass "warehouse holds transformation output: ${MART_ROWS} rows (the pipeline has run)"
else
    fail "warehouse transformation state is determinable" "could not read the analytics schema"
fi

# The landing table is filled by the extract step, and by the verification
# fixture until that step exists. Reported, not asserted — at cold start neither
# has run and its absence is correct.
LANDING_EXISTS="$(psql_query warehouse_db "SELECT count(*) FROM information_schema.tables WHERE table_schema='raw' AND table_name='customers'")"
if [[ "${LANDING_EXISTS}" == "1" ]]; then
    LANDING_ROWS="$(psql_query warehouse_db "SELECT count(*) FROM raw.customers")"
    pass "landing table holds ${LANDING_ROWS} rows"
else
    pass "landing table not yet created (nothing has extracted into the warehouse)"
fi

# --- Incident store --------------------------------------------------------
echo
echo "Incident store"

# The channel between the agent and the operator interface, and where the
# approval gate physically lives. It exists from a cold start so the interface
# can be built against rows written by hand, before any agent exists.
# See adr/0015-the-incident-record-is-the-channel-between-agent-and-operator.md
if [[ "$(psql_query warehouse_db "SELECT count(*) FROM information_schema.tables WHERE table_schema='ops' AND table_name='incidents'")" == "1" ]]; then
    INCIDENTS="$(psql_query warehouse_db "SELECT count(*) FROM ops.incidents")"
    IN_FLIGHT="$(psql_query warehouse_db "SELECT count(*) FROM ops.incidents WHERE state NOT IN ('resolved','rejected','unfixable','verification_failed')")"
    pass "incident store present (${INCIDENTS} recorded, ${IN_FLIGHT} in flight)"
else
    fail "incident store present" "ops.incidents not found in warehouse_db"
fi

# The lifecycle is enforced by the schema rather than by the code that writes to
# it, which is what makes the approval gate hold regardless of what any consumer
# gets wrong. If the enforcement is missing, the gate is not there either.
# See adr/0016-enforce-the-incident-lifecycle-in-the-database.md
GATE_PARTS="$(psql_query warehouse_db "
    SELECT count(*) FROM (
        SELECT 1 FROM pg_trigger WHERE tgrelid = 'ops.incidents'::regclass AND NOT tgisinternal
        UNION ALL
        SELECT 1 FROM pg_indexes WHERE schemaname='ops' AND indexname='incidents_only_one_in_flight'
    ) present")"
if [[ "${GATE_PARTS}" == "3" ]]; then
    pass "incident lifecycle is enforced by the database"
else
    fail "incident lifecycle is enforced by the database" \
        "expected 2 triggers and the single-in-flight index, found ${GATE_PARTS:-0} of 3"
fi

# --- Orchestrator ----------------------------------------------------------
echo
echo "Orchestrator"

AIRFLOW_URL="http://localhost:8080"

# Credentials are passed as environment variables rather than interpolated into
# the command, so they never appear in process arguments or in this script's
# output. The api-server itself does not carry them — only airflow-init does.
TOKEN="$(docker compose exec -T \
    -e ADMIN_USERNAME="${AIRFLOW_ADMIN_USERNAME}" \
    -e ADMIN_PASSWORD="${AIRFLOW_ADMIN_PASSWORD}" \
    airflow-apiserver python -c "
import json, os, urllib.request
body = json.dumps({
    'username': os.environ['ADMIN_USERNAME'],
    'password': os.environ['ADMIN_PASSWORD'],
}).encode()
request = urllib.request.Request(
    '${AIRFLOW_URL}/auth/token',
    data=body,
    headers={'Content-Type': 'application/json'},
)
with urllib.request.urlopen(request, timeout=15) as response:
    print(json.load(response)['access_token'])
" 2>/dev/null | tr -d '[:space:]')"

if [[ -n "${TOKEN}" ]]; then
    pass "API issues a token to the configured admin"

    DAG_STATUS="$(docker compose exec -T airflow-apiserver python -c "
import urllib.error, urllib.request
request = urllib.request.Request(
    '${AIRFLOW_URL}/api/v2/dags',
    headers={'Authorization': 'Bearer ${TOKEN}'},
)
try:
    with urllib.request.urlopen(request, timeout=15) as response:
        print(response.status)
except urllib.error.HTTPError as error:
    print(error.code)
" 2>/dev/null | tr -d '[:space:]')"

    if [[ "${DAG_STATUS}" == "200" ]]; then
        pass "authenticated API call succeeds (GET /api/v2/dags)"
    else
        fail "authenticated API call succeeds (GET /api/v2/dags)" "HTTP ${DAG_STATUS:-no response}"
    fi
else
    fail "API issues a token to the configured admin" "no token returned from /auth/token"
    fail "authenticated API call succeeds (GET /api/v2/dags)" "skipped, no token"
fi

# --- Observability ---------------------------------------------------------
echo
echo "Observability"

if docker compose exec -T phoenix python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:6006/healthz', timeout=10)" \
        >/dev/null 2>&1; then
    pass "trace collector answers"
else
    fail "trace collector answers" "no response on /healthz"
fi

# Observability must share no storage with the pipeline. If Phoenix were backed
# by the pipeline's PostgreSQL instance, resetting traces would touch pipeline
# state — see ADR-0006.
if docker compose exec -T postgres \
        psql -U "${POSTGRES_USER}" -d postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname LIKE '%phoenix%'" 2>/dev/null | grep -q 1; then
    fail "trace storage is independent of the pipeline database" "a phoenix database exists in PostgreSQL"
else
    pass "trace storage is independent of the pipeline database"
fi

# --- Agent -----------------------------------------------------------------
echo
echo "Agent"

# The agent checks its language model endpoint once at startup and reports the
# result rather than exiting, so a wrong model id or an unreachable endpoint is
# visible here instead of in the middle of an incident.
# See adr/0018-depend-on-an-openai-compatible-endpoint-not-a-vendor.md
ENDPOINT_LINE="$(docker compose logs agent 2>/dev/null | grep -o 'language model endpoint: .*' | tail -1)"
case "${ENDPOINT_LINE}" in
    *"endpoint: ok"*)
        pass "${ENDPOINT_LINE#language model }"
        ;;
    *"endpoint: unusable"*)
        fail "agent language model endpoint is usable" "${ENDPOINT_LINE#language model endpoint: }"
        ;;
    *)
        fail "agent language model endpoint is usable" \
            "the agent has not reported a startup check — see: docker compose logs agent"
        ;;
esac

# --- Operator console ------------------------------------------------------
echo
echo "Operator console"

if curl -fsS -o /dev/null --max-time 10 "http://localhost:${DASHBOARD_PORT:-8501}/_stcore/health"; then
    pass "console answers on port ${DASHBOARD_PORT:-8501}"
else
    fail "console answers on port ${DASHBOARD_PORT:-8501}" \
        "no response — see: docker compose logs streamlit"
fi

# The console's whole claim is that it writes one thing. Asserted here rather
# than trusted, because it is a claim made out loud during the demo and because
# a grant is exactly the kind of thing a later change can widen without anyone
# noticing.
# See adr/0027-bound-the-consoles-authority-by-grant.md
CONSOLE_WRITES="$(psql_query warehouse_db "
    SELECT coalesce(string_agg(DISTINCT privilege_type || ':' || coalesce(column_name, 'table'), ',' ORDER BY privilege_type || ':' || coalesce(column_name, 'table')), 'none')
    FROM information_schema.column_privileges
    WHERE table_schema = 'ops' AND grantee = '${DASHBOARD_DB_USER}'
      AND privilege_type <> 'SELECT'")"
if [[ "${CONSOLE_WRITES}" == "UPDATE:state" ]]; then
    pass "console may write the decision and nothing else"
else
    fail "console may write the decision and nothing else" \
        "its write grants are: ${CONSOLE_WRITES}"
fi

# The same claim on the other side. A console that could start a pipeline run
# would make it false whether or not it ever did.
#
# This asks the orchestrator to start one, rather than reading the user's role
# and trusting it. If the permission were ever widened the request would
# succeed, and this check would both fail and leave a pipeline run behind — an
# unwanted side effect from a readiness check, accepted because a check that
# only reads configuration proves less than one that tries the thing.
VIEWER_TOKEN="$(curl -fsS --max-time 10 -X POST "${AIRFLOW_URL}/auth/token" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"${AIRFLOW_VIEWER_USERNAME}\",\"password\":\"${AIRFLOW_VIEWER_PASSWORD}\"}" \
    2>/dev/null | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
if [[ -z "${VIEWER_TOKEN}" ]]; then
    fail "console's orchestrator user can read runs" "it was not issued a token"
else
    TRIGGER_CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
        -X POST "${AIRFLOW_URL}/api/v2/dags/customer_elt/dagRuns" \
        -H "Authorization: Bearer ${VIEWER_TOKEN}" \
        -H 'Content-Type: application/json' -d '{"logical_date": null}')"
    if [[ "${TRIGGER_CODE}" == "403" ]]; then
        pass "console's orchestrator user cannot start a pipeline run"
    else
        fail "console's orchestrator user cannot start a pipeline run" \
            "starting one answered HTTP ${TRIGGER_CODE}, expected 403"
    fi
fi

# --- Summary ---------------------------------------------------------------
echo
echo "==============="
if (( FAILED == 0 )); then
    printf '\033[32m%d passed, 0 failed — stack is ready\033[0m\n\n' "${PASSED}"
    exit 0
fi

printf '\033[31m%d passed, %d failed — stack is NOT ready\033[0m\n\n' "${PASSED}" "${FAILED}"
exit 1
