# src/omnitrace/core/ai_router.py
import os
import re
import json
import urllib.request
from urllib.error import URLError

def extract_cross_file_context(error_trace: str) -> str:
    """Parses a stack trace for local Python files and extracts their content for the AI."""
    # Regex to catch file paths in Python tracebacks
    file_paths = re.findall(r'File "([^"]+\.py)"', error_trace)
    
    context_str = ""
    # Use a set to remove duplicate files
    for path in set(file_paths):
        # Ignore global libraries, only read local project files
        if os.path.exists(path) and "site-packages" not in path and "lib/python" not in path:
            try:
                with open(path, 'r') as f:
                    content = f.read()
                    context_str += f"\n--- FILE: {path} ---\n```python\n{content}\n```\n"
            except Exception:
                pass
                
    return context_str

def analyze_error(error_trace: str) -> str:
    """Sends the stack trace and cross-file context to local Llama 3 via Ollama."""
    rag_context = extract_cross_file_context(error_trace)
    
    system_prompt = f"""You are OmniTrace, an autonomous AI debugging agent.
    Analyze the following Python stack trace and provide the exact fix.

    If the error involves imported modules, analyze the provided cross-file context.

    CROSS-FILE CONTEXT:
    {rag_context if rag_context else "No local cross-file context found."}

    STACK TRACE:
    {error_trace}

    Provide a brief plain-English diagnosis of the problem.
    Then, provide the fixed code using this EXACT format so the auto-patcher can parse it:
    <<<FILEPATH: path/to/the/broken_file.py>>>
    ```python
    # Insert the complete, corrected file content here
    """
    payload = {
    "model": "llama3",
    "prompt": system_prompt,
    "stream": False
}

    try:
        # Using standard urllib to avoid requiring the requests library
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("response", "Error: No response from Ollama.")
        
    except URLError:
        return "Error: Could not connect to local Ollama instance. Please ensure 'ollama run llama3' is running in the background."