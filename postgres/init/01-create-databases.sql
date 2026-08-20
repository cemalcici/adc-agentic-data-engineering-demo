-- Creates the three databases the stack runs on.
--
-- These are separate DATABASES, not schemas in one database. PostgreSQL cannot
-- query across databases without an extension, and that is the point: the
-- source is meant to represent an upstream system outside the pipeline's
-- control, so the boundary is enforced by the engine rather than by naming
-- convention. See adr/0001-separate-databases-for-source-warehouse-and-orchestrator.md
--
-- The consequence is that the pipeline must physically copy rows from source_db
-- into warehouse_db before transforming them. That copy must be schema-agnostic
-- so an upstream column rename reaches the transformation layer and breaks
-- there, which is what the demo depends on.

-- The simulated upstream system. The drift script mutates this and nothing else.
CREATE DATABASE source_db;
COMMENT ON DATABASE source_db IS
    'Simulated upstream system. Outside the pipeline''s control; only the drift script mutates it.';

-- The pipeline's output. Later also hosts the incidents table (CH5).
CREATE DATABASE warehouse_db;
COMMENT ON DATABASE warehouse_db IS
    'Pipeline output. Starts empty; the dbt model creates its table here (CH2).';

-- Orchestrator metadata, isolated from pipeline data without a second instance.
CREATE DATABASE airflow;
COMMENT ON DATABASE airflow IS
    'Airflow metadata. Kept separate from pipeline data.';
