import os
from flask import Flask, render_template, jsonify
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
engine = create_engine(os.getenv("POSTGRES_URL"))


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
