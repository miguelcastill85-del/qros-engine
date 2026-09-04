import copy
import datetime as dt
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("controller", ROOT / "scripts/qros_persistent_chat_controller.py")
controller = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(controller)

MAIN = "1" * 40
HEAD_BLOB = "2" * 40
ENTRYPOINT = "3" * 64
NOW = dt.datetime(2026, 9, 4, 5, 0, tzinfo=dt.timezone.utc)


def fixtures():
    protocol = {
        "schema": "QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_V1",
        "status": "ADOPTED_MANDATORY_OPERATIONAL_LAYER",
        "queue_contract": {"item_required_fields": [
            "item_id", "status", "source_head_schema", "source_head_commit", "scope",
            "action", "prerequisites", "guards", "checkpoint_path", "success_condition",
        ]},
        "checkpoint_policy": {"minimum_fields": [
            "dispatch_id", "queue_item_id", "parent_commit", "input_and_source_sha256",
            "completed_ranges", "output_sha256", "holdout_exposure", "scientific_outcome",
            "execution_state", "exact_resume_action",
        ]},
    }
    head = {
        "schema": "QROS_PERSISTENT_CONTROL_HEAD_V127",
        "g30": {"holdout_open_authorized": False},
        "governance": {
            "mt5_authorized": False, "branch_exhaustion_authorized": False,
            "all_gate_passers_advance": True,
        },
    }
    guards = dict(controller.QUEUE_GUARDS)
    item = {
        "item_id": "G30-F10-0003", "status": "READY",
        "source_head_schema": head["schema"], "source_head_commit": MAIN,
        "scope": "F10_DEV", "action": "RUN", "prerequisites": [], "guards": [],
        "checkpoint_path": "control/persistent_execution/checkpoints/F10.json",
        "success_condition": "EXACT",
    }
    queue = {
        "schema": "QROS_PERSISTENT_RUN_QUEUE_V1", "source_head_schema": head["schema"],
        "last_reconciled_head_blob_sha": HEAD_BLOB, "guards": guards, "queue": [item],
    }
    state = {
        "schema": "QROS_PERSISTENT_EXECUTION_STATE_V1", "enabled": True,
        "protocol_ref": "governance/QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_v1.json",
        "queue_ref": "control/persistent_execution/RUN_QUEUE.json",
        "automation": {"status": "ACTIVE", "automation_created": True, "paid_infrastructure": False},
        "holdout_opened": False, "lease_epoch": 0, "lease": None,
    }
    return protocol, queue, state, head


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.protocol, self.queue, self.state, self.head = fixtures()

    def test_current_documents_validate(self):
        controller.validate(self.protocol, self.queue, self.state, self.head, head_blob_sha=HEAD_BLOB)

    def test_every_queue_guard_fails_closed(self):
        for key, expected in controller.QUEUE_GUARDS.items():
            bad = copy.deepcopy(self.queue)
            bad["guards"][key] = not expected
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "unsafe queue guard"):
                controller.validate(self.protocol, bad, self.state, self.head)

    def test_head_schema_and_blob_drift_fail_closed(self):
        bad = copy.deepcopy(self.queue); bad["source_head_schema"] = "QROS_PERSISTENT_CONTROL_HEAD_V126"
        with self.assertRaisesRegex(ValueError, "schema mismatch"):
            controller.validate(self.protocol, bad, self.state, self.head)
        with self.assertRaisesRegex(ValueError, "blob mismatch"):
            controller.validate(self.protocol, self.queue, self.state, self.head, head_blob_sha="4" * 40)

    def test_head_governance_fails_closed(self):
        for key, unsafe in [("mt5_authorized", True), ("branch_exhaustion_authorized", True),
                            ("all_gate_passers_advance", False)]:
            bad = copy.deepcopy(self.head); bad["governance"][key] = unsafe
            with self.subTest(key=key), self.assertRaises(ValueError):
                controller.validate(self.protocol, self.queue, self.state, bad)

    def test_deterministic_next_item(self):
        self.assertEqual(controller.next_item(self.queue)["item_id"], "G30-F10-0003")

    def test_claim_active_rejected_and_expired_requires_recovery(self):
        claimed = controller.claim_lease(
            self.state, worker_id="canary", observed_main_sha=MAIN,
            entrypoint_sha256=ENTRYPOINT, now=NOW, ttl_minutes=15,
        )
        self.assertEqual(controller.lease_status(claimed, NOW), "ACTIVE")
        with self.assertRaisesRegex(ValueError, "unexpired"):
            controller.claim_lease(claimed, worker_id="other", observed_main_sha=MAIN,
                                   entrypoint_sha256=ENTRYPOINT, now=NOW, ttl_minutes=15)
        with self.assertRaisesRegex(ValueError, "recovery"):
            controller.claim_lease(claimed, worker_id="other", observed_main_sha=MAIN,
                                   entrypoint_sha256=ENTRYPOINT,
                                   now=NOW + dt.timedelta(minutes=16), ttl_minutes=15)

    def test_fencing_heartbeat_and_release(self):
        claimed = controller.claim_lease(
            self.state, worker_id="canary", observed_main_sha=MAIN,
            entrypoint_sha256=ENTRYPOINT, now=NOW, ttl_minutes=15,
        )
        lease = claimed["lease"]
        with self.assertRaisesRegex(ValueError, "stale or foreign"):
            controller.heartbeat_lease(claimed, lease_id=lease["lease_id"],
                                       fence_token=lease["fence_token"] + 1,
                                       observed_main_sha=MAIN, now=NOW, ttl_minutes=15)
        beat = controller.heartbeat_lease(claimed, lease_id=lease["lease_id"],
                                          fence_token=lease["fence_token"],
                                          observed_main_sha=MAIN,
                                          now=NOW + dt.timedelta(minutes=5), ttl_minutes=15)
        released = controller.release_lease(beat, lease_id=lease["lease_id"],
                                            fence_token=lease["fence_token"],
                                            observed_main_sha=MAIN,
                                            now=NOW + dt.timedelta(minutes=6), outcome="CANARY_PASS")
        self.assertIsNone(released["lease"])
        self.assertEqual(released["last_released_lease"]["outcome"], "CANARY_PASS")

    def test_checkpoint_validation(self):
        checkpoint = {
            "dispatch_id": "canary", "queue_item_id": "CONTROL-CANARY",
            "parent_commit": MAIN, "input_and_source_sha256": {"controller": ENTRYPOINT},
            "completed_ranges": ["claim", "checkpoint", "release"],
            "output_sha256": ENTRYPOINT, "holdout_exposure": "SEALED_NO_ACCESS",
            "scientific_outcome": "NONE_OPERATIONAL_ONLY", "execution_state": "CONTROL_CANARY",
            "exact_resume_action": "RECONCILE_QUEUE",
        }
        controller.validate_checkpoint(checkpoint, self.protocol)
        bad = copy.deepcopy(checkpoint); bad["holdout_exposure"] = "OPENED"
        with self.assertRaisesRegex(ValueError, "sealed holdout"):
            controller.validate_checkpoint(bad, self.protocol)


if __name__ == "__main__":
    unittest.main()
