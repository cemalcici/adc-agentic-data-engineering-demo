-- Customer dimension: the pipeline's output.
--
-- Materialised as a table (configured in dbt_project.yml) so that "the
-- warehouse holds output" is answerable by querying it. Built from the staging
-- model rather than the landing table, so only one model reads the source and
-- a failure upstream leaves this one reported as skipped.
--
-- One row per landing row; this layer labels rather than filters.

select
    customer_id,
    full_name,
    email,
    country,
    signup_date,
    signup_year,
    is_active,
    case when is_active then 'active' else 'churned' end as customer_status
from {{ ref('stg_customers') }}
