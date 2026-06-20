"""Database package: connection lifecycle, schema, and seeding."""
from .connection import close_db, get_db, init_app
from .schema import ROBOT_OFFLINE_SECONDS, ROBOT_REPORTABLE_STATUSES, ROBOT_STATUSES, SCHEMA, TASK_ACTIONS, TASK_STATUSES, init_schema
from .seed import clear_warehouse_data, load_demo_data, reset_sample_data, seed_if_empty

__all__ = [
    "get_db",
    "close_db",
    "init_app",
    "init_schema",
    "seed_if_empty",
    "clear_warehouse_data",
    "reset_sample_data",
    "load_demo_data",
    "SCHEMA",
    "ROBOT_STATUSES",
    "ROBOT_REPORTABLE_STATUSES",
    "ROBOT_OFFLINE_SECONDS",
    "TASK_ACTIONS",
    "TASK_STATUSES",
]
