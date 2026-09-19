# Configuration

All settings can be edited in the add-on **web UI** (open it with the **Open Web UI** button on the add-on's Info page). The Home Assistant **Configuration** tab is generated from `config.yaml` and shows a subset of the same options.

## Web UI sections

The web UI opens as a **setup wizard** (Connect GitHub → Repository → What to sync → Schedule & safety → Review). Once a repository and token are configured it switches to the settings view, where each section has its own **Save** button and a **Re-run wizard** option restarts the guided flow.

| Section | Purpose |
|---|---|
| 1. Connect GitHub | Device Flow via your own GitHub App, the default OAuth app, or a fine-grained PAT |
| 2. Repository setup | Load an existing repository or create a new one (owner/repo + branch) |
| 3. Sync scope | Mode, patterns, pre-commit gate, log level |
| 4. Mount points | Wholesale folders (`/media`, `/share`, …) |
| 5. Recommended .gitignore | One-click ignore defaults |
| 6. Scheduled sync | Automatic daily/weekly sync (web UI only) |
| 7. Dry run | Preview without pushing |
| 8. Documentation | Pointers to the full docs |

## Option reference

| Option | Default | Example | Description |
|---|---|---|---|
| `github_repository` | _empty_ | `TheBlackMini/home-assistant-config` | Target repository (`owner/repo`), set by the picker. |
| `github_branch` | `main` | `main` | Branch to push to. |
| `github_token` | _empty_ | set by Device Flow | Encrypted at rest; masked in the UI. |
| `github_client_id` | default OAuth app | `Ov23liAbCdEfGhIjKlM` | OAuth app client ID for Device Flow. Also the required **Client ID of your own GitHub App** when `auth_method` is `github_app` (no client secret needed). |
| `scheduler_timezone` | server local | `Europe/Berlin` | IANA timezone for scheduled sync. |
| `sync_include_patterns` | `*.yaml`, `*.json`, … | `packages\n*.yaml` | Allow-list patterns (`whitelist` mode). |
| `sync_exclude_patterns` | _empty_ | `home-assistant.log` | Never-sync patterns. |
| `clean_preserve_paths` | _empty_ | `docs` | Never deleted by clean uploads. |
| `version_retention_count` | `7` | `7` | Max auto-releases kept. |
| `dry_run` | `true` | `false` | Plan only; never push. |
| `include_addon_configs` | `false` | `true` | Sync `/addon_configs`. |
| `include_media` | `false` | `true` | Sync `/media` into `media/`. |
| `include_share` | `false` | `true` | Sync `/share` into `share/`. |
| `include_ssl` | `false` | `true` | Sync `/ssl` into `ssl/`. |
| `include_backups` | `false` | `true` | Sync `/backup(s)` into `backups/`. |
| `include_www` | `false` | `true` | Sync `/www` into `www/`. |
| `sync_mode` | `whitelist` | `blacklist` | Sync scope. |
| `precommit_mode` | `enabled` | `warn` | Pre-commit gate behavior. |
| `log_level` | `INFO` | `DEBUG` | Log verbosity. |

## Scheduled sync

Scheduled sync runs inside the add-on and is configured **only in the web UI** (Scheduled sync section) — `auto_sync_days`, `auto_sync_time`, and `auto_sync_create_release` are not part of `config.yaml` and do not appear in the HA Configuration tab.

Enable it, pick days and a time, optionally create a dated release before each sync, and set the retention count. The scheduler runs in the add-on background (24/7 timer) and honors `scheduler_timezone`.

## Authentication

- **GitHub App** (recommended) — create your own GitHub App (Settings → Developer settings → GitHub Apps), set repository permissions to **Metadata: Read-only** and **Contents: Read and write**, opt in to the **device flow**, install it on the repository(ies) you sync, and paste its **Client ID** into the connect step. GitHub shows the name you gave the app, never a third party's. No client secret is stored — the device flow needs only the Client ID.
- **Device Flow** (default) — click **Start Device Login**; confirm the code on GitHub. The token is saved automatically.
- **Fine-grained PAT** — paste a PAT scoped to the target repository (Contents: Read and write) in the connect step; device login is not used.

## Logging

`log_level` controls how much the add-on logs for GitHub and Home Assistant API calls.

- `DEBUG` — traces every request (URLs only, never credentials), useful for troubleshooting.
- `INFO` — default operational log.
- `WARN` — problems only.
- `ERROR` — errors only.

Logs are written to the add-on log and to `/data/sync.log`, redacted with the same secret patterns as the diagnostics export.