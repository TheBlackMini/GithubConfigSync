# Changelog

The full release history lives in
[CHANGELOG.md](https://github.com/TheBlackMini/GithubConfigSync/blob/main/CHANGELOG.md)
and is published per version on
[GitHub Releases](https://github.com/TheBlackMini/GithubConfigSync/releases), so the
Home Assistant update page shows only the changes between the user's version and the
update. The last 5 releases are kept at the top, per the project's changelog rules.

## 1.7.0

- **Feature**: New least-privilege auth method — use your own GitHub App (device flow,
  Client ID only, no client secret). The app asks only for Metadata (read-only) and
  Contents (read and write) on the repositories you select, and GitHub shows the app
  name you set instead of the maintainer's default (`auth_method: github_app`)
- **Feature**: Web UI is now a setup wizard (Connect GitHub → Repository → What to sync
  → Schedule & safety → Review) with per-section save buttons and a "Re-run wizard"
  option; auto-save-on-every-keystroke is gone
- **Feature**: Dark mode follows the Home Assistant/system theme by default, with a
  Theme toggle (Auto / Light / Dark) in the header
- **Fix**: Recommended .gitignore entries render beside their checkboxes instead of
  being right-aligned
- **Fix**: The Stable/Dev version boxes were removed from the top of the page — the
  installed version stays in the header badge

## 1.6.2

- **Chore**: Version bumps now promote the top `## Unreleased` changelog section into
  the released version, keeping the repo-root, add-on, and app changelogs in sync
  (`scripts/sync_versions.py`)
- **Chore**: Release notes are now published as GitHub releases (`vX.Y.Z`) so HA shows
  only the changelog differences between the installed and updated version
  (`scripts/create_release.py`)

## 1.6.1

- **Feature**: Allow-list ("whitelist") sync is now the default — only files matching
  the configured include patterns are uploaded; editable `sync_include_patterns`,
  `sync_exclude_patterns`, and `clean_preserve_paths` options
- **Fix**: Files that fall off the allow-list (or are excluded/preserved) are no longer
  deleted from GitHub; clean upload only touches files in the current sync scope
- **Security**: Saved GitHub token encrypted at rest (Fernet)
- **Fix**: New `scheduler_timezone` option (IANA name) controls scheduled sync timing
- **Fix**: Global 0.25s GitHub API throttle and fewer sync workers reduce rate-limit errors
- **Fix**: Sync log lines redacted with the same secret patterns as diagnostics
- **Fix**: Device Flow OAuth client ID now configurable via `github_client_id`
- **Feature**: Pre-commit gate runs before any push (new `precommit_mode` option)
- **Breaking**: Official support limited to `amd64` and `aarch64`
- **Chore**: Pre-commit (gitleaks), gitleaks GitHub Action, Dependabot, issue templates

## 1.6.0

- **Feature**: Reset to Defaults button for ignore patterns in web UI
- **Fix**: Reset to Defaults button was missing its event handler (Uncaught TypeError)
- **Fix**: Add-on rebuild via Supervisor API now works correctly

## 1.5.22

- **Fix**: "Token missing" badge no longer appears when the token is actually
  fine — transient GitHub check failures now show as an amber "Token check
  failed" badge instead of a red "Token missing"
- **Fix**: One slow/timed-out GitHub call no longer poisons the token badge —
  transient `error` health results cache for 30s (stable states keep 5m)
- **Fix**: Device Flow completion no longer reports "request timed out"
  mid-authorization — UI waits up to 130s (server polls GitHub up to 120s)
- **Fix**: Live token health check uses a bounded 20s GitHub call with a 30s
  client timeout
- **Fix**: `_save_state()` is now lock-serialized so concurrent status
  polls/sync writes can no longer drop the token-health cache entry

## 1.5.21

- **Fix**: Options now persist across restarts — Supervisor sync POSTs to
  `/addons/self/options` (works for any `hassio_role`)
- **Fix**: `hassio_api: true` added so `SUPERVISOR_TOKEN` is injected into the
  container (without it, the Supervisor sync silently skipped and the token was
  lost on reboot)
- **Fix**: Settings save can never overwrite the real token with the `********`
  mask placeholder