#!/usr/bin/env python3
"""Unit tests for credentials, lake paths, and workspace 409 handling."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "softprobe-agent-qa" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import credentials  # noqa: E402
import softprobe_api  # noqa: E402


class CredentialsTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "credentials.json"
            with mock.patch.dict(os.environ, {"SOFTPROBE_EXPLORER_CREDENTIALS": str(path)}, clear=False):
                os.environ.pop("SOFTPROBE_EXPLORER_TOKEN", None)
                saved = credentials.save_credentials(
                    access_token="tok_abc123456789",
                    refresh_token="ref_1",
                    expires_at=9_999_999_999,
                    email="a@example.com",
                )
                self.assertEqual(saved, path)
                loaded = credentials.load_credentials()
                self.assertEqual(loaded["access_token"], "tok_abc123456789")
                self.assertEqual(loaded["email"], "a@example.com")
                self.assertTrue(path.stat().st_mode & 0o600)

    def test_env_token_overrides_file(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "SOFTPROBE_EXPLORER_TOKEN": "env-token-value",
                "SOFTPROBE_EXPLORER_BASE": "https://example.test",
            },
            clear=False,
        ):
            loaded = credentials.load_credentials()
            self.assertEqual(loaded["access_token"], "env-token-value")
            self.assertEqual(loaded["explorer_base"], "https://example.test")

    def test_mask_token(self) -> None:
        self.assertEqual(credentials.mask_token("abcdefghijklmnop"), "abcdef…mnop")


class LakePathTests(unittest.TestCase):
    def test_lake_path_prefixes(self) -> None:
        self.assertEqual(softprobe_api.lake_path("/v1/llm/sessions/search"), "/api/thelake/v1/llm/sessions/search")
        self.assertEqual(
            softprobe_api.lake_path("/api/thelake/v1/llm/traces/abc"),
            "/api/thelake/v1/llm/traces/abc",
        )
        self.assertEqual(softprobe_api.lake_path("llm/x"), "/api/thelake/v1/llm/x")


class GatewayTests(unittest.TestCase):
    def test_workspace_409_message(self) -> None:
        creds = {
            "access_token": "tok",
            "explorer_base": "https://explorer.test",
        }

        def fake_http(method, url, token=None, payload=None, timeout=60):
            raise softprobe_api.ApiError(
                "conflict",
                status=409,
                body={"code": softprobe_api.WORKSPACE_PICKER_CODE, "message": "Select a workspace"},
            )

        with mock.patch.object(softprobe_api, "bearer_token", return_value=("tok", creds)):
            with mock.patch.object(softprobe_api, "_http", side_effect=fake_http):
                with self.assertRaises(softprobe_api.ApiError) as ctx:
                    softprobe_api.gateway_request("GET", "/api/thelake/v1/llm/sessions/x")
                self.assertEqual(ctx.exception.status, 409)
                self.assertIn("select-workspace", str(ctx.exception))

    def test_list_workspaces_path(self) -> None:
        creds = {"access_token": "tok", "explorer_base": "https://explorer.test"}
        calls: list[tuple[str, str]] = []

        def fake_http(method, url, token=None, payload=None, timeout=60):
            calls.append((method, url))
            return 200, {"workspaces": [{"id": "w1", "name": "One"}]}

        with mock.patch.object(softprobe_api, "bearer_token", return_value=("tok", creds)):
            with mock.patch.object(softprobe_api, "_http", side_effect=fake_http):
                status, body = softprobe_api.gateway_request(
                    "GET", "/api/workspaces", auto_workspace=False
                )
        self.assertEqual(status, 200)
        self.assertEqual(calls[0][1], "https://explorer.test/api/workspaces")
        self.assertEqual(body["workspaces"][0]["id"], "w1")


class InstallDryTests(unittest.TestCase):
    def test_single_skill_md_in_repo(self) -> None:
        skill_mds = list(ROOT.rglob("SKILL.md"))
        # Only the canonical skill (ignore anything under .git if present)
        skill_mds = [p for p in skill_mds if ".git" not in p.parts]
        self.assertEqual(len(skill_mds), 1)
        self.assertEqual(skill_mds[0], ROOT / "skills" / "softprobe-agent-qa" / "SKILL.md")


if __name__ == "__main__":
    unittest.main()
