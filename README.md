# OmniTrace

**A privacy-first, local AI debugging and state-orchestration fabric.**

OmniTrace is a local AI-powered debugging tool that monitors Python scripts and application logs, detects stack traces, and uses a locally running Large Language Model (LLM) to explain errors and suggest fixes.

Powered by [Ollama](https://ollama.com/), OmniTrace helps developers understand and troubleshoot errors without sending proprietary source code to external AI services.

## ✨ Features

- **🔒 Privacy First:** Keep your code and debugging data on your local machine.
- **🤖 AI-Powered Diagnostics:** Get plain-English explanations of Python exceptions and stack traces.
- **⚡ Real-Time Monitoring:** Detect and diagnose errors as they appear in application logs.
- **🛠️ Actionable Fixes:** Receive suggested solutions to help resolve bugs faster.
- **🦙 Local LLM Support:** Use models available through Ollama.
- **💻 Multiple Operating Modes:** Debug individual Python scripts or monitor application logs in the background.

## 📋 Requirements

Before installing OmniTrace, ensure you have:

- Python 3.9 or later (adjust this requirement to match your project's actual Python support).
- [Ollama](https://ollama.com/) installed and running.
- Git installed on your machine.

## 🚀 Installation

### 1. Install Ollama

Download and install Ollama from the official website:

https://ollama.com/

### 2. Start Ollama and Download a Model

Pull the default model:

```bash
ollama pull llama3.2
```

Make sure Ollama is running before using OmniTrace.

### 3. Clone the Repository

Replace `HadiAbdul30` with the GitHub username or organization that hosts the repository.

```bash
git clone https://github.com/HadiAbdul30/omnitrace.git
cd omnitrace
```

### 4. Create a Virtual Environment

Create and activate a Python virtual environment.

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**

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

OmniTrace supports two operating modes.

### Mode 1: Debug a Python Script

Run a Python script through OmniTrace to capture errors and request AI-powered diagnostics.

```bash
omnitrace my_broken_script.py
```

**How it works:**

1. OmniTrace executes the specified Python script.
2. It captures errors and stack traces.
3. It sends the relevant diagnostic information to your local Ollama model.
4. It displays an explanation of the error and suggested fixes.

Replace `my_broken_script.py` with the path to your Python script.

### Mode 2: Monitor Application Logs

Monitor a log file for errors while your application runs.

```bash
omnitrace --watch app.log
```

**How it works:**

1. OmniTrace monitors the specified log file.
2. It detects stack traces as they appear.
3. It sends the relevant error information to your local LLM.
4. It displays a diagnosis and suggested solutions.

This mode is useful for debugging background services and applications that write errors to log files.

> **Note:** Log monitoring requires the application to write its errors and stack traces to the monitored file. Exact detection behavior depends on the implementation.

## ⚙️ Configuration

OmniTrace uses Ollama to run a local language model.

You can change the model by setting the `OMNITRACE_MODEL` environment variable.

### Linux / macOS

```bash
export OMNITRACE_MODEL="qwen2.5-coder"
```

### Windows (PowerShell)

```powershell
$env:OMNITRACE_MODEL = "qwen2.5-coder"
```

Make sure the selected model is available locally. For example:

```bash
ollama pull qwen2.5-coder
```

If `OMNITRACE_MODEL` is not set, OmniTrace uses its configured default model, which should be `llama3.2`.

## 🔐 Privacy

OmniTrace is designed to keep debugging local by using Ollama to run AI models on your machine.

When configured to use a local Ollama instance:

- Your code does not need to be sent to a third-party AI API.
- Stack traces can be analyzed locally.
- Proprietary source code can remain on your machine.

**Important:** Local inference does not automatically guarantee complete privacy. Ensure your application, logging configuration, and any additional integrations do not transmit sensitive information externally.

## 🛠️ Troubleshooting

### Ollama is not responding

Make sure Ollama is installed and running.

Check whether the Ollama service is accessible:

```bash
ollama list
```

### The selected model is unavailable

Download the model before using it:

```bash
ollama pull llama3.2
```

If you are using a custom model, replace `llama3.2` with the model name you configured.

### The `omnitrace` command is not found

Ensure your virtual environment is activated and OmniTrace is installed:

```bash
pip install -e .
```

If the command is still unavailable, verify that your project's packaging configuration defines the appropriate command-line entry point.

## 🗺️ Roadmap

Potential future improvements include:

- [ ] Support for additional programming languages.
- [ ] More detailed root-cause analysis.
- [ ] Context-aware code fix suggestions.
- [ ] Configurable log monitoring and filtering.
- [ ] Integration with development workflows and testing tools.
- [ ] Structured diagnostic reports.

## 🤝 Contributing

Contributions, bug reports, and feature suggestions are welcome.

If you would like to contribute:

1. Fork the repository.
2. Create a branch for your changes.
3. Make your changes and test them.
4. Submit a pull request describing your improvements.

## 📄 License

Add your project's license information here.

If you intend to distribute OmniTrace as an open-source project, consider including a `LICENSE` file in the repository.

---

**OmniTrace — Debug locally. Understand errors faster. Keep your code private.**