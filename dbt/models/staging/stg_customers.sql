-- Staging layer over the landing table.
--
-- Every column is named explicitly. A `select *` here would let an upstream
-- rename flow straight through and produce silently wrong output downstream,
-- which is worse than failing: nothing would alert, and there would be no
-- error for an agent to diagnose.
--
-- Materialised as a view (configured in dbt_project.yml). PostgreSQL resolves
-- column references when the view is created, so a renamed upstream column
-- fails here rather than somewhere further along.

select
    customer_id,
    first_name || ' ' || last_name          as full_name,
    lower(email)                            as email,
    country,
    signup_date,
    extract(year from signup_date)::int     as signup_year,
    is_active
from {{ source('raw', 'customers') }}
