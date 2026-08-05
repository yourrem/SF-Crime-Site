import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "sfcrime.db"


def load(df: pd.DataFrame, table: str = "incidents") -> None:
    # SQLite can't store dict-valued columns — drop 'point' since lat/long already capture it
    df = df.drop(columns=["point"], errors="ignore")

    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql(table, conn, if_exists="replace", index=False)
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"Loaded {count} rows into '{table}' table")
