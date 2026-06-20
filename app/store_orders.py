"""Pick robots for store orders and build fulfillment notes."""
from __future__ import annotations

import re

OPEN_STATUSES = frozenset({"queued", "in_progress"})
STORE_ORDER_REF_RE = re.compile(r"Store:([^\s·]+)")
ASSIGNABLE_STATUSES = frozenset({"idle", "working"})


def _open_tasks_for_robot(tasks, robot_id):
    return sum(
        1 for t in tasks
        if t["robot_id"] == robot_id and t["status"] in OPEN_STATUSES
    )


def _robots_in_section(tasks, section_id):
    return {
        t["robot_id"]
        for t in tasks
        if t["section_id"] == section_id and t["status"] in OPEN_STATUSES
    }


def robot_eligible_for_backlog(robot, pending_created_at, assign_backlog_on_pair=False):
    """Whether a robot may receive an older store pick from the waiting queue."""
    if not robot.get("paired") or not robot.get("paired_at"):
        return False
    if assign_backlog_on_pair:
        return True
    if not pending_created_at:
        return False
    return pending_created_at >= robot["paired_at"]


def pick_robot(section_id, robots, tasks, reserved_robot_ids=None, *, rush=False, robot_filter=None):
    """Return the best online robot for a section, or None."""
    reserved = set(reserved_robot_ids or [])
    section_robots = _robots_in_section(tasks, section_id)

    candidates = [
        r for r in robots
        if r.get("paired")
        and r["status"] != "offline"
        and r["status"] in ASSIGNABLE_STATUSES
        and r["id"] not in reserved
        and (robot_filter is None or robot_filter(r))
    ]
    if not candidates:
        return None

    def sort_key(robot):
        rid = robot["id"]
        in_zone = rid in section_robots
        idle = robot["status"] == "idle"
        load = _open_tasks_for_robot(tasks, rid)
        if rush:
            tier = (
                0 if (idle and load == 0)
                else 1 if (idle and in_zone)
                else 2 if idle
                else 3 if in_zone
                else 4
            )
        else:
            tier = 0 if (in_zone and idle) else 1 if idle else 2 if in_zone else 3
        return (tier, load, rid)

    candidates.sort(key=sort_key)
    return candidates[0]["id"]


def pick_robot_for_store(section_id, robots, tasks, reserved_robot_ids=None, *, rush=False, robot_filter=None):
    """Pick an online robot, or queue on any paired robot (even offline)."""
    robot_id = pick_robot(section_id, robots, tasks, reserved_robot_ids, rush=rush, robot_filter=robot_filter)
    if robot_id:
        return robot_id

    reserved = set(reserved_robot_ids or [])
    section_robots = _robots_in_section(tasks, section_id)
    paired = [
        r for r in robots
        if r.get("paired") and r["id"] not in reserved and (robot_filter is None or robot_filter(r))
    ]
    if not paired:
        return None

    def fallback_key(robot):
        rid = robot["id"]
        in_zone = rid in section_robots
        load = _open_tasks_for_robot(tasks, rid)
        offline = robot["status"] == "offline"
        return (0 if in_zone else 1, 1 if offline else 0, load, rid)

    paired.sort(key=fallback_key)
    return paired[0]["id"]


def parse_store_order_ref(note):
    """Extract store order ref from a task note (e.g. Store:20250616-120000)."""
    if not note:
        return None
    match = STORE_ORDER_REF_RE.search(str(note))
    return match.group(1) if match else None


def order_status_from_tasks(tasks, pending_count=0):
    """Map warehouse pick tasks (+ optional pending queue) to a store-facing status."""
    if pending_count:
        return "delayed"
    if not tasks:
        return "unknown"
    statuses = [t.get("status") for t in tasks if t.get("status") != "cancelled"]
    if not statuses:
        return "unknown"
    if all(s == "done" for s in statuses):
        return "done"
    if any(s == "in_progress" for s in statuses):
        return "picking"
    if any(s == "queued" for s in statuses):
        return "preparing"
    return "preparing"


def build_store_note(*, order_ref, customer, rush=False, extra_note=""):
    parts = []
    if rush:
        parts.append("RUSH")
    parts.append(f"Store:{order_ref}")
    parts.append(customer)
    if extra_note:
        parts.append(str(extra_note).strip())
    return " · ".join(p for p in parts if p)[:240]
