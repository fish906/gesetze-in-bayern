from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import pymysql
import os
import yaml
import logging

logger = logging.getLogger("web")
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s | %(name)s | %(message)s"
)

app = FastAPI(title="BayRecht")

# Paths
_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_dir)

templates = Jinja2Templates(directory=os.path.join(_dir, "templates"))
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
    path = os.path.join(_root, "config.yml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["database"]


def get_connection():
    db_conf = load_db_config()
    return pymysql.connect(
        host=db_conf.get("host", "localhost"),
        user=db_conf["user"],
        password=db_conf["password"],
        database=db_conf["db"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


@app.get("/", response_class=HTMLResponse)
async def law_index(request: Request):
    """Display all available laws."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, description FROM laws ORDER BY name"
            )
            laws = cursor.fetchall()
    finally:
        conn.close()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "laws": laws,
    })


@app.get("/gesetz/{law_name}", response_class=HTMLResponse)
async def law_toc(request: Request, law_name: str):
    """Display table of contents for a specific law."""
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

    return templates.TemplateResponse("toc.html", {
        "request": request,
        "law": law,
        "norms": norms,
    })


@app.get("/gesetz/{law_name}/gesamt", response_class=HTMLResponse)
async def law_full_view(request: Request, law_name: str):
    """Display all norms of a law on a single page."""
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

    return templates.TemplateResponse("full_view.html", {
        "request": request,
        "law": law,
        "norms": norms,
    })


@app.get("/gesetz/{law_name}/{norm_number}", response_class=HTMLResponse)
async def norm_detail(request: Request, law_name: str, norm_number: str):
    """Display the full content of a single norm."""
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

    return templates.TemplateResponse("norm.html", {
        "request": request,
        "law": law,
        "norm": norm,
        "prev_norm": prev_norm,
        "next_norm": next_norm,
        "prev_norms": prev_norms,
        "next_norms": next_norms,
    })