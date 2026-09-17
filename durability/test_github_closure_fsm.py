import copy
import unittest

from qros_github_closure_fsm import (
    EVENT_SCHEMA,
    TransitionError,
    advance,
    new_journal,
)

PARENT = "a" * 40
COMMIT = "b" * 40
PAYLOAD = "c" * 64
PATHS = {"durability/a.py": "d" * 40, "durability/b.py": "e" * 40}
AUTHORITY = {
    "pointer_path": "control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json",
    "pointer_blob_sha1": "f" * 40,
    "version": "V255",
    "scientific_state": "PREREGISTERED_NO_RESULTS",
}


def ev(j, typ, **kwargs):
    return {
        "schema": EVENT_SCHEMA,
        "operation_id": j["identity"]["operation_id"],
        "identity_sha256": j["identity_sha256"],
        "type": typ,
        **kwargs,
    }


class GitHubClosureFSMTests(unittest.TestCase):
    def journal(self, max_retries=3):
        return new_journal("op-1", PARENT, PAYLOAD, PATHS, AUTHORITY, max_retries)

    def test_happy_path_closes_only_after_exact_readback(self):
        j = self.journal()
        j = advance(j, ev(j, "PARENT_OBSERVED", observed_head_sha=PARENT))
        self.assertEqual(j["phase"], "PREPARED")
        j = advance(j, ev(j, "COMMIT_CREATED", commit_sha=COMMIT, parent_sha=PARENT))
        self.assertEqual(j["phase"], "COMMIT_CREATED")
        j = advance(j, ev(j, "REF_PROMOTED", observed_head_sha=COMMIT))
        self.assertEqual(j["phase"], "REF_PROMOTED")
        j = advance(j, ev(j, "READBACK_VERIFIED", observed_head_sha=COMMIT, observed_paths=PATHS))
        self.assertEqual(j["phase"], "CLOSED")
        self.assertTrue(j["terminal"])
        self.assertEqual(j["decision"], "GITHUB_PUBLICATION_CLOSED")

    def test_terminal_closed_is_fixed_point_and_idempotent(self):
        j = self.journal()
        j = advance(j, ev(j, "COMMIT_CREATED", commit_sha=COMMIT, parent_sha=PARENT))
        j = advance(j, ev(j, "REF_PROMOTED", observed_head_sha=COMMIT))
        j = advance(j, ev(j, "READBACK_VERIFIED", observed_head_sha=COMMIT, observed_paths=PATHS))
        again = advance(j, ev(j, "READBACK_VERIFIED", observed_head_sha=COMMIT, observed_paths=PATHS))
        self.assertEqual(again["phase"], "CLOSED")
        self.assertEqual(again["decision"], "GITHUB_PUBLICATION_CLOSED")
        self.assertEqual(again["history"][-1]["outcome"], "IGNORED_TERMINAL_FIXED_POINT")

    def test_stale_parent_is_terminal_conflict_not_loop(self):
        j = self.journal()
        j = advance(j, ev(j, "PARENT_OBSERVED", observed_head_sha="1" * 40))
        self.assertEqual(j["phase"], "CONFLICT")
        self.assertTrue(j["terminal"])
        self.assertEqual(j["decision"], "FAIL_CLOSED_STALE_PARENT")

    def test_readback_mismatch_is_terminal_conflict(self):
        j = self.journal()
        j = advance(j, ev(j, "COMMIT_CREATED", commit_sha=COMMIT, parent_sha=PARENT))
        j = advance(j, ev(j, "REF_PROMOTED", observed_head_sha=COMMIT))
        bad = dict(PATHS)
        bad["durability/a.py"] = "0" * 40
        j = advance(j, ev(j, "READBACK_VERIFIED", observed_head_sha=COMMIT, observed_paths=bad))
        self.assertEqual(j["phase"], "CONFLICT")
        self.assertEqual(j["decision"], "FAIL_CLOSED_READBACK_BYTES")

    def test_retry_budget_is_bounded(self):
        j = self.journal(max_retries=2)
        j = advance(j, ev(j, "RETRYABLE_ERROR", error="net"))
        j = advance(j, ev(j, "RETRYABLE_ERROR", error="net"))
        self.assertFalse(j["terminal"])
        j = advance(j, ev(j, "RETRYABLE_ERROR", error="net"))
        self.assertEqual(j["phase"], "BLOCKED")
        self.assertEqual(j["retry_count"], 3)

    def test_out_of_order_cannot_advance(self):
        j = self.journal()
        with self.assertRaisesRegex(TransitionError, "OUT_OF_ORDER"):
            advance(j, ev(j, "REF_PROMOTED", observed_head_sha=COMMIT))

    def test_identity_tamper_is_rejected(self):
        j = self.journal()
        j["identity"]["scientific_authority"]["version"] = "V999"
        with self.assertRaisesRegex(TransitionError, "IDENTITY_TAMPERED"):
            advance(j, ev(self.journal(), "PARENT_OBSERVED", observed_head_sha=PARENT))

    def test_scientific_authority_is_invariant(self):
        j = self.journal()
        original = copy.deepcopy(j["identity"]["scientific_authority"])
        j = advance(j, ev(j, "COMMIT_CREATED", commit_sha=COMMIT, parent_sha=PARENT))
        j = advance(j, ev(j, "REF_PROMOTED", observed_head_sha=COMMIT))
        j = advance(j, ev(j, "READBACK_VERIFIED", observed_head_sha=COMMIT, observed_paths=PATHS))
        self.assertEqual(j["identity"]["scientific_authority"], original)

    def test_operation_identity_mismatch_rejected(self):
        j = self.journal()
        e = ev(j, "PARENT_OBSERVED", observed_head_sha=PARENT)
        e["operation_id"] = "different"
        with self.assertRaisesRegex(TransitionError, "OPERATION_ID_MISMATCH"):
            advance(j, e)


if __name__ == "__main__":
    unittest.main()
