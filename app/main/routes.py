"""Page routes — serve the rendered HTML."""
from flask import current_app, redirect, render_template, request, send_from_directory, url_for

from . import bp

BOARD_VIEWS = ("items", "fleet", "tasks", "map")


@bp.route("/sw.js")
def service_worker():
    """Serve the service worker from the root so it can control the whole app."""
    resp = send_from_directory(current_app.static_folder, "sw.js")
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@bp.route("/")
def index():
    """Legacy home — redirect old ?view= links and default board to /items."""
    view = request.args.get("view")
    if view in ("fleet", "tasks", "map"):
        return redirect(f"/{view}")
    return redirect(url_for("main.board_items"))


def _board(active_view):
    if active_view not in BOARD_VIEWS:
        active_view = "items"
    return render_template("index.html", active_view=active_view)


@bp.route("/items")
def board_items():
    return _board("items")


@bp.route("/fleet")
def board_fleet():
    return _board("fleet")


@bp.route("/fleet/pair")
def fleet_pair():
    return render_template("pair.html")


@bp.route("/tasks")
def board_tasks():
    return _board("tasks")


@bp.route("/tasks/<int:task_id>")
def task_detail(task_id):
    return render_template("task.html", task_id=task_id)


@bp.route("/map")
def board_map():
    return _board("map")


@bp.route("/guide")
def guide():
    return render_template("guide.html")


@bp.route("/settings")
def settings():
    return render_template("settings.html")


@bp.route("/items/<int:item_id>")
def item_detail(item_id):
    return render_template(
        "item.html",
        item_id=item_id,
        scan_url=current_app.config.get("SCAN_PUBLIC_URL", "http://localhost:5002"),
    )


@bp.route("/robots/<int:robot_id>")
def robot_detail(robot_id):
    return render_template("robot.html", robot_id=robot_id)
