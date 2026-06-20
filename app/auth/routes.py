"""Login and logout routes."""
from flask import redirect, render_template, request, session, url_for

from . import bp
from ..models import user
from ..security import clear_login_attempts, login_allowed, record_failed_login


@bp.route("/login", methods=["GET", "POST"])
def login():
    needs_setup = user.needs_setup()
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if needs_setup:
            try:
                row = user.create_owner(username, password)
            except ValueError as exc:
                return render_template("login.html", error=str(exc), username=username, needs_setup=True)
            clear_login_attempts(username)
            session.clear()
            session.permanent = True
            from flask import current_app
            from ..security import session_lifetime
            current_app.permanent_session_lifetime = session_lifetime()
            session["user_id"] = row["id"]
            session["username"] = row["username"]
            return redirect(url_for("main.index"))

        try:
            login_allowed(username)
        except ValueError as exc:
            return render_template("login.html", error=str(exc), username=username, needs_setup=False)

        row = user.verify(username, password)
        if row:
            clear_login_attempts(username)
            session.clear()
            session.permanent = True
            from flask import current_app
            from ..security import session_lifetime
            current_app.permanent_session_lifetime = session_lifetime()
            session["user_id"] = row["id"]
            session["username"] = row["username"]
            return redirect(url_for("main.index"))
        record_failed_login(username)
        return render_template(
            "login.html",
            error="Invalid username or password. Check both fields and try again.",
            username=username,
            needs_setup=False,
        )

    if session.get("user_id"):
        return redirect(url_for("main.index"))
    return render_template("login.html", needs_setup=needs_setup)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
