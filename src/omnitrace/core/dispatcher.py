# src/omnitrace/core/dispatcher.py
import json
import os
import re
import urllib.request
from urllib.error import URLError

from rich.console import Console

console = Console()

def send_to_discord(error_trace: str, diagnosis: str):
    """Sends the crash report and AI diagnosis to a Discord webhook."""
    webhook_url = os.getenv("OMNITRACE_DISCORD_WEBHOOK")
    
    if not webhook_url:
        return # Do nothing if the user hasn't configured a webhook
        
    console.print("[dim]Dispatching report to Discord...[/dim]")
    
    # Format the message for Discord's UI
    def redact(value: str) -> str:
        return re.sub(r"(?i)(token|password|secret|api[_-]?key)(\s*[=:]\s*)[^\s,;]+", r"\1\2[REDACTED]", value)

    payload = {
        "content": "🚨 **OMNITRACE: CRASH DETECTED** 🚨",
        "embeds": [
            {
                "title": "Raw Stack Trace",
                "description": f"```python\n{redact(error_trace)[-1000:]}\n```",
                "color": 16711680 # Red
            },
            {
                "title": "AI Diagnosis & Fix",
                "description": redact(diagnosis)[:4000],
                "color": 65280 # Green
            }
        ]
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        webhook_url, 
        data=data, 
        headers={'Content-Type': 'application/json', 'User-Agent': 'OmniTrace-Bot'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5):
            console.print("[bold green]✓ Report dispatched to Discord successfully.[/bold green]")
    except (URLError, TimeoutError, OSError, ValueError) as e:
        console.print(f"[bold red]Discord delivery failed ({type(e).__name__}); diagnosis remains local.[/bold red]")
