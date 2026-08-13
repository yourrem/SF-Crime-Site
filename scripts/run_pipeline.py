import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
from etl.extract import fetch_incidents, fetch_calls
from etl.transform import clean_incidents
from etl.load import load, upsert


def run_incidents(days: int = 7) -> None:
    print("=== Daily Incidents Pipeline ===")

    print("--- Extract ---")
    raw = fetch_incidents(days=days)
    print(f"Fetched {len(raw)} raw records")

    print("\n--- Transform ---")
    df = pd.DataFrame(raw)
    df_clean = clean_incidents(df)
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
    df_clean = clean_incidents(df)
    print(f"Cleaned shape: {df_clean.shape}")

    print("\n--- Upsert ---")
    upsert(df_clean, table="calls", unique_key="cad_number")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    if arg == "incidents":
        run_incidents()
    elif arg == "calls":
        run_calls()
    elif arg == "all":
        run_incidents()
        print()
        run_calls()
    else:
        print(f"Unknown argument '{arg}'. Use: incidents, calls, or all")
        sys.exit(1)

    print("\nDone.")
