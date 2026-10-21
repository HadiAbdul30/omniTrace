"""Bounded-output subprocess execution for the explicit wrapper command."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

MAX_CAPTURE_BYTES = 1_000_000


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    output_truncated: bool = False


def _drain(stream, destination: bytearray, overflow: list[bool]) -> None:
    while chunk := stream.read(8192):
        remaining = MAX_CAPTURE_BYTES - len(destination)
        if remaining > 0:
            destination.extend(chunk[:remaining])
        if len(chunk) > max(remaining, 0):
            overflow[0] = True


def _stop_process(child: subprocess.Popen) -> None:
    """Stop the command and its descendants when the platform allows it."""
    if os.name == "posix":
        try:
            # Kill the process group even if its leader exited at the timeout
            # boundary; descendants may still be holding its output pipes.
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif child.poll() is None:
        child.kill()


def run_command(
    argv: Sequence[str],
    *,
    timeout: float = 120,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> ProcessResult:
    """Run a command with bounded output and a timeout; this is not a sandbox."""
    timeout = max(0.1, min(float(timeout), 3600.0))
    creation_options = {"start_new_session": True} if os.name == "posix" else {}
    child = subprocess.Popen(
        list(argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env,
        **creation_options,
    )
    stdout, stderr = bytearray(), bytearray()
    overflow = [False, False]
    readers = [
        threading.Thread(target=_drain, args=(child.stdout, stdout, overflow,), daemon=True),
        threading.Thread(target=_drain, args=(child.stderr, stderr, overflow,), daemon=True),
    ]
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _stop_process(child)
        child.wait()
    except BaseException:
        _stop_process(child)
        child.wait()
        raise
    for reader in readers:
        reader.join(timeout=2)
    output_truncated = any(overflow)
    suffix = b"\n[OmniTrace: output truncated at 1 MB]\n"
    return ProcessResult(
        returncode=124 if timed_out else child.returncode,
        stdout=stdout.decode("utf-8", errors="replace") + (suffix.decode() if overflow[0] else ""),
        stderr=stderr.decode("utf-8", errors="replace") + (suffix.decode() if overflow[1] else ""),
        timed_out=timed_out,
        output_truncated=output_truncated,
    )


def run_script(script: str, timeout: float = 120) -> ProcessResult:
    """Run a requested script with the current Python and bounded output."""
    return run_command([sys.executable, script], timeout=timeout)
