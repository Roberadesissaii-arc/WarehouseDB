"""Store front API — catalog and pick requests that create floor tasks."""
from datetime import datetime, timezone
from uuid import uuid4

from flask import jsonify, request

from . import bp
from ..models import item, robot, store_pending, task
from ..store_notifications import notify_pick_request, notify_robot_assigned
from ..store_orders import build_store_note, pick_robot_for_store


def _store_catalog():
    products = []
    for row in item.search_items():
        qty = row.get("quantity") or 0
        if qty < 1:
            continue
        products.append({
            "id": row["id"],
            "name": row["name"],
            "sku": row["sku"],
            "quantity": qty,
            "location": row["location"],
            "created_at": row.get("created_at"),
        })
    return products


@bp.get("/store/catalog")
def store_catalog():
    return jsonify(products=_store_catalog())


@bp.post("/store/orders")
def store_place_order():
    data = request.get_json(silent=True) or {}
    lines = data.get("lines") or data.get("items")
    if not lines or not isinstance(lines, list):
        raise ValueError("lines is required — array of {item_id, quantity}")

    robots = robot.fetch_robots()
    tasks = task.list_tasks()
    created = []
    order_ref = (data.get("order_ref") or "").strip() or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    customer = (data.get("customer_name") or "").strip() or "Warehouse"
    priority = (data.get("priority") or "standard").strip().lower()
    if priority not in ("standard", "rush"):
        priority = "standard"
    rush = priority == "rush"
    order_id = str(uuid4())
    extra_note = (data.get("note") or "").strip()

    notify_pick_request(order_ref=order_ref, customer=customer)

    reserved_robots = []
    for line in lines:
        if not isinstance(line, dict):
            raise ValueError("Each line must be an object")
        item_id = line.get("item_id")
        quantity = line.get("quantity", 1)
        if not item_id:
            raise ValueError("Each line needs item_id")
        try:
            quantity = int(quantity)
        except (TypeError, ValueError) as exc:
            raise ValueError("quantity must be a number") from exc
        if quantity < 1:
            raise ValueError("quantity must be at least 1")

        it = item.get_item(int(item_id))
        if not it:
            raise ValueError(f"Item {item_id} not found")
        if quantity > (it.get("quantity") or 0):
            raise ValueError(f"Not enough stock for {it['name']} (have {it.get('quantity')}, need {quantity})")

        section_id = it["location"]["section_id"]
        note = build_store_note(
            order_ref=order_ref,
            customer=customer,
            rush=rush,
            extra_note=extra_note,
        )
        robot_id = pick_robot_for_store(
            section_id, robots, tasks, reserved_robots, rush=rush,
        )

        if robot_id:
            reserved_robots.append(robot_id)
            task_id = task.create_task(robot_id, "pick", section_id, it["id"], note, quantity)
            row = task.get_task(task_id)
            created.append(row)
            tasks.append(row)
            notify_robot_assigned(row)
        else:
            store_pending.enqueue(
                order_id, order_ref, customer, it, quantity, section_id, note, priority,
            )

    if store_pending.pending_count():
        dispatched = store_pending.dispatch_all(robot.fetch_robots(), tasks)
        created.extend(dispatched)
        tasks.extend(dispatched)

    pending_lines = store_pending.pending_count()

    if pending_lines:
        fulfillment = "delayed"
    else:
        fulfillment = "queued"

    return jsonify(
        order_id=order_id,
        order_ref=order_ref,
        customer_name=customer,
        priority=priority,
        fulfillment=fulfillment,
        tasks=created,
        pending_lines=pending_lines,
    ), 201


@bp.get("/store/orders/<order_ref>/status")
def store_order_status(order_ref):
    order_ref = (order_ref or "").strip()
    if not order_ref:
        raise ValueError("order_ref is required")
    from ..store_orders import order_status_from_tasks

    tasks = task.list_tasks_for_store_order(order_ref)
    pending = store_pending.pending_count_for_order(order_ref)
    status = order_status_from_tasks(tasks, pending)
    return jsonify(
        order_ref=order_ref,
        status=status,
        pending_lines=pending,
        tasks=[
            {
                "id": t["id"],
                "status": t["status"],
                "action": t["action"],
                "item": t.get("item"),
                "quantity": t.get("quantity"),
                "robot": t.get("robot"),
            }
            for t in tasks
        ],
    )


@bp.get("/store/orders/status")
def store_orders_status_batch():
    refs_raw = (request.args.get("refs") or "").strip()
    if not refs_raw:
        raise ValueError("refs query parameter is required")
    from ..store_orders import order_status_from_tasks

    results = []
    for order_ref in [r.strip() for r in refs_raw.split(",") if r.strip()]:
        tasks = task.list_tasks_for_store_order(order_ref)
        pending = store_pending.pending_count_for_order(order_ref)
        results.append({
            "order_ref": order_ref,
            "status": order_status_from_tasks(tasks, pending),
            "pending_lines": pending,
        })
    return jsonify(orders=results)
