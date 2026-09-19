from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import MagicMock, call, patch

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sync.engine import SyncEngine
from sync.errors import SyncError
from sync.models import SyncConfig, SyncPlan
from sync.precommit import PrecommitResult


class SyncEngineTests(unittest.TestCase):
    def test_plan_detects_added_changed_removed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "new.yaml").write_text("new", encoding="utf-8")
            (root / "changed.yaml").write_text("new-value", encoding="utf-8")
            addon_root = Path(tmp) / "addon_configs"
            (addon_root / "apps").mkdir(parents=True)
            (addon_root / "apps" / "kitchen.yaml").write_text("id: app", encoding="utf-8")

            config = SyncConfig(
                repository="owner/repo",
                branch="main",
                token="token",
                config_root=str(root),
                addon_config_root="/addon_configs",
                dry_run=False,
                include_addon_configs=True,
            )

            previous = {
                "changed.yaml": "old-hash",
                "removed.yaml": "removed-hash",
                "addon_configs/apps/old.yaml": "old-addon",
            }

            engine = SyncEngine(config, previous_hash_index=previous)
            plan, _ = engine.plan()

            self.assertEqual(plan.added, ["addon_configs/apps/kitchen.yaml", "new.yaml"])
            self.assertEqual(plan.changed, ["changed.yaml"])
            self.assertEqual(plan.removed, ["addon_configs/apps/old.yaml", "removed.yaml"])
            self.assertIn("addon_configs/apps/kitchen.yaml", plan.added)

    def test_run_dry_run_returns_counts_without_github_calls(self) -> None:
        config = SyncConfig(
            repository="owner/repo",
            branch="main",
            token="token",
            config_root=".",
            addon_config_root="/addon_configs",
            dry_run=True,
            include_addon_configs=True,
        )
        plan = SyncPlan(added=["a.yaml"], changed=["b.yaml"], removed=["c.yaml"], total_files=2)

        with patch("sync.engine.GitHubClient") as client_cls:
            engine = SyncEngine(config, previous_hash_index={})
            result = engine.run(plan)

        self.assertEqual(result.synced_count, 2)
        self.assertEqual(result.deleted_count, 1)
        self.assertEqual(result.skipped_count, 0)
        self.assertIn("Dry run completed", result.message)
        client_cls.return_value.put_content.assert_not_called()
        client_cls.return_value.delete_content.assert_not_called()

    def test_run_live_upserts_deletes_and_skips_missing_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "added.yaml").write_text("added", encoding="utf-8")
            (root / "changed.yaml").write_text("changed", encoding="utf-8")

            config = SyncConfig(
                repository="owner/repo",
                branch="main",
                token="token",
                config_root=str(root),
                addon_config_root="/addon_configs",
                dry_run=False,
                include_addon_configs=True,
                precommit_mode="disabled",
            )
            plan = SyncPlan(
                added=["added.yaml", "missing.yaml"],
                changed=["changed.yaml"],
                removed=["removed.yaml", "unknown.yaml"],
                total_files=2,
            )

            fake_client = MagicMock()
            fake_client.get_content.side_effect = [
                {"sha": "a1"},
                {"sha": "b1"},
                {"sha": "c1"},
                None,
            ]

            with patch("sync.engine.GitHubClient", return_value=fake_client):
                engine = SyncEngine(config, previous_hash_index={})
                result = engine.run(plan)

            self.assertEqual(result.synced_count, 2)
            self.assertEqual(result.deleted_count, 1)
            self.assertEqual(result.skipped_count, 2)
            self.assertIn("Sync completed", result.message)
            self.assertEqual(fake_client.put_content.call_count, 2)
            self.assertEqual(fake_client.delete_content.call_count, 1)

    def test_run_live_retries_on_sha_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.yaml").write_text("a", encoding="utf-8")

            config = SyncConfig(
                repository="owner/repo",
                branch="main",
                token="token",
                config_root=str(root),
                addon_config_root="/addon_configs",
                dry_run=False,
                include_addon_configs=True,
                precommit_mode="disabled",
            )
            plan = SyncPlan(added=["a.yaml"], changed=[], removed=[], total_files=1)

            fake_client = MagicMock()
            fake_client.get_content.side_effect = [
                {"sha": "oldsha"},
                {"sha": "newsha"},
            ]
            fake_client.put_content.side_effect = [
                Exception('GitHub API error HTTP 409 for PUT https://api.github.com/repos/owner/repo/contents/a.yaml: {"status":"409"}'),
                {"content": {"html_url": "https://example.com"}},
            ]

            with patch("sync.engine.GitHubClient", return_value=fake_client):
                engine = SyncEngine(config, previous_hash_index={})
                result = engine.run(plan)

            self.assertEqual(result.synced_count, 1)
            self.assertEqual(fake_client.put_content.call_count, 2)

    def test_put_content_retries_on_sha_conflict(self) -> None:
        from sync.github_client import GitHubClient
        from sync.errors import SyncError

        client = GitHubClient(repository="owner/repo", branch="main", token="token")
        calls = {"count": 0}

        def fake_request(method: str, url: str, payload=None):  # noqa: ANN001
            calls["count"] += 1
            if calls["count"] == 1:
                raise SyncError(
                    'GitHub API error HTTP 409 for PUT https://api.github.com/repos/owner/repo/contents/.gitignore: {"status":"409"}'
                )
            return {"content": {"path": ".gitignore"}}

        with patch.object(GitHubClient, "_request_json", side_effect=fake_request), patch.object(
            GitHubClient, "get_content", return_value={"sha": "refreshed"}
        ):
            result = client.put_content(".gitignore", b"data", "update .gitignore", sha="stale")

        self.assertEqual(result["content"]["path"], ".gitignore")
        self.assertEqual(calls["count"], 2)

    def test_run_live_can_be_cancelled_between_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.yaml").write_text("1", encoding="utf-8")
            (root / "two.yaml").write_text("2", encoding="utf-8")

            config = SyncConfig(
                repository="owner/repo",
                branch="main",
                token="token",
                config_root=str(root),
                addon_config_root="/addon_configs",
                dry_run=False,
                include_addon_configs=True,
                precommit_mode="disabled",
            )
            plan = SyncPlan(added=["one.yaml", "two.yaml"], changed=[], removed=[], total_files=2)
            fake_client = MagicMock()
            fake_client.get_content.return_value = None
            calls = {"count": 0}

            def cancel_checker() -> bool:
                calls["count"] += 1
                return calls["count"] > 1

            with patch("sync.engine.GitHubClient", return_value=fake_client):
                engine = SyncEngine(config, previous_hash_index={})
                engine.set_cancel_checker(cancel_checker)
                result = engine.run(plan)

            self.assertTrue(result.cancelled)
            self.assertEqual(result.synced_count, 1)
            self.assertEqual(fake_client.put_content.call_count, 1)

    def test_run_live_reports_progress_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.yaml").write_text("1", encoding="utf-8")

            config = SyncConfig(
                repository="owner/repo",
                branch="main",
                token="token",
                config_root=str(root),
                addon_config_root="/addon_configs",
                dry_run=False,
                include_addon_configs=True,
                precommit_mode="disabled",
            )
            plan = SyncPlan(added=["one.yaml"], changed=[], removed=[], total_files=1)
            fake_client = MagicMock()
            fake_client.get_content.return_value = None

            with patch("sync.engine.GitHubClient", return_value=fake_client):
                engine = SyncEngine(config, previous_hash_index={})
                progress_events: list[dict[str, object]] = []
                engine.set_progress_callback(progress_events.append)
                engine.run(plan)

            self.assertTrue(
                any(
                    event.get("current_action") == "upserting"
                    and event.get("current_path") == ""
                    for event in progress_events
                )
            )

    def test_delete_remote_tree_wipes_nested_tree(self) -> None:
        config = SyncConfig(
            repository="owner/repo",
            branch="main",
            token="token",
            config_root=".",
            addon_config_root="/addon_configs",
            dry_run=False,
            include_addon_configs=True,
        )
        fake_client = MagicMock()
        fake_client.list_directory_contents.side_effect = [
            [
                {"type": "dir", "name": "config", "path": "config"},
                {"type": "file", "name": "root.yaml", "path": "root.yaml", "sha": "rootsha"},
            ],
            [
                {"type": "file", "name": "nested.yaml", "path": "config/nested.yaml", "sha": "nestedsha"},
            ],
        ]

        with patch("sync.engine.GitHubClient", return_value=fake_client):
            engine = SyncEngine(config, previous_hash_index={})
            engine._delete_remote_tree("")

        fake_client.list_directory_contents.assert_any_call("")
        fake_client.delete_content.assert_any_call(
            path="config/nested.yaml",
            sha="nestedsha",
            message="sync: delete config/nested.yaml",
        )
        fake_client.delete_content.assert_any_call(
            path="root.yaml",
            sha="rootsha",
            message="sync: delete root.yaml",
        )

    def test_clean_remote_tree_uses_git_tree_delete_flow(self) -> None:
        config = SyncConfig(
            repository="owner/repo",
            branch="main",
            token="token",
            config_root=".",
            addon_config_root="/addon_configs",
            dry_run=False,
            include_addon_configs=True,
        )
        fake_client = MagicMock()
        fake_client.get_branch_head_sha.return_value = "headsha"
        fake_client.get_commit_tree_sha.return_value = "basetree"
        fake_client.list_directory_contents.side_effect = [
            [
                {"type": "file", "path": "root.yaml", "sha": "rootsha"},
                {"type": "dir", "path": "nested", "name": "nested"},
            ],
            [{"type": "file", "path": "nested/inside.yaml", "sha": "innersha"}],
        ]
        fake_client.create_git_tree.return_value = {"sha": "treesha"}
        fake_client.create_git_commit.return_value = {"sha": "commitsha"}

        with patch("sync.engine.GitHubClient", return_value=fake_client):
            engine = SyncEngine(config, previous_hash_index={})
            engine.clean_remote_tree()

        fake_client.get_branch_head_sha.assert_called_once()
        fake_client.get_commit_tree_sha.assert_called_once_with("headsha")
        fake_client.create_git_tree.assert_called_once()
        fake_client.create_git_commit.assert_called_once_with(
            message="sync: fast clean remote tree",
            tree_sha="treesha",
            parent_sha="headsha",
        )
        fake_client.update_branch_ref.assert_called_once_with("commitsha")

    def test_restore_repo_skeleton_uses_app_root_assets(self) -> None:
        config = SyncConfig(
            repository="owner/repo",
            branch="main",
            token="token",
            config_root=".",
            addon_config_root="/addon_configs",
            dry_run=False,
            include_addon_configs=True,
        )
        fake_client = MagicMock()
        fake_client.list_directory_contents.return_value = []

        with patch("sync.engine.GitHubClient", return_value=fake_client), patch("sync.engine.Path.exists", return_value=True), patch(
            "sync.engine.Path.read_bytes", return_value=b"content"
        ):
            engine = SyncEngine(config, previous_hash_index={})
            engine.restore_repo_skeleton()

        self.assertTrue(fake_client.put_content.called)

    def test_whitelist_plan_only_includes_matching_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "configuration.yaml").write_text("a: 1", encoding="utf-8")
            (root / "notes.md").write_text("notes", encoding="utf-8")
            (root / "media").mkdir()
            (root / "media" / "clip.mp4").write_bytes(b"png")

            config = SyncConfig(
                repository="owner/repo",
                branch="main",
                token="token",
                config_root=str(root),
                addon_config_root="/addon_configs",
                dry_run=True,
                sync_mode="whitelist",
                sync_include_patterns=("*.yaml",),
            )

            engine = SyncEngine(config, previous_hash_index={})
            plan, _ = engine.plan()

            self.assertEqual(plan.added, ["configuration.yaml"])
            self.assertNotIn("notes.md", plan.added)
            self.assertNotIn("media/clip.mp4", plan.added)

    def test_exclude_patterns_filter_in_blacklist_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "configuration.yaml").write_text("a: 1", encoding="utf-8")
            (root / "debug.log").write_text("log", encoding="utf-8")

            config = SyncConfig(
                repository="owner/repo",
                branch="main",
                token="token",
                config_root=str(root),
                addon_config_root="/addon_configs",
                dry_run=True,
                sync_mode="blacklist",
                sync_exclude_patterns=("*.log",),
            )

            engine = SyncEngine(config, previous_hash_index={})
            plan, _ = engine.plan()

            self.assertEqual(plan.added, ["configuration.yaml"])
            self.assertNotIn("debug.log", plan.added)

    def test_files_falling_off_whitelist_are_not_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "configuration.yaml").write_text("a: 1", encoding="utf-8")

            config = SyncConfig(
                repository="owner/repo",
                branch="main",
                token="token",
                config_root=str(root),
                addon_config_root="/addon_configs",
                dry_run=True,
                sync_mode="whitelist",
                sync_include_patterns=("*.yaml",),
            )

            previous = {"configuration.yaml": "old-hash", "notes.md": "old-md"}
            engine = SyncEngine(config, previous_hash_index=previous)
            plan, _ = engine.plan()

            self.assertEqual(plan.added, [])
            self.assertEqual(plan.changed, ["configuration.yaml"])
            self.assertEqual(plan.removed, [])

    def test_empty_whitelist_syncs_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "configuration.yaml").write_text("a: 1", encoding="utf-8")

            config = SyncConfig(
                repository="owner/repo",
                branch="main",
                token="token",
                config_root=str(root),
                addon_config_root="/addon_configs",
                dry_run=True,
                sync_mode="whitelist",
                sync_include_patterns=(),
            )

            engine = SyncEngine(config, previous_hash_index={})
            plan, _ = engine.plan()

            self.assertEqual(plan.added, [])
            self.assertEqual(plan.removed, [])

    def test_clean_scope_preserves_excluded_and_out_of_scope_paths(self) -> None:
        config = SyncConfig(
            repository="owner/repo",
            branch="main",
            token="token",
            config_root=".",
            addon_config_root="/addon_configs",
            dry_run=False,
            include_addon_configs=True,
            sync_mode="whitelist",
            sync_include_patterns=("*.yaml",),
            clean_preserve_paths=("docs",),
        )
        fake_client = MagicMock()
        fake_client.get_branch_head_sha.return_value = "headsha"
        fake_client.get_commit_tree_sha.return_value = "basetree"
        fake_client.list_directory_contents.side_effect = [
            [
                {"type": "file", "path": "root.yaml", "sha": "rootsha"},
                {"type": "file", "path": "notes.md", "sha": "notesha"},
                {"type": "dir", "path": "docs", "name": "docs"},
                {"type": "dir", "path": "nested", "name": "nested"},
            ],
            [],
            [],
        ]
        fake_client.create_git_tree.return_value = {"sha": "treesha"}
        fake_client.create_git_commit.return_value = {"sha": "commitsha"}

        with patch("sync.engine.GitHubClient", return_value=fake_client):
            engine = SyncEngine(config, previous_hash_index={})
            engine.clean_remote_tree()

        deletions = fake_client.create_git_tree.call_args.kwargs["tree"]
        self.assertEqual([item["path"] for item in deletions], ["root.yaml"])
        self.assertNotIn("notes.md", [item["path"] for item in deletions])
        self.assertNotIn("docs", [item["path"] for item in deletions])

    def test_precommit_gate_blocks_live_run_in_enabled_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.yaml").write_text("a: 1", encoding="utf-8")

            config = SyncConfig(
                repository="owner/repo",
                branch="main",
                token="token",
                config_root=str(root),
                addon_config_root="/addon_configs",
                dry_run=False,
                include_addon_configs=True,
                precommit_mode="enabled",
            )
            plan = SyncPlan(added=["a.yaml"], changed=[], removed=[], total_files=1)
            failing = PrecommitResult(
                passed=False,
                exit_code=1,
                output="",
                failed_hooks=("check-yaml",),
                failed_files=("a.yaml: failed to decode",),
            )

            fake_client = MagicMock()
            with patch("sync.engine.GitHubClient", return_value=fake_client), patch(
                "sync.engine.run_precommit_gate", return_value=failing
            ):
                engine = SyncEngine(config, previous_hash_index={})
                with self.assertRaises(SyncError) as ctx:
                    engine.run(plan)

        self.assertIn("Pre-commit gate blocked", str(ctx.exception))
        self.assertIn("check-yaml", str(ctx.exception))
        fake_client.put_content.assert_not_called()
        fake_client.delete_content.assert_not_called()

    def test_precommit_gate_warn_mode_logs_and_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.yaml").write_text("a: 1", encoding="utf-8")

            config = SyncConfig(
                repository="owner/repo",
                branch="main",
                token="token",
                config_root=str(root),
                addon_config_root="/addon_configs",
                dry_run=False,
                include_addon_configs=True,
                precommit_mode="warn",
            )
            plan = SyncPlan(added=["a.yaml"], changed=[], removed=[], total_files=1)
            logs: list[str] = []
            failing = PrecommitResult(
                passed=False,
                exit_code=1,
                output="",
                failed_hooks=("check-yaml",),
                failed_files=("a.yaml: failed to decode",),
            )

            fake_client = MagicMock()
            fake_client.get_content.return_value = None
            with patch("sync.engine.GitHubClient", return_value=fake_client), patch(
                "sync.engine.run_precommit_gate", return_value=failing
            ):
                engine = SyncEngine(config, previous_hash_index={})
                engine.set_log_callback(logs.append)
                result = engine.run(plan)

        self.assertEqual(result.synced_count, 1)
        self.assertEqual(fake_client.put_content.call_count, 1)
        self.assertTrue(any("check-yaml" in line for line in logs))

    def test_precommit_gate_disabled_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.yaml").write_text("a: 1", encoding="utf-8")

            config = SyncConfig(
                repository="owner/repo",
                branch="main",
                token="token",
                config_root=str(root),
                addon_config_root="/addon_configs",
                dry_run=False,
                include_addon_configs=True,
                precommit_mode="disabled",
            )
            plan = SyncPlan(added=["a.yaml"], changed=[], removed=[], total_files=1)

            fake_client = MagicMock()
            fake_client.get_content.return_value = None
            with patch("sync.engine.GitHubClient", return_value=fake_client), patch(
                "sync.engine.run_precommit_gate"
            ) as gate:
                engine = SyncEngine(config, previous_hash_index={})
                engine.run(plan)

        gate.assert_not_called()
        self.assertEqual(fake_client.put_content.call_count, 1)

    def test_precommit_gate_runs_before_any_upload_using_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.yaml").write_text("a: 1", encoding="utf-8")

            config = SyncConfig(
                repository="owner/repo",
                branch="main",
                token="token",
                config_root=str(root),
                addon_config_root="/addon_configs",
                dry_run=False,
                include_addon_configs=True,
                precommit_mode="enabled",
            )
            plan = SyncPlan(added=["a.yaml"], changed=[], removed=[], total_files=1)
            passed = PrecommitResult(passed=True, exit_code=0, output="")

            fake_client = MagicMock()
            fake_client.get_content.return_value = None
            with patch("sync.engine.GitHubClient", return_value=fake_client), patch(
                "sync.engine.run_precommit_gate", return_value=passed
            ) as gate:
                engine = SyncEngine(config, previous_hash_index={})
                result = engine.run(plan)

        gate.assert_called_once()
        files_arg = gate.call_args.kwargs["files"]
        self.assertEqual(len(files_arg), 1)
        relative, local_path = files_arg[0]
        self.assertEqual(relative, "a.yaml")
        self.assertEqual(local_path, root / "a.yaml")
        self.assertEqual(result.synced_count, 1)


if __name__ == "__main__":
    unittest.main()
