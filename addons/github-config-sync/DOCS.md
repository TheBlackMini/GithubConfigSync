# Github Config Sync — Documentation

A Home Assistant add-on that syncs your config folder to GitHub with an ingress web UI. This documentation covers installation, the configuration options, scheduled sync, and troubleshooting.

> **This is a sync tool, not a backup tool.** Prefer private repositories, and never run a second two-way sync against the same repository.

## Installation

1. In Home Assistant, open **Settings → Add-ons → Add-on Store → Repositories** and add `https://github.com/TheBlackMini/GithubConfigSync`.
2. Install **Github Config Sync**.
3. Start the add-on and open the web UI with the **Open Web UI** button on the add-on's **Info** page.

## First run

Everything happens in the web UI — no manual file editing. On first run the UI opens as a **setup wizard**:

1. **Connect GitHub (step 1)** — pick an authentication method and click **Start Device Login**. GitHub opens in a new tab showing a code; confirm it on GitHub and the add-on stores the token automatically. For a **GitHub App**, the wizard walks you through creating your own app (Metadata: Read-only, Contents: Read and write, device flow enabled) and installing it on the repository to sync — paste its **Client ID** before starting. For a fine-grained PAT, switch the authentication method and paste the token.
2. **Repository (step 2)** — pick an adopted/owned repository with **Load Repositories**, or choose **Create new repository** (private by default, name defaults to `ha-github-config-sync`). The owner/repo and branch fields are also editable here.
3. **What to sync (step 3)** — set the sync mode, patterns, mount points and .gitignore defaults.
4. **Schedule & safety (step 4)** — scheduled sync + dry run.
5. **Review (step 5)** — a summary of your choices; **Finish** saves and switches to the settings view.

Every section in the settings view has its own **Save** button (only that section is written), and **Re-run wizard** restarts the guided flow at any time.

## Authentication

| Method | When to use | Setup |
| --- | --- | --- |
| **GitHub App** (recommended) | Least privilege, one or a few repositories | Create your own GitHub App (Settings → Developer settings → GitHub Apps) with **Metadata: Read-only** and **Contents: Read and write**, tick **Opt in to the device flow**, install it on only the repositories to sync, and paste its **Client ID** into the connect step. GitHub shows the app name you chose. No client secret is needed for the device flow. |
| **GitHub Device Flow** (default) | Most users | Click **Start Device Login** and confirm the code on GitHub. |
| **Fine-grained PAT** | Restricted environments, scripts | Create a PAT scoped to the target repository with **Contents: Read and write**; paste it in the connect step. |

The token is saved encrypted at rest and never shown again in the UI (masked as `********`).

## Repository setup

- **Existing repository** — pick one from the picker. To use a repository that wasn't created by this add-on, tick the risk acknowledgement and **Adopt** it (adds the add-on marker file). Adoption only happens after a confirmation dialog.
- **Create new repository** — filled in by two fields (name + description). It defaults to `ha-github-config-sync`, **private**, and becomes the target automatically.

Clean actions and the repository picker only target repositories carrying the add-on marker, to avoid wiping a repository you didn't mean to.

## Synchronization

### Sync scope

- **`whitelist` (default)** — only the config-root files matching the **include patterns** are uploaded. A pattern like `themes` also matches everything beneath `themes`. An **empty include list means sync nothing**.
- **`blacklist`** — everything is synced except the **exclude patterns**, the default ignore list, and sensitive files.

**Exclude patterns** and the default ignore entries always win. Files that fall off the allow-list are never deleted from GitHub; clean uploads only touch files within the current scope. Deletes only ever happen on GitHub — local files are never removed.

### Mount points

Enabled mount points sync their *entire* contents into their own folder in the repository, independent of the include patterns:

| Mount point | Syncs into | Example |
| --- | --- | --- |
| `/addon_configs` | `addon_configs/` | `addon_configs/<slug>/config.yml` |
| `/media` | `media/` | `media/photos/holiday.jpg` |
| `/share` | `share/` | `share/files/weather.csv` |
| `/ssl` | `ssl/` | `ssl/privkey.pem` |
| `/backup` or `/backups` | `backups/` | `backups/backup_2026_09_19_03_00.tar` |
| `/www` | `www/` | `www/custom.js` |

> `ssl/` and `backups/` contain private material — only enable these on a **private** repository.

### Pre-commit gate

Before any live upload, the add-on copies the to-be-pushed files into a throwaway worktree, runs the pre-commit hooks, and then:

- **Enabled** (default) — the upload is cancelled and the report lists the failed hooks/files.
- **Warn only** — violations are logged but the upload proceeds.
- **Disabled** — hooks are skipped.

Rules are read from `.pre-commit-config.yaml` in your Home Assistant config folder, falling back to the bundled offline builtin hooks. Requires the `prek` executable, included in the add-on image for `amd64`/`aarch64`.

## Scheduled sync

Scheduled sync runs in the background inside the add-on and lives **only in the web UI (Scheduled sync section)** — it is not part of `config.yaml`, so the Home Assistant **Configuration** tab does not show it.

1. Enable **scheduled sync**.
2. Pick the **days** (Mon–Sun) and a **time**.
3. Optionally tick **create a dated release before each sync**; releases are pruned to the **version retention count**.

The scheduler uses `scheduler_timezone` (an IANA name such as `Europe/Berlin`) if set, otherwise the server's local timezone. Use **Use Home Assistant timezone** to copy the HA timezone into the field.

> **Why is the schedule not in the Configuration tab?** The schedule is runtime behaviour configured from the add-on web UI, and the values are stored/synced to the add-on options automatically, so they survive restarts. It is intentionally not part of `config.yaml`: exposing it there would create a second, competing editor for the same settings in the Home Assistant **Configuration** tab. Configure it once in the web UI (Scheduled sync section) and it just runs.

## Logging

`log_level` (see below) controls the verbosity of GitHub and Home Assistant API logging. On `DEBUG`, every GitHub/Supervisor request is traced without credentials. Your own token is never logged.

## Configuration reference

The full set of options, with the web-UI section where each is edited:

| Option | Web UI location | Default | Example |
| --- | --- | --- | --- |
| `github_repository` | Repository / connect | _empty_ | `TheBlackMini/home-assistant-config` |
| `github_branch` | Repository | `main` | `main` |
| `github_token` | Connect | _empty_ | set by Device Flow |
| `github_client_id` | Connect | default OAuth app | your GitHub App's Client ID for `github_app` |
| `scheduler_timezone` | 4 | _empty_ (server local) | `Europe/Berlin` |
| `sync_include_patterns` | 5 | `*.yaml`, `*.json`, `themes`, … | `packages\n*.yaml` |
| `sync_exclude_patterns` | 5 | _empty_ | `home-assistant.log\n**/*.tmp` |
| `clean_preserve_paths` | 5 | _empty_ | `docs\nREADME.md` |
| `version_retention_count` | 4 | `7` | `7` |
| `dry_run` | 8 | `true` | `false` for live |
| `include_addon_configs` | 6 | `false` | `true` to sync `/addon_configs` |
| `include_media` | 6 | `false` | `true` to sync `/media` |
| `include_share` | 6 | `false` | `true` to sync `/share` |
| `include_ssl` | 6 | `false` | `true` to sync `/ssl` |
| `include_backups` | 6 | `false` | `true` to sync `/backup(s)` |
| `include_www` | 6 | `false` | `true` to sync `/www` |
| `sync_mode` | 5 | `whitelist` | `blacklist` for legacy behavior |
| `precommit_mode` | 5 | `enabled` | `warn` to only log violations |
| `log_level` | 5 | `INFO` | `DEBUG` for request tracing |

Values marked "Web UI location" are editable directly in the web UI. The same keys are persisted to the add-on options and — where listed in `config.yaml` — shown in the Home Assistant **Configuration** tab.

## Running a sync

### Start a sync from the UI

The web UI is the only place to start a sync. With the add-on running, open it with **Open Web UI** on the add-on's Info page:

1. Complete the **Connect GitHub** step and pick or create a repository (repository step).
2. Leave **Dry run** enabled (Schedule & safety) and click **Sync Now** — the **Dry-run plan** panel shows exactly what would be uploaded and deleted, without touching GitHub.
3. When the preview looks right, untick **Dry run** and click **Sync Now** again to push the changes to GitHub. Progress shows in the **Live sync activity** card.
4. The same **Sync Now** button also starts a manual sync when you want one outside the configured schedule.

- **Preview** — with **Dry run** enabled, click **Sync Now**. The **Dry-run plan** panel shows exactly what would be uploaded and deleted.
- **Live** — disable dry run, click **Sync Now**. Progress (remaining uploads/deletes, elapsed time) shows in the **Live sync activity** card.
- **Force full re-upload** — **Danger Zone → Clean Upload** rebuilds the remote tree from the local config (paths in `clean_preserve_paths` are kept).
- **Reset the remote** — **Danger Zone → Clean Repo** empties the remote repository and restores the starter files.
- During an upload, **Cancel Current Upload** stops the sync; syncs are not cancellable once a git-tree operation has started.

## Security

- Token encrypted at rest (Fernet); masked everywhere in the UI and exports.
- Logs are silently throttled and redacted with the same secret patterns as diagnostics.
- Never combine this add-on with another tool writing to the same repository while it runs.

## Diagnostics

When reporting an issue: open the web UI, expand **Diagnostics**, and click **Download Diagnostics**. Attach the JSON bundle — it contains masked options, current state, auth status, and a redacted log tail. Additional log detail is available by setting `log_level` to `DEBUG`.

## Runbook — common tasks

| Task | What to do |
| --- | --- |
| First live sync | Complete the wizard (Connect, Repository, What to sync), run a dry run, disable dry run, **Sync Now**. |
| Change branch | **Settings → Repository setup → Target branch**, save. |
| Switch to a PAT or GitHub App | **Settings → Connect GitHub → Authentication method**, save. |
| Sync once at 02:00 every weekend | **Scheduled sync**: enable, tick Sat+Sun, time `02:00`. |
| Add `/media` to the repo | **Mount points**: tick **Include /media** (uploads to `media/`). |
| Stop accidental pushes | Keep **Dry run** enabled in **Dry run**. |

## License

MIT — this fork adds personal modifications by TheBlackMini on top of the original work by MJP-76.