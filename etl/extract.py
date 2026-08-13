import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

INCIDENTS_ENDPOINT = "https://data.sfgov.org/resource/wg3w-h783.json"
TOKEN = os.getenv("SOCRATA_APP_TOKEN")
PAGE_SIZE = 1000


def fetch_incidents(days=7, start_date=None, end_date=None):
    if start_date:
        since = start_date
    else:
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    headers = {"X-App-Token": TOKEN}
    all_records = []
    offset = 0

    where = f"incident_date >= '{since}'"
    if end_date:
        where += f" AND incident_date <= '{end_date}'"

    while True:
        params = {
            "$select": (
                "row_id,incident_id,incident_number,cad_number,"
                "incident_datetime,incident_date,incident_time,incident_year,"
                "incident_day_of_week,report_datetime,"
                "incident_category,incident_subcategory,incident_code,"
                "incident_description,report_type_code,report_type_description,"
                "resolution,police_district,analysis_neighborhood,"
                "supervisor_district,intersection,latitude,longitude,"
                "data_as_of,data_loaded_at"
            ),
            "$where": where,
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$order": "incident_date DESC",
        }
        response = requests.get(INCIDENTS_ENDPOINT, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        all_records.extend(batch)
        offset += PAGE_SIZE
        print(f"  Fetched {len(all_records)} records so far...")

    return all_records


CALLS_ENDPOINT = "https://data.sfgov.org/resource/gnap-fj3t.json"


def fetch_calls(hours=2):
    since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
    headers = {"X-App-Token": TOKEN}
    all_records = []
    offset = 0

    while True:
        params = {
            "$where": f"received_datetime >= '{since}'",
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$order": "received_datetime DESC",
        }
        response = requests.get(CALLS_ENDPOINT, headers=headers, params=params)
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        all_records.extend(batch)
        offset += PAGE_SIZE
        print(f"  Fetched {len(all_records)} call records so far...")

    return all_records


if __name__ == "__main__":
    print("Pulling last 7 days of incident reports...")
    data = fetch_incidents(days=7)
    print(f"\nDone. Total records: {len(data)}")
    print("\nSample record:")
    print(data[0])
