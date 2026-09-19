from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import sync.precommit as precommit
from sync.errors import SyncError
from sync.precommit import (
    DEFAULT_TIMEOUT_SECONDS,
    HOOKS_CONFIG_NAME,
    effective_hooks_config,
    format_report,
    parse_report,
    run_precommit_gate,
)

FAILING_YAML_OUTPUT = """check yaml...............................................................Failed
- hook id: check-yaml
- description: Checks YAML files for parseable syntax
- exit code: 1

  yaml_bad.yaml: Failed to yaml decode (unclosed bracket '[' at line 1, column 4)
trim trailing whitespace.................................................Passed
"""


class ParseReportTests(unittest.TestCase):
    def test_parse_report_extracts_failed_hook_and_file(self) -> None:
        failed_hooks, failed_files = parse_report(FAILING_YAML_OUTPUT)
        self.assertEqual(failed_hooks, ["check-yaml"])
        self.assertEqual(len(failed_files), 1)
        self.assertIn("yaml_bad.yaml", failed_files[0])

    def test_parse_report_captures_unindented_detail_lines(self) -> None:
        output = """check for added large files...................................................Failed
- hook id: check-added-large-files
- exit code: 1

big.blob.zip (683 KB) exceeds 500 KB
"""
        failed_hooks, failed_files = parse_report(output)
        self.assertEqual(failed_hooks, ["check-added-large-files"])
        self.assertEqual(len(failed_files), 1)
        self.assertIn("big.blob.zip", failed_files[0])

    def test_parse_report_empty_output_is_clean(self) -> None:
        failed_hooks, failed_files = parse_report("")
        self.assertEqual(failed_hooks, [])
        self.assertEqual(failed_files, [])

    def test_parse_report_ignores_passed_sections(self) -> None:
        output = """check yaml...............................................................Passed
detect private key.......................................................Passed
"""
        failed_hooks, failed_files = parse_report(output)
        self.assertEqual(failed_hooks, [])
        self.assertEqual(failed_files, [])


class ConfigDiscoveryTests(unittest.TestCase):
    def test_effective_hooks_config_prefers_user_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_root = Path(tmp)
            user_config = config_root / HOOKS_CONFIG_NAME
            user_config.write_text("repo: builtin", encoding="utf-8")
            found = effective_hooks_config(config_root)
            self.assertEqual(found, user_config)

    def test_effective_hooks_config_falls_back_to_bundled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            found = effective_hooks_config(Path(tmp))
            self.assertIsNotNone(found)
            self.assertTrue(found.is_file())

    def test_effective_hooks_config_returns_none_when_both_missing(self) -> None:
        with patch.object(precommit, "HOOKS_CONFIG_NAME", ".missing-config.yaml"):
            with tempfile.TemporaryDirectory() as tmp:
                found = effective_hooks_config(Path(tmp))
                self.assertIsNone(found)


class RunGateModeTests(unittest.TestCase):
    def test_disabled_always_passes(self) -> None:
        result = run_precommit_gate([("a.yaml", Path("/nope/a.yaml"))], Path("/nope"), mode="disabled")
        self.assertTrue(result.passed)

    def test_no_files_passes(self) -> None:
        result = run_precommit_gate([], Path("/nope"))
        self.assertTrue(result.passed)

    def test_missing_config_skips_with_pass(self) -> None:
        with patch(
            "sync.precommit.effective_hooks_config",
            return_value=None,
        ):
            result = run_precommit_gate([("a.yaml", Path("/nope/a.yaml"))], Path("/nope"))
        self.assertTrue(result.passed)
        self.assertIn("no pre-commit config", result.output)

    def test_missing_prek_skips_with_pass(self) -> None:
        with patch("sync.precommit.precommit_available", return_value=False):
            result = run_precommit_gate([("a.yaml", Path("/nope/a.yaml"))], Path("/nope"))
        self.assertTrue(result.passed)
        self.assertIn("prek not available", result.output)

    def test_missing_git_skips_with_pass(self) -> None:
        with patch("sync.precommit.precommit_available", return_value=True), patch(
            "sync.precommit.git_available", return_value=False
        ):
            result = run_precommit_gate([("a.yaml", Path("/nope/a.yaml"))], Path("/nope"))
        self.assertTrue(result.passed)
        self.assertIn("git not available", result.output)

    def test_run_error_is_a_failure(self) -> None:
        def boom(*_) -> None:
            raise SyncError("git init failed for pre-commit worktree: broken")

        with patch("sync.precommit.precommit_available", return_value=True), patch(
            "sync.precommit.git_available", return_value=True
        ), patch("sync.precommit._stage_worktree", side_effect=boom):
            result = run_precommit_gate([("a.yaml", Path("/nope/a.yaml"))], Path("/nope"))
        self.assertFalse(result.passed)
        self.assertIn("pre-commit gate error", result.output)

    def test_stage_worktree_rejects_unsafe_paths(self) -> None:
        with patch("sync.precommit.precommit_available", return_value=True), patch(
            "sync.precommit.git_available", return_value=True
        ):
            result = run_precommit_gate(
                [("../escape.yaml", Path("/etc/escape.yaml"))],
                Path("/nope"),
            )
        self.assertFalse(result.passed)
        self.assertIn("pre-commit gate error", result.output)


def _prek_bin() -> str | None:
    explicit = os.environ.get("PREK_BIN")
    if explicit:
        return explicit
    return shutil.which("prek")


class RunGateIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(_prek_bin() is not None, "prek not installed")
    def test_gate_blocks_violations_and_passes_good_files(self) -> None:
        prek_bin = _prek_bin()
        assert prek_bin is not None
        bin_dir = str(Path(prek_bin).resolve().parent)
        env = {"PATH": f"{bin_dir}:{os.environ.get('PATH', '')}", "PREK_COLOR": "never"}

        with tempfile.TemporaryDirectory() as tmp:
            config_root = Path(tmp)
            bad_file = config_root / "bad.yaml"
            bad_file.write_text("x: [1, 2\n", encoding="utf-8")
            good_file = config_root / "good.yaml"
            good_file.write_text("x: 1\n", encoding="utf-8")
            user_config = config_root / HOOKS_CONFIG_NAME
            user_config.write_text(
                "repos:\n"
                "  - repo: builtin\n"
                "    hooks:\n"
                "      - id: check-yaml\n"
                "      - id: trailing-whitespace\n",
                encoding="utf-8",
            )

            with patch("sync.precommit._prek_env", return_value=env):
                failing = run_precommit_gate(
                    [("bad.yaml", bad_file)],
                    config_root,
                    timeout=DEFAULT_TIMEOUT_SECONDS,
                )
                passing = run_precommit_gate(
                    [("good.yaml", good_file)],
                    config_root,
                    timeout=DEFAULT_TIMEOUT_SECONDS,
                )

        self.assertFalse(failing.passed)
        self.assertEqual(failing.exit_code, 1)
        self.assertIn("check-yaml", failing.failed_hooks)
        self.assertTrue(passing.passed)
        self.assertEqual(passing.exit_code, 0)

    def test_format_report_includes_failed_hooks_and_files(self) -> None:
        from sync.precommit import PrecommitResult

        result = PrecommitResult(
            passed=False,
            exit_code=1,
            output="",
            failed_hooks=("check-yaml",),
            failed_files=("bad.yaml: boom",),
        )
        report = format_report(result)
        self.assertIn("exited with code 1", report)
        self.assertIn("- hook: check-yaml", report)
        self.assertIn("- bad.yaml: boom", report)


if __name__ == "__main__":
    unittest.main()