from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .errors import SyncError

HOOKS_CONFIG_NAME = ".pre-commit-config.yaml"

VALID_MODES = ("enabled", "warn", "disabled")

DEFAULT_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class PrecommitResult:
    passed: bool
    exit_code: int | None
    output: str
    failed_hooks: tuple[str, ...] = ()
    failed_files: tuple[str, ...] = ()


def _log(log_callback: Callable[[str], None] | None, message: str) -> None:
    if log_callback is not None:
        log_callback(message)


def effective_hooks_config(config_root: Path) -> Path | None:
    """"Return the .pre-commit-config.yaml to enforce, or None when nothing exists.

    A user-provided file in the Home Assistant config folder wins; otherwise the
    bundled offline (builtin-hooks) default shipped with the add-on is used.
    """
    user_path = Path(config_root) / HOOKS_CONFIG_NAME
    if user_path.is_file():
        return user_path
    bundled_path = Path(__file__).resolve().parents[1] / HOOKS_CONFIG_NAME
    if bundled_path.is_file():
        return bundled_path
    return None


def precommit_available() -> bool:
    return shutil.which("prek") is not None


def git_available() -> bool:
    return shutil.which("git") is not None


def _stage_worktree(files: list[tuple[str, Path]], config_text: str) -> Path:
    """Copy the files about to be pushed into a fresh, throwaway git worktree."""
    worktree = Path(tempfile.mkdtemp(prefix="github-config-sync-precommit-"))
    try:
        for relative, local_path in files:
            if not relative or relative.startswith("/") or relative.startswith("..") or "/../" in f"/{relative}":
                raise SyncError(f"Unsafe path for pre-commit gate: {relative}")
            destination = worktree / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if local_path.is_file():
                shutil.copy2(local_path, destination)
        (worktree / HOOKS_CONFIG_NAME).write_text(config_text, encoding="utf-8")
        result = subprocess.run(
            ["git", "init", "-q"],
            cwd=worktree,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise SyncError(f"git init failed for pre-commit worktree: {result.stderr.strip()}")
        return worktree
    except Exception:
        shutil.rmtree(worktree, ignore_errors=True)
        raise


def _prek_env() -> dict[str, str]:
    env = {
        "PREK_COLOR": "never",
        "PATH": "/usr/local/bin:/usr/bin:/bin:/sbin:/usr/sbin",
    }
    prek_home = env.get("PREK_HOME")
    if not prek_home:
        data_root = Path("/data")
        if data_root.is_dir():
            prek_home = "/data/.prek"
            data_root.joinpath(".prek").mkdir(parents=True, exist_ok=True)
    if prek_home:
        env["PREK_HOME"] = prek_home
    return env


def _run_prek(worktree: Path, relative_paths: list[str], timeout: int) -> tuple[int, str]:
    command = [
        "prek",
        "run",
        "--files",
        *relative_paths,
        "--no-progress",
        "--color",
        "never",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=worktree,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_prek_env(),
        )
    except subprocess.TimeoutExpired:
        return 124, f"Pre-commit gate timed out after {timeout}s"
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output


def parse_report(output: str) -> tuple[list[str], list[str]]:
    """Extract failed hook ids and per-file messages from prek's text report."""
    failed_hooks: list[str] = []
    failed_files: list[str] = []
    collecting = False
    for raw_line in output.splitlines():
        tail = raw_line.strip()
        if not tail:
            continue
        if tail.startswith("- hook id:"):
            hook_id = tail.split(":", 1)[1].strip()
            if hook_id:
                failed_hooks.append(hook_id)
            collecting = True
            continue
        if tail.startswith("- "):
            continue
        if tail.endswith(("Passed", "Skipped")):
            collecting = False
            continue
        if tail.endswith("Failed"):
            collecting = True
            continue
        if collecting:
            failed_files.append(tail)
    return failed_hooks, failed_files


def format_report(result: PrecommitResult) -> str:
    lines = [f"prek exited with code {result.exit_code}"]
    for hook_id in result.failed_hooks:
        lines.append(f"- hook: {hook_id}")
    for detail in result.failed_files:
        lines.append(f"  - {detail}")
    if not result.failed_hooks and not result.failed_files and result.output:
        lines.extend(line for line in result.output.splitlines() if line.strip())
    return "\n".join(lines)


def run_precommit_gate(
    files: list[tuple[str, Path]],
    config_root: Path,
    *,
    mode: str = "enabled",
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    log_callback: Callable[[str], None] | None = None,
) -> PrecommitResult:
    """Run the configured pre-commit hooks against the files about to be pushed.

    Returns ``passed=True`` when checks succeed or when the gate cannot run
    (prek/git missing or no config); violations or run errors return ``passed=False``.
    The caller decides whether a failure blocks the upload based on ``mode``.
    """
    mode = mode.strip().lower()
    if mode == "disabled":
        return PrecommitResult(passed=True, exit_code=None, output="pre-commit gate disabled")
    if not files:
        return PrecommitResult(passed=True, exit_code=None, output="no files to check")
    effective_config = effective_hooks_config(config_root)
    if effective_config is None:
        _log(log_callback, "pre-commit gate: no .pre-commit-config.yaml found; skipping hooks")
        return PrecommitResult(passed=True, exit_code=None, output="no pre-commit config")
    if not precommit_available():
        _log(log_callback, "pre-commit gate: 'prek' binary not available; skipping hooks")
        return PrecommitResult(passed=True, exit_code=None, output="prek not available")
    if not git_available():
        _log(log_callback, "pre-commit gate: 'git' binary not available; skipping hooks")
        return PrecommitResult(passed=True, exit_code=None, output="git not available")

    worktree: Path | None = None
    try:
        config_text = effective_config.read_text(encoding="utf-8")
        worktree = _stage_worktree(files, config_text)
        exit_code, output = _run_prek(worktree, [relative for relative, _ in files], timeout)
    except Exception as err:  # noqa: BLE001
        _log(log_callback, f"pre-commit gate: error running hooks: {err}")
        return PrecommitResult(passed=False, exit_code=None, output=f"pre-commit gate error: {err}")
    finally:
        if worktree is not None:
            shutil.rmtree(worktree, ignore_errors=True)

    failed_hooks, failed_files = parse_report(output)
    result = PrecommitResult(
        passed=exit_code == 0,
        exit_code=exit_code,
        output=output,
        failed_hooks=tuple(failed_hooks),
        failed_files=tuple(failed_files),
    )
    _log(log_callback, "pre-commit gate: " + ("hooks passed" if result.passed else "hooks found violations"))
    return result