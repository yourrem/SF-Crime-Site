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
    data_loaded_at

from deduped
where rn = 1
