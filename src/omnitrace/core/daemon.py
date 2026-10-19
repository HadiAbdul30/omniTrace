# src/omnitrace/core/daemon.py
import time
import os
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from omnitrace.core.ai_router import analyze_error
from omnitrace.core.dispatcher import send_to_discord
from omnitrace.db.database import log_error

console = Console()

def process_error(error_trace: str):
    """Handles the UI and AI routing for a detected background error."""
    console.print(Panel(error_trace.strip(), title="❌ BACKGROUND CRASH DETECTED", border_style="red"))
    
    with console.status("[bold green]OmniTrace is analyzing the failure locally...", spinner="dots"):
        diagnosis = analyze_error(error_trace.strip())
        
    console.print("\n[bold cyan]🩺 OMNITRACE DIAGNOSIS:[/bold cyan]\n")
    console.print(Markdown(diagnosis))

    send_to_discord(error_trace.strip(), diagnosis)
    log_error(error_trace.strip(), diagnosis)
    
    console.print("\n[bold dim]OmniTrace is actively watching for new errors...[/bold dim]\n")

def start_daemon(log_file: str):
    """Tails a log file in real-time and intercepts stack traces."""
    if not os.path.exists(log_file):
        # Create the file if it doesn't exist so we don't crash on startup
        open(log_file, 'w').close()
        
    console.print(f"[bold blue]OmniTrace Daemon[/bold blue] is now active and watching [bold yellow]{log_file}[/bold yellow]...\n")
    
    with open(log_file, 'r') as f:
        # Move to the end of the file to only watch for NEW errors
        f.seek(0, os.SEEK_END)
        
        buffer = []
        collecting_traceback = False
        
        while True:
            line = f.readline()
            
            if not line:
                # If we were collecting an error and the file paused, process it
                if collecting_traceback and len(buffer) > 0:
                    process_error("".join(buffer))
                    buffer = []
                    collecting_traceback = False
                
                # Sleep briefly before checking for new lines
                time.sleep(0.5)
                continue
                
            # Detect the start of a Python stack trace
            if "Traceback (most recent call last):" in line:
                collecting_traceback = True
                buffer.append(line)
            elif collecting_traceback:
                # Keep appending lines to the buffer as long as the error is printing
                buffer.append(line)