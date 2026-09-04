#!/usr/bin/env python3
"""Atomic multi-file GitHub writer for QROS persistent state.

The transaction is compare-and-swap: the branch must equal expected_main_sha
both before object creation and immediately before a non-force ref update.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class CASConflict(RuntimeError):
    pass


class GitHubCAS:
    def __init__(self, repository: str, token: str, api_url: str = "https://api.github.com") -> None:
        if repository.count("/") != 1:
            raise ValueError("repository must be owner/name")
        self.repository = repository
        self.token = token
        self.api_url = api_url.rstrip("/")

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        req = urllib.request.Request(
            self.api_url + path,
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "qros-persistent-git-cas/1",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:2000]
            if exc.code in {409, 422}:
                raise CASConflict(f"GitHub rejected compare-and-swap: {exc.code} {detail}") from exc
            raise RuntimeError(f"GitHub API error: {exc.code} {detail}") from exc

    def ref_sha(self, branch: str) -> str:
        encoded = urllib.parse.quote(branch, safe="")
        return self.request("GET", f"/repos/{self.repository}/git/ref/heads/{encoded}")["object"]["sha"]

    def apply(self, *, branch: str, expected_main_sha: str, files: dict[str, str], message: str) -> str:
        if self.ref_sha(branch) != expected_main_sha:
            raise CASConflict("branch changed before transaction")
        parent = self.request("GET", f"/repos/{self.repository}/git/commits/{expected_main_sha}")
        elements = []
        for path in sorted(files):
            blob = self.request("POST", f"/repos/{self.repository}/git/blobs", {
                "content": files[path], "encoding": "utf-8",
            })
            elements.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        tree = self.request("POST", f"/repos/{self.repository}/git/trees", {
            "base_tree": parent["tree"]["sha"], "tree": elements,
        })
        commit = self.request("POST", f"/repos/{self.repository}/git/commits", {
            "message": message, "tree": tree["sha"], "parents": [expected_main_sha],
        })
        if self.ref_sha(branch) != expected_main_sha:
            raise CASConflict("branch changed before promotion")
        encoded = urllib.parse.quote(branch, safe="")
        promoted = self.request("PATCH", f"/repos/{self.repository}/git/refs/heads/{encoded}", {
            "sha": commit["sha"], "force": False,
        })
        if promoted["object"]["sha"] != commit["sha"]:
            raise RuntimeError("promoted ref does not match created commit")
        return commit["sha"]


def parse_file(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError("--file must be REPO_PATH=LOCAL_PATH")
    repo_path, local_path = value.split("=", 1)
    if repo_path.startswith("/") or ".." in Path(repo_path).parts:
        raise ValueError("unsafe repository path")
    return repo_path, Path(local_path).read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--expected-main-sha", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--file", action="append", required=True)
    parser.add_argument("--token-env", default="QROS_GITHUB_TOKEN")
    args = parser.parse_args()
    token = os.environ.get(args.token_env)
    if not token:
        raise RuntimeError(f"missing token environment variable {args.token_env}")
    files = dict(parse_file(value) for value in args.file)
    sha = GitHubCAS(args.repository, token).apply(
        branch=args.branch, expected_main_sha=args.expected_main_sha, files=files, message=args.message
    )
    print(json.dumps({"status": "PASS_CAS", "commit_sha": sha, "force": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
