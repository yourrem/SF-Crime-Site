with base as (
    select * from {{ ref('stg_incidents') }}
    where police_district is not null
)

select
    incident_date,
    police_district,
    count(*) as incident_count
from base
group by incident_date, police_district
order by incident_date desc, incident_count desc
