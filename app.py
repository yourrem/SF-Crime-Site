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


@app.route("/api/districts")
def districts():
    with engine.connect() as conn:
        # Build district polygons from incident points using PostGIS concave hulls
        rows = conn.execute(text("""
            SELECT
                d.police_district,
                d.total,
                ST_AsGeoJSON(ST_ConcaveHull(ST_Collect(ST_MakePoint(i.longitude, i.latitude)), 0.8)) AS geometry
            FROM (
                SELECT police_district, SUM(incident_count) as total
                FROM analytics.incidents_by_district
                WHERE incident_date >= now() - interval '30 days'
                GROUP BY police_district
            ) d
            JOIN public.incidents i
                ON i.police_district = d.police_district
               AND i.latitude IS NOT NULL
               AND i.longitude IS NOT NULL
            GROUP BY d.police_district, d.total
        """)).fetchall()

    features = []
    for r in rows:
        if r[2]:
            features.append({
                "type": "Feature",
                "properties": {
                    "district": r[0],
                    "total": int(r[1])
                },
                "geometry": __import__('json').loads(r[2])
            })

    return jsonify({"type": "FeatureCollection", "features": features})


if __name__ == "__main__":
    app.run(debug=True)
