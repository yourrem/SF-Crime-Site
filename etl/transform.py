import pandas as pd


def clean_incidents(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Drop columns with no analytical value
    df = df.drop(columns=["filed_online"], errors="ignore")

    # Parse date/time columns
    for col in ["incident_datetime", "incident_date", "report_datetime"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Coerce numeric columns
    for col in ["latitude", "longitude"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Flag rows missing location data for later investigation
    has_location_cols = {"latitude", "longitude", "analysis_neighborhood"} & set(df.columns)
    if has_location_cols:
        df["has_location"] = df[list(has_location_cols)].notnull().all(axis=1)

    # Standardize string columns
    str_cols = ["incident_category", "incident_subcategory", "resolution",
                "police_district", "analysis_neighborhood"]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].str.strip().str.title()

    # Remove duplicates on unique key (drop_duplicates() fails on dict-valued columns like 'point')
    key_col = next((c for c in ["row_id", "incident_id"] if c in df.columns), None)
    if key_col:
        df = df.drop_duplicates(subset=[key_col])

    return df
