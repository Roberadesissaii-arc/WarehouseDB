"""Smoke tests — run before shipping or deploying."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

WH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WH))

# Use an isolated database so tests never touch the live warehouse.db.
os.environ.setdefault("FLASK_ENV", "development")
os.environ["DATABASE"] = os.path.join(tempfile.gettempdir(), "warehousedb_test.db")

from app import create_app  # noqa: E402


class AppSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(os.environ["DATABASE"]):
            os.remove(os.environ["DATABASE"])
        cls.app = create_app()
        with cls.app.app_context():
            from app.models import user

            if user.needs_setup():
                user.create_owner(
                    "admin", "admin1234",
                    first_name="Admin", last_name="User", email="admin@example.com",
                )

    def setUp(self):
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess.clear()

    def test_health(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("service"), "warehousedb")

    def test_login_page(self):
        r = self.client.get("/login")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"login", r.data.lower())

    def test_api_requires_session(self):
        r = self.client.get("/api/tree")
        self.assertEqual(r.status_code, 401)

    def test_login_and_tree(self):
        r = self.client.post(
            "/login",
            data={"username": "admin", "password": "admin1234"},
            follow_redirects=False,
        )
        self.assertIn(r.status_code, (302, 303))
        r2 = self.client.get("/api/tree")
        self.assertEqual(r2.status_code, 200)
        self.assertIsInstance(r2.get_json(), list)

    def test_api_auth_login_for_scan(self):
        r = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin1234"},
        )
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()
        self.assertTrue(body.get("signed_in"))
        self.assertEqual(body.get("username"), "admin")
        me = self.client.get("/api/me")
        self.assertEqual(me.status_code, 200, me.get_json())
        self.assertEqual(me.get_json().get("username"), "admin")

    def test_api_auth_lockout_is_per_username(self):
        from app.security import _FAILED

        _FAILED.clear()
        for _ in range(12):
            self.client.post(
                "/api/auth/login",
                json={"username": "baduser", "password": "wrong"},
            )
        locked = self.client.post(
            "/api/auth/login",
            json={"username": "baduser", "password": "wrong"},
        )
        self.assertEqual(locked.status_code, 429, locked.get_json())
        self.assertIn("failed", (locked.get_json().get("error") or "").lower())

        ok = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin1234"},
        )
        self.assertEqual(ok.status_code, 200, ok.get_json())

    def test_board_routes(self):
        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        for path, view in (
            ("/items", b"data-active-view=\"items\""),
            ("/fleet", b"data-active-view=\"fleet\""),
            ("/tasks", b"data-active-view=\"tasks\""),
            ("/map", b"data-active-view=\"map\""),
        ):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertIn(view, r.data, path)
        legacy = self.client.get("/?view=tasks", follow_redirects=False)
        self.assertEqual(legacy.status_code, 302)
        self.assertIn("/tasks", legacy.headers.get("Location", ""))
        pair = self.client.get("/fleet/pair")
        self.assertEqual(pair.status_code, 200)
        self.assertIn(b"pair-page", pair.data)
        task_page = self.client.get("/tasks/1")
        self.assertEqual(task_page.status_code, 200)
        self.assertIn(b"task-page", task_page.data)
        self.assertIn(b'data-task-id="1"', task_page.data)

    def test_warehouse_relay_api(self):
        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        r = self.client.get("/api/relay")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("enabled", data)
        self.assertIn("installed", data)
        self.assertIn("url", data)
        self.assertFalse(data["enabled"])
        settings = self.client.get("/api/settings")
        self.assertIn("relay", settings.get_json())
        enabled = self.client.put("/api/settings", json={"relay": {"enabled": True}})
        self.assertEqual(enabled.status_code, 200)
        self.assertTrue(enabled.get_json()["relay"]["enabled"])
        disabled = self.client.put("/api/settings", json={"relay": {"enabled": False}})
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.get_json()["relay"]["enabled"])

    def test_firmware_catalog_and_robot_status(self):
        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        catalog = self.client.get("/api/firmware")
        self.assertEqual(catalog.status_code, 200)
        cat = catalog.get_json()
        self.assertEqual(cat.get("latest"), "1.1.0")

        self.client.post(
            "/api/robots/pair",
            json={"pairing_code": "777888", "name": "FwBot", "unit_image": 1},
        )
        claimed = self.client.post(
            "/api/robots/claim",
            json={"pairing_code": "777888", "device_id": "fw-test-device"},
        )
        rid = claimed.get_json()["id"]
        hb = self.client.post(
            f"/api/robots/{rid}/heartbeat",
            json={"status": "idle", "firmware_version": "1.0.0"},
        )
        self.assertEqual(hb.status_code, 200, hb.get_json())

        detail = self.client.get(f"/api/robots/{rid}")
        fw = detail.get_json().get("firmware") or {}
        self.assertEqual(fw.get("installed"), "1.0.0")
        self.assertEqual(fw.get("latest"), "1.1.0")
        self.assertTrue(fw.get("update_available"))
        home = self.client.get("/", follow_redirects=False)
        self.assertEqual(home.status_code, 302)
        self.assertIn("/items", home.headers.get("Location", ""))

    def test_system_overview(self):
        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        r = self.client.get("/api/system")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("host", data)
        self.assertIn("database", data)
        self.assertIn("hostname", data["host"])
        self.assertIn("uptime_seconds", data["host"])
        self.assertIn("path", data["database"])

    def test_organization(self):
        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        r = self.client.get("/api/organization")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("org_name", data)
        self.assertIn("max_length", data)
        r2 = self.client.put("/api/organization", json={"org_name": "Test Depot Co."})
        self.assertEqual(r2.status_code, 200)
        saved = r2.get_json()
        self.assertEqual(saved["org_name"], "Test Depot Co.")
        self.assertTrue(saved.get("updated_at"))

    def test_store_catalog_requires_key(self):
        r = self.client.get("/api/store/catalog")
        self.assertEqual(r.status_code, 401)

    def test_store_api_with_key(self):
        import os
        key = os.environ.get("STORE_API_KEY", "store-dev-key")
        headers = {"X-Store-Key": key}
        r = self.client.get("/api/store/catalog", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertIn("products", r.get_json())

    def test_store_order_creates_alert(self):
        import os

        from app.database import get_db
        from app.models import home_bay

        with self.app.app_context():
            db = get_db()
            wid = db.execute("INSERT INTO warehouses(name) VALUES(?)", ("Test WH",)).lastrowid
            sid = db.execute(
                "INSERT INTO sections(warehouse_id, name) VALUES(?,?)", (wid, "Aisle 1")
            ).lastrowid
            shid = db.execute(
                "INSERT INTO shelves(section_id, code) VALUES(?,?)", (sid, "A-01")
            ).lastrowid
            iid = db.execute(
                "INSERT INTO items(name, sku, shelf_id, quantity) VALUES(?,?,?,?)",
                ("Widget", "WDG-001", shid, 10),
            ).lastrowid
            home_bay.ensure_defaults(db)
            dock = db.execute("SELECT id FROM home_bays LIMIT 1").fetchone()["id"]
            db.execute(
                "INSERT INTO robots(name, status, home_bay_id, pairing_code, paired_at, last_seen_at) "
                "VALUES(?,?,?,?,datetime('now'),datetime('now'))",
                ("TestBot", "idle", dock, "123456"),
            )
            db.commit()

        key = os.environ.get("STORE_API_KEY", "store-dev-key")
        r = self.client.post(
            "/api/store/orders",
            headers={"X-Store-Key": key},
            json={
                "lines": [{"item_id": iid, "quantity": 2}],
                "customer_name": "Jane",
            },
        )
        self.assertEqual(r.status_code, 201, r.get_json())

        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        alerts = self.client.get("/api/notifications").get_json()
        self.assertTrue(
            any(
                n.get("kind") == "store"
                and "pick request" in (n.get("title") or "").lower()
                and "Jane" in (n.get("body") or "")
                for n in alerts
            ),
            alerts,
        )
        self.assertTrue(
            any(
                n.get("kind") == "task"
                and "assigned to pick" in (n.get("title") or "").lower()
                for n in alerts
            ),
            alerts,
        )

    def test_store_order_offline_robot_still_places(self):
        """Checkout succeeds when a paired robot exists but is offline."""
        import os

        from app.database import get_db
        from app.models import home_bay

        with self.app.app_context():
            db = get_db()
            wid = db.execute("INSERT INTO warehouses(name) VALUES(?)", ("Offline WH",)).lastrowid
            sid = db.execute(
                "INSERT INTO sections(warehouse_id, name) VALUES(?,?)", (wid, "Quarantine")
            ).lastrowid
            shid = db.execute(
                "INSERT INTO shelves(section_id, code) VALUES(?,?)", (sid, "Q-01")
            ).lastrowid
            iid = db.execute(
                "INSERT INTO items(name, sku, shelf_id, quantity) VALUES(?,?,?,?)",
                ("Pending Unit", "QAR-004", shid, 4),
            ).lastrowid
            home_bay.ensure_defaults(db)
            dock = db.execute("SELECT id FROM home_bays LIMIT 1").fetchone()["id"]
            db.execute(
                "INSERT INTO robots(name, status, home_bay_id, pairing_code, paired_at, last_seen_at) "
                "VALUES(?,?,?,?,datetime('now'),datetime('now','-1 hour'))",
                ("OfflineBot", "offline", dock, "998877"),
            )
            db.commit()

        key = os.environ.get("STORE_API_KEY", "store-dev-key")
        r = self.client.post(
            "/api/store/orders",
            headers={"X-Store-Key": key},
            json={
                "lines": [{"item_id": iid, "quantity": 1}],
                "customer_name": "Robert",
            },
        )
        self.assertEqual(r.status_code, 201, r.get_json())
        body = r.get_json()
        self.assertEqual(body.get("fulfillment"), "queued")
        self.assertTrue(body.get("tasks"))

    def test_store_order_without_robot_is_delayed(self):
        """Checkout succeeds with no robots — fulfillment waits for pairing."""
        import os

        from app.database import get_db

        with self.app.app_context():
            db = get_db()
            wid = db.execute("INSERT INTO warehouses(name) VALUES(?)", ("Empty WH",)).lastrowid
            sid = db.execute(
                "INSERT INTO sections(warehouse_id, name) VALUES(?,?)", (wid, "Aisle Z")
            ).lastrowid
            shid = db.execute(
                "INSERT INTO shelves(section_id, code) VALUES(?,?)", (sid, "Z-01")
            ).lastrowid
            iid = db.execute(
                "INSERT INTO items(name, sku, shelf_id, quantity) VALUES(?,?,?,?)",
                ("Solo Item", "SOLO-1", shid, 2),
            ).lastrowid
            db.execute("DELETE FROM robots")
            db.commit()

        key = os.environ.get("STORE_API_KEY", "store-dev-key")
        r = self.client.post(
            "/api/store/orders",
            headers={"X-Store-Key": key},
            json={
                "lines": [{"item_id": iid, "quantity": 1}],
                "customer_name": "Alex",
            },
        )
        self.assertEqual(r.status_code, 201, r.get_json())
        body = r.get_json()
        self.assertEqual(body.get("fulfillment"), "delayed")
        self.assertEqual(body.get("pending_lines"), 1)
        self.assertEqual(body.get("tasks"), [])

    def test_new_robot_does_not_take_old_pending_by_default(self):
        """A newly paired robot must not grab store picks that were waiting before it paired."""
        import os

        from app.database import get_db

        with self.app.app_context():
            db = get_db()
            db.execute("DELETE FROM robots")
            db.execute("DELETE FROM store_pending_lines")
            wid = db.execute("INSERT INTO warehouses(name) VALUES(?)", ("Backlog WH",)).lastrowid
            sid = db.execute(
                "INSERT INTO sections(warehouse_id, name) VALUES(?,?)", (wid, "Queue Aisle")
            ).lastrowid
            shid = db.execute(
                "INSERT INTO shelves(section_id, code) VALUES(?,?)", (sid, "Q-02")
            ).lastrowid
            iid = db.execute(
                "INSERT INTO items(name, sku, shelf_id, quantity) VALUES(?,?,?,?)",
                ("Backlog Item", "BKL-001", shid, 3),
            ).lastrowid
            db.commit()

        key = os.environ.get("STORE_API_KEY", "store-dev-key")
        order = self.client.post(
            "/api/store/orders",
            headers={"X-Store-Key": key},
            json={"lines": [{"item_id": iid, "quantity": 1}], "customer_name": "Early"},
        )
        self.assertEqual(order.status_code, 201, order.get_json())
        self.assertEqual(order.get_json().get("pending_lines"), 1)

        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        paired = self.client.post(
            "/api/robots/pair",
            json={"pairing_code": "445566", "name": "LateBot", "unit_image": 1},
        )
        self.assertEqual(paired.status_code, 201, paired.get_json())
        claimed = self.client.post(
            "/api/robots/claim",
            json={"pairing_code": "445566", "device_id": "late-bot-device"},
        )
        self.assertEqual(claimed.status_code, 200, claimed.get_json())

        with self.app.app_context():
            pending = get_db().execute("SELECT COUNT(*) AS n FROM store_pending_lines").fetchone()["n"]
            tasks = get_db().execute(
                "SELECT COUNT(*) AS n FROM tasks WHERE robot_id=?",
                (claimed.get_json()["id"],),
            ).fetchone()["n"]
        self.assertEqual(pending, 1)
        self.assertEqual(tasks, 0)

        enabled = self.client.put(
            "/api/settings",
            json={"fleet": {"assign_backlog_on_pair": True}},
        )
        self.assertEqual(enabled.status_code, 200, enabled.get_json())
        heartbeat = self.client.post(
            f"/api/robots/{claimed.get_json()['id']}/heartbeat",
            json={"status": "idle"},
        )
        self.assertEqual(heartbeat.status_code, 200, heartbeat.get_json())

        with self.app.app_context():
            pending = get_db().execute("SELECT COUNT(*) AS n FROM store_pending_lines").fetchone()["n"]
            tasks = get_db().execute(
                "SELECT COUNT(*) AS n FROM tasks WHERE robot_id=?",
                (claimed.get_json()["id"],),
            ).fetchone()["n"]
        self.assertEqual(pending, 0)
        self.assertEqual(tasks, 1)

    def test_store_order_status_and_staff_fulfill(self):
        """Store order status tracks task progress; staff can manually fulfill."""
        import os
        from uuid import uuid4

        from app.database import get_db
        from app.models import home_bay

        with self.app.app_context():
            db = get_db()
            # Isolate from robots created by earlier tests so this order is
            # deterministically assigned to PickerBot below.
            db.execute("DELETE FROM robots")
            wid = db.execute("INSERT INTO warehouses(name) VALUES(?)", ("Status WH",)).lastrowid
            sid = db.execute(
                "INSERT INTO sections(warehouse_id, name) VALUES(?,?)", (wid, "Pick Aisle")
            ).lastrowid
            shid = db.execute(
                "INSERT INTO shelves(section_id, code) VALUES(?,?)", (sid, "P-01")
            ).lastrowid
            iid = db.execute(
                "INSERT INTO items(name, sku, shelf_id, quantity) VALUES(?,?,?,?)",
                ("Gadget", "GDG-001", shid, 5),
            ).lastrowid
            home_bay.ensure_defaults(db)
            dock = db.execute("SELECT id FROM home_bays LIMIT 1").fetchone()["id"]
            db.execute(
                "INSERT INTO robots(name, status, home_bay_id, pairing_code, paired_at, last_seen_at) "
                "VALUES(?,?,?,?,datetime('now'),datetime('now'))",
                ("PickerBot", "idle", dock, "777888"),
            )
            db.commit()

        key = os.environ.get("STORE_API_KEY", "store-dev-key")
        headers = {"X-Store-Key": key}
        order_ref = f"status-test-{uuid4().hex[:12]}"
        placed = self.client.post(
            "/api/store/orders",
            headers=headers,
            json={
                "lines": [{"item_id": iid, "quantity": 1}],
                "customer_name": "Alex",
                "order_ref": order_ref,
            },
        )
        self.assertEqual(placed.status_code, 201, placed.get_json())
        body = placed.get_json()
        self.assertEqual(body["order_ref"], order_ref)
        task_id = body["tasks"][0]["id"]

        status = self.client.get(f"/api/store/orders/{order_ref}/status", headers=headers)
        self.assertEqual(status.status_code, 200, status.get_json())
        self.assertEqual(status.get_json()["status"], "preparing")

        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        accepted = self.client.post(f"/api/tasks/{task_id}/accept")
        self.assertEqual(accepted.status_code, 200, accepted.get_json())
        self.assertEqual(accepted.get_json()["status"], "in_progress")
        self.assertEqual(accepted.get_json()["staff_username"], "admin")

        notes = self.client.get("/api/notifications").get_json()
        accept_note = next(
            (n for n in notes if n.get("title") == "admin accepted pick"),
            None,
        )
        self.assertIsNotNone(accept_note, notes)
        self.assertIn("PickerBot", accept_note.get("body", ""))

        picking = self.client.get(f"/api/store/orders/{order_ref}/status", headers=headers)
        self.assertEqual(picking.get_json()["status"], "picking")

        self.client.put(
            "/api/account",
            json={"username": "floorlead", "current_password": "admin1234"},
        )

        fulfilled = self.client.post(f"/api/tasks/{task_id}/fulfill")
        self.assertEqual(fulfilled.status_code, 200, fulfilled.get_json())
        self.assertEqual(fulfilled.get_json()["status"], "done")
        self.assertEqual(fulfilled.get_json()["store_order_status"], "done")
        self.assertEqual(fulfilled.get_json()["staff_username"], "floorlead")

        notes = self.client.get("/api/notifications").get_json()
        fulfill_note = next(
            (n for n in notes if n.get("title") == "floorlead fulfilled pick"),
            None,
        )
        self.assertIsNotNone(fulfill_note, notes)

        done = self.client.get(f"/api/store/orders/{order_ref}/status", headers=headers)
        self.assertEqual(done.get_json()["status"], "done")

        batch = self.client.get(
            f"/api/store/orders/status?refs={order_ref}",
            headers=headers,
        )
        self.assertEqual(batch.status_code, 200, batch.get_json())
        self.assertEqual(batch.get_json()["orders"][0]["status"], "done")

        # Restore the shared account name so later tests can log in as admin.
        self.client.put(
            "/api/account",
            json={"username": "admin", "current_password": "admin1234"},
        )

    def test_robot_ping_open(self):
        r = self.client.get("/api/robots/ping")
        self.assertEqual(r.status_code, 200)

    def test_cancel_pending_pairing(self):
        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        created = self.client.post(
            "/api/robots/pair",
            json={"pairing_code": "654321", "name": "PendingBot", "unit_image": 1},
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        robot_id = created.get_json()["id"]
        cancelled = self.client.post(f"/api/robots/{robot_id}/cancel-pairing")
        self.assertEqual(cancelled.status_code, 200, cancelled.get_json())
        robots = self.client.get("/api/robots").get_json()
        self.assertFalse(any(r["id"] == robot_id for r in robots))

    def test_item_by_sku(self):
        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        items = self.client.get("/api/items").get_json()
        self.assertTrue(items)
        sku = items[0].get("sku")
        if not sku:
            self.skipTest("no SKU in seed data")
        found = self.client.get(f"/api/items/by-sku/{sku}").get_json()
        self.assertEqual(found["id"], items[0]["id"])

    def test_repair_same_device(self):
        """After firmware upload the robot shows a new code; claim must merge, not reject."""
        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        self.client.post(
            "/api/robots/pair",
            json={"pairing_code": "222333", "name": "OldBot", "unit_image": 1},
        )
        claimed = self.client.post(
            "/api/robots/claim",
            json={"pairing_code": "222333", "device_id": "esp32-mac-aa"},
        )
        self.assertEqual(claimed.status_code, 200, claimed.get_json())
        old_id = claimed.get_json()["id"]

        pending = self.client.post(
            "/api/robots/pair",
            json={"pairing_code": "444555", "name": "RefreshedBot", "unit_image": 2},
        )
        self.assertEqual(pending.status_code, 201, pending.get_json())

        repair = self.client.post(
            "/api/robots/claim",
            json={"pairing_code": "444555", "device_id": "esp32-mac-aa"},
        )
        self.assertEqual(repair.status_code, 200, repair.get_json())
        body = repair.get_json()
        self.assertEqual(body["id"], old_id)
        self.assertEqual(body["name"], "RefreshedBot")
        self.assertEqual(body["pairing_code"], "444555")
        robots = self.client.get("/api/robots").get_json()
        self.assertEqual(sum(1 for r in robots if r.get("pairing_code") == "444555"), 1)

        status = self.client.get("/api/robots/pair-status?code=444555").get_json()
        self.assertTrue(status["paired"])
        self.assertEqual(status["robot_id"], old_id)

    def test_pair_pending_same_code_updates_name(self):
        """Staff can re-submit the same on-screen code with a new display name."""
        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        first = self.client.post(
            "/api/robots/pair",
            json={"pairing_code": "333444", "name": "Bolt-10", "unit_image": 1},
        )
        self.assertEqual(first.status_code, 201, first.get_json())
        first_id = first.get_json()["id"]
        second = self.client.post(
            "/api/robots/pair",
            json={"pairing_code": "333444", "name": "Rover-22", "unit_image": 3},
        )
        self.assertEqual(second.status_code, 201, second.get_json())
        self.assertEqual(second.get_json()["id"], first_id)
        robots = self.client.get("/api/robots").get_json()
        match = next(r for r in robots if r["id"] == first_id)
        self.assertEqual(match["name"], "Rover-22")
        self.assertFalse(match["paired"])

    def test_task_staff_username(self):
        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        items = self.client.get("/api/items").get_json()
        robots = self.client.get("/api/robots").get_json()
        paired = [r for r in robots if r.get("paired")]
        if not paired:
            self.client.post(
                "/api/robots/pair",
                json={"pairing_code": "111222", "name": "TaskBot", "unit_image": 1},
            )
            self.client.post(
                "/api/robots/claim",
                json={"pairing_code": "111222", "device_id": "test-device"},
            )
            robots = self.client.get("/api/robots").get_json()
            paired = [r for r in robots if r.get("paired")]
        self.assertTrue(paired, "need a paired robot")
        robot_id = paired[0]["id"]
        item_id = items[0]["id"]
        r = self.client.post(
            "/api/tasks",
            json={"robot_id": robot_id, "action": "pick", "item_id": item_id, "quantity": 1},
        )
        self.assertEqual(r.status_code, 201, r.get_json())
        task = r.get_json()
        self.assertIsNone(task.get("staff_username"))

    def test_pick_notification_uses_renamed_username(self):
        """After renaming the account, accept/fulfill alerts use the new username."""
        self.client.post("/login", data={"username": "admin", "password": "admin1234"})
        self.client.put(
            "/api/account",
            json={"username": "robert", "current_password": "admin1234"},
        )
        items = self.client.get("/api/items").get_json()
        robots = self.client.get("/api/robots").get_json()
        paired = [r for r in robots if r.get("paired")]
        if not paired:
            self.client.post(
                "/api/robots/pair",
                json={"pairing_code": "111222", "name": "NotifyBot", "unit_image": 1},
            )
            self.client.post(
                "/api/robots/claim",
                json={"pairing_code": "111222", "device_id": "notify-device"},
            )
            robots = self.client.get("/api/robots").get_json()
            paired = [r for r in robots if r.get("paired")]
        self.assertTrue(paired, "need a paired robot")
        created = self.client.post(
            "/api/tasks",
            json={
                "robot_id": paired[0]["id"],
                "action": "pick",
                "item_id": items[0]["id"],
                "quantity": 1,
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        task_id = created.get_json()["id"]

        accepted = self.client.post(f"/api/tasks/{task_id}/accept")
        self.assertEqual(accepted.status_code, 200, accepted.get_json())
        notes = self.client.get("/api/notifications").get_json()
        self.assertTrue(
            any(n.get("title") == "robert accepted pick" for n in notes),
            notes,
        )

        fulfilled = self.client.post(f"/api/tasks/{task_id}/fulfill")
        self.assertEqual(fulfilled.status_code, 200, fulfilled.get_json())
        notes = self.client.get("/api/notifications").get_json()
        self.assertTrue(
            any(n.get("title") == "robert fulfilled pick" for n in notes),
            notes,
        )

        self.client.put(
            "/api/account",
            json={"username": "admin", "current_password": "admin1234"},
        )


if __name__ == "__main__":
    unittest.main()
