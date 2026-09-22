# AGENTS.md

This is a Home Assistant **add-on** (Flask app) for syncing the HA config folder to GitHub, plus a legacy redirect-only HACS integration. The real product lives under `addons/github-config-sync/`; `custom_components/github_config_sync/` is only a stub that aborts installs with `addon_only`.

## Layout

- Add-on: `addons/github-config-sync/` — `config.yaml` (version + options), `build.yaml`, `Dockerfile` (add-on base image `ghcr.io/home-assistant/base:3.24-2026.08.0`, `amd64`/`aarch64` only; installs `py3-flask` and `py3-cryptography`; there is no pip requirements file).
- App: `rootfs/app/server.py` (~2000-line Flask app), `rootfs/app/static/index.html` (UI), `rootfs/app/sync/` (`engine.py`, `github_client.py`, `hashing.py`, `models.py`, `errors.py`).
- Integration stub: `custom_components/github_config_sync/` — only contributes `const.py` `DOMAIN`; it has no runtime features.
- CI: `.github/workflows/validate.yml` (unit tests), `hassfest.yml` + `hacs.json` (integration checks), `docs.yml` (mkdocs docs), `gitleaks.yml` (secret scan). Repo hygiene: `.pre-commit-config.yaml` (pre-commit-hooks + gitleaks), `.github/dependabot.yml`, `.github/ISSUE_TEMPLATE/`.

## Commands

- Run tests: `python3 -m unittest discover -s addons/github-config-sync/rootfs/app/tests -v` — run from repo root. Flask is required for server API tests, which self-skip (`SkipTest`) without it.
- Docs build (matches CI): `mkdocs build --strict`
- Version sync check: `python3 scripts/sync_versions.py --integration X.Y.Z --channel stable --check`
- Version bump: `python3 scripts/sync_versions.py --integration X.Y.Z --channel stable`

There is **no** `pyproject.toml`, uv, ruff, mypy, or pytest config in this repo — don't invent those commands. Pre-commit config exists but nothing forces it in CI; gitleaks is enforced via the GitHub Action.

## Versioning

- `addons/github-config-sync/config.yaml` is the single source of truth for the version; `server.py` reads it at startup. Never hardcode a version as a literal string in `server.py` — `scripts/sync_versions.py` fails on `APP_VERSION = "..."`.
- Bump flow: update `config.yaml`, then run `scripts/sync_versions.py`, which syncs `manifest.json`, `hacs.json`, the `<!-- VERSION:START -->` blocks in `README.md`, the add-on README, `PROJECT.md`, and `docs/project-guide.md`, and promotes the top `## Unreleased` changelog section into `## X.Y.Z` in `CHANGELOG.md`, `addons/github-config-sync/CHANGELOG.md`, and `rootfs/app/CHANGELOG.md` (leaving a fresh empty `## Unreleased` at the top). `--channel dev` bumps the patch for the dev track; `--check` reports drift without writing.
- Pre-release versions use a suffix in `config.yaml` (`1.8.0-beta-1`); `sync_versions.py` and `create_release.py` accept and propagate them, and `create_release.py` marks such GitHub releases as pre-releases so HA/HACS can opt in via their beta/pre-release toggles.
- Changelog notes for unreleased work go under the top `## Unreleased` heading in all three changelogs; keep them identical.
- Releases publish via `scripts/create_release.py` (creates the GitHub release `vX.Y.Z` whose body is that version's changelog section — that body is what the Home Assistant update page / HACS shows).
- Trunk-based: `main` is the only branch; all development and releases happen directly on `main`. A release = tag `vX.Y.Z` on `main` + `scripts/create_release.py`.

## Testing quirks

- `tests/test_hashing.py` asserts the runtime ignore/sensitive lists in `rootfs/app/sync/hashing.py` (the single source of truth) and covers `path_matches_patterns` (allow-list include/exclude/preserve matching). `DEFAULT_INCLUDE_PATTERNS` also lives there and is the default allow-list in whitelist mode.
- `static/index.html` is not covered by tests; UI changes only take effect after an add-on image rebuild in HA.

## Conventions

- Integration imports must be relative (`from .const import DOMAIN`); the add-on app imports `sync` absolutely (`from sync.engine import ...`) with the app root on `sys.path`.
- Keep GitHub tokens masked as `********` in API responses/diagnostics and treat that placeholder as no-op when persisting options. Never log tokens. At rest, the token is encrypted (Fernet, `enc:v1:` prefix) on disk/Supervisor sync, decrypting transparently in `_merge_options`; `_encrypt_secret`/`_decrypt_secret` no-op without `cryptography`. Auth methods: `github_app` (default; user-owned GitHub App via device flow — scope must be absent, `github_client_id` required), `device_flow` (scope `repo`) and `fine_grained_pat`. `/api/auth/device/start` chooses the scope from the flow's auth method, and `start_device_flow(client_id, scope)` omits `scope` when empty.
- Sync scope is allow-list by default (`sync_mode: whitelist`): config-root files must match `sync_include_patterns`, `sync_exclude_patterns` filters in either mode, `clean_preserve_paths` pins files during clean, and enabled mount roots (`include_media`, etc.) sync wholesale. Empty include list = sync nothing.
- Pre-commit gate: before any live upload, `engine.run()` stages copies of the to-be-pushed files into a throwaway git worktree and runs `prek run --files ...` (pre-commit runner, `repo: builtin` hooks are offline). Effective config = `${CONFIG_ROOT}/.pre-commit-config.yaml` if present, else the bundled `rootfs/app/.pre-commit-config.yaml`. `precommit_mode` (`enabled` blocks with `SyncError` + `format_report`, `warn` logs only, `disabled` skips) flows from options through `SyncConfig`/`_sync_config`/`_repo_sync_config` into the engine. `prek` is installed in the Dockerfile (musl asset matched by `TARGETARCH`, `amd64`/`arm64`); the add-on only supports those two architectures. Engine log lines are wired via `set_log_callback` on the three live run sites (`trigger_sync`, `trigger_clean_sync`, scheduler `_do_sync`) — keep that wiring when editing them.
- Auth: mutating `/api/*` endpoints and most reads require auth (`X-Hass-Source: core.ingress` from a private IP, or a GitHub token Bearer header). `/api/status` and `/api/health` stay public.
- House style is strong typing, non-mixedCase module vars, and LF line endings; nothing in CI enforces it.
- Keep comments short and only where they explain a non-obvious why. No section-divider comments.