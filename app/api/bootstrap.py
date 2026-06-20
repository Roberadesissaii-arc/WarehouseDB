"""Single-request payload for the board and other screens that need full workspace data."""
from flask import jsonify

from . import bp
from ..models import home_bay, item, location, robot, setting, task


@bp.get("/bootstrap")
def bootstrap():
    return jsonify(
        tree=location.fetch_tree(),
        items=item.search_items(),
        robots=robot.fetch_robots(),
        tasks=task.list_tasks(),
        settings=setting.get_public(),
        home_bays=home_bay.fetch_payload(),
    )
