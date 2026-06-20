"""API routes for in-app notifications."""
import json
import time

from flask import Response, current_app, jsonify, request

from . import bp
from ..models import notification


@bp.get("/notifications")
def list_notifications():
    return jsonify(notification.list_recent())


@bp.get("/notifications/unread-count")
def unread_count():
    return jsonify(count=notification.unread_count())


@bp.get("/notifications/snapshot")
def notif_snapshot():
    return jsonify(notification.snapshot())


@bp.get("/notifications/updates")
def notif_updates():
    since = request.args.get("since", 0, type=int)
    return jsonify(notification.list_since(since))


@bp.get("/notifications/stream")
def notif_stream():
    """Server-sent events — pushes when new alerts arrive (live warehouse feed)."""
    app = current_app._get_current_object()

    def generate():
        with app.app_context():
            last = None
            while True:
                snap = notification.snapshot()
                key = (snap["latest_id"], snap["unread"])
                if key != last:
                    last = key
                    yield f"data: {json.dumps(snap)}\n\n"
                time.sleep(2)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@bp.put("/notifications/<int:notification_id>/read")
def read_one(notification_id):
    if notification.mark_read(notification_id):
        return jsonify(ok=True)
    return jsonify(error="Not found"), 404


@bp.put("/notifications/read-all")
def read_all():
    notification.mark_all_read()
    return jsonify(ok=True)


@bp.delete("/notifications/clear-all")
def clear_all():
    notification.clear_all()
    return jsonify(ok=True)
