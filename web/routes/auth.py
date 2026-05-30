import logging
import re

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

from flask import Blueprint, flash, redirect, render_template, request
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db, login_manager
from models import User

logger = logging.getLogger("web.auth")

auth_bp = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect("/")
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.session.query(User).filter(User.email == email).first()
        if user and user.is_active and check_password_hash(user.password_hash, password):
            login_user(user)
            next_url = request.args.get("next", "")
            if not next_url.startswith("/"):
                next_url = "/"
            return redirect(next_url)
        error = "Ungültige E-Mail-Adresse oder Passwort."
    return render_template("login.html", error=error)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


@auth_bp.route("/register", methods=["GET", "POST"])
def registrierung():
    from ..mail import send_mail
    from flask import current_app

    if current_user.is_authenticated:
        return redirect("/")
    error = None
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not first_name or not last_name:
            error = "Bitte geben Sie Vor- und Nachnamen an."
        elif not email:
            error = "Bitte geben Sie eine E-Mail-Adresse an."
        elif not _EMAIL_RE.match(email):
            error = "Bitte geben Sie eine gültige E-Mail-Adresse an."
        elif db.session.query(User).filter(User.email == email).first():
            error = "Diese E-Mail-Adresse ist bereits registriert."
        elif len(password) < 8:
            error = "Das Passwort muss mindestens 8 Zeichen lang sein."
        elif password != confirm:
            error = "Die Passwörter stimmen nicht überein."
        else:
            user = User(
                first_name=first_name,
                last_name=last_name,
                email=email,
                password_hash=generate_password_hash(password),
                is_active=0,
            )
            db.session.add(user)
            db.session.commit()

            serializer = current_app.config["TOKEN_SERIALIZER"]
            base_url = current_app.config["BASE_URL"]
            token = serializer.dumps(email, salt="email-verify")
            verify_url = f"{base_url}/verify/{token}"
            try:
                send_mail(
                    to=email,
                    subject="E-Mail-Adresse bestätigen — BayRecht",
                    body_text=(
                        f"Hallo {first_name},\n\n"
                        f"bitte bestätigen Sie Ihre E-Mail-Adresse über folgenden Link:\n{verify_url}\n\n"
                        "Der Link ist 24 Stunden gültig.\n\nIhr BayRecht-Team"
                    ),
                    body_html=(
                        f"<p>Hallo {first_name},</p>"
                        f"<p>bitte bestätigen Sie Ihre E-Mail-Adresse:</p>"
                        f'<p><a href="{verify_url}">{verify_url}</a></p>'
                        "<p>Der Link ist 24 Stunden gültig.</p>"
                        "<p>Ihr BayRecht-Team</p>"
                    ),
                )
            except Exception:
                logger.exception(f"Failed to send verification email to {email}")
                db.session.delete(user)
                db.session.commit()
                error = "Die Bestätigungs-E-Mail konnte nicht gesendet werden. Bitte versuchen Sie es später erneut."
            else:
                return render_template("registrierung.html", success=True, email=email)

    return render_template("registrierung.html", error=error)


@auth_bp.route("/verify/<token>")
def verify(token):
    from flask import current_app

    serializer = current_app.config["TOKEN_SERIALIZER"]
    try:
        email = serializer.loads(token, salt="email-verify", max_age=86400)
    except SignatureExpired:
        return render_template("verify.html", state="expired")
    except BadSignature:
        return render_template("verify.html", state="invalid")

    user = db.session.query(User).filter(User.email == email).first()
    if not user:
        return render_template("verify.html", state="invalid")
    if user.is_active:
        return render_template("verify.html", state="already")

    user.is_active = 1
    db.session.commit()
    flash("E-Mail-Adresse bestätigt. Sie können sich jetzt anmelden.", "success")
    return redirect("/login")
