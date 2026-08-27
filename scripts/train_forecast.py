import os
import math
import joblib
import pandas as pd
import numpy as np
from datetime import timedelta
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_URL     = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
ML_DIR     = os.path.join(os.path.dirname(__file__), "..", "ml")
MODEL_PATH = os.path.join(ML_DIR, "forecast_model.pkl")
FORECAST_DAYS = 30
TEST_DAYS     = 90

FEATURE_COLS = ["lag_1", "lag_7", "lag_30", "day_of_week", "month", "year", "is_weekend"]


def build_features(df):
    df = df.sort_values("incident_date").copy()
    df["lag_1"]       = df["incident_count"].shift(1)
    df["lag_7"]       = df["incident_count"].shift(7)
    df["lag_30"]      = df["incident_count"].shift(30)
    dates             = pd.to_datetime(df["incident_date"])
    df["day_of_week"] = dates.dt.dayofweek
    df["month"]       = dates.dt.month
    df["year"]        = dates.dt.year
    df["is_weekend"]  = (df["day_of_week"] >= 5).astype(int)
    return df.dropna()


def main():
    engine = create_engine(DB_URL)

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT incident_date, incident_count
            FROM analytics.daily_trends
            ORDER BY incident_date ASC
        """)).fetchall()

    df = pd.DataFrame(rows, columns=["incident_date", "incident_count"])
    df["incident_date"] = pd.to_datetime(df["incident_date"]).dt.date
    df = build_features(df)

    # Train / test split — last TEST_DAYS held out
    cutoff = df["incident_date"].max() - timedelta(days=TEST_DAYS)
    train  = df[df["incident_date"] <= cutoff]
    test   = df[df["incident_date"] >  cutoff]

    model = Ridge(alpha=1.0)
    model.fit(train[FEATURE_COLS], train["incident_count"])

    preds_test = model.predict(test[FEATURE_COLS])
    mae  = mean_absolute_error(test["incident_count"], preds_test)
    rmse = math.sqrt(mean_squared_error(test["incident_count"], preds_test))

    print(f"Training rows : {len(train)}")
    print(f"Test rows     : {len(test)}")
    print(f"Test MAE      : {mae:.1f}  incidents/day")
    print(f"Test RMSE     : {rmse:.1f}  incidents/day")

    os.makedirs(ML_DIR, exist_ok=True)
    joblib.dump({"model": model, "mae": round(mae, 1), "rmse": round(rmse, 1),
                 "train_rows": len(train), "test_rows": len(test)}, MODEL_PATH)
    print(f"Model saved   → {MODEL_PATH}")

    # Recursive 30-day forward forecast — each predicted value feeds the next day's lags
    history = list(df["incident_count"].values)
    today   = df["incident_date"].max()
    forecast_rows = []

    for i in range(1, FORECAST_DAYS + 1):
        fdate    = today + timedelta(days=i)
        lag_1    = history[-1]
        lag_7    = history[-7]
        lag_30   = history[-30]
        dow      = fdate.weekday()
        X = pd.DataFrame([{
            "lag_1": lag_1, "lag_7": lag_7, "lag_30": lag_30,
            "day_of_week": dow, "month": fdate.month,
            "year": fdate.year, "is_weekend": int(dow >= 5),
        }])
        pred = max(float(model.predict(X)[0]), 0)
        forecast_rows.append({
            "forecast_date":   fdate,
            "predicted_count": round(pred, 1),
            "lower_bound":     round(max(pred - rmse, 0), 1),
            "upper_bound":     round(pred + rmse, 1),
        })
        history.append(pred)

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS analytics.crime_forecast (
                forecast_date   DATE PRIMARY KEY,
                predicted_count FLOAT,
                lower_bound     FLOAT,
                upper_bound     FLOAT,
                created_at      TIMESTAMPTZ DEFAULT now()
            )
        """))
        for row in forecast_rows:
            conn.execute(text("""
                INSERT INTO analytics.crime_forecast
                    (forecast_date, predicted_count, lower_bound, upper_bound)
                VALUES (:forecast_date, :predicted_count, :lower_bound, :upper_bound)
                ON CONFLICT (forecast_date) DO UPDATE SET
                    predicted_count = EXCLUDED.predicted_count,
                    lower_bound     = EXCLUDED.lower_bound,
                    upper_bound     = EXCLUDED.upper_bound,
                    created_at      = now()
            """), row)

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS analytics.forecast_meta (
                id         INT PRIMARY KEY DEFAULT 1,
                mae        FLOAT,
                rmse       FLOAT,
                train_rows INT,
                test_rows  INT,
                trained_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        conn.execute(text("""
            INSERT INTO analytics.forecast_meta (id, mae, rmse, train_rows, test_rows)
            VALUES (1, :mae, :rmse, :train_rows, :test_rows)
            ON CONFLICT (id) DO UPDATE SET
                mae        = EXCLUDED.mae,
                rmse       = EXCLUDED.rmse,
                train_rows = EXCLUDED.train_rows,
                test_rows  = EXCLUDED.test_rows,
                trained_at = now()
        """), {"mae": round(mae, 1), "rmse": round(rmse, 1),
               "train_rows": len(train), "test_rows": len(test)})

    print(f"Forecast written: {forecast_rows[0]['forecast_date']} → {forecast_rows[-1]['forecast_date']}")


if __name__ == "__main__":
    main()
