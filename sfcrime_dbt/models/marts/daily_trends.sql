with daily as (
    select
        incident_date,
        count(*) as incident_count
    from {{ ref('stg_incidents') }}
    where not is_unfounded
      and not is_non_criminal
      and is_valid_location
    group by incident_date
)

select
    incident_date,
    incident_count,
    round(avg(incident_count) over (
        order by incident_date
        rows between 6 preceding and current row
    ), 1) as rolling_7day_avg
from daily
order by incident_date desc
