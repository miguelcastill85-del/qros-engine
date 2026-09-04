import datetime as dt
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("controller", ROOT / "scripts/qros_persistent_chat_controller.py")
controller = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(controller)


class PersistentChatControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = controller.load(ROOT / "governance/QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_v1.json")
        cls.queue = controller.load(ROOT / "control/persistent_execution/RUN_QUEUE.json")
        cls.state = controller.load(ROOT / "control/persistent_execution/STATE.json")
        cls.head = {"schema": "QROS_PERSISTENT_CONTROL_HEAD_V126", "g30": {"holdout_open_authorized": False}}

    def test_control_documents_validate(self):
        controller.validate(self.protocol, self.queue, self.state, self.head)

    def test_next_authorized_item_is_ready(self):
        self.assertEqual(controller.next_item(self.queue)["item_id"], "G30-F10-0001")

    def test_holdout_guard_fails_closed(self):
        bad = dict(self.head); bad["g30"] = {"holdout_open_authorized": True}
        with self.assertRaisesRegex(ValueError, "holdout"):
            controller.validate(self.protocol, self.queue, self.state, bad)

    def test_lease_states(self):
        now = dt.datetime(2026, 9, 4, tzinfo=dt.timezone.utc)
        self.assertEqual(controller.lease_status(self.state, now), "FREE")
        active = dict(self.state); active["lease"] = {"expires_at": "2026-09-04T01:00:00Z"}
        expired = dict(self.state); expired["lease"] = {"expires_at": "2026-09-03T23:59:59Z"}
        self.assertEqual(controller.lease_status(active, now), "ACTIVE")
        self.assertEqual(controller.lease_status(expired, now), "EXPIRED")


if __name__ == "__main__":
    unittest.main()
