-- The incident record: the channel between the agent and the operator.
--
-- The agent writes what it found, what it proposes, and how things ended. The
-- operator's interface writes exactly one thing — the decision — and reads
-- everything else. There is no service between them; this record is both the
-- channel and the audit trail, so the two cannot disagree about what happened.
-- See adr/0015-the-incident-record-is-the-channel-between-agent-and-operator.md
--
-- The lifecycle is enforced here rather than in the code that writes it. The
-- human approval gate is a state in this table and nothing else, so whatever
-- checks the transition into it decides what the gate is worth. In the schema,
-- an approval can only follow a proposal regardless of what either consumer
-- gets wrong — including rows written by hand, which is how the interface is
-- developed before the agent exists.
-- See adr/0016-enforce-the-incident-lifecycle-in-the-database.md

\connect warehouse_db

-- Its own schema: raw, staging and analytics describe the data's lineage, and
-- an incident is not part of that lineage. public stays unused.
CREATE SCHEMA ops;

COMMENT ON SCHEMA ops IS
    'Operational state for the agent and the operator interface. Not part of the pipeline''s data lineage.';

CREATE TABLE ops.incidents (
    id                      BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Lifecycle. Four of these are terminal; see the transition trigger below.
    state                   TEXT        NOT NULL DEFAULT 'open',

    -- What failed. The agent learns all of this from the orchestrator's API.
    dag_id                  TEXT        NOT NULL,
    failing_run_id          TEXT        NOT NULL,
    failing_task_id         TEXT        NOT NULL,
    failure_output          TEXT,

    -- What the agent made of it.
    diagnosis               TEXT,
    trace_url               TEXT,

    -- The proposed fix, as complete file contents rather than a difference, so
    -- what the operator approves and what gets written cannot diverge. The
    -- difference shown on screen is derived from these two.
    -- See adr/0017-carry-proposed-fixes-as-file-contents.md
    target_model_path       TEXT,
    model_contents_before   TEXT,
    model_contents_after    TEXT,

    -- The run that proved the fix worked, kept apart from the one that failed:
    -- "this broke on run A and was confirmed fixed on run D" is the sentence
    -- the run history wants to be able to say.
    verifying_run_id        TEXT,

    -- Why an incident ended the way it did, when the ending needs explaining.
    -- An agent that gives up owes the operator a reason: 'unfixable' says that
    -- it could not write a working fix and nothing at all about what it could
    -- not fix. Null for endings that speak for themselves.
    conclusion_note         TEXT,

    opened_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    concluded_at            TIMESTAMPTZ,

    CONSTRAINT incident_state_must_be_known CHECK (
        state IN (
            'open',                 -- a failure was noticed
            'proposed',             -- a validated fix awaits a decision
            'approved',             -- the operator said yes
            'resolved',             -- terminal: the pipeline recovered
            'rejected',             -- terminal: the operator declined
            'unfixable',            -- terminal: the agent could not write a working fix
            'verification_failed'   -- terminal: the fix was applied and did not work
        )
    ),

    -- With more than one model in the project, a fix that does not say which
    -- file it applies to is not actionable. Enforced from the moment a proposal
    -- exists; an incident that never got that far is exempt.
    CONSTRAINT a_proposal_names_its_target CHECK (
        state IN ('open', 'unfixable')
        OR (target_model_path IS NOT NULL AND model_contents_after IS NOT NULL)
    ),

    CONSTRAINT a_concluded_incident_has_a_conclusion_time CHECK (
        (state IN ('resolved', 'rejected', 'unfixable', 'verification_failed'))
            = (concluded_at IS NOT NULL)
    )
);

COMMENT ON TABLE ops.incidents IS
    'One row per incident. At most one is in flight at a time; see incidents_only_one_in_flight.';

-- At most one incident that has not reached an outcome.
--
-- Failures are never retried away (ADR-0011), so a persistent fault fails every
-- scheduled run. Without this, a bug could open an incident per failure and
-- which one an approval referred to would be genuinely ambiguous.
--
-- A unique index over a constant expression permits exactly one row matching
-- the predicate.
CREATE UNIQUE INDEX incidents_only_one_in_flight
    ON ops.incidents ((TRUE))
    WHERE state NOT IN ('resolved', 'rejected', 'unfixable', 'verification_failed');

CREATE INDEX incidents_opened_at_idx ON ops.incidents (opened_at DESC);

-- Legal transitions, and nothing else.
CREATE FUNCTION ops.enforce_incident_lifecycle() RETURNS trigger AS $$
BEGIN
    IF NEW.state = OLD.state THEN
        -- Updating a diagnosis or a trace reference without moving the incident
        -- along is ordinary and always allowed.
        RETURN NEW;
    END IF;

    IF OLD.state IN ('resolved', 'rejected', 'unfixable', 'verification_failed') THEN
        RAISE EXCEPTION
            'incident % has already concluded as %, and a concluded incident stays concluded',
            OLD.id, OLD.state
            USING ERRCODE = 'check_violation';
    END IF;

    IF NOT (
        (OLD.state = 'open'     AND NEW.state IN ('proposed', 'unfixable'))
     OR (OLD.state = 'proposed' AND NEW.state IN ('approved', 'rejected'))
     OR (OLD.state = 'approved' AND NEW.state IN ('resolved', 'verification_failed'))
    ) THEN
        RAISE EXCEPTION
            'incident % cannot move from % to %; an approval must follow a proposal',
            OLD.id, OLD.state, NEW.state
            USING ERRCODE = 'check_violation';
    END IF;

    -- Set the conclusion time rather than requiring every writer to remember.
    IF NEW.state IN ('resolved', 'rejected', 'unfixable', 'verification_failed') THEN
        NEW.concluded_at := coalesce(NEW.concluded_at, now());
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER incidents_lifecycle
    BEFORE UPDATE ON ops.incidents
    FOR EACH ROW EXECUTE FUNCTION ops.enforce_incident_lifecycle();

-- An incident always starts at the beginning. Inserting one already approved
-- would walk straight past the gate.
CREATE FUNCTION ops.enforce_incident_starts_open() RETURNS trigger AS $$
BEGIN
    IF NEW.state <> 'open' THEN
        RAISE EXCEPTION
            'an incident must be created in the open state, not %', NEW.state
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER incidents_start_open
    BEFORE INSERT ON ops.incidents
    FOR EACH ROW EXECUTE FUNCTION ops.enforce_incident_starts_open();
