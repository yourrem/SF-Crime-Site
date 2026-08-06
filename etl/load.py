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


def upsert(df: pd.DataFrame, table: str, unique_key: str) -> None:
    """Insert only rows that don't already exist, matched on unique_key."""
    df = df.drop(columns=["point"], errors="ignore")

    temp = f"_{table}_staging"
    with sqlite3.connect(DB_PATH) as conn:
        # Write new records to a staging table
        df.to_sql(temp, conn, if_exists="replace", index=False)

        # Insert rows from staging that aren't already in the main table
        conn.execute(f"""
            INSERT OR IGNORE INTO {table}
            SELECT * FROM {temp}
            WHERE {unique_key} NOT IN (SELECT {unique_key} FROM {table})
        """)
        conn.execute(f"DROP TABLE {temp}")

        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"Upsert complete — {table} now has {count} rows")
