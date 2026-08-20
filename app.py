import os
from flask import Flask, render_template, jsonify, request
from flask_caching import Cache
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
engine = create_engine(os.getenv("POSTGRES_URL"))

cache = Cache(app, config={
    "CACHE_TYPE": "RedisCache",
    "CACHE_REDIS_URL": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "CACHE_DEFAULT_TIMEOUT": 300,
})


@app.route("/")
def index():
    with engine.connect() as conn:
        # KPIs from mart tables
        total_ytd = conn.execute(text("""
            SELECT SUM(incident_count) FROM analytics.daily_trends
            WHERE incident_date >= date_trunc('year', now())
        """)).scalar()

        total_week = conn.execute(text("""
            SELECT SUM(incident_count) FROM analytics.daily_trends
            WHERE incident_date >= now() - interval '7 days'
        """)).scalar()

        top_category = conn.execute(text("""
            SELECT incident_category, SUM(incident_count) as total
            FROM analytics.incidents_by_category
            WHERE incident_date >= now() - interval '30 days'
            GROUP BY incident_category
            ORDER BY total DESC
            LIMIT 1
        """)).fetchone()

        top_district = conn.execute(text("""
            SELECT police_district, SUM(incident_count) as total
            FROM analytics.incidents_by_district
            WHERE incident_date >= now() - interval '30 days'
            GROUP BY police_district
            ORDER BY total DESC
            LIMIT 1
        """)).fetchone()

    kpis = {
        "total_ytd": f"{int(total_ytd or 0):,}",
        "total_week": f"{int(total_week or 0):,}",
        "top_category": top_category[0] if top_category else "N/A",
        "top_district": top_district[0] if top_district else "N/A",
    }
    return render_template("index.html", kpis=kpis)


@app.route("/recent")
def recent():
    with engine.connect() as conn:
        incidents = conn.execute(text("""
            SELECT
                incident_datetime,
                incident_category,
                incident_description,
                analysis_neighborhood,
                police_district,
                resolution
            FROM public.incidents
            WHERE incident_datetime IS NOT NULL
            ORDER BY incident_datetime DESC
            LIMIT 10
        """)).fetchall()

        calls = conn.execute(text("""
            SELECT
                received_datetime,
                call_type_final_desc,
                analysis_neighborhood,
                police_district,
                priority_final,
                disposition
            FROM public.calls
            WHERE received_datetime IS NOT NULL
            ORDER BY received_datetime DESC
            LIMIT 10
        """)).fetchall()

    return render_template("recent.html", incidents=incidents, calls=calls)


@app.route("/trends")
def trends():
    return render_template("trends.html")


@app.route("/api/trends")
def api_trends():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                to_char(incident_date, 'YYYY-MM-DD') AS date,
                incident_count,
                rolling_7day_avg
            FROM analytics.daily_trends
            WHERE incident_date >= now() - interval '90 days'
            ORDER BY incident_date ASC
        """)).fetchall()
    return jsonify([
        {"date": r[0], "count": r[1], "avg": float(r[2])}
        for r in rows
    ])


@app.route("/district")
def district():
    return render_template("district.html")


@app.route("/category")
def category():
    return render_template("category.html")


@app.route("/api/categories")
@cache.cached(query_string=True)
def api_categories():
    start = request.args.get("start")
    end   = request.args.get("end")
    limit = request.args.get("limit", "15")
    limit_clause = f"LIMIT {int(limit)}" if limit.isdigit() else ""
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT incident_category, COUNT(*) AS total
            FROM analytics.stg_incidents
            WHERE incident_date BETWEEN :start AND :end
              AND incident_category IS NOT NULL
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY incident_category
            ORDER BY total DESC
            {limit_clause}
        """), {"start": start, "end": end}).fetchall()
    return jsonify([{"category": r[0], "total": r[1]} for r in rows])


@app.route("/api/category/time")
@cache.cached(query_string=True)
def api_category_time():
    category  = request.args.get("category")
    granularity = request.args.get("granularity", "hour")
    start = request.args.get("start")
    end   = request.args.get("end")

    # Use incident_datetime (when it happened), fall back to report_datetime if null
    time_col = "COALESCE(incident_datetime, report_datetime)"

    queries = {
        "hour": f"""
            SELECT EXTRACT(HOUR FROM {time_col})::int AS bucket,
                   to_char({time_col}, 'HH24') || chr(58) || '00' AS label,
                   COUNT(*) AS total
            FROM analytics.stg_incidents
            WHERE incident_category = :category
              AND incident_date BETWEEN :start AND :end
              AND {time_col} IS NOT NULL
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY bucket, label ORDER BY bucket
        """,
        "dow": """
            SELECT EXTRACT(DOW FROM incident_date)::int AS bucket,
                   to_char(incident_date, 'Dy') AS label,
                   COUNT(*) AS total
            FROM analytics.stg_incidents
            WHERE incident_category = :category
              AND incident_date BETWEEN :start AND :end
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY bucket, label ORDER BY bucket
        """,
        "month": """
            SELECT EXTRACT(MONTH FROM incident_date)::int AS bucket,
                   to_char(incident_date, 'Mon') AS label,
                   COUNT(*) AS total
            FROM analytics.stg_incidents
            WHERE incident_category = :category
              AND incident_date BETWEEN :start AND :end
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY bucket, label ORDER BY bucket
        """,
        "year": """
            SELECT EXTRACT(YEAR FROM incident_date)::int AS bucket,
                   EXTRACT(YEAR FROM incident_date)::text AS label,
                   COUNT(*) AS total
            FROM analytics.stg_incidents
            WHERE incident_category = :category
              AND incident_date BETWEEN :start AND :end
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY bucket, label ORDER BY bucket
        """,
    }

    sql = queries.get(granularity, queries["hour"])
    with engine.connect() as conn:
        rows = conn.execute(text(sql),
            {"category": category, "start": start, "end": end}).fetchall()
    return jsonify([{"label": r[1], "total": r[2]} for r in rows])


@app.route("/api/districts/summary")
def api_districts_summary():
    days = request.args.get("days", 30, type=int)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT police_district, COUNT(*) AS total
            FROM analytics.stg_incidents
            WHERE incident_date >= now() - interval ':days days'
              AND police_district IS NOT NULL
              AND police_district != 'Out Of Sf'
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY police_district
            ORDER BY total DESC
        """.replace(":days days", f"{days} days"))).fetchall()
    return jsonify([{"district": r[0], "total": r[1]} for r in rows])


@app.route("/api/neighborhoods")
@cache.cached(query_string=True)
def api_neighborhoods():
    start = request.args.get("start")
    end   = request.args.get("end")
    limit = request.args.get("limit", "15")
    limit_clause = f"LIMIT {int(limit)}" if limit.isdigit() else ""
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT analysis_neighborhood, COUNT(*) AS total
            FROM analytics.stg_incidents
            WHERE incident_date BETWEEN :start AND :end
              AND analysis_neighborhood IS NOT NULL
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY analysis_neighborhood
            ORDER BY total DESC
            {limit_clause}
        """), {"start": start, "end": end}).fetchall()
    return jsonify([{"neighborhood": r[0], "total": r[1]} for r in rows])


@app.route("/api/neighborhood/categories")
@cache.cached(query_string=True)
def api_neighborhood_categories():
    neighborhood = request.args.get("neighborhood")
    start = request.args.get("start")
    end   = request.args.get("end")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT incident_category, COUNT(*) AS total
            FROM analytics.stg_incidents
            WHERE analysis_neighborhood = :neighborhood
              AND incident_date BETWEEN :start AND :end
              AND incident_category IS NOT NULL
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY incident_category
            ORDER BY total DESC
            LIMIT 8
        """), {"neighborhood": neighborhood, "start": start, "end": end}).fetchall()
    return jsonify([{"category": r[0], "total": r[1]} for r in rows])


@app.route("/api/neighborhood/time")
@cache.cached(query_string=True)
def api_neighborhood_time():
    neighborhood  = request.args.get("neighborhood")
    granularity   = request.args.get("granularity", "hour")
    start = request.args.get("start")
    end   = request.args.get("end")

    queries = {
        "hour": """
            SELECT EXTRACT(HOUR FROM incident_datetime)::int AS bucket,
                   to_char(incident_datetime, 'HH24') || chr(58) || '00' AS label,
                   COUNT(*) AS total
            FROM analytics.stg_incidents
            WHERE analysis_neighborhood = :neighborhood
              AND incident_date BETWEEN :start AND :end
              AND incident_datetime IS NOT NULL
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY bucket, label ORDER BY bucket
        """,
        "dow": """
            SELECT EXTRACT(DOW FROM incident_date)::int AS bucket,
                   to_char(incident_date, 'Dy') AS label,
                   COUNT(*) AS total
            FROM analytics.stg_incidents
            WHERE analysis_neighborhood = :neighborhood
              AND incident_date BETWEEN :start AND :end
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY bucket, label ORDER BY bucket
        """,
        "month": """
            SELECT EXTRACT(MONTH FROM incident_date)::int AS bucket,
                   to_char(incident_date, 'Mon') AS label,
                   COUNT(*) AS total
            FROM analytics.stg_incidents
            WHERE analysis_neighborhood = :neighborhood
              AND incident_date BETWEEN :start AND :end
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY bucket, label ORDER BY bucket
        """,
        "year": """
            SELECT EXTRACT(YEAR FROM incident_date)::int AS bucket,
                   EXTRACT(YEAR FROM incident_date)::text AS label,
                   COUNT(*) AS total
            FROM analytics.stg_incidents
            WHERE analysis_neighborhood = :neighborhood
              AND incident_date BETWEEN :start AND :end
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY bucket, label ORDER BY bucket
        """,
    }

    sql = queries.get(granularity, queries["hour"])
    with engine.connect() as conn:
        rows = conn.execute(text(sql),
            {"neighborhood": neighborhood, "start": start, "end": end}).fetchall()
    return jsonify([{"label": r[1], "total": r[2]} for r in rows])


@app.route("/api/districts/trends")
@cache.cached(query_string=True)
def api_districts_trends():
    days = request.args.get("days", 60, type=int)
    with engine.connect() as conn:
        # Get top 5 districts for the period first
        top = conn.execute(text("""
            SELECT police_district
            FROM analytics.stg_incidents
            WHERE incident_date >= now() - interval ':days days'
              AND police_district IS NOT NULL
              AND police_district != 'Out Of Sf'
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY police_district
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """.replace(":days days", f"{days} days"))).scalars().all()

        rows = conn.execute(text("""
            SELECT to_char(incident_date, 'YYYY-MM-DD') AS date,
                   police_district,
                   COUNT(*) AS total
            FROM analytics.stg_incidents
            WHERE incident_date >= now() - interval ':days days'
              AND police_district = ANY(:districts)
              AND NOT is_unfounded AND NOT is_non_criminal AND is_valid_location
            GROUP BY date, police_district
            ORDER BY date
        """.replace(":days days", f"{days} days")), {"districts": list(top)}).fetchall()

    # Pivot into {dates, series} structure for Chart.js
    from collections import defaultdict
    date_set = sorted({r[0] for r in rows})
    by_district = defaultdict(dict)
    for date, district, total in rows:
        by_district[district][date] = total

    series = [
        {"district": d, "data": [by_district[d].get(date, 0) for date in date_set]}
        for d in top
    ]
    return jsonify({"dates": date_set, "series": series})


@app.route("/api/monthly")
def api_monthly():
    year = request.args.get("year", 2026, type=int)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                EXTRACT(MONTH FROM incident_date)::int AS month,
                to_char(incident_date, 'Mon')          AS month_name,
                SUM(incident_count)::int               AS total
            FROM analytics.daily_trends
            WHERE EXTRACT(YEAR FROM incident_date) = :year
            GROUP BY month, month_name
            ORDER BY month
        """), {"year": year}).fetchall()
        years = conn.execute(text("""
            SELECT DISTINCT EXTRACT(YEAR FROM incident_date)::int AS yr
            FROM analytics.daily_trends
            ORDER BY yr
        """)).scalars().all()
    return jsonify({
        "months": [{"month": r[0], "label": r[1], "total": r[2]} for r in rows],
        "years": years,
    })


@app.route("/api/quarterly")
def api_quarterly():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                EXTRACT(YEAR FROM incident_date)::int    AS yr,
                EXTRACT(QUARTER FROM incident_date)::int AS qtr,
                SUM(incident_count)::int                 AS total
            FROM analytics.daily_trends
            GROUP BY yr, qtr
            ORDER BY yr, qtr
        """)).fetchall()
    return jsonify([
        {"label": f"Q{r[1]} '{str(r[0])[2:]}", "total": r[2]}
        for r in rows
    ])


@app.route("/api/heatmap")
def heatmap():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT latitude, longitude
            FROM public.incidents
            WHERE incident_date >= now() - interval '30 days'
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            LIMIT 5000
        """)).fetchall()
    points = [[float(r[0]), float(r[1])] for r in rows]
    return jsonify(points)


if __name__ == "__main__":
    app.run(debug=True)
