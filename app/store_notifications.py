"""Warehouse alert feed entries for garage / store pick requests."""
from .models import notification


def notify_pick_request(*, order_ref, customer, summary=None):
    """First alert when a customer sends a pick request to the floor."""
    body = (customer or "Customer").strip() or "Customer"
    if summary:
        body = f"{body} — {summary}"
    notification.create(
        "store",
        f"Pick request · {order_ref}",
        body,
        "/tasks",
    )


def notify_robot_assigned(task_row):
    """Second alert when a nearest available robot receives the pick task."""
    if not task_row:
        return
    robot_name = task_row.get("robot") or "Robot"
    target = task_row.get("item") or task_row.get("section") or "warehouse"
    order_ref = task_row.get("store_order_ref")
    order_prefix = f"Pick request {order_ref} · " if order_ref else ""
    href = f"/tasks/{task_row['id']}" if task_row.get("id") else "/tasks"
    notification.create(
        "task",
        f"{robot_name} assigned to pick",
        f"{order_prefix}{target}",
        href,
    )
