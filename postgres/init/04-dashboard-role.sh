#!/bin/bash
# The operator console's database role.
#
# A shell file rather than plain SQL because the role's name and password come
# from the environment: nothing under postgres/init may contain a credential
# literal, and psql only substitutes variables it is given explicitly.
#
# ADR-0015 describes an asymmetry — the agent writes everything about an
# incident except the decision, and the console writes only the decision. Until
# this role existed that described what the code did rather than limiting what
# it could do, and it is a claim the demo makes out loud.
#
# Here it becomes a privilege. See adr/0027-bound-the-consoles-authority-by-grant.md
set -euo pipefail

psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" \
     --dbname warehouse_db \
     -v dashboard_user="$DASHBOARD_DB_USER" \
     -v dashboard_password="$DASHBOARD_DB_PASSWORD" <<'SQL'
CREATE ROLE :"dashboard_user" WITH LOGIN PASSWORD :'dashboard_password';

COMMENT ON ROLE :"dashboard_user" IS
    'The operator console. May read incidents and record a decision; may write nothing else.';

GRANT CONNECT ON DATABASE warehouse_db TO :"dashboard_user";
GRANT USAGE ON SCHEMA ops TO :"dashboard_user";

-- Read the whole story...
GRANT SELECT ON ops.incidents TO :"dashboard_user";

-- ...and write one field of it. Column-level UPDATE is the whole mechanism: an
-- UPDATE naming any other column is refused by the server, not by the console.
GRANT UPDATE (state) ON ops.incidents TO :"dashboard_user";

-- Which values that column may take is not this file's problem. The lifecycle
-- trigger already permits only the transitions an operator is entitled to make,
-- and it applies to every writer.
-- See adr/0016-enforce-the-incident-lifecycle-in-the-database.md

-- Deliberately not granted: INSERT and DELETE. The console does not open
-- incidents and does not remove them. An interface able to insert one could
-- insert it already approved — the gate's whole subject — and while the insert
-- trigger would refuse that, it should not be the only thing in the way.

-- Also deliberately absent: any access to raw, staging or analytics. The
-- console must not be able to answer "is the pipeline healthy?" from the
-- warehouse's contents, because a failed run leaves the previous output in
-- place and the answer would be wrong for exactly as long as it mattered.
-- Health comes from the orchestrator.
-- See adr/0026-read-pipeline-health-from-the-run-not-the-data.md
SQL

echo "dashboard role provisioned"
