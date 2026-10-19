# src/omnitrace/core/dispatcher.py
import os
import json
import urllib.request
from rich.console import Console

console = Console()

def send_to_discord(error_trace: str, diagnosis: str):
    """Sends the crash report and AI diagnosis to a Discord webhook."""
    webhook_url = os.getenv("OMNITRACE_DISCORD_WEBHOOK")
    
    if not webhook_url:
        return # Do nothing if the user hasn't configured a webhook
        
    console.print("[dim]Dispatching report to Discord...[/dim]")
    
    # Format the message for Discord's UI
    payload = {
        "content": "🚨 **OMNITRACE: CRASH DETECTED** 🚨",
        "embeds": [
            {
                "title": "Raw Stack Trace",
                "description": f"```python\n{error_trace[-1000:]}\n```",
                "color": 16711680 # Red
            },
            {
                "title": "AI Diagnosis & Fix",
                "description": diagnosis[:4000], # Discord description limit
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
        urllib.request.urlopen(req)
        console.print("[bold green]✓ Report dispatched to Discord successfully.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Failed to dispatch to Discord: {e}[/bold red]")