import dotenv
dotenv.load_dotenv()

import logging
import os
import time as _time

import click
from flask import Flask, render_template
from itsdangerous import URLSafeTimedSerializer
from werkzeug.exceptions import HTTPException
from werkzeug.security import generate_password_hash

from .extensions import db, login_manager
from . import hits
from .routes.auth import auth_bp
from .routes.laws import laws_bp
from .routes.misc import misc_bp
from .routes.user import user_bp
from models import User, UserRole

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s | %(name)s | %(message)s",
)
logger = logging.getLogger("web")

_ERROR_MESSAGES = {
    404: {"title": "Nicht gefunden", "message": "Die angeforderte Seite konnte nicht gefunden werden."},
    500: {"title": "Serverfehler", "message": "Ein interner Fehler ist aufgetreten. Bitte versuchen Sie es später erneut."},
}


def create_app() -> Flask:
    app = Flask(__name__)

    required_vars = ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "SECRET_KEY"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    db_host = os.environ["DB_HOST"]
    db_port = int(os.environ.get("DB_PORT", 3306))
    db_user = os.environ["DB_USER"]
    db_password = os.environ["DB_PASSWORD"]
    db_name = os.environ["DB_NAME"]

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    app.config["API_VERSION"] = os.environ.get("API_VERSION", "1.0")
    app.config["BASE_URL"] = os.environ.get("BASE_URL", "https://recht.netzsys.de")
    app.config["TOKEN_SERIALIZER"] = URLSafeTimedSerializer(app.config["SECRET_KEY"])
    app.config["START_TIME"] = _time.time()

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(laws_bp)
    app.register_blueprint(misc_bp)

    hits.init_app(app)

    @app.context_processor
    def inject_globals():
        return {"base_url": app.config["BASE_URL"]}

    @app.errorhandler(HTTPException)
    def http_exception_handler(e):
        error = _ERROR_MESSAGES.get(e.code, {
            "title": f"Fehler {e.code}",
            "message": e.description or "Ein unbekannter Fehler ist aufgetreten.",
        })
        return render_template("error.html", status_code=e.code, **error), e.code

    @app.errorhandler(Exception)
    def general_exception_handler(e):
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        return render_template("error.html", status_code=500, **_ERROR_MESSAGES[500]), 500

    @app.cli.command("create-user")
    @click.argument("email")
    @click.option("--role", type=click.Choice(["admin", "user"]), default="user", show_default=True)
    @click.option("--first-name", default="", help="First name")
    @click.option("--last-name", default="", help="Last name")
    @click.password_option()
    def create_user(email, role, first_name, last_name, password):
        """Create a new user account."""
        email = email.strip().lower()
        if db.session.query(User).filter(User.email == email).first():
            click.echo(f"Error: a user with email '{email}' already exists.")
            return
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password_hash=generate_password_hash(password),
            role=UserRole(role),
        )
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created user: {email} (role: {role})")

    return app


app = create_app()
