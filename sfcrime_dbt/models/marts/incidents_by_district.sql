WITH base AS (
    SELECT * FROM {{ ref('stg_incidents') }}
    where police_district IS NOT NULL
      AND NOT is_unfounded
      AND NOT is_non_criminal
      AND NOT is_valid_location
)

SELECT
    incident_date,
    police_district,
    COUNT(*) AS incident_count
FROM base
GROUP BY incident_date, police_district
ORDER BY incident_date DESC, incident_count DESC
