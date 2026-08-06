import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
from etl.extract import fetch_incidents, fetch_calls
from etl.transform import clean
from etl.load import load, upsert


def run_incidents(days: int = 7) -> None:
    print("=== Daily Incidents Pipeline ===")

    print("--- Extract ---")
    raw = fetch_incidents(days=days)
    print(f"Fetched {len(raw)} raw records")

    print("\n--- Transform ---")
    df = pd.DataFrame(raw)
    df_clean = clean(df)
    print(f"Cleaned shape: {df_clean.shape}")
    print(f"Rows missing location: {(~df_clean['has_location']).sum()}")

    print("\n--- Load ---")
    load(df_clean)


def run_calls(hours: int = 2) -> None:
    print("=== Real-time Calls Pipeline ===")

    print("--- Extract ---")
    raw = fetch_calls(hours=hours)
    print(f"Fetched {len(raw)} raw records")

    print("\n--- Transform ---")
    df = pd.DataFrame(raw)
    df_clean = clean(df)
    print(f"Cleaned shape: {df_clean.shape}")

    print("\n--- Upsert ---")
    upsert(df_clean, table="calls", unique_key="cad_number")


if __name__ == "__main__":
    run_incidents()
    print()
    run_calls()
    print("\nAll pipelines complete.")
