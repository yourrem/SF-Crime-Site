import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
from etl.extract import fetch_incidents
from etl.transform import clean
from etl.load import load


def run(days: int = 7) -> None:
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

    print("\nPipeline complete.")


if __name__ == "__main__":
    run()
