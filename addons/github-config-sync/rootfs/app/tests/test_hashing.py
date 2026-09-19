from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sync.hashing import (
    IGNORE_DIRS,
    IGNORE_PATTERNS,
    build_hash_index,
    diff_hash_indexes,
    path_matches_patterns,
    _is_file_sensitive,
    scan_sensitive_files,
)


class HashingTests(unittest.TestCase):
    def test_build_hash_index_ignores_runtime_and_cache_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "automations.yaml").write_text("id: a", encoding="utf-8")
            (root / "appdaemon").mkdir()
            (root / "appdaemon" / "apps").mkdir(parents=True)
            (root / "appdaemon" / "appdaemon.yaml").write_text("secrets: true", encoding="utf-8")
            (root / "appdaemon" / "apps" / "lights.yaml").write_text("app: demo", encoding="utf-8")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "x.pyc").write_bytes(b"pyc")
            (root / ".storage").mkdir()
            (root / ".storage" / "core.config_entries").write_text("{}", encoding="utf-8")
            (root / ".cache").mkdir()
            (root / ".cache" / "brands").mkdir(parents=True)
            (root / ".cache" / "brands" / "icon.png").write_bytes(b"png")
            (root / "home-assistant.log").write_text("log", encoding="utf-8")

            index = build_hash_index(root)

            self.assertIn("automations.yaml", index)
            self.assertIn("appdaemon/appdaemon.yaml", index)
            self.assertIn("appdaemon/apps/lights.yaml", index)
            self.assertNotIn("__pycache__/x.pyc", index)
            self.assertNotIn(".storage/core.config_entries", index)
            self.assertNotIn(".cache/brands/icon.png", index)
            self.assertNotIn("home-assistant.log", index)

    def test_build_hash_index_ignores_sensitive_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "secrets.yaml").write_text("token: hidden", encoding="utf-8")
            (root / "my-secret-notes.yaml").write_text("token: hidden", encoding="utf-8")
            (root / ".storage").mkdir()
            (root / ".storage" / "core.config").write_text("{}", encoding="utf-8")

            index = build_hash_index(root)

            self.assertNotIn("secrets.yaml", index)
            self.assertNotIn("my-secret-notes.yaml", index)
            self.assertNotIn(".storage/core.config", index)

    def test_build_hash_index_ignores_sensitive_name_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "password.txt").write_text("hello", encoding="utf-8")
            (root / "api_key.yaml").write_text("key: 123", encoding="utf-8")
            (root / "oauth_token.json").write_text("token: abc", encoding="utf-8")
            (root / "safe.yaml").write_text("value: 1", encoding="utf-8")

            index = build_hash_index(root)

            self.assertNotIn("password.txt", index)
            self.assertNotIn("api_key.yaml", index)
            self.assertNotIn("oauth_token.json", index)
            self.assertIn("safe.yaml", index)

    def test_build_hash_index_ignores_sensitive_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text("bearer ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz", encoding="utf-8")
            (root / "safe.yaml").write_text("value: 1", encoding="utf-8")

            index = build_hash_index(root)

            self.assertNotIn("config.yaml", index)
            self.assertIn("safe.yaml", index)

    def test_is_file_sensitive_checks_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sensitive = root / "config.yaml"
            sensitive.write_text("password=secret123", encoding="utf-8")
            safe = root / "safe.yaml"
            safe.write_text("value: 1", encoding="utf-8")

            self.assertTrue(_is_file_sensitive(root, sensitive))
            self.assertFalse(_is_file_sensitive(root, safe))

    def test_ignore_patterns_match_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "HOME-ASSISTANT.LOG").write_text("log", encoding="utf-8")
            (root / "Database.DB").write_bytes(b"data")
            (root / "safe.yaml").write_text("value: 1", encoding="utf-8")

            index = build_hash_index(root)

            self.assertNotIn("HOME-ASSISTANT.LOG", index)
            self.assertNotIn("Database.DB", index)
            self.assertIn("safe.yaml", index)

    def test_scan_sensitive_files_skips_hard_ignored_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "big.db").write_text("password=secret123", encoding="utf-8")
            (root / "token.txt").write_text("abc", encoding="utf-8")
            (root / "safe.yaml").write_text("value: 1", encoding="utf-8")

            flagged = scan_sensitive_files(root)

            self.assertNotIn("big.db", flagged)
            self.assertIn("token.txt", flagged)
            self.assertNotIn("safe.yaml", flagged)

    def test_scan_sensitive_files_bounds_content_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "notes.txt"
            path.write_text("a" * (2 * 1024 * 1024) + "bearer ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz", encoding="utf-8")

            flagged = scan_sensitive_files(root)

            self.assertEqual(flagged, [])

    def test_default_ignore_patterns_cover_common_home_assistant_files(self) -> None:
        self.assertIn("secrets.yaml", IGNORE_PATTERNS)
        self.assertIn("ip_bans.yaml", IGNORE_PATTERNS)
        self.assertIn("known_devices.yaml", IGNORE_PATTERNS)
        self.assertIn(".storage", IGNORE_DIRS)
        self.assertIn(".cache", IGNORE_DIRS)
        self.assertIn(".ruff.toml", IGNORE_PATTERNS)
        self.assertIn("core.config_entries", IGNORE_PATTERNS)
        self.assertIn(".env", IGNORE_PATTERNS)

    def test_path_matches_patterns_matches_extensions_and_dirs(self) -> None:
        patterns = ("*.yaml", "themes", ".gitignore", "packages")
        self.assertTrue(path_matches_patterns("automations.yaml", patterns))
        self.assertTrue(path_matches_patterns("sub/dir/config.yaml", patterns))
        self.assertTrue(path_matches_patterns("themes/board/theme.yaml", patterns))
        self.assertTrue(path_matches_patterns("packages/kitchen.yaml", patterns))
        self.assertFalse(path_matches_patterns("notes.txt", patterns))
        self.assertFalse(path_matches_patterns(".github/workflows/ci.yml", patterns))
        self.assertFalse(path_matches_patterns("configuration.json", patterns))

    def test_path_matches_patterns_case_insensitive(self) -> None:
        self.assertTrue(path_matches_patterns("AUTOMATIONS.YAML", ("*.yaml",)))
        self.assertTrue(path_matches_patterns("Packages/Kitchen.YAML", ("packages", "*.yaml")))

    def test_diff_hash_indexes_returns_expected_added_changed_removed(self) -> None:
        previous = {"a.yaml": "1", "b.yaml": "2"}
        current = {"b.yaml": "3", "c.yaml": "4"}

        added, changed, removed = diff_hash_indexes(previous, current)

        self.assertEqual(added, ["c.yaml"])
        self.assertEqual(changed, ["b.yaml"])
        self.assertEqual(removed, ["a.yaml"])


if __name__ == "__main__":
    unittest.main()
