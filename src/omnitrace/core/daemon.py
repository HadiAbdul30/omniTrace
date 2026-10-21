# src/omnitrace/core/daemon.py
import os
import time

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from omnitrace.core.ai_router import analyze_error
from omnitrace.core.dispatcher import send_to_discord
from omnitrace.core.review import review_and_apply
from omnitrace.db.database import log_error

console = Console()
MAX_TRACE_BYTES = 100_000
IDLE_FLUSH_SECONDS = 1.0

def process_error(error_trace: str):
    """Handles the UI and AI routing for a detected background error."""
    console.print(Panel(error_trace.strip(), title="❌ BACKGROUND CRASH DETECTED", border_style="red"))
    
    with console.status("[bold green]OmniTrace is analyzing the failure locally...", spinner="dots"):
        diagnosis = analyze_error(error_trace.strip())
        
    console.print("\n[bold cyan]🩺 OMNITRACE DIAGNOSIS:[/bold cyan]\n")
    display_text = diagnosis.partition("<<<FILEPATH:")[0].strip()
    console.print(Markdown(display_text or "No diagnosis text was returned."))

    send_to_discord(error_trace.strip(), diagnosis)
    log_error(error_trace.strip(), diagnosis)

    if "<<<" in diagnosis:
        console.print("\n")
        review_and_apply(diagnosis, console)
    else:
        console.print("Patch report: no valid structured patch is available; original files were not changed.")
    
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
        buffer_bytes = 0
        last_line_at = 0.0
        
        while True:
            line = f.readline()
            
            if not line:
                # If we were collecting an error and the file paused, process it
                if (collecting_traceback and buffer
                        and time.monotonic() - last_line_at >= IDLE_FLUSH_SECONDS):
                    process_error("".join(buffer))
                    buffer = []
                    collecting_traceback = False
                    buffer_bytes = 0
                
                # Sleep briefly before checking for new lines
                time.sleep(0.1)
                continue
                
            # Detect the start of a Python stack trace
            if "Traceback (most recent call last):" in line:
                collecting_traceback = True
                buffer = [line[:MAX_TRACE_BYTES]]
                buffer_bytes = len(buffer[0].encode("utf-8", errors="replace"))
                last_line_at = time.monotonic()
            elif collecting_traceback:
                last_line_at = time.monotonic()
                remaining = MAX_TRACE_BYTES - buffer_bytes
                if remaining > 0:
                    clipped = line.encode("utf-8", errors="replace")[:remaining].decode("utf-8", errors="ignore")
                    buffer.append(clipped)
                    buffer_bytes += len(clipped.encode("utf-8", errors="replace"))
