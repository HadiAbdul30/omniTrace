"""Conservative application of the reviewable OmniTrace search/replace format."""
from __future__ import annotations

import difflib
import hashlib
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

console = Console()
_ENCODING = "utf-8"

_PATCH = re.compile(
    r"<<<FILEPATH:\s*(.*?)>>>\s*<<<SEARCH>>>\n(.*?)\n<<<REPLACE>>>\n(.*?)\n<<<END>>>",
    re.DOTALL,
)


@dataclass(frozen=True)
class PatchPreview:
    target: Path
    diff: str
    syntax_validated: bool
    source_digest: str


def _target_path(raw: str, root: Path) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("patch target must be inside the current project directory")
    if not resolved.is_file() or candidate.is_symlink():
        raise ValueError("patch target must be a regular file, not a symbolic link")
    return resolved


def _prepare_patch(diagnosis: str, root: Path | None = None):
    """Parse and validate a patch without modifying the project."""
    markers = ("<<<FILEPATH:", "<<<SEARCH>>>", "<<<REPLACE>>>", "<<<END>>>")
    if any(diagnosis.count(marker) != 1 for marker in markers):
        raise ValueError("patch markers must each appear exactly once")
    matches = list(_PATCH.finditer(diagnosis))
    if len(matches) != 1:
        raise ValueError("expected exactly one complete patch block")
    match = matches[0]
    raw_path, search, replacement = (part.strip("\n") for part in match.groups())
    if not raw_path or not search or search == replacement:
        raise ValueError("patch path and search text must be non-empty and change content")
    base = (root or Path.cwd()).resolve()
    target = _target_path(raw_path, base)
    original_bytes = target.read_bytes()
    decoded = original_bytes.decode(_ENCODING)
    original = decoded.replace("\r\n", "\n").replace("\r", "\n")
    if original.count(search) != 1:
        raise ValueError("search text must match exactly once in the current file")
    updated = original.replace(search, replacement, 1)

    if target.suffix == ".py":
        import ast
        ast.parse(updated, filename=str(target))
    return target, original, updated, original_bytes


def inspect_patch(diagnosis: str, root: Path | None = None) -> PatchPreview:
    """Validate a proposed patch and return review information without writing."""
    target, original, updated, original_bytes = _prepare_patch(diagnosis, root)
    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=f"a/{target.name}",
        tofile=f"b/{target.name}",
    ))
    return PatchPreview(
        target,
        diff,
        target.suffix == ".py",
        hashlib.sha256(original_bytes).hexdigest(),
    )


def preview_patch(diagnosis: str, root: Path | None = None) -> str:
    """Return a unified diff after all patch preconditions and syntax checks pass."""
    return inspect_patch(diagnosis, root).diff


def _apply_patch(
    diagnosis: str,
    root: Path | None = None,
    expected_digest: str | None = None,
) -> bool:
    """Apply a single exact, unique replacement after staging and validation."""
    target, _original, updated, original_bytes = _prepare_patch(diagnosis, root)
    if expected_digest is not None and hashlib.sha256(original_bytes).hexdigest() != expected_digest:
        raise RuntimeError("source changed after the proposed diff was reviewed")
    backup = target.with_name(target.name + ".bak")
    if backup.exists():
        raise FileExistsError(f"backup already exists; preserve it before patching: {backup}")
    fd, staged_name = tempfile.mkstemp(prefix=".omnitrace-tmp-", dir=target.parent)
    try:
        line_ending = "\r\n" if b"\r\n" in original_bytes else "\n"
        staged_bytes = updated.replace("\n", line_ending).encode(_ENCODING)
        with os.fdopen(fd, "wb") as staged:
            staged.write(staged_bytes)
            staged.flush()
            os.fsync(staged.fileno())
        os.chmod(staged_name, stat.S_IMODE(target.stat().st_mode))
        # Exclusive create avoids clobbering a backup created concurrently.
        backup_fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(backup_fd, "wb") as backup_file:
                backup_file.write(original_bytes)
                backup_file.flush()
                os.fsync(backup_file.fileno())
            shutil.copystat(target, backup)
        except Exception:
            backup.unlink(missing_ok=True)
            raise
        # Recheck before replacement to avoid overwriting edits made during staging.
        if target.read_bytes() != original_bytes:
            backup.unlink(missing_ok=True)
            raise RuntimeError("source changed while patch was being prepared")
        os.replace(staged_name, target)
        return True
    except Exception:
        Path(staged_name).unlink(missing_ok=True)
        raise


def extract_and_apply_patch(diagnosis: str, expected_digest: str | None = None) -> bool:
    """Apply an approved patch. Callers must obtain explicit approval first."""
    try:
        target, _, _, _ = _prepare_patch(diagnosis)
        _apply_patch(diagnosis, expected_digest=expected_digest)
    except (ValueError, OSError, RuntimeError, SyntaxError) as exc:
        console.print(f"[bold red]Patch rejected: {exc}[/bold red]")
        return False
    syntax_status = "passed" if target.suffix == ".py" else "skipped (not a Python file)"
    console.print(f"[bold green]Patch applied; syntax check {syntax_status}. Backup: {target}.bak[/bold green]")
    return True


def revert_file(filepath: str) -> bool:
    """Restore a backup, preserving current contents as ``.pre-revert`` first."""
    target = Path(filepath)
    backup = Path(f"{filepath}.bak")
    if backup.is_symlink() or not backup.is_file():
        console.print(f"[bold red]No regular backup file found at {backup}[/bold red]")
        return False
    if target.is_symlink():
        console.print(f"[bold red]Refusing to restore through symbolic link {target}[/bold red]")
        return False
    staged_name = None
    preserved = Path(f"{filepath}.pre-revert")
    preserved_created = False
    restored = False
    try:
        original = backup.read_bytes()
        fd, staged_name = tempfile.mkstemp(prefix=".omnitrace-tmp-", dir=target.parent or Path("."))
        with os.fdopen(fd, "wb") as staged:
            staged.write(original)
            staged.flush()
            os.fsync(staged.fileno())
        os.chmod(staged_name, stat.S_IMODE(backup.stat().st_mode))
        if target.exists():
            current_fd = os.open(preserved, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(current_fd, "wb") as current_copy:
                current_copy.write(target.read_bytes())
                current_copy.flush()
                os.fsync(current_copy.fileno())
            preserved_created = True
        os.replace(staged_name, target)
        staged_name = None
        restored = True
        backup.unlink()
    except OSError as exc:
        if staged_name is not None:
            Path(staged_name).unlink(missing_ok=True)
        if preserved_created and not restored:
            preserved.unlink(missing_ok=True)
        console.print(f"[bold red]Could not restore backup: {exc}[/bold red]")
        return False
    detail = f" Current contents saved at {preserved}." if preserved_created else ""
    console.print(f"[bold green]Restored {target} from its backup.{detail}[/bold green]")
    return True
