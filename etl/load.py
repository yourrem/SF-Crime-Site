import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "sfcrime.db"


def _drop_dict_columns(df: pd.DataFrame) -> pd.DataFrame:
    dict_cols = [c for c in df.columns if df[c].apply(lambda x: isinstance(x, dict)).any()]
    if dict_cols:
        print(f"  Dropping dict-valued columns (unsupported by SQLite): {dict_cols}")
    return df.drop(columns=dict_cols)


def load(df: pd.DataFrame, table: str = "incidents") -> None:
    df = _drop_dict_columns(df)

    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql(table, conn, if_exists="replace", index=False)
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"Loaded {count} rows into '{table}' table")


def upsert(df: pd.DataFrame, table: str, unique_key: str) -> None:
    """Insert only rows that don't already exist, matched on unique_key."""
    df = _drop_dict_columns(df)

    temp = f"_{table}_staging"
    with sqlite3.connect(DB_PATH) as conn:
        table_exists = conn.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
        ).fetchone()

        # First run — no table yet, just load directly
        if not table_exists:
            df.to_sql(table, conn, if_exists="replace", index=False)
        else:
            df.to_sql(temp, conn, if_exists="replace", index=False)

            # Use only columns that exist in both tables to avoid mismatch errors
            existing_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            shared_cols = [c for c in df.columns if c in existing_cols]
            cols_sql = ", ".join(shared_cols)

            conn.execute(f"""
                INSERT OR IGNORE INTO {table} ({cols_sql})
                SELECT {cols_sql} FROM {temp}
                WHERE {unique_key} NOT IN (SELECT {unique_key} FROM {table})
            """)
            conn.execute(f"DROP TABLE {temp}")

        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"Upsert complete — {table} now has {count} rows")
