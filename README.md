# OmniTrace

OmniTrace is a local-first Python debugging tool that diagnoses crashes with Ollama and offers a reviewable, syntax-checked source replacement before it changes a file.

> Early-stage software: this project is not yet ready for production use. Patch checks establish exact text matching and Python syntax only; they do not establish that a fix is correct.

## What it currently does

- Runs a Python script and analyzes its stderr when it exits unsuccessfully.
- Watches an existing log for Python tracebacks (`--watch`).
- Sends diagnostic context to a locally configured Ollama server (default model name `llama3`; OmniTrace does not install or download it). The router requests schema-constrained JSON and rejects malformed or incomplete model output before constructing a patch.
- Stores crashes in `~/.omnitrace.db` and serves a local dashboard (`--ui`, requires the dashboard extra).
- Offers an explicit confirmation before applying one exact, unique search/replace block. Python syntax is checked before the original file changes, with a sibling `.bak` backup.

There is no Discord transmission unless `OMNITRACE_DISCORD_WEBHOOK` is explicitly configured. When enabled, a redacted, truncated trace and diagnosis are sent to that webhook. Ollama requests go to `http://localhost:11434`; a remote endpoint is not configurable. The dashboard binds to `127.0.0.1`; logs remain sensitive data on disk.

## Requirements and installation

Python 3.10 or newer. The CLI uses Rich. Ollama is needed for AI diagnosis; Flask is only needed for the dashboard.

```bash
git clone https://github.com/HadiAbdul30/omniTrace.git
cd omniTrace
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
omnitrace --help
```

To install dashboard support, use `python -m pip install -e '.[dashboard]'`. To install development tools, use `python -m pip install -e '.[dev]'`.

Install Ollama from [ollama.com](https://ollama.com/), start it, and pull a model yourself. The router defaults to model identifier `llama3`; set `OMNITRACE_MODEL` to a model you have installed. No model is downloaded automatically. Use an Ollama version that supports schema-constrained JSON output. `OMNITRACE_OLLAMA_TIMEOUT` sets request timeout seconds (default 90).

Optional environment settings:

- `OMNITRACE_RUN_TIMEOUT`: wrapper process timeout in seconds (default 120; capped at 3600).
- `OMNITRACE_DISCORD_WEBHOOK`: explicitly enables remote Discord reporting. A short trace excerpt and diagnosis may be sent; basic secret-like fields are redacted, but redaction is not guaranteed.
- `OMNITRACE_TEST_COMMAND`: optional test command, such as `pytest -q`. OmniTrace asks before running it against separate temporary baseline and patched copies inside Linux Bubblewrap isolation. It is tokenized without a shell and receives a reduced environment.
- `OMNITRACE_TEST_TIMEOUT`: per-run timeout in seconds (default 120; maximum 3600).

## Usage

```bash
omnitrace examples/dummy_app.py
omnitrace --watch app.log
omnitrace --ui
omnitrace revert path/to/file.py
```

Wrapper mode runs the requested script with the current Python interpreter, inherited environment, and a 120-second default timeout (`OMNITRACE_RUN_TIMEOUT` changes it). Captured stdout and stderr are each limited to 1 MB. This executes that script with the user's normal account permissions; it is not a sandbox. The watcher starts at the end of an existing log and analyzes new traceback text. Dashboard startup requires the dashboard extra.

## Patch format and safeguards

The router asks Ollama for structured JSON, validates its fields, then formats a patch block like this for review:

```text
<<<FILEPATH: relative/path.py>>>
<<<SEARCH>>>
exact complete original text
<<<REPLACE>>>
replacement text
<<<END>>>
```

OmniTrace requires exactly one complete block, a target inside the current project directory, a regular non-symlink file, and a search string matching exactly once. It stages the replacement and parses Python syntax before writing, creates a `.bak` without overwriting an existing backup, checks for concurrent edits, then atomically replaces the file. The CLI shows a unified diff and asks for approval before changing the original. `omnitrace revert FILE` restores `FILE.bak` and preserves the current contents as `FILE.pre-revert`; keep version control checkpoints as well.

When `OMNITRACE_TEST_COMMAND` is configured and approved interactively, OmniTrace reports baseline and patched-candidate results. A failing candidate blocks application unless the user explicitly overrides that result. Test execution requires Linux Bubblewrap with working unprivileged namespaces; otherwise OmniTrace skips tests without falling back to host execution. The sandbox hides host home directories, disables networking and gives the staged project write access while exposing the host filesystem read-only for installed tools. Treat this as a risk reduction layer, not a guarantee against kernel vulnerabilities or unsafe test behavior. Syntax validation and successful tests cannot prove a fix correct.

## Development and testing

```bash
python -m pip install -e '.[dev,dashboard]'
pytest
ruff check src tests
python -m build
```

The tests mock external services and should not require an Ollama model. The dashboard loads persisted traces and diagnoses and should only be used on a trusted local machine.

## Troubleshooting

- **Ollama request failed:** start Ollama locally, confirm its API is reachable at `http://localhost:11434`, and check that `OMNITRACE_MODEL` names a model you installed. OmniTrace does not download models.
- **No patch was proposed:** the model may return diagnosis text without one valid patch block. OmniTrace rejects incomplete, ambiguous, stale, or syntactically invalid patches.
- **Tests were skipped:** set `OMNITRACE_TEST_COMMAND`, approve execution in an interactive terminal, and use Linux with Bubblewrap and working unprivileged namespaces. The command runs once on the baseline copy and once on the candidate copy. Unsupported hosts fail closed.
- **Dashboard unavailable:** install the `dashboard` extra. The dashboard reads the local diagnostic database and binds only to loopback.
- **Patch application refused:** inspect the reported reason. Existing `.bak` backups are never overwritten; preserve or move one yourself before retrying. Use version control for durable recovery.

## Project status and contributions

The repository is an early prototype. Discord reporting, source-context collection, SQLite persistence, log watching, dashboard rendering, and optional isolated test verification are present. Contributions that improve test coverage, patch verification, privacy, and installation are welcome. Please include focused tests and describe any data-flow changes.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.

OmniTrace is licensed under the MIT License; see [LICENSE](LICENSE).

## Roadmap

- Improve focused regression checks and report when the original failure is reproduced.
- Make log, source-context, and diagnostic data limits configurable.
- Strengthen isolation coverage and validate the Bubblewrap setup across supported Linux distributions.
- Improve release automation and verify the supported Python matrix in CI.
- Add CI across supported Python versions and release build checks.
