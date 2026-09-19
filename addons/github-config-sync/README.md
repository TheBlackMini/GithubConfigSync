# Github Config Sync App
[![CI](https://github.com/TheBlackMini/GithubConfigSync/actions/workflows/validate.yml/badge.svg)](https://github.com/TheBlackMini/GithubConfigSync/actions/workflows/validate.yml)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Add--on-03a9f4.svg)](https://www.home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://www.python.org/)
[![HASSfest](https://img.shields.io/badge/HASSfest-validated-success.svg)](https://developers.home-assistant.io/docs/add-ons/)
[![Release](https://img.shields.io/github/v/tag/TheBlackMini/GithubConfigSync?label=release)](https://github.com/TheBlackMini/GithubConfigSync/releases)

Containerized Home Assistant app with an ingress web UI for GitHub config sync operations. Current release details are tracked below in the version tracker. This is a sync tool, not a backup tool.

Authentication supports GitHub Device Flow or a fine-grained PAT scoped to the single target repository.

> **Note:** This is a Home Assistant **add-on**. Install it from the Add-on Store (**Settings → Add-ons → Add-on Store → Repositories**). It is not a HACS integration.


> **Warning:** Use caution with public repositories and with any two-way sync or other tools that can also write to the Home Assistant config tree, because they can cause local config loss or unexpected deletions.

This documentation and code were drafted with AI assistance and then reviewed/edited by the maintainer.

## Support me

If you find this project useful, and would like to help support its continued development, you can do so here:

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=000000)](https://www.buymeacoffee.com/mjp76)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=ffffff)](https://ko-fi.com/mjp76)
[![Octopus Energy — you get £50, I get £50](https://img.shields.io/badge/Octopus%20Energy-%E2%80%94%20you%20get%20%C2%A350%2C%20I%20get%20%C2%A350-14294A?style=for-the-badge&logo=octopus-energy&logoColor=ffffff)](https://share.octopus.energy/iron-moose-196)

## Version Tracker

<!-- VERSION:START -->
- Integration version: `1.6.0`
- Add-on version: `1.6.0`
- Channel: `stable`
- Release tag: `v1.6.0`
<!-- VERSION:END -->

## What it provides

- Ingress-ready web UI (`/api` + browser dashboard)
- Config persistence in `/data`
- GitHub repository connectivity checks
- Hash-based change detection (added/changed/removed files)
- Manual sync trigger with live progress tracking
- Scheduled sync with day-of-week and time-of-day selection
- Runtime status and log tail in the UI

## Architecture

- `server.py` is the app API surface and UI backend.
- `sync/engine.py` computes the plan from the current `/config` tree and the saved hash index.
- AppDaemon configs and apps under `/addon_configs/` are included in the normal sync scan.
- The mount-point checklist lets you include or exclude standard Home Assistant folders, and the recommended .gitignore keeps the ignore list aligned.
- `dry_run=true` stops after planning and returns the counts that would be applied for manual actions.
- `dry_run=false` probes the GitHub repository first, then performs upserts and deletes with the GitHub Contents API. Remote deletes never remove local files.
- Live uploads run a **pre-commit gate** first: the files about to be pushed are copied into a throwaway git worktree and checked with pre-commit hooks before any GitHub write happens; violations block the push (see **Pre-commit gate** below).
- **Clean Repo** always runs live, empties the remote repo with a fast git-tree reset, and restores the starter files in the same step.
- Repository creation uses the add-on flow and defaults to `ha-github-config-sync` with private visibility, with an optional public visibility choice.
- Runtime state is persisted in `/data/state.json`, `/data/hash_index.json`, `/data/device_flow.json`, and `/data/sync.log`.
- The stable local API contract is `/api/health`, `/api/status`, `/api/sync`, and `/api/diagnostics`.
- SHA conflict retries with exponential backoff (up to 3 attempts).
- Version is auto-read from `config.yaml` at startup (single source of truth).
- Default ignores include:
  - `.storage`, `.cloud`, `.cache`, `.venv`, `.vscode`, `.idea`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `tts`, `__pycache__`, `.git`
  - `home-assistant.log`, `home-assistant.log.*`, `home-assistant_v2.db`, `home-assistant_v2.db-*`, `secrets.yaml`, `ip_bans.yaml`, `known_devices.yaml`, `.ha_run.lock`, `*.db`, `*.sqlite`, `*.sqlite3`, `*.tmp`, `*.swp`, `*.pyc`, `*.log`, `.yaml_fix_backups`, `.yaml_fix_backups/*`, `.ha_fix_yaml.py`, `.smbdelete*`, `.DS_Store`, `Thumbs.db`
- Live uploads also write a root `SECURITY_UPLOAD_WARNINGS.md` file when suspicious files are skipped.
- The add-on writes an internal repo marker on newly created repositories so clean actions and the repo picker only target safe repos.

## Sync scope (allow-list mode)

The add-on syncs an **allow-list by default** (`sync_mode: whitelist`, editable in the **Sync scope** UI section):

- **Include patterns** — only files matching these fnmatch-style patterns (one per line, e.g. `*.yaml`, `*.json`, `themes`, `packages`) are uploaded from the config root. A directory pattern also matches everything beneath it. An empty list means **sync nothing**.
- **Exclude patterns** — matching paths are never synced, in either mode.
- **Clean-upload preserve paths** — matching paths are never deleted by a clean upload.
- Enabled mount points (`/media`, `/share`, `/ssl`, `/backups`, `/www`, `/addon_configs`) sync their contents wholesale, independent of include patterns.

In `blacklist` mode legacy behavior is preserved: everything is synced except ignored, excluded, and sensitive files. Files that fall off the allow-list are never deleted from GitHub; clean uploads only touch files within the current sync scope.

## Pre-commit gate

Before any upload, the add-on runs pre-commit hooks against **copies** of the files about to be pushed and blocks (or warns) based on the **Pre-commit mode** setting:

- **Enabled** (default) — hooks must pass, otherwise the upload is cancelled before a single file reaches GitHub and the report lists the failed hooks/files.
- **Warn only** — violations are logged but the upload proceeds.
- **Disabled** — hooks are not run.

Rules are read from `.pre-commit-config.yaml` in your Home Assistant config folder when present; otherwise a bundled default (offline `builtin` hooks: yaml/json/toml lint, merge-conflict, trailing-whitespace, end-of-file, private-key, and large-file checks) is used. The gate uses the fast Rust pre-commit runner `prek` (shipped in the image) and a cached hook store under `/data/.prek`. Your own files are never modified — only temporary copies are checked.

## Security

- The saved GitHub token is encrypted at rest with Fernet (key derived from the supervisor machine-id) wherever options are persisted, and stays masked as `********` in the UI and diagnostics. If the `cryptography` package is unavailable the token is stored in plaintext with a warning.
- Sync logs are redacted with the same secret patterns as the diagnostics export.
- GitHub API traffic is globally throttled (min 0.25s between requests) to avoid secondary rate limits.

## Runbook

### Dry run

1. Configure repository, branch, and device-flow credentials.
2. Enable dry run mode in the Installation card.
3. Start a sync from the UI.
4. Confirm the scan summary and dry-run result match expectations.

### Defaults

1. Scheduled sync uses day-of-week + time-of-day selection (default: disabled).
2. Both settings are editable in the Installation card.

### Live run

1. Confirm the repository is reachable with the saved token.
2. Confirm the branch name is correct for the target repo.
3. Disable dry run mode.
4. Start a sync from the UI, or use **Clean Upload** to force a full re-upload plus cleanup of remote extras. **Clean Repo** empties the remote repo with a fast git-tree reset and restores the starter files in one live step.
5. Confirm the probe succeeds and the final result reports upserts, deletes, and skips.

### Diagnostics bundle

1. Open the UI and click **Download Diagnostics**.
2. Share the JSON bundle for troubleshooting.
3. The bundle includes masked options, current state, auth diagnostics, and a sanitized log tail.

## Release checklist

1. Bump the version in `config.yaml` (single source of truth).
2. Run the app unit tests.
3. Update the changelog.
4. Commit and push to dev, then to main for stable.

## First run

1. In Home Assistant, open **Settings → Add-ons → Add-on Store → Repositories** and add this repository URL: `https://github.com/TheBlackMini/GithubConfigSync`.
2. Install **Github Config Sync**.
3. Open the app web UI from the Installation and Usage card.
4. Complete GitHub Device Flow login (section 1).
5. Pick an existing repository or create a new one (section 2).
6. Confirm the target repository and branch (section 3).
7. Run a dry run first to confirm the scan looks correct.
8. Switch to a live run when ready.

## Notes

- Dry run is enabled by default to avoid accidental pushes.
- This app is designed as a polished operator UI layer and can be wired to deeper sync logic incrementally.
- Security-focused safeguards are in place: private repositories are strongly recommended, sensitive-path filtering is active, and two-way sync warnings are visible.
- The add-on repository metadata is minimal and valid for Home Assistant add-on store ingestion.
- New repository creation defaults blank name/description fields to a humanized repository name.
- Release track: stable releases on `main`, dev releases on `dev` repo.
- Versioning rule: keep numeric `x.y.z` versions and use stable releases on `main` with dev releases on `dev`.

## Verification notes

- Start with a dry run and confirm the API summary matches the expected file changes.
- For a live run, disable dry run only after the repository probe passes and the GitHub token has repo write access.
- Missing local files during an upsert are skipped; missing remote files during deletes are skipped as well.
