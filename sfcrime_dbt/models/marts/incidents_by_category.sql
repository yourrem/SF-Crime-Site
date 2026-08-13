with base as (
    select * from {{ ref('stg_incidents') }}
    where incident_category is not null
      and not is_unfounded
      and not is_non_criminal
      and is_valid_location
)

select
    incident_date,
    incident_category,
    count(*) as incident_count
from base
group by incident_date, incident_category
order by incident_date desc, incident_count desc
