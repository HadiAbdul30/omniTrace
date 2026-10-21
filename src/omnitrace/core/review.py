"""Interactive patch review, optional staging tests, and final approval."""
from __future__ import annotations

import os
import shlex
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text

from omnitrace.core.patcher import extract_and_apply_patch, inspect_patch
from omnitrace.core.process import ProcessResult
from omnitrace.core.verification import TestVerification, verify_patch_tests


def _check_status(result: ProcessResult) -> str:
    if result.timed_out:
        return "TIMEOUT"
    return "PASS" if result.returncode == 0 else f"FAIL (exit {result.returncode})"


def _show_output(console: Console, title: str, result: ProcessResult) -> None:
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    if combined:
        console.print(Panel(Text(combined), title=title))
    if result.output_truncated:
        console.print(f"{title}: output truncated at 1 MB per stream.")


def _run_configured_tests(diagnosis: str, console: Console) -> bool | None:
    command = os.environ.get("OMNITRACE_TEST_COMMAND", "").strip()
    if not command:
        return None
    try:
        argv = shlex.split(command)
        if not argv:
            return None
        timeout = float(os.environ.get("OMNITRACE_TEST_TIMEOUT", "120"))
    except ValueError:
        console.print("Test validation skipped: invalid OMNITRACE_TEST_TIMEOUT.")
        return None
    if not sys.stdin.isatty():
        console.print("Test validation skipped: test execution needs interactive approval.")
        return None
    display_command = shlex.join(argv)
    console.print(Text(f"Configured test command: {display_command}"))
    if not Confirm.ask(
        "Run this command on temporary copies inside Linux Bubblewrap isolation?",
        default=False,
    ):
        console.print("Test validation skipped by user.")
        return None
    try:
        result: TestVerification = verify_patch_tests(diagnosis, argv, timeout=timeout)
    except (OSError, ValueError, RuntimeError, SyntaxError) as exc:
        console.print(f"Test validation setup failed ({type(exc).__name__}): {exc}; no tests ran.")
        return None

    console.print(
        "Validation report: "
        f"baseline {_check_status(result.baseline)} · "
        f"patched candidate {_check_status(result.candidate)}"
    )
    _show_output(console, "Baseline test output", result.baseline)
    _show_output(console, "Patched candidate test output", result.candidate)
    return result.candidate_passed


def review_and_apply(diagnosis: str, console: Console | None = None) -> bool:
    """Show a verified diff, optionally run approved staging tests, then ask before writing."""
    console = console or Console()
    try:
        preview = inspect_patch(diagnosis)
    except (ValueError, OSError, SyntaxError) as exc:
        console.print(f"Patch not eligible for review: {exc}")
        return False

    syntax_status = "PASS" if preview.syntax_validated else "SKIPPED (non-Python target)"
    console.print(
        "Patch report: generated PASS · parsed PASS · exact source match PASS · "
        f"syntax {syntax_status} · tests PENDING · original write PENDING APPROVAL"
    )
    console.print(Panel(preview.diff or "No content changes.", title=f"Proposed diff: {preview.target}"))
    if not preview.diff:
        console.print("No changes to apply.")
        return False

    test_status = _run_configured_tests(diagnosis, console)
    if test_status is None:
        console.print("Patch report: tests SKIPPED; syntax validation is not proof the fix is correct.")
    elif not test_status:
        console.print("Patch report: candidate tests FAILED; patch application is blocked by default.")
        if not sys.stdin.isatty() or not Confirm.ask(
            "Apply despite the failed candidate tests?", default=False
        ):
            console.print("Patch not applied.")
            return False

    if not sys.stdin.isatty():
        console.print("Patch not applied: approval requires an interactive terminal.")
        return False
    if not Confirm.ask("Apply this exact change to the original file?", default=False):
        console.print("Patch reviewed but not applied.")
        return False
    return extract_and_apply_patch(diagnosis, expected_digest=preview.source_digest)
