-- Defines the upstream customers table.
--
-- Column names are deliberately ordinary. The whole demo rests on an audience
-- believing that a real upstream system renamed a real column, so nothing here
-- may read as a placeholder.
--
-- customer_id is the column CH4's drift script renames to cust_id. Everything
-- downstream — the extract, the dbt model, the agent's diagnosis — is built
-- around that rename, so this column's original name matters.

\connect source_db

CREATE TABLE customers (
    customer_id BIGINT      PRIMARY KEY,
    first_name  TEXT        NOT NULL,
    last_name   TEXT        NOT NULL,
    email       TEXT        NOT NULL,
    country     TEXT        NOT NULL,
    signup_date DATE        NOT NULL,
    is_active   BOOLEAN     NOT NULL
);

COMMENT ON TABLE customers IS
    'Upstream customer records. Populated by the seeder service, not by this script.';
COMMENT ON COLUMN customers.customer_id IS
    'Primary key. CH4 renames this to cust_id to trigger the drift scenario.';

CREATE INDEX customers_country_idx ON customers (country);
CREATE INDEX customers_signup_date_idx ON customers (signup_date);
