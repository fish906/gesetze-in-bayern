import re

from flask import Blueprint, abort, render_template, request
from sqlalchemy import Integer, cast, case, func, or_, and_

from ..cache import cache_get, cache_set, page_cache_get, page_cache_set
from ..extensions import db
from ..hits import record
from models import Law, Norm

laws_bp = Blueprint("laws", __name__)


@laws_bp.route("/")
def law_index():
    cache_key = "law_index"
    cached = page_cache_get(cache_key)
    if cached:
        return cached

    laws = db.session.query(Law).order_by(Law.name).all()
    laws_data = [{"id": law.id, "name": law.name, "description": law.description} for law in laws]
    rendered = render_template("index.html", laws=laws_data)
    page_cache_set(cache_key, rendered)
    return rendered


@laws_bp.route("/gesetz/<law_name>")
def law_toc(law_name):
    record("law", law_name)

    cache_key = f"toc_{law_name}"
    cached = page_cache_get(cache_key)
    if cached:
        return cached

    law = db.session.query(Law).filter(Law.name == law_name).first()
    if not law:
        abort(404)

    norms = db.session.query(Norm).filter(
        Norm.law_id == law.id,
        or_(Norm.is_stale == 0, Norm.is_stale == None),
    ).order_by(cast(Norm.number, Integer), Norm.number).all()

    law_data = {"id": law.id, "name": law.name, "description": law.description}
    norms_data = [{"number": n.number, "number_raw": n.number_raw, "title": n.title} for n in norms]

    rendered = render_template("toc.html", law=law_data, norms=norms_data)
    page_cache_set(cache_key, rendered)
    return rendered


@laws_bp.route("/gesetz/<law_name>/gesamt")
def law_full_view(law_name):
    record("law", law_name)

    cache_key = f"full_view_{law_name}"
    cached = page_cache_get(cache_key)
    if cached:
        return cached

    law = db.session.query(Law).filter(Law.name == law_name).first()
    if not law:
        abort(404)

    norms = db.session.query(Norm).filter(
        Norm.law_id == law.id,
        or_(Norm.is_stale == 0, Norm.is_stale == None),
    ).order_by(cast(Norm.number, Integer), Norm.number).all()

    law_data = {"id": law.id, "name": law.name, "description": law.description}
    norms_data = [{"number": n.number, "number_raw": n.number_raw, "title": n.title, "content": n.content} for n in norms]

    rendered = render_template("full_view.html", law=law_data, norms=norms_data)
    page_cache_set(cache_key, rendered)
    return rendered


@laws_bp.route("/gesetz/<law_name>/<norm_number>")
def norm_detail(law_name, norm_number):
    record("norm", f"{law_name}/{norm_number}")

    cache_key = f"norm_{law_name}_{norm_number}"
    cached = page_cache_get(cache_key)
    if cached:
        return cached

    law = db.session.query(Law).filter(Law.name == law_name).first()
    if not law:
        abort(404)

    norm = db.session.query(Norm).filter(
        Norm.law_id == law.id,
        Norm.number == norm_number,
    ).first()
    if not norm:
        abort(404)

    prev_norm = db.session.query(Norm).filter(
        Norm.law_id == law.id,
        or_(Norm.is_stale == 0, Norm.is_stale == None),
        or_(
            cast(Norm.number, Integer) < cast(norm_number, Integer),
            and_(
                cast(Norm.number, Integer) == cast(norm_number, Integer),
                Norm.number < norm_number,
            ),
        ),
    ).order_by(cast(Norm.number, Integer).desc(), Norm.number.desc()).limit(1).first()

    next_norm = db.session.query(Norm).filter(
        Norm.law_id == law.id,
        or_(Norm.is_stale == 0, Norm.is_stale == None),
        or_(
            cast(Norm.number, Integer) > cast(norm_number, Integer),
            and_(
                cast(Norm.number, Integer) == cast(norm_number, Integer),
                Norm.number > norm_number,
            ),
        ),
    ).order_by(cast(Norm.number, Integer), Norm.number).limit(1).first()

    prev_norms = db.session.query(Norm).filter(
        Norm.law_id == law.id,
        or_(Norm.is_stale == 0, Norm.is_stale == None),
        or_(
            cast(Norm.number, Integer) < cast(norm_number, Integer),
            and_(
                cast(Norm.number, Integer) == cast(norm_number, Integer),
                Norm.number < norm_number,
            ),
        ),
    ).order_by(cast(Norm.number, Integer).desc(), Norm.number.desc()).limit(5).all()
    prev_norms = list(reversed(prev_norms))

    next_norms = db.session.query(Norm).filter(
        Norm.law_id == law.id,
        or_(Norm.is_stale == 0, Norm.is_stale == None),
        or_(
            cast(Norm.number, Integer) > cast(norm_number, Integer),
            and_(
                cast(Norm.number, Integer) == cast(norm_number, Integer),
                Norm.number > norm_number,
            ),
        ),
    ).order_by(cast(Norm.number, Integer), Norm.number).limit(5).all()

    rendered = render_template(
        "norm.html",
        law={"id": law.id, "name": law.name, "description": law.description},
        norm={"number": norm.number, "number_raw": norm.number_raw, "title": norm.title, "content": norm.content, "url": norm.url},
        prev_norm={"number": prev_norm.number, "title": prev_norm.title} if prev_norm else None,
        next_norm={"number": next_norm.number, "title": next_norm.title} if next_norm else None,
        prev_norms=[{"number": n.number, "title": n.title} for n in prev_norms],
        next_norms=[{"number": n.number, "title": n.title} for n in next_norms],
    )
    page_cache_set(cache_key, rendered)
    return rendered


@laws_bp.route("/suche")
def search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return ""

    direct_match = None
    combined = re.match(
        r'^(?:Art\.?\s*)?(\d+\w*)\s+([A-Za-zÄÖÜäöüß][\w\-]*)$', q, re.IGNORECASE
    ) or re.match(
        r'^([A-Za-zÄÖÜäöüß][\w\-]*)\s+(?:Art\.?\s*)?(\d+\w*)$', q, re.IGNORECASE
    )

    if combined:
        groups = combined.groups()
        if re.match(r'^\d', groups[0]):
            norm_number, law_name = groups
        else:
            law_name, norm_number = groups

        direct_match = db.session.query(
            Law.name.label("law_name"), Norm.number, Norm.title,
        ).join(Norm).filter(
            Norm.number == norm_number,
            func.lower(Law.name) == func.lower(law_name),
            or_(Norm.is_stale == 0, Norm.is_stale == None),
        ).first()

    rank_expr = case((Law.name == q, 0), (Law.name.like(f"{q}%"), 1), else_=2)
    laws = db.session.query(
        Law.name, Law.description, rank_expr.label("rank"),
    ).filter(
        or_(Law.name.like(f"%{q}%"), Law.description.like(f"%{q}%"))
    ).order_by("rank", Law.views.desc(), Law.name).limit(5).all()

    norm_rank_expr = case((Norm.number == q, 0), (Norm.number.like(f"{q}%"), 1), else_=2)
    norms = db.session.query(
        Law.name.label("law_name"), Law.description.label("law_description"),
        Norm.number, Norm.title, norm_rank_expr.label("rank"),
    ).join(Norm).filter(
        or_(
            Norm.number.like(f"{q}%"),
            Norm.number_raw.like(f"%{q}%"),
            Norm.title.like(f"%{q}%"),
        ),
        or_(Norm.is_stale == 0, Norm.is_stale == None),
    ).order_by("rank", Norm.views.desc(), Law.name, cast(Norm.number, Integer), Norm.number).limit(10).all()

    if not direct_match and not laws and not norms:
        return '<div class="search-empty">Keine Ergebnisse</div>'

    html_parts = []

    if direct_match:
        title = direct_match.title or "(ohne Titel)"
        html_parts.append(
            '<div class="search-group"><span class="search-group-label">Direktes Ergebnis</span>'
            f'<a href="/gesetz/{direct_match.law_name}/{direct_match.number}" '
            f'class="search-result search-result-direct">'
            f'<span class="search-result-abbr">Art. {direct_match.number} {direct_match.law_name}</span>'
            f'<span class="search-result-text">{title}</span>'
            f'</a></div>'
        )

    if laws:
        html_parts.append('<div class="search-group"><span class="search-group-label">Gesetze</span>')
        for law in laws:
            html_parts.append(
                f'<a href="/gesetz/{law.name}/gesamt" class="search-result">'
                f'<span class="search-result-abbr">{law.name}</span>'
                f'<span class="search-result-text">{law.description}</span>'
                f'</a>'
            )
        html_parts.append('</div>')

    if norms:
        html_parts.append('<div class="search-group"><span class="search-group-label">Normen</span>')
        for norm in norms:
            title = norm.title or "(ohne Titel)"
            html_parts.append(
                f'<a href="/gesetz/{norm.law_name}/{norm.number}" class="search-result">'
                f'<span class="search-result-abbr">Art. {norm.number} {norm.law_name}</span>'
                f'<span class="search-result-text">{title}</span>'
                f'</a>'
            )
        html_parts.append('</div>')

    return "\n".join(html_parts)
