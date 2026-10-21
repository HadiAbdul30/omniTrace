import io
import json
import os
import runpy
import shlex
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch as mock_patch
from urllib.error import URLError

import pytest

from omnitrace import __main__ as cli
from omnitrace.core import review as review_module
from omnitrace.core.ai_router import analyze_error, extract_cross_file_context
from omnitrace.core.dispatcher import send_to_discord
from omnitrace.core.patcher import (
    _apply_patch,
    extract_and_apply_patch,
    inspect_patch,
    preview_patch,
    revert_file,
)
from omnitrace.core.process import run_command, run_script
from omnitrace.core.review import review_and_apply
from omnitrace.core.verification import SandboxUnavailable, verify_patch_tests
from omnitrace.db import database


def patch(path: str, search: str, replacement: str) -> str:
    return f"<<<FILEPATH: {path}>>>\n<<<SEARCH>>>\n{search}\n<<<REPLACE>>>\n{replacement}\n<<<END>>>"


def test_patch_replaces_exact_unique_block_and_makes_backup(tmp_path: Path):
    source = tmp_path / "sample.py"
    source.write_text("x = 1\nprint(x)\n")
    assert _apply_patch(patch("sample.py", "x = 1", "x = 2"), tmp_path)
    assert source.read_text() == "x = 2\nprint(x)\n"
    assert (tmp_path / "sample.py.bak").read_text() == "x = 1\nprint(x)\n"


def test_preview_is_unified_diff_and_does_not_modify_file(tmp_path: Path):
    source = tmp_path / "sample.py"
    source.write_text("x = 1\n")
    diff = preview_patch(patch("sample.py", "x = 1", "x = 2"), tmp_path)
    assert "-x = 1" in diff
    assert "+x = 2" in diff
    assert source.read_text() == "x = 1\n"
    assert not (tmp_path / "sample.py.bak").exists()


def test_apply_rejects_source_changed_after_review(tmp_path: Path):
    source = tmp_path / "sample.py"
    source.write_text("x = 1\n")
    diagnosis = patch("sample.py", "x = 1", "x = 2")
    preview = inspect_patch(diagnosis, tmp_path)
    source.write_text("x = 1\n# concurrent edit\n")
    assert not extract_and_apply_patch(diagnosis, expected_digest=preview.source_digest)
    assert source.read_text() == "x = 1\n# concurrent edit\n"
    assert not (tmp_path / "sample.py.bak").exists()


def test_patch_preserves_crlf_and_file_mode(tmp_path: Path):
    source = tmp_path / "sample.py"
    source.write_bytes(b"x = 1\r\nprint(x)\r\n")
    source.chmod(0o755)
    assert _apply_patch(patch("sample.py", "x = 1", "x = 2"), tmp_path)
    assert source.read_bytes() == b"x = 2\r\nprint(x)\r\n"
    assert os.stat(source).st_mode & 0o777 == 0o755


@pytest.mark.parametrize("content", ["x=1\nx=1\n", "x=2\n"])
def test_rejects_ambiguous_or_stale_source_without_modification(tmp_path: Path, content: str):
    source = tmp_path / "sample.py"
    source.write_text(content)
    with pytest.raises(ValueError):
        _apply_patch(patch("sample.py", "x=1", "x=3"), tmp_path)
    assert source.read_text() == content
    assert not (tmp_path / "sample.py.bak").exists()


def test_rejects_syntax_error_without_modification(tmp_path: Path):
    source = tmp_path / "sample.py"
    source.write_text("x = 1\n")
    with pytest.raises(SyntaxError):
        _apply_patch(patch("sample.py", "x = 1", "def ("), tmp_path)
    assert source.read_text() == "x = 1\n"
    assert not (tmp_path / "sample.py.bak").exists()


def test_rejects_path_traversal(tmp_path: Path):
    outside = tmp_path.parent / "outside.py"
    outside.write_text("x=1\n")
    with pytest.raises(ValueError):
        _apply_patch(patch("../outside.py", "x=1", "x=2"), tmp_path)


def test_rejects_existing_backup(tmp_path: Path):
    source = tmp_path / "sample.txt"
    source.write_text("a\n")
    (tmp_path / "sample.txt.bak").write_text("keep\n")
    with pytest.raises(FileExistsError):
        _apply_patch(patch("sample.txt", "a", "b"), tmp_path)
    assert source.read_text() == "a\n"
    assert (tmp_path / "sample.txt.bak").read_text() == "keep\n"


def test_failed_atomic_replace_keeps_source_intact(tmp_path: Path):
    source = tmp_path / "sample.py"
    original = b"value = 1\n"
    source.write_bytes(original)
    with (
        mock_patch("omnitrace.core.patcher.os.replace", side_effect=OSError("disk full")),
        pytest.raises(OSError, match="disk full"),
    ):
        _apply_patch(patch("sample.py", "value = 1", "value = 2"), tmp_path)
    assert source.read_bytes() == original
    assert (tmp_path / "sample.py.bak").read_bytes() == original
    assert not list(tmp_path.glob(".omnitrace-tmp-*"))


def test_revert_restores_and_consumes_backup(tmp_path: Path):
    source = tmp_path / "sample.txt"
    source.write_text("new\n")
    (tmp_path / "sample.txt.bak").write_text("old\n")
    assert revert_file(str(source))
    assert source.read_text() == "old\n"
    assert not (tmp_path / "sample.txt.bak").exists()
    assert (tmp_path / "sample.txt.pre-revert").read_text() == "new\n"


def test_revert_rejects_symlink_backup_and_target(tmp_path: Path):
    original = tmp_path / "original.txt"
    original.write_text("outside backup data\n")
    backup_link_target = tmp_path / "sample.txt.bak"
    backup_link_target.symlink_to(original)
    target = tmp_path / "sample.txt"
    target.write_text("keep this\n")
    assert not revert_file(str(target))
    assert target.read_text() == "keep this\n"

    backup_link_target.unlink()
    backup_link_target.write_text("restore me\n")
    target.unlink()
    target.symlink_to(original)
    assert not revert_file(str(target))
    assert target.is_symlink()
    assert original.read_text() == "outside backup data\n"


def test_rejects_symlink_target(tmp_path: Path):
    actual = tmp_path / "actual.txt"
    actual.write_text("a\n")
    (tmp_path / "alias.txt").symlink_to(actual)
    with pytest.raises(ValueError):
        _apply_patch(patch("alias.txt", "a", "b"), tmp_path)
    assert actual.read_text() == "a\n"


@pytest.mark.skipif(os.name == "nt", reason="directory symlink setup is platform-dependent")
def test_rejects_symlink_directory_escaping_project(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "sample.py"
    target.write_text("value = 1\n")
    (project / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="inside the current project"):
        _apply_patch(patch("linked/sample.py", "value = 1", "value = 2"), project)
    assert target.read_text() == "value = 1\n"


def test_database_persists_crash_record(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "ledger.sqlite3"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    database.init_db()
    database.log_error("traceback", "diagnosis")
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT error_trace, ai_diagnosis FROM error_logs").fetchone()
    assert row == ("traceback", "diagnosis")
    assert os.stat(db_path).st_mode & 0o777 == 0o600


def test_database_rejects_symlink_target(tmp_path: Path, monkeypatch):
    target = tmp_path / "important.db"
    target.write_bytes(b"preserve me")
    link = tmp_path / "ledger.db"
    link.symlink_to(target)
    monkeypatch.setattr(database, "DB_PATH", str(link))
    with pytest.raises(OSError, match="symbolic link"):
        database.init_db()
    assert target.read_bytes() == b"preserve me"


def test_process_runner_bounds_output(tmp_path: Path):
    script = tmp_path / "noisy.py"
    script.write_text("print('x' * 1_100_000)\n")
    result = run_script(str(script), timeout=5)
    assert result.returncode == 0
    assert result.output_truncated
    assert len(result.stdout.encode()) < 1_000_100


def test_process_runner_times_out(tmp_path: Path):
    script = tmp_path / "slow.py"
    script.write_text("import time\ntime.sleep(10)\n")
    result = run_script(str(script), timeout=0.1)
    assert result.timed_out
    assert result.returncode == 124


@pytest.mark.skipif(os.name != "posix", reason="process-group cleanup is POSIX-specific")
def test_process_runner_timeout_stops_child_processes(tmp_path: Path):
    ready = tmp_path / "ready"
    marker = tmp_path / "survived"
    child_code = (
        "import time; from pathlib import Path; time.sleep(0.8); "
        f"Path({str(marker)!r}).touch()"
    )
    parent_code = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
        f"open({str(ready)!r}, 'w').close(); time.sleep(10)"
    )
    script = tmp_path / "parent.py"
    script.write_text(parent_code)
    result = run_script(str(script), timeout=0.3)
    assert result.timed_out
    assert ready.exists()
    time.sleep(1)
    assert not marker.exists()


def _enable_staged_runner_for_unit_test(monkeypatch):
    # These tests use inert local Python snippets; they exercise staging and
    # comparison, while production sandbox availability is tested separately.
    monkeypatch.setattr("omnitrace.core.verification._sandbox_prefix", lambda: ("bwrap",))
    monkeypatch.setattr(
        "omnitrace.core.verification._run_isolated",
        lambda argv, *, timeout, cwd, env, bwrap: run_command(
            argv, timeout=timeout, cwd=cwd, env=env
        ),
    )


def test_staged_validation_runs_baseline_and_candidate_without_touching_source(tmp_path: Path, monkeypatch):
    _enable_staged_runner_for_unit_test(monkeypatch)
    source = tmp_path / "app.py"
    source.write_text("value = 1\n")
    (tmp_path / ".npmrc").write_text("//registry.example/:_authToken=secret\n")
    result = verify_patch_tests(
        patch("app.py", "value = 1", "value = 2"),
        [sys.executable, "-c", "from pathlib import Path; assert not Path('.npmrc').exists() and 'value = 2' in Path('app.py').read_text()"],
        project_root=tmp_path,
        timeout=5,
    )
    assert result.baseline.returncode != 0
    assert result.candidate.returncode == 0
    assert result.candidate_passed
    assert source.read_text() == "value = 1\n"
    assert not (tmp_path / "app.py.bak").exists()


def test_staged_validation_reports_candidate_regression(tmp_path: Path, monkeypatch):
    _enable_staged_runner_for_unit_test(monkeypatch)
    source = tmp_path / "app.py"
    source.write_text("value = 1\n")
    result = verify_patch_tests(
        patch("app.py", "value = 1", "value = 2"),
        [sys.executable, "-c", "from pathlib import Path; assert 'value = 1' in Path('app.py').read_text()"],
        project_root=tmp_path,
        timeout=5,
    )
    assert result.baseline.returncode == 0
    assert result.candidate.returncode != 0
    assert not result.candidate_passed
    assert source.read_text() == "value = 1\n"


def test_staged_validation_fails_closed_when_sandbox_unavailable(tmp_path: Path, monkeypatch):
    source = tmp_path / "app.py"
    source.write_text("value = 1\n")
    called = []
    monkeypatch.setattr(
        "omnitrace.core.verification._sandbox_prefix",
        lambda: (_ for _ in ()).throw(SandboxUnavailable("sandbox unavailable")),
    )
    monkeypatch.setattr(
        "omnitrace.core.verification._run_isolated",
        lambda *args, **kwargs: called.append(True),
    )
    with pytest.raises(SandboxUnavailable, match="sandbox unavailable"):
        verify_patch_tests(
            patch("app.py", "value = 1", "value = 2"),
            [sys.executable, "-c", "raise SystemExit(1)"],
            project_root=tmp_path,
        )
    assert not called
    assert source.read_text() == "value = 1\n"


def test_noninteractive_review_never_runs_or_applies_patch(tmp_path: Path, monkeypatch):
    source = tmp_path / "app.py"
    source.write_text("value = 1\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OMNITRACE_TEST_COMMAND", "pytest")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    result = review_and_apply(patch("app.py", "value = 1", "value = 2"))
    assert not result
    assert source.read_text() == "value = 1\n"
    assert not (tmp_path / "app.py.bak").exists()


def test_approved_review_applies_exact_patch_and_keeps_backup(tmp_path: Path, monkeypatch):
    source = tmp_path / "app.py"
    original = "value = 1\n"
    source.write_text(original)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OMNITRACE_TEST_COMMAND", raising=False)
    monkeypatch.setattr(review_module.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(review_module.Confirm, "ask", lambda *args, **kwargs: True)

    assert review_and_apply(patch("app.py", "value = 1", "value = 2"))
    assert source.read_text() == "value = 2\n"
    assert (tmp_path / "app.py.bak").read_text() == original


def test_review_runs_candidate_tests_then_applies_approved_patch(
    tmp_path: Path, monkeypatch, capsys
):
    _enable_staged_runner_for_unit_test(monkeypatch)
    source = tmp_path / "app.py"
    original = "value = 1\n"
    source.write_text(original)
    diagnosis = patch("app.py", "value = 1", "value = 2")
    command = shlex.join(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; assert 'value = 2' in Path('app.py').read_text()",
        ]
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OMNITRACE_TEST_COMMAND", command)
    monkeypatch.setenv("OMNITRACE_TEST_TIMEOUT", "5")
    monkeypatch.setattr(review_module.sys.stdin, "isatty", lambda: True)
    approvals = []

    def approve(prompt, **kwargs):
        approvals.append(prompt)
        return True

    monkeypatch.setattr(review_module.Confirm, "ask", approve)
    assert review_and_apply(diagnosis)
    output = capsys.readouterr().out
    assert "baseline FAIL (exit 1)" in output
    assert "patched candidate PASS" in output
    assert len(approvals) == 2
    assert source.read_text() == "value = 2\n"
    assert (tmp_path / "app.py.bak").read_text() == original


def test_ai_router_accepts_valid_ollama_response(monkeypatch):
    structured = {
        "diagnosis": "Diagnosis only",
        "patch": {"filepath": "", "search": "", "replace": ""},
    }
    response = io.BytesIO(json.dumps({"response": json.dumps(structured)}).encode())
    monkeypatch.setenv("OMNITRACE_MODEL", "test-model")
    monkeypatch.setenv("OMNITRACE_OLLAMA_TIMEOUT", "12")

    def respond(request, timeout):
        assert timeout == 12
        assert json.loads(request.data)["model"] == "test-model"
        assert json.loads(request.data)["format"]["required"] == ["diagnosis", "patch"]
        assert json.loads(request.data)["options"]["temperature"] == 0
        return response

    monkeypatch.setattr("urllib.request.urlopen", respond)
    assert analyze_error("Traceback (most recent call last):\nValueError") == "Diagnosis only"


def test_ai_router_formats_structured_patch_for_strict_patcher(monkeypatch):
    structured = {
        "diagnosis": "Handle a zero divisor.",
        "patch": {
            "filepath": "app.py",
            "search": "return n / d",
            "replace": "if d == 0:\n    raise ValueError('zero divisor')\nreturn n / d",
        },
    }
    response = io.BytesIO(json.dumps({"response": json.dumps(structured)}).encode())
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: response)
    result = analyze_error("Traceback (most recent call last):\nZeroDivisionError")
    assert "<<<FILEPATH: app.py>>>" in result
    assert "<<<SEARCH>>>\nreturn n / d\n<<<REPLACE>>>" in result
    assert result.endswith("<<<END>>>")


def test_ai_router_reports_connection_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise URLError("offline")
    monkeypatch.setattr("urllib.request.urlopen", fail)
    assert "Ollama request failed" in analyze_error("traceback")


def test_ai_router_rejects_malformed_response(monkeypatch):
    response = io.BytesIO(b'{"unexpected": true}')
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: response)
    assert "malformed response" in analyze_error("traceback")


def test_ai_router_rejects_malformed_structured_output(monkeypatch):
    response = io.BytesIO(json.dumps({"response": "Here's a patch"}).encode())
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: response)
    assert "malformed structured output" in analyze_error("traceback")


def test_ai_router_discards_incomplete_patch_fields(monkeypatch):
    structured = {
        "diagnosis": "Likely typo.",
        "patch": {
            "filepath": "app.py",
            "search": "print(wrong_name)",
        },
    }
    response = io.BytesIO(json.dumps({"response": json.dumps(structured)}).encode())
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: response)
    result = analyze_error("traceback")
    assert "discarded an incomplete patch proposal" in result
    assert "<<<FILEPATH:" not in result


def test_ai_router_rejects_empty_response(monkeypatch):
    response = io.BytesIO(b'{"response": "  "}')
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: response)
    assert "empty or malformed" in analyze_error("traceback")


def test_ai_router_reports_timeout(monkeypatch):
    with mock_patch("urllib.request.urlopen", side_effect=TimeoutError):
        assert "Ollama request failed" in analyze_error("traceback")


def test_context_reader_never_reads_outside_project(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    local = project / "local.py"
    local.write_text("safe_local = True\n")
    outside = tmp_path / "secret.py"
    outside.write_text("secret_value = 'do not include'\n")
    monkeypatch.chdir(project)
    trace = f'File "{local}"\nFile "{outside}"\n'
    context = extract_cross_file_context(trace)
    assert "safe_local" in context
    assert "do not include" not in context


def test_discord_disabled_does_not_make_network_request(monkeypatch):
    monkeypatch.delenv("OMNITRACE_DISCORD_WEBHOOK", raising=False)
    with mock_patch("urllib.request.urlopen") as urlopen:
        send_to_discord("trace", "diagnosis")
    urlopen.assert_not_called()


def test_discord_failure_is_reported_without_raising(monkeypatch):
    monkeypatch.setenv("OMNITRACE_DISCORD_WEBHOOK", "https://example.invalid/hook")
    with mock_patch("urllib.request.urlopen", side_effect=TimeoutError):
        send_to_discord("trace", "diagnosis")


def test_discord_payload_redacts_values_and_uses_timeout(monkeypatch):
    monkeypatch.setenv("OMNITRACE_DISCORD_WEBHOOK", "https://example.invalid/webhook")
    with mock_patch("urllib.request.urlopen", return_value=io.BytesIO(b"")) as urlopen:
        send_to_discord("password=very-secret", "token: abc123")
    request = urlopen.call_args.args[0]
    timeout = urlopen.call_args.kwargs["timeout"]
    payload = json.loads(request.data)
    assert timeout == 5
    assert "very-secret" not in json.dumps(payload)
    assert "abc123" not in json.dumps(payload)


def test_dashboard_escapes_diagnostic_html_and_limits_results(tmp_path: Path, monkeypatch):
    pytest.importorskip("flask")
    from omnitrace.ui import server
    db_path = tmp_path / "dashboard.sqlite3"
    monkeypatch.setattr(server, "DB_PATH", str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE error_logs (id INTEGER, timestamp TEXT, error_trace TEXT, ai_diagnosis TEXT)")
        conn.execute("INSERT INTO error_logs VALUES (1, 'now', '<script>alert(1)</script>', '<img src=x onerror=alert(1)>')")
    response = server.app.test_client().get("/")
    assert response.status_code == 200
    assert b"&lt;script&gt;" in response.data
    assert b"&lt;img" in response.data
    assert b"https://" not in response.data


@pytest.mark.parametrize(("argv", "expected"), [(["omnitrace", "--help"], 0), (["omnitrace", "--not-a-command"], 2), (["omnitrace"], 1)])
def test_cli_basic_exit_codes(argv, expected, monkeypatch):
    monkeypatch.setattr(cli.sys, "argv", argv)
    monkeypatch.setattr(cli, "init_db", lambda: pytest.fail("CLI should not initialize DB for help/usage errors"))
    assert cli.main() == expected


def test_importing_package_does_not_create_user_files(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-c", "import omnitrace"],
        env=environment,
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert list(home.iterdir()) == []


def test_wrapper_missing_script_has_actionable_exit_code():
    assert cli.run_wrapper_mode("/definitely/not/a/script.py") == 2


def test_dummy_logger_example_returns_a_traceback():
    example = Path(__file__).resolve().parents[1] / "examples" / "dummy_logger.py"
    namespace = runpy.run_path(str(example), run_name="omnitrace_test_example")
    traceback_text = namespace["simulate_background_crash"]()
    assert "KeyError" in traceback_text
    assert "database_password" in traceback_text
