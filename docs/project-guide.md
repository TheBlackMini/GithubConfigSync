# Project guide

A summary of [PROJECT.md](https://github.com/TheBlackMini/GithubConfigSync/blob/main/PROJECT.md) — the single source of truth for
status, architecture, security, and workflow.

## Current status

<!-- VERSION:START -->
- Integration version: `1.7.1`
- Add-on version: `1.7.1`
- Channel: `stable`
- Release tag: `v1.7.1`
<!-- VERSION:END -->

- **Repo:** `TheBlackMini/GithubConfigSync` — trunk-based: `main` is the only branch (development and releases happen directly on `main`)
- **Add-on path:** `addons/github-config-sync/`
- **Integration path:** `custom_components/github_config_sync/`
- **App source:** `addons/github-config-sync/rootfs/app/`
- **Version source of truth:** `config.yaml` (auto-read at startup)

## Architecture

1. **Integration** (`custom_components/github_config_sync/`) — config flow for
   GitHub token setup, button entities for sync/clean actions, sensor entities
   for sync status.
2. **Add-on** (`addons/github-config-sync/`) — ingress web UI running a Flask
   server that handles OAuth Device Flow, repository management (list, create,
   adopt), config sync (upload, clean-upload, clean-repo), and settings
   persistence via the HA options API.
3. **Sync engine** (`rootfs/app/sync/`) — core logic in `engine.py` (planning,
   diffing, upload, clean, version snapshots), `github_client.py` (GitHub API
   with rate-limit retry/backoff), `models.py`, `errors.py`, and `hashing.py`
   (content hashing for change detection).

## Security

- Tokens are never persisted or logged in plaintext; the UI masks them.
- Sensitive-file scanning **blocks** uploads (since v1.5.0) and writes
  `SECURITY_UPLOAD_WARNINGS.md`.
- `_local_path_for` validates resolved paths stay inside the allowed root map.
- Diagnostics redaction strips `ghp_`, `github_pat_`, `gho_`, bearer tokens,
  key-value secrets, and credential URLs.

## Release workflow

1. Trunk-based: commit work directly to `main` (no feature branches); add the changes as notes under `## Unreleased` in the three changelogs.
2. Bump version in `config.yaml` (single source of truth).
3. Run `python3 scripts/sync_versions.py --integration X.Y.Z --channel stable` — bumps `manifest.json`,
   `hacs.json`, the `VERSION` blocks in the READMEs and `PROJECT.md`/`project-guide.md`, and promotes the top
   `## Unreleased` changelog section into `## X.Y.Z` across the repo-root, add-on, and app changelogs.
4. Add any unreleased notes under the fresh `## Unreleased` heading before bumping, so each release
   notes section only contains that release's changes.
5. Commit, push to `main`, tag `vX.Y.Z`, and run
   `python3 scripts/create_release.py` — it publishes a GitHub release whose body is the version's
   changelog section, which is exactly what Home Assistant's update page shows on top of the
   changelog (the differences between the user's version and the update). Pre-release versions
   (e.g. `1.8.0-beta-1`) are automatically marked `--prerelease` so HA/HACS only surface them
   to users who opt into beta/pre-release tracks.

The full [PROJECT.md](https://github.com/TheBlackMini/GithubConfigSync/blob/main/PROJECT.md) contains the milestone history and the
per-tag release checklist.