from flask import Blueprint, flash, redirect, render_template, request
from flask_login import current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db

user_bp = Blueprint("user", __name__)


@user_bp.route("/profil")
@login_required
def profil():
    return render_template("profil.html")


@user_bp.route("/profil/passwort", methods=["POST"])
@login_required
def profil_passwort():
    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm_pw = request.form.get("confirm_password", "")

    if not check_password_hash(current_user.password_hash, current_pw):
        flash("Das aktuelle Passwort ist falsch.", "error")
    elif len(new_pw) < 8:
        flash("Das neue Passwort muss mindestens 8 Zeichen lang sein.", "error")
    elif new_pw != confirm_pw:
        flash("Die Passwörter stimmen nicht überein.", "error")
    else:
        current_user.password_hash = generate_password_hash(new_pw)
        db.session.commit()
        flash("Passwort erfolgreich geändert.", "success")

    return redirect("/profil")
