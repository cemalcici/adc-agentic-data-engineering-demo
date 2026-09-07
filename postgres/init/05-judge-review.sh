#!/bin/bash
# Add advisory review and the human's assessment without changing lifecycle states.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname warehouse_db \
     -v dashboard_user="$DASHBOARD_DB_USER" <<'SQL'
BEGIN;
ALTER TABLE ops.incidents ADD COLUMN IF NOT EXISTS judge_review JSONB;
ALTER TABLE ops.incidents ADD COLUMN IF NOT EXISTS judge_feedback TEXT
    CHECK (judge_feedback IN ('agree', 'partly_agree', 'disagree'));
ALTER TABLE ops.incidents ADD COLUMN IF NOT EXISTS judge_feedback_note TEXT;
CREATE OR REPLACE FUNCTION ops.require_judge_feedback() RETURNS trigger AS $$
BEGIN
    IF OLD.state = 'proposed' AND NEW.state IN ('approved', 'rejected')
       AND NEW.judge_review->>'status' = 'completed'
       AND NEW.judge_feedback IS NULL THEN
        RAISE EXCEPTION 'Assess the judge review before deciding on the proposal'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS incidents_judge_feedback ON ops.incidents;
CREATE TRIGGER incidents_judge_feedback BEFORE UPDATE ON ops.incidents
    FOR EACH ROW EXECUTE FUNCTION ops.require_judge_feedback();
GRANT UPDATE (judge_feedback, judge_feedback_note) ON ops.incidents TO :"dashboard_user";
COMMIT;
SQL
