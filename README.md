# Github Config Sync

[![Documentation][badge-docs]][docs]
[![Home Assistant][badge-home-assistant]][home-assistant]
[![HACS][badge-hacs]][hacs]
[![HACS Validation][badge-hacs-validation]][workflow-hacs-validation]
[![Hassfest][badge-hassfest]][workflow-hassfest]
[![CI][badge-ci]][workflow-ci]
[![Release][badge-release]][releases]
[![Built with AI][badge-built-with-ai]][built-with-ai]

Home Assistant **add-on** for syncing your config folder to GitHub. This is a config sync tool, not a backup tool.

A fork of the original [Github Config Sync](https://github.com/MJP-76/GithubConfigSync) by [MJP-76](https://github.com/MJP-76), with personal modifications by [TheBlackMini](https://github.com/TheBlackMini).

**Private repositories are strongly recommended.** Use caution with public repos and any two-way sync tools that also write to your Home Assistant config tree — they can cause local config loss or unexpected deletions.

<!-- VERSION:START -->
- Integration version: `1.7.1`
- Add-on version: `1.7.1`
- Channel: `stable`
- Release tag: `v1.7.1`
<!-- VERSION:END -->

## Features

- GitHub authentication with least privilege: your own GitHub App (device flow), the default OAuth Device Flow, or a fine-grained PAT
- Wizard-style setup with a dark-mode UI and per-section reconfiguration
- Create a new repository or use an existing one
- Sync your Home Assistant config folder to GitHub
- Auto-generate a Home Assistant-friendly `.gitignore`
- Customizable ignore patterns
- Manual sync button in Home Assistant
- Scheduled syncs (day-of-week + time-of-day selection)
- Optional dated GitHub release creation before each sync
- Clean Upload — force full re-upload and remove remote extras
- Clean Repo — wipe remote repo and restore starter files in one step
- Repository picker with safety checks to avoid accidental overwrites
- Sensitive-file scanning and reporting

## Installation

> **This is a Home Assistant add-on, not a HACS integration.** Install it from the Add-on Store.

1. In Home Assistant, open **Settings → Add-ons → Add-on Store → Repositories**.
2. Add this repository URL: `https://github.com/TheBlackMini/GithubConfigSync`.
3. Install **Github Config Sync** and start it.
4. Open the app web UI (ingress) and follow the setup wizard: connect GitHub (Device Flow via your own GitHub App, the default OAuth app, or a fine-grained PAT), pick a repository, choose the sync scope, then review.

## Getting Started

1. Open the app UI from the Add-on page.
2. Complete the GitHub connect step (the wizard walks you through authorizing).
3. Pick an existing repository or create a new one.
4. Run a dry run first to confirm the scan looks correct.
5. Switch to a live run when ready.

## Default Ignore List

The following are excluded from sync by default:

- **HA runtime:** `.storage`, `.cloud`, `tts`, `.ha_run.lock`, `home-assistant.log`, `home-assistant.log.*`, `home-assistant_v2.db`, `home-assistant_v2.db-*`, `secrets.yaml`, `ip_bans.yaml`, `known_devices.yaml`
- **Databases:** `*.db`, `*.sqlite`, `*.sqlite3`
- **Dev/cache:** `.git`, `.cache`, `.venv`, `.vscode`, `.idea`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `__pycache__`, `.yaml_fix_backups`, `.yaml_fix_backups/*`
- **Temp/junk:** `*.tmp`, `*.swp`, `*.pyc`, `*.log`, `*.smbdelete*`, `.DS_Store`, `Thumbs.db`, `.ha_fix_yaml.py`

You can add extra patterns in the app UI. Live uploads also write a root `SECURITY_UPLOAD_WARNINGS.md` file when suspicious files are skipped.

## Sync Scope (allow-list mode)

The add-on syncs an **allow-list by default**. In `whitelist` mode only files matching the configured include patterns (in the **Sync scope** section of the UI) are uploaded, so unrelated files never end up in your repo:

- **Include patterns** — fnmatch-style, one per line (e.g. `*.yaml`, `*.json`, `themes`, `packages`). A directory name also matches everything beneath it. An empty list means *sync nothing*.
- **Exclude patterns** — never synced, in either mode.
- **Clean-upload preserve paths** — never deleted by a clean upload, no matter the mode.
- Enabled mount points (`/media`, `/share`, `/ssl`, `/backups`, `/www`, `/addon_configs`) sync their contents wholesale regardless of include patterns.

In `blacklist` mode the legacy behavior is kept: everything is synced except ignored, excluded, and sensitive files. Files that fall off the allow-list are **not** deleted from GitHub — previously synced remote files are left untouched unless you run a clean upload against a repo you own.

## Pre-commit gate

Before any file is pushed, the add-on checks copies of the about-to-be-uploaded files with pre-commit hooks and blocks the push on violations (configurable: `enabled` blocks, `warn` logs only, `disabled` skips). Hooks come from `.pre-commit-config.yaml` in your HA config folder or a bundled offline builtin default; runs on the fast Rust `prek` runner shipped in the image (amd64/aarch64).

## Notes

- This is not a zip-backup tool — files are synced individually as repository contents.
- The Home Assistant config folder is used automatically.
- A managed `.gitignore` is created with HA defaults and your extra patterns.
- Keep the repository private if your config contains sensitive data.
- After a release, Home Assistant may need a rebuild/reinstall to pick up UI changes from the add-on image.

## Development Track

To use the dev branch, add the dev repository URL in **Settings → Add-ons → Add-on Store → Repositories**:

```
https://github.com/TheBlackMini/GithubConfigSync-dev
```

Development happens on the `dev` repo. When ready, changes are pushed to both repos.

## Documentation

- **[Project Guide](PROJECT.md)** — architecture, security, milestones, and release workflow.
- **[Changelog](CHANGELOG.md)** — release history.

[badge-docs]: https://img.shields.io/badge/Documentation-41BDF5?style=flat-square&logo=bookstack&logoColor=white
[docs]: https://TheBlackMini.github.io/GithubConfigSync/
[badge-home-assistant]: https://img.shields.io/badge/Home%20Assistant-41BDF5?style=flat-square&logo=homeassistant&logoColor=white
[home-assistant]: https://www.home-assistant.io/
[badge-hacs]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs]: https://github.com/hacs/integration
[badge-hacs-validation]: https://img.shields.io/badge/HACS%20Validation-passing-brightgreen
[workflow-hacs-validation]: https://github.com/TheBlackMini/GithubConfigSync/actions/workflows/validate.yml
[badge-hassfest]: https://img.shields.io/github/actions/workflow/status/TheBlackMini/GithubConfigSync/hassfest.yml?branch=main&label=Hassfest
[workflow-hassfest]: https://github.com/TheBlackMini/GithubConfigSync/actions/workflows/hassfest.yml
[badge-ci]: https://github.com/TheBlackMini/GithubConfigSync/actions/workflows/ci.yml/badge.svg
[workflow-ci]: https://github.com/TheBlackMini/GithubConfigSync/actions/workflows/ci.yml
[badge-release]: https://img.shields.io/github/v/release/TheBlackMini/GithubConfigSync?style=flat&label=Release
[releases]: https://github.com/TheBlackMini/GithubConfigSync/releases
[badge-built-with-ai]: https://img.shields.io/badge/Built%20with-AI-black?logo=openai&logoColor=white
[built-with-ai]: https://openai.com
