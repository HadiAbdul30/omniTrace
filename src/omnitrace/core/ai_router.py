# src/omnitrace/core/ai_router.py
import json
import os
import re
import urllib.request
from pathlib import Path
from urllib.error import URLError

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "diagnosis": {"type": "string"},
        "patch": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "search": {"type": "string"},
                "replace": {"type": "string"},
            },
            "required": ["filepath", "search", "replace"],
            "additionalProperties": False,
        },
    },
    "required": ["diagnosis", "patch"],
    "additionalProperties": False,
}


def extract_cross_file_context(error_trace: str) -> str:
    """Extract bounded Python context only from regular files inside the project."""
    # Regex to catch file paths in Python tracebacks
    file_paths = re.findall(r'File "([^"]+\.py)"', error_trace)
    
    context_str = ""
    # Use a set to remove duplicate files
    total = 0
    root = Path.cwd().resolve()
    for path in set(file_paths):
        try:
            candidate = Path(path)
            resolved = candidate.resolve(strict=True)
            if (not resolved.is_relative_to(root) or candidate.is_symlink()
                    or not resolved.is_file() or resolved.stat().st_size > 1_000_000):
                continue
            with resolved.open('r', encoding='utf-8', errors='replace') as f:
                content = f.read(min(20_000, 40_000 - total))
            total += len(content)
            context_str += f"\n--- FILE: {resolved.relative_to(root)} ---\n```python\n{content}\n```\n"
            if total >= 40_000:
                break
        except (OSError, ValueError):
            continue
                
    return context_str

def analyze_error(error_trace: str) -> str:
    """Sends the stack trace and cross-file context to local Llama 3 via Ollama."""
    error_trace = error_trace[:100_000]
    rag_context = extract_cross_file_context(error_trace)
    
    system_prompt = f"""You are OmniTrace, a local Python debugging assistant.
Analyze the traceback and available source context. Return one JSON object
matching the response schema exactly. The diagnosis must be a concise string.
Always return a patch object with filepath, search, and replace string fields.
When the source context shows the failing code and supports a narrow fix, set
filepath to a project-relative path shown in the source context, search to
complete original source text copied exactly, and replace to the complete
replacement text. Never return a full-file replacement. If no safe exact edit
can be based on the shown source, set all three patch fields to empty strings.
In particular, when a NameError includes a suggested identifier that is defined
in the shown source, replace the misspelled identifier. Do not put markdown or
extra text in JSON string fields.

SOURCE CONTEXT:
{rag_context if rag_context else "No local cross-file context found."}

STACK TRACE:
{error_trace}
"""
    model = os.environ.get("OMNITRACE_MODEL", "llama3").strip()
    if not model:
        model = "llama3"
    try:
        timeout = max(1.0, min(float(os.environ.get("OMNITRACE_OLLAMA_TIMEOUT", "90")), 600.0))
    except ValueError:
        timeout = 90.0
    payload = {
        "model": model,
        "prompt": system_prompt,
        "format": _RESPONSE_SCHEMA,
        "options": {"temperature": 0},
        "stream": False,
    }

    try:
        # Using standard urllib to avoid requiring the requests library
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read(1_000_001).decode("utf-8"))
            answer = result.get("response") if isinstance(result, dict) else None
            if not isinstance(answer, str) or not answer.strip():
                return "Ollama returned an empty or malformed response. Check the selected model and try again."
            if len(answer) > 1_000_000:
                return "Ollama response exceeded the 1 MB safety limit."
            try:
                structured = json.loads(answer)
            except json.JSONDecodeError:
                return "Ollama returned malformed structured output; no patch was proposed."
            required = {"diagnosis", "patch"}
            if not isinstance(structured, dict) or set(structured) != required:
                return "Ollama returned an unexpected structured response; no patch was proposed."
            diagnosis = structured["diagnosis"]
            if not isinstance(diagnosis, str) or not diagnosis.strip():
                return "Ollama returned an empty or malformed diagnosis."
            patch = structured["patch"]
            if (
                not isinstance(patch, dict)
                or set(patch) != {"filepath", "search", "replace"}
            ):
                return diagnosis.strip() + "\n\nOmniTrace discarded an incomplete patch proposal."
            filepath, search, replacement = patch["filepath"], patch["search"], patch["replace"]
            if (
                not isinstance(filepath, str)
                or not isinstance(search, str)
                or not isinstance(replacement, str)
            ):
                return diagnosis.strip() + "\n\nOmniTrace discarded an incomplete patch proposal."
            if not filepath and not search and not replacement:
                return diagnosis.strip()
            if not filepath.strip() or not search.strip():
                return diagnosis.strip() + "\n\nOmniTrace discarded an incomplete patch proposal."
            return (
                diagnosis.strip()
                + f"\n\n<<<FILEPATH: {filepath.strip()}>>>\n<<<SEARCH>>>\n"
                + search
                + "\n<<<REPLACE>>>\n"
                + replacement
                + "\n<<<END>>>"
            )
        
    except (URLError, OSError, ValueError) as exc:
        return f"Ollama request failed ({type(exc).__name__}). Ensure Ollama is running and model '{model}' is available; configure OMNITRACE_MODEL and OMNITRACE_OLLAMA_TIMEOUT if needed."
