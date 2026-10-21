"""Run approved test commands in temporary copies inside Bubblewrap isolation."""
from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import sys
import sysconfig
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from omnitrace.core.patcher import _apply_patch, inspect_patch
from omnitrace.core.process import ProcessResult, run_command

_IGNORED_DIRS = {
    ".git", ".venv", "venv", "env", "ENV", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", "node_modules", "dist", "build", ".aws", ".ssh",
}
_IGNORED_FILES = {
    ".env",
    ".git-credentials",
    ".netrc",
    ".npmrc",
    ".omnitrace.db",
    ".pypirc",
    "id_ed25519",
    "id_rsa",
}
_MAX_PROJECT_BYTES = 250_000_000
_MAX_PROJECT_FILES = 20_000


class SandboxUnavailable(RuntimeError):
    """Raised when a working Linux Bubblewrap sandbox is unavailable."""


def _sandbox_prefix() -> tuple[str, ...]:
    """Probe the exact isolation primitives before allowing test execution."""
    if not sys.platform.startswith("linux"):
        raise SandboxUnavailable("isolated test execution is supported on Linux only")
    bwrap = shutil.which("bwrap")
    true = shutil.which("true")
    if not bwrap or not true:
        raise SandboxUnavailable("install Bubblewrap (bwrap) to run isolated tests")
    probe = run_command(
        [bwrap, "--unshare-all", "--die-with-parent", "--ro-bind", "/", "/",
         "--proc", "/proc", "--dev", "/dev", "--", true],
        timeout=5,
    )
    if probe.returncode != 0 or probe.timed_out:
        raise SandboxUnavailable(
            "Bubblewrap isolation is unavailable (user namespaces may be disabled); tests were not run"
        )
    return (bwrap,)


def _run_isolated(
    argv: Sequence[str], *, timeout: float, cwd: Path, env: dict[str, str],
    bwrap: str,
) -> ProcessResult:
    executable = shutil.which(argv[0], path=env.get("PATH")) if not Path(argv[0]).is_absolute() else argv[0]
    if not executable:
        raise SandboxUnavailable(f"test executable not found: {argv[0]}")
    if Path(executable).is_relative_to(Path.home()) or str(executable).startswith(("/home/", "/root/")):
        raise SandboxUnavailable("test executable is inside a hidden host home directory")
    # The host filesystem is visible read-only for interpreters and installed
    # test tools. Only the staged project is writable; network and namespaces
    # are isolated, and host home directories are hidden.
    isolated_env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/tmp/home",
        "TMPDIR": "/tmp",
        "TEMP": "/tmp",
        "TMP": "/tmp",
        "PYTHONPATH": os.pathsep.join(
            part for part in ("/workspace/src", "/workspace", sysconfig.get_paths().get("stdlib", "")) if part
        ),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
    }
    command = [
        bwrap, "--unshare-all", "--die-with-parent", "--new-session",
        "--ro-bind", "/", "/",
        "--bind", str(cwd), "/workspace",
        "--tmpfs", "/home", "--tmpfs", "/root", "--tmpfs", "/tmp",
        "--proc", "/proc", "--dev", "/dev",
        "--dir", "/tmp/home", "--chdir", "/workspace", "--clearenv",
    ]
    for key, value in isolated_env.items():
        if value:
            command.extend(("--setenv", key, value))
    command.extend(("--", executable, *argv[1:]))
    return run_command(command, timeout=timeout, cwd=cwd, env={"PATH": "/usr/bin:/bin"})


@dataclass(frozen=True)
class TestVerification:
    command: tuple[str, ...]
    baseline: ProcessResult
    candidate: ProcessResult

    @property
    def candidate_passed(self) -> bool:
        return self.candidate.returncode == 0 and not self.candidate.timed_out


def _ignored_file(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered in {item.lower() for item in _IGNORED_FILES}
        or lowered.startswith(".env.")
        or lowered.endswith((".log", ".bak", ".pre-revert", ".pem", ".key", ".p12", ".pfx"))
    )


def _copy_project(source: Path, destination: Path) -> None:
    total_bytes = 0
    files = 0
    for current, directories, names in os.walk(source, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_dirs = []
        for name in directories:
            if name in _IGNORED_DIRS:
                continue
            item = current_path / name
            if item.is_symlink():
                raise ValueError(f"staging skipped because the project contains a symbolic link: {item.relative_to(source)}")
            kept_dirs.append(name)
        directories[:] = kept_dirs
        relative_dir = current_path.relative_to(source)
        (destination / relative_dir).mkdir(parents=True, exist_ok=True)
        for name in names:
            if _ignored_file(name):
                continue
            item = current_path / name
            if item.is_symlink():
                raise ValueError(f"staging skipped because the project contains a symbolic link: {item.relative_to(source)}")
            if not item.is_file():
                continue
            files += 1
            total_bytes += item.stat().st_size
            if files > _MAX_PROJECT_FILES or total_bytes > _MAX_PROJECT_BYTES:
                raise ValueError("staging skipped because the project exceeds the 20,000 file or 250 MB limit")
            target = destination / relative_dir / name
            shutil.copy2(item, target)


def _test_environment(project_copy: Path, home: Path) -> dict[str, str]:
    # Preserve only runtime necessities; do not pass the user's environment wholesale.
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "PATHEXT") if key in os.environ}
    env["HOME"] = str(home)
    env["TMPDIR"] = str(home)
    env["TEMP"] = str(home)
    env["TMP"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    import sysconfig

    python_paths = [str(project_copy / "src"), str(project_copy)]
    stdlib = sysconfig.get_paths().get("stdlib")
    if stdlib:
        python_paths.append(stdlib)
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    env["PYTHONUTF8"] = "1"
    return env


def verify_patch_tests(
    diagnosis: str,
    command: str | Sequence[str],
    *,
    project_root: Path | None = None,
    timeout: float = 120,
) -> TestVerification:
    """Run the same explicit command on baseline and patched temporary copies."""
    argv = tuple(shlex.split(command) if isinstance(command, str) else command)
    if not argv:
        raise ValueError("test command is empty")
    root = (project_root or Path.cwd()).resolve()
    bwrap = _sandbox_prefix()[0]
    preview = inspect_patch(diagnosis, root)
    relative_target = preview.target.relative_to(root)
    rewritten = re.sub(
        r"<<<FILEPATH:\s*.*?>>>",
        f"<<<FILEPATH: {relative_target.as_posix()}>>>",
        diagnosis,
        count=1,
        flags=re.DOTALL,
    )

    with tempfile.TemporaryDirectory(prefix="omnitrace-verify-") as temporary:
        temp_root = Path(temporary)
        baseline_root = temp_root / "baseline"
        candidate_root = temp_root / "candidate"
        _copy_project(root, baseline_root)
        _copy_project(root, candidate_root)
        staged_target = candidate_root / relative_target
        if hashlib.sha256(staged_target.read_bytes()).hexdigest() != preview.source_digest:
            raise RuntimeError("source changed while the test copies were being prepared")
        _apply_patch(rewritten, candidate_root)
        results = []
        for name, copy_root in (("baseline", baseline_root), ("candidate", candidate_root)):
            result = _run_isolated(
                argv,
                timeout=timeout,
                cwd=copy_root,
                env=_test_environment(copy_root, temp_root),
                bwrap=bwrap,
            )
            results.append(result)
    return TestVerification(argv, results[0], results[1])
