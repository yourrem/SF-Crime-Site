{{ config(
    materialized='table',
    post_hook=[
        "CREATE INDEX IF NOT EXISTS idx_stg_incidents_date ON {{ this }}(incident_date)",
        "CREATE INDEX IF NOT EXISTS idx_stg_incidents_neighborhood_date ON {{ this }}(analysis_neighborhood, incident_date)",
    ]
) }}

with source as (
    select * from {{ source('public', 'incidents') }}
),

deduped as (
    select *,
        row_number() over (partition by row_id order by data_loaded_at desc) as rn
    from source
)

select
    -- identifiers
    row_id,
    incident_id,
    incident_number,
    cad_number,

    -- timestamps
    incident_datetime,
    incident_date,
    incident_time,
    incident_year,
    incident_day_of_week,
    report_datetime,

    -- classification
    incident_category,
    incident_subcategory,
    incident_code,
    incident_description,
    report_type_code,
    report_type_description,

    -- resolution
    resolution,

    -- location
    police_district,
    analysis_neighborhood,
    supervisor_district,
    intersection,
    latitude,
    longitude,
    has_location,

    -- metadata
    data_as_of,
    data_loaded_at,

    -- data quality flags
    resolution = 'Unfounded'                                        as is_unfounded,
    incident_category = 'Non-Criminal'                              as is_non_criminal,
    (latitude between 37.70 and 37.85
     and longitude between -122.55 and -122.35)                     as is_valid_location

from deduped
where rn = 1
