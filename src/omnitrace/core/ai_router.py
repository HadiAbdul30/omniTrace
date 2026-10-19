# src/omnitrace/core/ai_router.py
import os
import ollama

def analyze_error(error_trace: str) -> str:
    # Allow the user to define their model via env var, default to the newer llama3.2
    model_name = os.getenv("OMNITRACE_MODEL", "llama3.2")
    
    prompt = f"""
    You are OmniTrace, an expert Python debugging assistant.
    Analyze the following Python stack trace and explain exactly what went wrong in plain English.

    You MUST append a patch block at the very end of your response to fix the code. 
    The FILEPATH must be the actual path to the failing file extracted from the stack trace.
    The SEARCH block must contain the EXACT broken lines from the original file.
    
    Use this EXACT format:
    
    <<<FILEPATH: [Insert the actual file path from the stack trace here]>>>
    <<<SEARCH>>>
    [Insert the exact lines of old, broken code here]
    <<<REPLACE>>>
    [Insert the exact lines of new, fixed code here]
    <<<END>>>

    Stack Trace:
    {error_trace}
    """
    
    try:
        response = ollama.chat(model=model_name, messages=[
            {'role': 'user', 'content': prompt}
        ])
        return response['message']['content']
    except Exception as e:
        error_str = str(e)
        if "not found" in error_str.lower() and "404" in error_str:
            return (f"❌ Model '{model_name}' is not installed locally.\n"
                    f"To fix this, run:\n\n    ollama pull {model_name}\n\n"
                    f"Or set a different model: export OMNITRACE_MODEL='your-model-name'")
        return f"OmniTrace LLM routing failed. Ensure the Ollama app is running in the background. Error: {error_str}"