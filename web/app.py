from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import pymysql
import dotenv
import os
import yaml
import logging
from urllib.parse import quote
import time as _time
import psutil
import json as _json

logger = logging.getLogger("web")
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s | %(name)s | %(message)s"
)

# General settings
API_VERSION = os.environ.get("API_VERSION", "1.0")
app = FastAPI(title="BayRecht", version=API_VERSION, docs_url="/docs", redoc_url= None)
BASE_URL = os.environ.get("BASE_URL", "https://bayrecht.netzsys.de")


_start_time = _time.time()

# Caching
_cache = {}
CACHE_TTL = int(os.environ.get("CACHE_TTL", 3600))  # Cache time-to-live in seconds

def cache_get(key):
    """Get a cached value if it exists and hasn't expired."""
    entry = _cache.get(key)
    if entry and (_time.time() - entry["time"]) < CACHE_TTL:
        return entry["value"]
    return None

def cache_set(key, value):
    """Store a value in cache with current timestamp."""
    _cache[key] = {"value": value, "time": _time.time()}

# Paths
_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_dir)

templates = Jinja2Templates(directory=os.path.join(_dir, "templates"))
templates.env.globals["base_url"] = BASE_URL
app.mount("/static", StaticFiles(directory=os.path.join(_dir, "static")), name="static")


ERROR_MESSAGES = {
    404: {
        "title": "Nicht gefunden",
        "message": "Die angeforderte Seite konnte nicht gefunden werden.",
    },
    500: {
        "title": "Serverfehler",
        "message": "Ein interner Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.",
    },
}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    error = ERROR_MESSAGES.get(exc.status_code, {
        "title": f"Fehler {exc.status_code}",
        "message": exc.detail or "Ein unbekannter Fehler ist aufgetreten.",
    })
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": exc.status_code,
        "title": error["title"],
        "message": error["message"],
    }, status_code=exc.status_code)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    error = ERROR_MESSAGES[500]
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 500,
        "title": error["title"],
        "message": error["message"],
    }, status_code=500)


def load_db_config():
    required_vars = ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]

    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return {
        "host": os.environ["DB_HOST"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "db": os.environ["DB_NAME"],
        "port": int(os.environ.get("DB_PORT", 3306)),
    }

def get_connection():
    db_conf = load_db_config()
    
    return pymysql.connect(
        host=db_conf["host"],
        port=db_conf["port"],
        user=db_conf["user"],
        password=db_conf["password"],
        database=db_conf["db"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon for non-HTML pages."""
    
    path = os.path.join(_dir, "static", "favicon.ico")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/x-icon")
    return Response(status_code=204)

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    # Server metrics
    uptime_seconds = round(_time.time() - _start_time)
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    server = {
        "uptime_seconds": uptime_seconds,
        "cpu_percent": cpu_percent,
        "memory": {
            "total_mb": round(memory.total / 1024 / 1024),
            "used_mb": round(memory.used / 1024 / 1024),
            "percent": memory.percent,
        },
        "disk": {
            "total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
            "used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
            "percent": disk.percent,
        },
    }

    # Database check
    db_status = "connected"
    db_response_ms = None
    try:
        t0 = _time.time()
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        conn.close()
        db_response_ms = round((_time.time() - t0) * 1000, 1)
    except Exception as e:
        logger.error(f"Health check DB failed: {e}")
        db_status = "unreachable"

    status = "ok" if db_status == "connected" else "degraded"
    status_code = 200 if status == "ok" else 503

    result = {
        "api_version": API_VERSION,
        "status": status,
        "database": {
            "status": db_status,
            "response_ms": db_response_ms,
        },
        "server": server,
    }

    return Response(
        content=_json.dumps(result, indent=2),
        status_code=status_code,
        media_type="application/json",
    )


@app.get("/", response_class=HTMLResponse)
async def law_index(request: Request):
    """Display all available laws."""

    cache_key = "law_index"
    cached = cache_get(cache_key)
    if cached:
        return HTMLResponse(cached)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, description FROM laws ORDER BY name"
            )
            laws = cursor.fetchall()
    finally:
        conn.close()

    response = templates.TemplateResponse("index.html", {
        "request": request,
        "laws": laws,
    })
    cache_set(cache_key, response.body.decode("utf-8"))

    return response

@app.get("/gesetz/{law_name}", response_class=HTMLResponse)
async def law_toc(request: Request, law_name: str):
    """Display table of contents for a specific law."""

    cache_key = f"toc_{law_name}"
    cached = cache_get(cache_key)
    if cached:
        return HTMLResponse(cached)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, description FROM laws WHERE name = %s",
                (law_name,)
            )
            law = cursor.fetchone()

            if not law:
                raise HTTPException(status_code=404, detail="Gesetz nicht gefunden")

            cursor.execute(
                """SELECT number, number_raw, title 
                   FROM norms 
                   WHERE law_id = %s AND (is_stale = 0 OR is_stale IS NULL)
                   ORDER BY CAST(number AS UNSIGNED), number""",
                (law["id"],)
            )
            norms = cursor.fetchall()
    finally:
        conn.close()

    response = templates.TemplateResponse("toc.html", {
        "request": request,
        "law": law,
        "norms": norms,
    })  
    cache_set(cache_key, response.body.decode("utf-8"))
    
    return response


@app.get("/gesetz/{law_name}/gesamt", response_class=HTMLResponse)
async def law_full_view(request: Request, law_name: str):
    """Display all norms of a law on a single page."""
    cache_key = f"full_view_{law_name}"
    cached = cache_get(cache_key)
    if cached:
        return HTMLResponse(cached)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, description FROM laws WHERE name = %s",
                (law_name,)
            )
            law = cursor.fetchone()

            if not law:
                raise HTTPException(status_code=404, detail="Gesetz nicht gefunden")

            cursor.execute(
                """SELECT number, number_raw, title, content
                   FROM norms
                   WHERE law_id = %s AND (is_stale = 0 OR is_stale IS NULL)
                   ORDER BY CAST(number AS UNSIGNED), number""",
                (law["id"],)
            )
            norms = cursor.fetchall()
    finally:
        conn.close()

    response = templates.TemplateResponse("full_view.html", {
        "request": request,
        "law": law,
        "norms": norms,
    })
    cache_set(cache_key, response.body.decode("utf-8"))
    
    return response


@app.get("/gesetz/{law_name}/{norm_number}", response_class=HTMLResponse)
async def norm_detail(request: Request, law_name: str, norm_number: str):
    """Display the full content of a single norm."""

    cache_key = f"norm_{law_name}_{norm_number}"
    cached = cache_get(cache_key)
    if cached:
        logger.info(f"Serving norm {law_name} {norm_number} from cache")
        return HTMLResponse(cached)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, description FROM laws WHERE name = %s",
                (law_name,)
            )
            law = cursor.fetchone()

            if not law:
                raise HTTPException(status_code=404, detail="Gesetz nicht gefunden")

            cursor.execute(
                """SELECT number, number_raw, title, content, url
                   FROM norms
                   WHERE law_id = %s AND number = %s""",
                (law["id"], norm_number)
            )
            norm = cursor.fetchone()

            if not norm:
                raise HTTPException(status_code=404, detail="Norm nicht gefunden")

            # Get previous and next norms for navigation
            cursor.execute(
                """SELECT number, title FROM norms
                   WHERE law_id = %s AND (is_stale = 0 OR is_stale IS NULL)
                     AND CAST(number AS UNSIGNED) < CAST(%s AS UNSIGNED)
                      OR (CAST(number AS UNSIGNED) = CAST(%s AS UNSIGNED) AND number < %s)
                   ORDER BY CAST(number AS UNSIGNED) DESC, number DESC
                   LIMIT 1""",
                (law["id"], norm_number, norm_number, norm_number)
            )
            prev_norm = cursor.fetchone()

            cursor.execute(
                """SELECT number, title FROM norms
                   WHERE law_id = %s AND (is_stale = 0 OR is_stale IS NULL)
                     AND (CAST(number AS UNSIGNED) > CAST(%s AS UNSIGNED)
                      OR (CAST(number AS UNSIGNED) = CAST(%s AS UNSIGNED) AND number > %s))
                   ORDER BY CAST(number AS UNSIGNED), number
                   LIMIT 1""",
                (law["id"], norm_number, norm_number, norm_number)
            )
            next_norm = cursor.fetchone()

            # Get surrounding norms for sidebar context
            cursor.execute(
                """(SELECT number, title FROM norms
                    WHERE law_id = %s AND (is_stale = 0 OR is_stale IS NULL)
                      AND (CAST(number AS UNSIGNED) < CAST(%s AS UNSIGNED)
                       OR (CAST(number AS UNSIGNED) = CAST(%s AS UNSIGNED) AND number < %s))
                    ORDER BY CAST(number AS UNSIGNED) DESC, number DESC
                    LIMIT 5)
                   ORDER BY CAST(number AS UNSIGNED), number""",
                (law["id"], norm_number, norm_number, norm_number)
            )
            prev_norms = cursor.fetchall()

            cursor.execute(
                """SELECT number, title FROM norms
                   WHERE law_id = %s AND (is_stale = 0 OR is_stale IS NULL)
                     AND (CAST(number AS UNSIGNED) > CAST(%s AS UNSIGNED)
                      OR (CAST(number AS UNSIGNED) = CAST(%s AS UNSIGNED) AND number > %s))
                   ORDER BY CAST(number AS UNSIGNED), number
                   LIMIT 5""",
                (law["id"], norm_number, norm_number, norm_number)
            )
            next_norms = cursor.fetchall()
    finally:
        conn.close()

    response = templates.TemplateResponse("norm.html", {
        "request": request,
        "law": law,
        "norm": norm,
        "prev_norm": prev_norm,
        "next_norm": next_norm,
        "prev_norms": prev_norms,
        "next_norms": next_norms,
    })
    cache_set(cache_key, response.body.decode("utf-8"))

    return response

@app.get("/sitemap.xml")
async def sitemap():
    """Generate sitemap.xml from database content (cached)."""

    cached = cache_get("sitemap")
    if cached:
        #logger.info("Serving sitemap.xml from cache")
        return Response(content=cached, media_type="application/xml")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name FROM laws ORDER BY name")
            laws = cursor.fetchall()

            cursor.execute(
                """SELECT l.name AS law_name, n.number
                   FROM norms n
                   JOIN laws l ON l.id = n.law_id
                   WHERE n.is_stale = 0 OR n.is_stale IS NULL
                   ORDER BY l.name, CAST(n.number AS UNSIGNED), n.number"""
            )
            norms = cursor.fetchall()
    finally:
        conn.close()

    urls = []

    # Homepage
    urls.append(f"<url><loc>{BASE_URL}/</loc><priority>1.0</priority></url>")

    # Law TOC pages
    for law in laws:
        name = quote(law["name"], safe="")
        urls.append(
            f"<url><loc>{BASE_URL}/gesetz/{name}</loc><priority>0.8</priority></url>"
        )
        urls.append(
            f"<url><loc>{BASE_URL}/gesetz/{name}/gesamt</loc><priority>0.5</priority></url>"
        )

    # Individual norm pages
    for norm in norms:
        name = quote(norm["law_name"], safe="")
        number = quote(str(norm["number"]), safe="")
        urls.append(
            f"<url><loc>{BASE_URL}/gesetz/{name}/{number}</loc><priority>0.6</priority></url>"
        )

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<?xml-stylesheet type="text/xsl" href="/static/sitemap.xsl"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += "\n".join(urls)
    xml += "\n</urlset>"

    cache_set("sitemap", xml)

    return Response(content=xml, media_type="application/xml")


@app.get("/robots.txt")
async def robots():
    """Serve robots.txt."""
    content = f"""User-agent: *
Allow: /

Sitemap: {BASE_URL}/sitemap.xml
"""
    return PlainTextResponse(content)


@app.get("/suche", response_class=HTMLResponse)
async def search(request: Request, q: str = ""):
    """Live search endpoint returning HTML results for HTMX."""
    q = q.strip()
    if len(q) < 2:
        return HTMLResponse("")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Search laws by name or description
            cursor.execute(
                """SELECT name, description FROM laws
                   WHERE name LIKE %s OR description LIKE %s
                   ORDER BY name
                   LIMIT 5""",
                (f"%{q}%", f"%{q}%")
            )
            laws = cursor.fetchall()

            # Search norms by number (match beginning)
            cursor.execute(
                """SELECT l.name AS law_name, l.description AS law_description,
                          n.number, n.title
                   FROM norms n
                   JOIN laws l ON l.id = n.law_id
                   WHERE (n.is_stale = 0 OR n.is_stale IS NULL)
                     AND (n.number LIKE %s OR n.number_raw LIKE %s)
                   ORDER BY l.name, CAST(n.number AS UNSIGNED), n.number
                   LIMIT 10""",
                (f"{q}%", f"%{q}%")
            )
            norms = cursor.fetchall()
    finally:
        conn.close()

    if not laws and not norms:
        return HTMLResponse('<div class="search-empty">Keine Ergebnisse</div>')

    html_parts = []

    if laws:
        html_parts.append('<div class="search-group"><span class="search-group-label">Gesetze</span>')
        for law in laws:
            html_parts.append(
                f'<a href="/gesetz/{law["name"]}/gesamt" class="search-result">'
                f'<span class="search-result-abbr">{law["name"]}</span>'
                f'<span class="search-result-text">{law["description"]}</span>'
                f'</a>'
            )
        html_parts.append('</div>')

    if norms:
        html_parts.append('<div class="search-group"><span class="search-group-label">Normen</span>')
        for norm in norms:
            title = norm["title"] or "(ohne Titel)"
            html_parts.append(
                f'<a href="/gesetz/{norm["law_name"]}/{norm["number"]}" class="search-result">'
                f'<span class="search-result-abbr">{norm["law_name"]} Art. {norm["number"]}</span>'
                f'<span class="search-result-text">{title}</span>'
                f'</a>'
            )
        html_parts.append('</div>')

    return HTMLResponse("\n".join(html_parts))

@app.get("/impressum", response_class=HTMLResponse)
async def impressum(request: Request):
    """Serve impressum page."""
    return templates.TemplateResponse("impressum.html", {"request": request})

@app.get("/datenschutz", response_class=HTMLResponse)
async def datenschutz(request: Request):
    """Serve privacy policy page."""
    return templates.TemplateResponse("privacy.html", {"request": request})