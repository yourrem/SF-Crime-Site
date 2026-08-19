from datetime import datetime, timedelta
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator

PYTHON   = "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
DBT      = "/Library/Frameworks/Python.framework/Versions/3.14/bin/dbt"
PROJECT  = "/Users/yourrem/python_work/SF-Crime-Site"
PIPELINE = f"{PROJECT}/scripts/run_pipeline.py"
DBT_DIR  = f"{PROJECT}/sfcrime_dbt"

default_args = {
    "owner": "sfcrime",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

# ── Daily incidents pipeline + dbt refresh ───────────────────────────────────
with DAG(
    dag_id="sfcrime_incidents_daily",
    description="Fetch SFPD incident reports and refresh dbt analytics models",
    schedule="0 6 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["sfcrime", "incidents", "dbt"],
) as incidents_dag:

    fetch_incidents = BashOperator(
        task_id="fetch_incidents",
        bash_command=f"cd {PROJECT} && {PYTHON} {PIPELINE} incidents",
    )

    run_dbt = BashOperator(
        task_id="run_dbt",
        bash_command=f"cd {DBT_DIR} && {DBT} run",
    )

    fetch_incidents >> run_dbt


# ── Real-time calls pipeline (every 10 minutes) ───────────────────────────────
with DAG(
    dag_id="sfcrime_calls_realtime",
    description="Fetch SFPD real-time calls for service (every 10 min)",
    schedule="*/10 * * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["sfcrime", "calls"],
) as calls_dag:

    BashOperator(
        task_id="fetch_calls",
        bash_command=f"cd {PROJECT} && {PYTHON} {PIPELINE} calls",
    )
