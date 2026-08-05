import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = "https://data.sfgov.org/resource/wg3w-h783.json"
TOKEN = os.getenv("SOCRATA_APP_TOKEN")
PAGE_SIZE = 1000


def fetch_incidents(days=7):
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    headers = {"X-App-Token": TOKEN}
    all_records = []
    offset = 0

    while True:
        params = {
            "$where": f"incident_date >= '{since}'",
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$order": "incident_date DESC",
        }
        response = requests.get(ENDPOINT, headers=headers, params=params)
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        all_records.extend(batch)
        offset += PAGE_SIZE
        print(f"  Fetched {len(all_records)} records so far...")

    return all_records


if __name__ == "__main__":
    print("Pulling last 7 days of incident reports...")
    data = fetch_incidents(days=7)
    print(f"\nDone. Total records: {len(data)}")
    print("\nSample record:")
    print(data[0])
