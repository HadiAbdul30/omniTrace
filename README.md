# OmniTrace

**A privacy-first, local AI debugging and state-orchestration fabric.**

OmniTrace is a local AI-powered debugging tool that monitors Python scripts and application logs, detects errors, and uses locally running Large Language Models (LLMs) to explain exceptions and suggest code fixes.

Powered by [Ollama](https://ollama.com/), OmniTrace helps developers diagnose bugs, review historical crashes, and streamline debugging without sending proprietary source code to external AI services.

## 🎬 Demo

![OmniTrace Auto-Patcher Demo](demo.gif)

*OmniTrace Auto-Patcher in action.*

## ✨ Features

- **🔒 Privacy First:** Run AI-powered debugging locally without relying on external AI APIs.
- **🤖 AI-Powered Diagnostics:** Get plain-English explanations of exceptions and stack traces.
- **🛠️ Automated Fix Suggestions:** Receive actionable recommendations to help resolve bugs.
- **⚡ Real-Time Log Monitoring:** Detect and diagnose errors as they appear in application logs.
- **📊 Visual Debug Dashboard:** Browse historical crashes and AI-generated diagnoses through a local web interface.
- **🗃️ Persistent Debug Ledger:** Store historical debugging records in a local SQLite database.
- **🦙 Local LLM Support:** Use models available through Ollama.
- **💻 Multiple Operating Modes:** Debug individual Python scripts, monitor application logs, or explore your debugging history.

## 📋 Requirements

Before installing OmniTrace, ensure you have:

- Python 3.9 or later.
- [Ollama](https://ollama.com/) installed and running.
- Git installed on your machine.

> **Note:** Confirm the minimum supported Python version against your project's actual requirements.

## 🚀 Installation

### 1. Install Ollama

Download and install Ollama from the official website:

https://ollama.com/

### 2. Download a Language Model

Pull the default model:

```bash
ollama pull llama3.2
```

Ensure Ollama is running before using OmniTrace.

### 3. Clone the Repository

Replace `YOUR_USERNAME` with your GitHub username or organization.

```bash
git clone https://github.com/YOUR_USERNAME/omnitrace.git
cd omnitrace
```

### 4. Create a Virtual Environment

Create and activate a Python virtual environment.

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 5. Install OmniTrace

Install the project in editable mode:

```bash
pip install -e .
```

Once installation is complete, the `omnitrace` command should be available in your environment.

## 💡 Usage

OmniTrace supports three operating modes.

### Mode 1: Debug a Python Script

Run a Python script through OmniTrace to capture errors and request AI-powered diagnostics.

```bash
omnitrace my_broken_script.py
```

**How it works:**

1. OmniTrace executes the specified Python script.
2. It captures errors and stack traces.
3. It sends relevant diagnostic information to your local Ollama model.
4. It displays an explanation of the error and suggested fixes.

Replace `my_broken_script.py` with the path to your Python script.

**Use case:** Quickly understand exceptions and investigate bugs while developing Python applications.

### Mode 2: Monitor Application Logs

Monitor a log file for errors while your application runs.

```bash
omnitrace --watch app.log
```

**How it works:**

1. OmniTrace monitors the specified log file.
2. It detects stack traces as they appear.
3. It sends relevant error information to your local LLM.
4. It displays a diagnosis and suggested solutions.

This mode is useful for debugging background services and applications that write errors to log files.

> **Note:** Log monitoring requires your application to write errors to the monitored file. Detection behavior depends on the implementation.

### Mode 3: Dashboard (Visualize Your Debug Ledger)

Launch the local web dashboard to explore historical crash logs and AI-generated diagnoses.

```bash
omnitrace --ui
```

**Dashboard features:**

- **📊 Crash History:** Browse previously recorded crashes and stack traces.
- **🤖 AI Diagnoses:** Review explanations and suggested fixes for historical errors.
- **🗃️ SQLite Storage:** Access debugging records persisted in a local SQLite database.
- **🔍 Error Investigation:** Review past failures to help identify recurring problems.

**How it works:**

1. Run `omnitrace --ui` in your terminal.
2. OmniTrace starts its local web dashboard.
3. Open the local URL displayed in your terminal.
4. Browse historical crash records and their associated AI diagnoses.

The dashboard makes it easier to investigate past errors without manually searching through log files or querying the database.

> **Privacy note:** Keep the dashboard bound to localhost unless remote access is explicitly configured and secured.

## ⚙️ Configuration

OmniTrace uses Ollama to run language models locally.

You can change the model using the `OMNITRACE_MODEL` environment variable.

### Linux / macOS

```bash
export OMNITRACE_MODEL="qwen2.5-coder"
```

### Windows (PowerShell)

```powershell
$env:OMNITRACE_MODEL = "qwen2.5-coder"
```

Download the selected model if it is not already available:

```bash
ollama pull qwen2.5-coder
```

If `OMNITRACE_MODEL` is not set, OmniTrace uses its configured default model, expected to be `llama3.2`.

## 🔐 Privacy and Security

OmniTrace is designed to keep your debugging workflow local by using Ollama for AI inference.

When configured to use a local Ollama instance:

- Your code does not need to be sent to a third-party AI API.
- Stack traces can be analyzed locally.
- Debugging records can be stored in a local SQLite database.
- Proprietary source code can remain on your machine.

**Security recommendations:**

- Avoid including passwords, API keys, access tokens, or other secrets in logs.
- Keep the dashboard accessible only from trusted interfaces.
- Protect your SQLite database and log files from unauthorized access.
- Review any suggested code changes before applying them.

Local inference does not automatically guarantee complete privacy. Ensure your application, logging configuration, and additional integrations do not transmit sensitive information externally.

## 🛠️ Troubleshooting

### Ollama is not responding

Make sure Ollama is installed and running.

Check the installed models:

```bash
ollama list
```

### The selected model is unavailable

Download the model you want to use:

```bash
ollama pull llama3.2
```

For a different model, replace `llama3.2` with the configured model name.

### The `omnitrace` command is not found

Ensure your virtual environment is activated and install the project again:

```bash
pip install -e .
```

If the command is still unavailable, verify that your packaging configuration defines the appropriate command-line entry point.

### The dashboard does not start

Try the following:

1. Ensure OmniTrace is installed correctly.
2. Confirm that the dashboard command-line option is supported.
3. Check the terminal output for startup errors.
4. Verify that the dashboard's configured port is available.

### No historical crashes appear in the dashboard

Check that:

- OmniTrace has recorded crashes in the SQLite database.
- The dashboard is reading from the correct database file.
- The application has permission to access the database.

## 🗺️ Roadmap

Potential future improvements include:

- [ ] Enhanced root-cause analysis.
- [ ] Context-aware code fix suggestions.
- [ ] Automated patch generation and application.
- [ ] Configurable log monitoring and filtering.
- [ ] Support for additional programming languages.
- [ ] Search and filtering for historical crash records.
- [ ] Exportable diagnostic reports.
- [ ] Integration with testing tools and development workflows.

## 🤝 Contributing

Contributions, bug reports, and feature suggestions are welcome.

To contribute:

1. Fork the repository.
2. Create a branch for your changes.
3. Implement and test your improvements.
4. Submit a pull request describing your changes.

Please include relevant test cases when introducing new functionality.

## 📄 License

Add your project's license information here.

If you intend to distribute OmniTrace as an open-source project, include a `LICENSE` file in the repository.

---

**OmniTrace — Debug locally. Understand errors faster. Keep your code private.**