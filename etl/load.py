import os
from dotenv import load_dotenv

import pandas as pd
from sqlalchemy import create_engine, text

load_dotenv()

ENGINE = create_engine(os.getenv("POSTGRES_URL"))


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    # Drop dict-valued columns — Postgres can store them as JSONB but keep it simple for now
    dict_cols = [c for c in df.columns if df[c].apply(lambda x: isinstance(x, dict)).any()]
    if dict_cols:
        print(f"  Dropping dict-valued columns: {dict_cols}")
    df = df.drop(columns=dict_cols)

    # Drop columns with empty or whitespace-only names
    bad_cols = [c for c in df.columns if not str(c).strip()]
    if bad_cols:
        print(f"  Dropping unnamed columns: {bad_cols}")
    df = df.drop(columns=bad_cols)

    # Sanitize column names
    df.columns = [str(c).strip().replace(" ", "_").replace("-", "_") for c in df.columns]

    return df


def load(df: pd.DataFrame, table: str = "incidents") -> None:
    df = _prepare(df)

    with ENGINE.begin() as conn:
        df.to_sql(table, conn, if_exists="replace", index=False)
        count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        print(f"Loaded {count} rows into '{table}' table")


def upsert(df: pd.DataFrame, table: str, unique_key: str) -> None:
    df = _prepare(df)

    temp = f"_{table}_staging"
    with ENGINE.begin() as conn:
        table_exists = conn.execute(text(
            f"SELECT to_regclass('{table}')"
        )).scalar()

        # First run — no table yet, just load directly
        if not table_exists:
            df.to_sql(table, conn, if_exists="replace", index=False)
        else:
            df.to_sql(temp, conn, if_exists="replace", index=False)

            # Get shared columns to avoid mismatch errors
            result = conn.execute(text(
                f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}'"
            ))
            existing_cols = {row[0] for row in result}
            shared_cols = [c for c in df.columns if c in existing_cols]
            cols_sql = ", ".join(shared_cols)

            conn.execute(text(f"""
                INSERT INTO {table} ({cols_sql})
                SELECT {cols_sql} FROM {temp}
                WHERE {unique_key} NOT IN (SELECT {unique_key} FROM {table})
                ON CONFLICT DO NOTHING
            """))
            conn.execute(text(f"DROP TABLE {temp}"))

        count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        print(f"Upsert complete — {table} now has {count} rows")
