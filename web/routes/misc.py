import json as _json
import time as _time
from urllib.parse import quote

import psutil
from flask import Blueprint, current_app, make_response, render_template, send_from_directory
from sqlalchemy import Integer, cast, or_, text

from ..cache import cache_get, cache_set
from ..extensions import db
from models import Law, Norm

misc_bp = Blueprint("misc", __name__)


@misc_bp.route("/favicon.ico")
def favicon():
    return send_from_directory(current_app.static_folder, "favicon.ico", mimetype="image/x-icon")


@misc_bp.route("/health")
def health_check():
    uptime = round(_time.time() - current_app.config["START_TIME"])
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    db_status = "connected"
    db_response_ms = None
    try:
        t0 = _time.time()
        db.session.execute(text("SELECT 1"))
        db_response_ms = round((_time.time() - t0) * 1000, 1)
    except Exception as e:
        current_app.logger.error(f"Health check DB failed: {e}")
        db_status = "unreachable"

    status = "ok" if db_status == "connected" else "degraded"
    result = {
        "api_version": current_app.config["API_VERSION"],
        "status": status,
        "database": {"status": db_status, "response_ms": db_response_ms},
        "server": {
            "uptime_seconds": uptime,
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
        },
    }
    return make_response(_json.dumps(result, indent=2), 200 if status == "ok" else 503, {"Content-Type": "application/json"})


@misc_bp.route("/sitemap.xml")
def sitemap():
    cached = cache_get("sitemap")
    if cached:
        return make_response(cached, 200, {"Content-Type": "application/xml"})

    base_url = current_app.config["BASE_URL"]
    laws = db.session.query(Law).order_by(Law.name).all()
    norms = db.session.query(Law.name, Norm.number).join(Norm).filter(
        or_(Norm.is_stale == 0, Norm.is_stale == None)
    ).order_by(Law.name, cast(Norm.number, Integer), Norm.number).all()

    urls = [f"<url><loc>{base_url}/</loc><priority>1.0</priority></url>"]
    for law in laws:
        name = quote(law.name, safe="")
        urls.append(f"<url><loc>{base_url}/gesetz/{name}</loc><priority>0.8</priority></url>")
        urls.append(f"<url><loc>{base_url}/gesetz/{name}/gesamt</loc><priority>0.5</priority></url>")
    for law_name, number in norms:
        name = quote(law_name, safe="")
        number_encoded = quote(str(number), safe="")
        urls.append(f"<url><loc>{base_url}/gesetz/{name}/{number_encoded}</loc><priority>0.6</priority></url>")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<?xml-stylesheet type="text/xsl" href="/static/sitemap.xsl"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )
    cache_set("sitemap", xml)
    return make_response(xml, 200, {"Content-Type": "application/xml"})


@misc_bp.route("/robots.txt")
def robots():
    base_url = current_app.config["BASE_URL"]
    content = f"User-agent: *\nAllow: /\n\nSitemap: {base_url}/sitemap.xml\n"
    return make_response(content, 200, {"Content-Type": "text/plain; charset=utf-8"})


@misc_bp.route("/impressum")
def impressum():
    return render_template("impressum.html")


@misc_bp.route("/datenschutz")
def datenschutz():
    return render_template("privacy.html")
