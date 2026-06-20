"""User accounts for the login gate. Passwords are stored hashed."""
import click
from werkzeug.security import check_password_hash, generate_password_hash

from ..database import get_db

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"


def ensure_default_admin():
    """Legacy no-op — first account is created on the setup screen."""
    return


def needs_setup() -> bool:
    return get_db().execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0


def create_owner(username, password, *, first_name="", last_name="", email=""):
    """Create the sole warehouse account (first run only)."""
    from ..security import validate_password

    if not needs_setup():
        raise ValueError("An account already exists for this warehouse.")
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    email = (email or "").strip()
    username = (username or "").strip()
    if not first_name:
        raise ValueError("First name is required")
    if not last_name:
        raise ValueError("Last name is required")
    if not username:
        raise ValueError("Username is required")
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise ValueError("A valid email address is required")
    validate_password(password)
    db = get_db()
    db.execute(
        "INSERT INTO users(username, password_hash, first_name, last_name, email) VALUES(?,?,?,?,?)",
        (username, generate_password_hash(password), first_name, last_name, email),
    )
    db.commit()
    return get_by_username(username)


def get_by_username(username: str):
    return get_db().execute("SELECT * FROM users WHERE username=?", ((username or "").strip(),)).fetchone()


def list_usernames():
    rows = get_db().execute("SELECT username FROM users ORDER BY username").fetchall()
    return [row["username"] for row in rows]


def reset_staff_password(username, password, *, create_if_missing=False):
    """Set a staff password (CLI recovery). Optionally rename the sole account."""
    from ..security import validate_password

    username = (username or "").strip()
    if not username:
        raise ValueError("Username is required")
    validate_password(password)

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        count = db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        if create_if_missing and count == 0:
            db.execute(
                "INSERT INTO users(username, password_hash) VALUES(?,?)",
                (username, generate_password_hash(password)),
            )
            db.commit()
            return "created"
        if count == 1 and create_if_missing:
            only = db.execute("SELECT id FROM users").fetchone()
            db.execute(
                "UPDATE users SET username=?, password_hash=? WHERE id=?",
                (username, generate_password_hash(password), only["id"]),
            )
            db.commit()
            return "updated"
        raise ValueError(f"No user named {username!r}")

    db.execute(
        "UPDATE users SET password_hash=? WHERE id=?",
        (generate_password_hash(password), row["id"]),
    )
    db.commit()
    return "updated"


@click.command("reset-staff-password")
@click.option("--username", default=DEFAULT_USERNAME, show_default=True, help="Staff username to set.")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="New password (8+ chars, letter and number).")
@click.option("--create-if-missing", is_flag=True, help="Create the account if the database has no users.")
def reset_staff_password_command(username, password, create_if_missing):
    """Reset a WarehouseDB staff password (does not affect Store or Scan apps)."""
    action = reset_staff_password(username, password, create_if_missing=create_if_missing)
    click.echo(f"Staff account {action}: {username}")


def get_by_id(user_id):
    return get_db().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def verify(username, password):
    """Return the user row if credentials are valid, else None."""
    username = (username or "").strip()
    row = get_db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        return row
    return None


def verify_password(user_id, password):
    row = get_by_id(user_id)
    return bool(row and check_password_hash(row["password_hash"], password))


def resolve_session_username(sess):
    """Return the canonical username for a logged-in session."""
    name = (sess.get("username") or "").strip()
    if name:
        return name
    uid = sess.get("user_id")
    if not uid:
        return None
    row = get_by_id(uid)
    if not row:
        return None
    return (row["username"] or "").strip() or None


def update_credentials(user_id, username, new_password=None):
    """Update the username, and the password too if one is provided."""
    from ..security import validate_password

    username = (username or "").strip()
    if not username:
        raise ValueError("Username is required")
    if new_password is not None:
        new_password = new_password.strip() or None
    if new_password:
        validate_password(new_password)
    db = get_db()
    if new_password:
        db.execute(
            "UPDATE users SET username=?, password_hash=? WHERE id=?",
            (username, generate_password_hash(new_password), user_id),
        )
    else:
        db.execute("UPDATE users SET username=? WHERE id=?", (username, user_id))
    db.commit()
