import os
import sys
import logging
from datetime import date
from pathlib import Path
from logging.handlers import RotatingFileHandler

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).parent.parent / ".env")

from etl.extract import fetch_incidents, fetch_calls
from etl.transform import clean_incidents
from etl.load import upsert

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_PATH = Path(__file__).parent.parent / "logs" / "pipeline.log"
logging.basicConfig(
    handlers=[
        RotatingFileHandler(LOG_PATH, maxBytes=5_000_000, backupCount=3),
        logging.StreamHandler(),
    ],
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────
_engine = create_engine(os.getenv("POSTGRES_URL"))


def _days_since_last_load() -> int:
    """Query MAX(incident_date) from Postgres and return how many days to fetch."""
    with _engine.connect() as conn:
        max_date = conn.execute(
            text("SELECT MAX(incident_date) FROM public.incidents")
        ).scalar()
    if max_date is None:
        return 7
    delta = (date.today() - max_date.date()).days
    return max(delta + 1, 2)  # always at least 2 for the reporting lag


# ── Pipeline functions ────────────────────────────────────────────────────────
def run_incidents() -> None:
    logger.info("=== Daily Incidents Pipeline ===")

    days = _days_since_last_load()
    logger.info(f"Fetching last {days} days (auto-detected from DB max date)")

    logger.info("--- Extract ---")
    raw = fetch_incidents(days=days)
    logger.info(f"Fetched {len(raw)} raw records")

    if not raw:
        logger.info("No new records — skipping load.")
        return

    logger.info("--- Transform ---")
    df = pd.DataFrame(raw)
    df_clean = clean_incidents(df)
    logger.info(f"Cleaned shape: {df_clean.shape}")
    logger.info(f"Rows missing location: {(~df_clean['has_location']).sum()}")

    logger.info("--- Upsert ---")
    upsert(df_clean, table="incidents", unique_key="row_id")

    logger.info("Incidents pipeline complete.")


def run_calls() -> None:
    logger.info("=== Real-time Calls Pipeline ===")

    logger.info("--- Extract ---")
    raw = fetch_calls(hours=2)
    logger.info(f"Fetched {len(raw)} raw records")

    logger.info("--- Transform ---")
    df = pd.DataFrame(raw)
    df_clean = clean_incidents(df)
    logger.info(f"Cleaned shape: {df_clean.shape}")

    logger.info("--- Upsert ---")
    upsert(df_clean, table="calls", unique_key="cad_number")

    logger.info("Calls pipeline complete.")


# ── CLI entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    try:
        if arg == "incidents":
            run_incidents()
        elif arg == "calls":
            run_calls()
        elif arg == "all":
            run_incidents()
            run_calls()
        else:
            logger.error(f"Unknown argument '{arg}'. Use: incidents, calls, or all")
            sys.exit(1)
    except Exception:
        logger.exception("Pipeline failed with unhandled exception")
        sys.exit(1)
