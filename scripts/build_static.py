#!/usr/bin/env python3
"""Build a fully static snapshot of the site into docs/ for GitHub Pages.

Usage:
    python3 scripts/build_static.py

Captures every page and every UI-reachable API response through the Flask
test client, rewrites the pages to work from static files, and injects a
fetch shim that maps /api/... calls to pre-generated JSON under docs/api/.
Re-running wipes and regenerates docs/ from the current database state.

Publish: commit docs/, then GitHub Settings -> Pages -> main branch /docs.
"""
import json
import os
import re
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPO_URL = "https://github.com/yourrem/SF-Crime-Site"

# Force the SimpleCache fallback before app import (load_dotenv won't override).
os.environ["REDIS_URL"] = ""
sys.path.insert(0, str(ROOT))
from app import app  # noqa: E402

client = app.test_client()
stats = {"files": 0, "bytes": 0}

PAGES = {
    "/": "index.html",
    "/district": "district.html",
    "/category": "category.html",
    "/trends": "trends.html",
    "/forecast": "forecast.html",
    "/recent": "recent.html",
    "/clusters": "clusters.html",
}

# ── Filename mapping (must stay in sync with the JS shim below) ──────────


def sanitize(s: str) -> str:
    """[A-Za-z0-9-] passes through; every other char -> _XX per UTF-8 byte.

    Injective: '_' only ever appears as the start of an _XX block, so the
    '__' pair delimiter and '-' key/value delimiter can't be forged by data.
    """
    out = []
    for c in s:
        if c.isascii() and (c.isalnum() or c == "-"):
            out.append(c)
        else:
            out.append("".join(f"_{b:02X}" for b in c.encode("utf-8")))
    return "".join(out)


def api_key(path: str, params: dict) -> str:
    endpoint = path[len("/api/"):].replace("/", "_")
    if not params:
        return endpoint
    pairs = [f"{sanitize(k)}-{sanitize(v)}" for k, v in sorted(params.items())]
    return endpoint + "__" + "__".join(pairs)


def snap(path: str, params: dict | None = None):
    """GET an API route via test client, write docs/api/<key>.json, return parsed JSON."""
    params = {k: str(v) for k, v in (params or {}).items()}
    resp = client.get(path, query_string=params)
    if resp.status_code != 200:
        raise SystemExit(f"FAILED {path} {params}: HTTP {resp.status_code}")
    out = DOCS / "api" / f"{api_key(path, params)}.json"
    out.write_bytes(resp.data)
    stats["files"] += 1
    stats["bytes"] += len(resp.data)
    return json.loads(resp.data)


# ── Injected assets ──────────────────────────────────────────────────────

SHIM_JS = """<script>
(function () {
    var MIN_YEAR = __MIN_YEAR__, MAX_YEAR = __MAX_YEAR__;
    var origFetch = window.fetch.bind(window);
    function sanitize(s) {
        var out = '', enc = new TextEncoder();
        for (var ch of s) {
            if (/^[A-Za-z0-9-]$/.test(ch)) { out += ch; continue; }
            var bytes = enc.encode(ch);
            for (var i = 0; i < bytes.length; i++) {
                out += '_' + bytes[i].toString(16).toUpperCase().padStart(2, '0');
            }
        }
        return out;
    }
    window.fetch = function (input, init) {
        var raw = (typeof input === 'string') ? input : (input && input.url) || '';
        if (raw.indexOf('/api/') !== 0) return origFetch(input, init);
        var u = new URL(raw, window.location.origin);
        var endpoint = u.pathname.slice(5).replace(/\\//g, '_');
        var pairs = Array.from(u.searchParams.entries());
        if (endpoint === 'monthly') {
            pairs = pairs.map(function (p) {
                if (p[0] !== 'year') return p;
                return ['year', String(Math.min(Math.max(+p[1], MIN_YEAR), MAX_YEAR))];
            });
        }
        pairs.sort(function (a, b) { return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0; });
        var name = endpoint + (pairs.length
            ? '__' + pairs.map(function (p) { return sanitize(p[0]) + '-' + sanitize(p[1]); }).join('__')
            : '');
        return origFetch('api/' + name + '.json').then(function (r) {
            if (r.ok) return r;
            var body = (endpoint === 'monthly') ? '{"months":[],"years":[]}' : '[]';
            return new Response(body, { status: 200, headers: { 'Content-Type': 'application/json' } });
        });
    };
})();
</script>"""

BANNER_CSS = """<style>
.static-banner {
    background: #111;
    color: #cfc8ba;
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    text-align: center;
    padding: 0.5rem 1rem;
    letter-spacing: 0.3px;
    line-height: 1.5;
}
.static-banner .tag {
    color: #111;
    background: #c4952e;
    font-weight: 500;
    padding: 1px 7px;
    margin-right: 8px;
    letter-spacing: 1px;
    text-transform: uppercase;
    font-size: 0.62rem;
}
.static-banner a { color: #e0b354; text-decoration: underline; text-underline-offset: 2px; }
#customBtn, #customWrap { display: none !important; }
</style>"""

BANNER_HTML = (
    '<div class="static-banner"><span class="tag">Portfolio demo</span>'
    'Snapshot of the live app as of __DATA_DATE__ &mdash; every chart, map, and filter '
    'works, served by pre-rendered API responses. The full data pipeline '
    '(Airflow &middot; dbt &middot; Postgres &middot; scikit-learn) and source are on '
    f'<a href="{REPO_URL}">GitHub</a>.</div>'
)


# ── HTML capture & rewrite ───────────────────────────────────────────────


def replace_assert(html: str, old: str, new: str, page: str) -> str:
    if old not in html:
        raise SystemExit(f"[{page}] rewrite anchor not found: {old!r}")
    return html.replace(old, new)


def build_pages(latest: date, min_year: int, max_year: int):
    shim = SHIM_JS.replace("__MIN_YEAR__", str(min_year)).replace("__MAX_YEAR__", str(max_year))
    banner = BANNER_HTML.replace("__DATA_DATE__", latest.strftime("%B %-d, %Y"))
    masthead_date = latest.strftime("%A, %B %-d, %Y")

    for route, filename in PAGES.items():
        resp = client.get(route)
        if resp.status_code != 200:
            raise SystemExit(f"FAILED page {route}: HTTP {resp.status_code}")
        html = resp.get_data(as_text=True)

        html = replace_assert(html, 'href="/static/style.css"', 'href="static/style.css"', filename)
        for page_route, page_file in PAGES.items():
            if page_route == "/":
                continue
            html = replace_assert(html, f'href="{page_route}"', f'href="{page_file}"', filename)
        html = replace_assert(html, 'href="/"', 'href="index.html"', filename)

        html = replace_assert(html, "</head>", BANNER_CSS + "\n</head>", filename)
        html = replace_assert(html, "<body>", "<body>\n" + shim + "\n" + banner, filename)

        # Freeze the masthead date to the data snapshot date for coherence.
        html, n = re.subn(
            r'(<span class="masthead-date">)[^<]*(</span>)',
            rf"\g<1>{masthead_date}\g<2>",
            html,
        )
        if n != 1:
            raise SystemExit(f"[{filename}] masthead date rewrite matched {n} times")

        if filename in ("district.html", "category.html"):
            html = replace_assert(
                html,
                '<div class="custom-wrap" id="customWrap">',
                '<span class="hint-text">Preset ranges only in this snapshot</span>'
                '<div class="custom-wrap" id="customWrap">',
                filename,
            )

        if filename == "trends.html":
            html = replace_assert(
                html,
                "loadMonthly(new Date().getFullYear());",
                f"loadMonthly({max_year});",
                filename,
            )

        (DOCS / filename).write_text(html, encoding="utf-8")
        print(f"  page  {filename}")


# ── API snapshot enumeration ─────────────────────────────────────────────


def iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def build_api(latest: date, years: list[int]):
    # Presets mirror the client math in district/category pages: the JS
    # anchors maxDate at local noon of latest_date, so calendar arithmetic
    # here produces byte-identical start/end strings.
    ranges = [(iso(latest - timedelta(days=n)), iso(latest)) for n in (1, 7, 30, 90)]
    ranges.append((f"{latest.year}-01-01", iso(latest)))

    print("  singles")
    snap("/api/trends")
    snap("/api/forecast")
    snap("/api/quarterly")
    for y in years:
        snap("/api/monthly", {"year": y})

    print("  maps & clusters")
    for d in (7, 30, 90):
        snap("/api/map-incidents", {"days": d})
    for d in (30, 60, 90):
        snap("/api/districts/trends", {"days": d})
    for d in (30, 90, 365):
        snap("/api/neighborhood-clusters", {"days": d})
        for k in (5, 10, 15, 20):
            snap("/api/crime-clusters", {"days": d, "k": k})

    for start, end in ranges:
        se = {"start": start, "end": end}
        print(f"  range {start}..{end}")
        snap("/api/neighborhoods", {**se, "limit": "15"})
        for row in snap("/api/neighborhoods", {**se, "limit": "all"}):
            nb = row["neighborhood"]
            snap("/api/neighborhood/categories", {"neighborhood": nb, **se})
            for g in ("hour", "dow", "month", "year"):
                snap("/api/neighborhood/time", {"neighborhood": nb, "granularity": g, **se})
        snap("/api/categories", {**se, "limit": "15"})
        for row in snap("/api/categories", {**se, "limit": "all"}):
            for g in ("hour", "dow", "month", "year"):
                snap("/api/category/time", {"category": row["category"], "granularity": g, **se})


# ── Orchestration ────────────────────────────────────────────────────────


def main():
    if DOCS.exists():
        shutil.rmtree(DOCS)
    (DOCS / "api").mkdir(parents=True)
    shutil.copytree(ROOT / "static", DOCS / "static")
    (DOCS / ".nojekyll").touch()

    latest_raw = snap("/api/latest-date")["latest_date"]
    if not latest_raw:
        raise SystemExit("No data: /api/latest-date returned null")
    latest = date.fromisoformat(latest_raw)

    years = snap("/api/monthly", {"year": latest.year})["years"]
    if not years:
        raise SystemExit("No data: /api/monthly returned no years")

    print(f"Snapshot anchored to {latest} (years {min(years)}-{max(years)})")
    print("Rendering pages...")
    build_pages(latest, min(years), max(years))
    print("Snapshotting API...")
    build_api(latest, years)

    print(
        f"\nDone: {stats['files']} JSON files, {stats['bytes'] / 1e6:.1f} MB "
        f"-> {DOCS.relative_to(ROOT)}/"
    )
    print("Preview:  python3 -m http.server 8080 --directory docs")


if __name__ == "__main__":
    main()
