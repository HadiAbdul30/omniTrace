# src/omnitrace/__main__.py
import sys
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from omnitrace.core.ai_router import analyze_error
from omnitrace.core.daemon import start_daemon
from omnitrace.core.dispatcher import send_to_discord
from omnitrace.db.database import init_db, log_error
from omnitrace.ui.server import start_ui

console = Console()

def run_wrapper_mode(target_script: str):
    console.print(f"[bold blue]OmniTrace[/bold blue] is now wrapping and executing: [bold yellow]{target_script}[/bold yellow]...\n")
    
    result = subprocess.run([sys.executable, target_script], capture_output=True, text=True)

    if result.returncode != 0:
        error_trace = result.stderr.strip()
        console.print(Panel(error_trace, title="❌ CRASH DETECTED", border_style="red"))
        
        with console.status("[bold green]OmniTrace is analyzing the failure locally...", spinner="dots"):
            diagnosis = analyze_error(error_trace)
        
        console.print("\n[bold cyan]🩺 OMNITRACE DIAGNOSIS:[/bold cyan]\n")
        console.print(Markdown(diagnosis))

        send_to_discord(error_trace, diagnosis)
        log_error(error_trace, diagnosis)

        return result.returncode
    else:
        console.print("[bold green]✅ Process completed successfully.[/bold green]")
        if result.stdout:
            console.print(result.stdout)
        return 0

def main():
    init_db()
    
    if len(sys.argv) < 2:
        console.print("[bold red]Usage:[/bold red]")
        console.print("  [dim]Wrapper mode:[/dim] omnitrace <python_script.py>")
        console.print("  [dim]Daemon mode:[/dim]  omnitrace --watch <log_file.log>")
        console.print("  [dim]UI mode:[/dim]      omnitrace --ui")
        return 1

    # Check if user wants to run the Dashboard UI
    if sys.argv[1] == "--ui":
        console.print("[bold blue]Starting OmniTrace Dashboard...[/bold blue]")
        console.print("🌐 View your debug ledger at: [bold underline cyan]http://127.0.0.1:5000[/bold underline cyan]\n")
        try:
            start_ui()
        except KeyboardInterrupt:
            console.print("\n[bold green]Dashboard shut down gracefully.[/bold green]")
        return 0

    # Check if user wants to run the daemon
    elif sys.argv[1] == "--watch":
        if len(sys.argv) < 3:
            console.print("[bold red]Error:[/bold red] Please specify a log file to watch.")
            return 1
            
        log_file = sys.argv[2]
        try:
            start_daemon(log_file)
        except KeyboardInterrupt:
            console.print("\n[bold green]OmniTrace Daemon shut down gracefully.[/bold green]")
            return 0
    
    # Otherwise, run the normal wrapper mode
    else:
        return run_wrapper_mode(sys.argv[1])

if __name__ == "__main__":
    sys.exit(main())