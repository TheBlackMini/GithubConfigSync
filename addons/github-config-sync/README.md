# ⑂ Github Config Sync

[![CI](https://github.com/TheBlackMini/GithubConfigSync/actions/workflows/validate.yml/badge.svg)](https://github.com/TheBlackMini/GithubConfigSync/actions/workflows/validate.yml)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Add--on-03a9f4.svg)](https://www.home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://www.python.org/)
[![HASSfest](https://img.shields.io/badge/HASSfest-validated-success.svg)](https://developers.home-assistant.io/docs/add-ons/)
[![Release](https://img.shields.io/github/v/tag/TheBlackMini/GithubConfigSync?label=release)](https://github.com/TheBlackMini/GithubConfigSync/releases)

A Home Assistant add-on that syncs your Home Assistant config folder to a GitHub repository — with an ingress web UI, device-flow login, scheduled sync, and a pre-commit gate.

This add-on is a fork of the original **Github Config Sync** by [MJP-76](https://github.com/MJP-76), with personal modifications by TheBlackMini.

> **Note:** This is a Home Assistant **add-on**. Install it from the Add-on Store (**Settings → Add-ons → Add-on Store → Repositories**). It is **not** a HACS integration.

> **Warning:** Use caution with public repositories and with any two-way sync or other tools that can also write to the Home Assistant config tree, because they can cause local config loss or unexpected deletions. **This is a sync tool, not a backup tool.**

## Installation

1. In Home Assistant, open **Settings → Add-ons → Add-on Store → Repositories**.
2. Add the repository URL: `https://github.com/TheBlackMini/GithubConfigSync`.
3. Install **Github Config Sync**.
4. Open the add-on web UI with the **Open Web UI** button on the add-on's **Info** page.

Detailed setup, option reference, and troubleshooting are in the add-on [Documentation](./DOCS.md).

## First run

The web UI guides you through the whole flow — nothing needs to be typed by hand:

1. **1. GitHub Device Login** — click **Start Device Login**. GitHub opens in a new tab with a code; confirm it and the add-on saves your token automatically.
2. **2. Repository setup** — pick an existing repository or click **Create Repository** (defaults to `ha-github-config-sync`, **private**).
3. Your target repository and branch are stored automatically. To change the branch or set a token manually, open **3. Advanced options**.
4. Run a **Dry run** first (enabled by default) to preview what would be uploaded.
5. Switch to a live run and click **Sync Now**.

## What it provides

- Ingress web UI for setup, sync control, and live upload progress
- GitHub **Device Flow** login (no token pasting) or a **fine-grained PAT**
- Repository picker plus one-click private repo creation
- **Allow-list synchronization** by default — only files matching your include patterns are uploaded
- Optional wholesale syncing of the mount points `/media`, `/share`, `/ssl`, `/backups`, `/www`, `/addon_configs`
- **Pre-commit gate** that checks the files about to be pushed before anything reaches GitHub
- Scheduled sync (days of week + time) and dated auto-releases with retention
- Hash-based change detection — only changed files are uploaded
- Encrypted token storage at rest and redacted logs

## Synchronization

In `whitelist` mode (default) only files in the config root that match the **include patterns** are synced; in `blacklist` mode everything is synced except the excluded and ignored files. Mount points sync wholesale into their own folders regardless of the allow-list. Files that fall off the allow-list are never deleted from GitHub, and remote deletes never touch local files.

See [Synchronization](./DOCS.md#synchronization) in the documentation for the full details.

## Configuration

Configuration is managed in the add-on web UI. A small number of options are also exposed to the Home Assistant **Configuration** tab (generated from `config.yaml`):

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `github_repository` | string | _empty_ | Target repository (`owner/repo`). Set automatically by the repository picker. |
| `github_branch` | string | `main` | Branch that files are pushed to. |
| `github_token` | password | _empty_ | Set by Device Flow; paste a fine-grained PAT to override. |
| `github_client_id` | string | default OAuth app | OAuth client ID for Device Flow (own OAuth apps only). |
| `scheduler_timezone` | string | _empty_ | IANA timezone for scheduled sync; empty uses the server's local timezone. |
| `sync_include_patterns` | list | `*.yaml`, `*.json`, … | Allow-list patterns (`whitelist` mode). Empty list = sync nothing. |
| `sync_exclude_patterns` | list | _empty_ | Never-sync patterns, in either mode. |
| `clean_preserve_paths` | list | _empty_ | Paths never deleted by a clean upload. |
| `version_retention_count` | int | `7` | Max GitHub releases/episodes kept. |
| `dry_run` | bool | `true` | Plan only, never push. |
| `include_addon_configs` | bool | `false` | Sync `/addon_configs`. |
| `include_media` | bool | `false` | Sync `/media`. |
| `include_share` | bool | `false` | Sync `/share`. |
| `include_ssl` | bool | `false` | Sync `/ssl`. |
| `include_backups` | bool | `false` | Sync `/backup` (or `/backups`). |
| `include_www` | bool | `false` | Sync `/www`. |
| `sync_mode` | select | `whitelist` | Sync scope (`whitelist` / `blacklist`). |
| `precommit_mode` | select | `enabled` | Pre-commit gate (`enabled` / `warn` / `disabled`). |
| `log_level` | select | `INFO` | Log verbosity (`DEBUG` / `INFO` / `WARN` / `ERROR`). |

> Scheduled-sync settings (`enable`, days, time, releases) live **only in the web UI** — they are not part of `config.yaml` and therefore not shown in the Home Assistant **Configuration** tab. Configure them under **4. Scheduled sync** in the web UI.

The full option reference with examples is in the add-on [Documentation](./DOCS.md#configuration).

## Pre-commit gate

Before anything reaches GitHub, the add-on copies the to-be-pushed files into a throwaway worktree and runs the pre-commit hooks. **Enabled** (default) blocks the upload on violations, **warn** logs them, **disabled** skips the check. Rules come from `.pre-commit-config.yaml` in your Home Assistant config folder, or a bundled offline default. Uses the fast Rust runner `prek` (included on `amd64`/`aarch64`).

## Security

- The GitHub token is encrypted at rest (Fernet, key from the Supervisor machine-id) and masked as `********` in the UI, diagnostics, and logs.
- GitHub API traffic is throttled to avoid secondary rate limits.
- Repository writes are marker-gated: clean actions and the repo picker only target repositories created or adopted by this add-on.
- Private repositories are strongly recommended; sensitive files (`.storage`, `secrets.yaml`, databases, logs, …) are ignored and skipped.

## Changelog

See the [add-on changelog](./CHANGELOG.md) for release notes.

## License

MIT — see [LICENSE](../../LICENSE) and the [project guide](../../PROJECT.md).

## Version Tracker

<!-- VERSION:START -->
- Integration version: `1.6.1`
- Add-on version: `1.6.1`
- Channel: `stable`
- Release tag: `v1.6.1`
<!-- VERSION:END -->