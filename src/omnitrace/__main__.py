# src/omnitrace/__main__.py
import os
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from omnitrace.core.ai_router import analyze_error
from omnitrace.core.daemon import start_daemon
from omnitrace.core.dispatcher import send_to_discord
from omnitrace.core.patcher import revert_file
from omnitrace.core.process import run_script
from omnitrace.core.review import review_and_apply
from omnitrace.db.database import init_db, log_error

console = Console()

def run_wrapper_mode(target_script: str):
    console.print(f"[bold blue]OmniTrace[/bold blue] is now wrapping and executing: [bold yellow]{target_script}[/bold yellow]...\n")
    
    try:
        result = run_script(target_script, os.environ.get("OMNITRACE_RUN_TIMEOUT", "120"))
    except ValueError:
        console.print("[bold red]OMNITRACE_RUN_TIMEOUT must be a number of seconds.[/bold red]")
        return 2
    except OSError as exc:
        console.print(f"[bold red]Could not start target script ({type(exc).__name__}). Check the path and permissions.[/bold red]")
        return 2
    if result.timed_out:
        console.print("[bold red]Target timed out after the configured limit (OMNITRACE_RUN_TIMEOUT).[/bold red]")
        return result.returncode

    if result.returncode != 0:
        error_trace = "\n".join(part for part in (result.stderr.strip(), result.stdout.strip()) if part)
        if not error_trace:
            error_trace = f"Wrapped process exited with status {result.returncode} and produced no output."
        if result.output_truncated:
            console.print("[dim]Captured process output exceeded its 1 MB per-stream limit.[/dim]")
        console.print(Panel(error_trace, title="❌ CRASH DETECTED", border_style="red"))
        
        with console.status("[bold green]OmniTrace is analyzing the failure locally...", spinner="dots"):
            diagnosis = analyze_error(error_trace)
        
        console.print("\n[bold cyan]🩺 OMNITRACE DIAGNOSIS:[/bold cyan]\n")
        display_text = diagnosis.partition("<<<FILEPATH:")[0].strip()
        console.print(Markdown(display_text or "No diagnosis text was returned."))

        send_to_discord(error_trace, diagnosis)
        log_error(error_trace, diagnosis)
        
        if "<<<" in diagnosis:
            console.print()
            review_and_apply(diagnosis, console)
        else:
            console.print("Patch report: no valid structured patch is available; original files were not changed.")

        return result.returncode
    else:
        console.print("[bold green]✅ Process completed successfully.[/bold green]")
        if result.stdout:
            console.print(result.stdout)
        return 0

def main():
    if len(sys.argv) == 2 and sys.argv[1] in ("--help", "-h"):
        console.print("OmniTrace: local-first Python crash diagnosis\n\nUsage:\n  omnitrace <script.py>\n  omnitrace --watch <log_file>\n  omnitrace --ui\n  omnitrace revert <file>\n\nOptions:\n  --help  Show this help\n\nOllama settings: OMNITRACE_MODEL (default: llama3), OMNITRACE_OLLAMA_TIMEOUT (seconds).")
        return 0
    if len(sys.argv) < 2:
        console.print("[bold red]Usage:[/bold red]")
        console.print("  [dim]Wrapper mode:[/dim] omnitrace <python_script.py>")
        console.print("  [dim]Daemon mode:[/dim]  omnitrace --watch <log_file.log>")
        console.print("  [dim]UI mode:[/dim]      omnitrace --ui")
        return 1

    if sys.argv[1].startswith("-") and sys.argv[1] not in ("--ui", "--watch"):
        console.print(f"[bold red]Unknown option: {sys.argv[1]}[/bold red]")
        return 2
    
    if sys.argv[1] == "revert":
        if len(sys.argv) < 3:
            console.print("[bold red]Error:[/bold red] Please specify a file to revert.")
            return 1
        return 0 if revert_file(sys.argv[2]) else 1

    # Check if user wants to run the Dashboard UI
    elif sys.argv[1] == "--ui":
        try:
            from omnitrace.ui.server import start_ui
        except ImportError:
            console.print(
                "Dashboard support is optional. Install it with: pip install 'omnitrace"
                + "[dashboard]'",
                markup=False,
            )
            return 2
        console.print("[bold blue]Starting OmniTrace Dashboard...[/bold blue]")
        console.print("🌐 View your debug ledger at: [bold underline cyan]http://127.0.0.1:5000[/bold underline cyan]\n")
        init_db()
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
            init_db()
            start_daemon(log_file)
        except KeyboardInterrupt:
            console.print("\n[bold green]OmniTrace Daemon shut down gracefully.[/bold green]")
            return 0
    
    # Otherwise, run the normal wrapper mode
    else:
        init_db()
        return run_wrapper_mode(sys.argv[1])

if __name__ == "__main__":
    sys.exit(main())
