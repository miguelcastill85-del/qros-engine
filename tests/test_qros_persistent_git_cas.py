import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("git_cas", ROOT / "scripts/qros_persistent_git_cas.py")
git_cas = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(git_cas)


class FakeCAS(git_cas.GitHubCAS):
    def __init__(self, refs):
        super().__init__("owner/repo", "not-a-real-token")
        self.refs = list(refs)
        self.calls = []

    def ref_sha(self, branch):
        self.calls.append(("REF", branch))
        return self.refs.pop(0)

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET" and "/git/commits/" in path:
            return {"tree": {"sha": "base-tree"}}
        if path.endswith("/git/blobs"):
            return {"sha": "blob-" + str(len(self.calls))}
        if path.endswith("/git/trees"):
            return {"sha": "new-tree"}
        if path.endswith("/git/commits"):
            return {"sha": "new-commit"}
        if "/git/refs/heads/" in path:
            return {"object": {"sha": "new-commit"}}
        raise AssertionError((method, path, payload))


class GitCASTests(unittest.TestCase):
    def test_atomic_non_force_transaction(self):
        expected = "a" * 40
        api = FakeCAS([expected, expected])
        result = api.apply(branch="main", expected_main_sha=expected,
                           files={"b.json": "B", "a.json": "A"}, message="canary")
        self.assertEqual(result, "new-commit")
        patch = [call for call in api.calls if call[0] == "PATCH"][0]
        self.assertEqual(patch[2], {"sha": "new-commit", "force": False})
        blob_paths = [call[1] for call in api.calls if call[0] == "POST" and call[1].endswith("/git/blobs")]
        self.assertEqual(len(blob_paths), 2)

    def test_conflict_before_objects(self):
        api = FakeCAS(["b" * 40])
        with self.assertRaisesRegex(git_cas.CASConflict, "before transaction"):
            api.apply(branch="main", expected_main_sha="a" * 40,
                      files={"a": "A"}, message="canary")

    def test_conflict_before_promotion(self):
        expected = "a" * 40
        api = FakeCAS([expected, "b" * 40])
        with self.assertRaisesRegex(git_cas.CASConflict, "before promotion"):
            api.apply(branch="main", expected_main_sha=expected,
                      files={"a": "A"}, message="canary")

    def test_unsafe_repo_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsafe"):
            git_cas.parse_file("../escape=x")


if __name__ == "__main__":
    unittest.main()
