from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
SYNC_VERSIONS_PATH = REPO_ROOT / "scripts" / "sync_versions.py"
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

SPEC = importlib.util.spec_from_file_location("sync_versions", SYNC_VERSIONS_PATH)
assert SPEC.loader is not None
sync_versions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_versions)


class ChangelogPromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._content = (
            "# Changelog\n"
            "\n"
            "## Unreleased\n"
            "\n"
            "- **Feature**: alpha\n"
            "\n"
            "## 1.6.1\n"
            "\n"
            "- **Fix**: beta\n"
        )

    def test_promotes_top_unreleased_section_to_released_version(self) -> None:
        promoted = sync_versions._replace_changelog_released(self._content, "1.6.2")
        self.assertTrue(promoted.startswith("# Changelog\n\n## Unreleased\n\n## 1.6.2\n\n- **Feature**: alpha"))
        self.assertIn("\n## 1.6.1\n", promoted)

    def test_is_idempotent_for_already_released_version(self) -> None:
        once = sync_versions._replace_changelog_released(self._content, "1.6.2")
        twice = sync_versions._replace_changelog_released(once, "1.6.2")
        self.assertEqual(once, twice)

    def test_raises_when_heading_already_promoted_and_version_missing(self) -> None:
        promoted = sync_versions._replace_changelog_released(self._content, "1.6.2")
        with self.assertRaisesRegex(ValueError, "Unreleased"):
            sync_versions._replace_changelog_released(
                promoted.replace("## Unreleased\n", "", 1),
                "1.6.3",
            )

    def test_raises_without_changelog_title(self) -> None:
        with self.assertRaisesRegex(ValueError, "title line"):
            sync_versions._replace_changelog_released("no title here\n", "1.6.2")

    def test_raises_without_unreleased_section(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unreleased"):
            sync_versions._replace_changelog_released("# Changelog\n\n## 1.6.1\n", "1.6.2")

    def test_empty_content_is_noop(self) -> None:
        self.assertEqual("", sync_versions._replace_changelog_released("", "1.6.2"))


if __name__ == "__main__":
    unittest.main()