# src/omnitrace/__main__.py
import sys
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from omnitrace.core.ai_router import analyze_error
from omnitrace.core.daemon import start_daemon
from omnitrace.core.dispatcher import send_to_discord

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
        return result.returncode
    else:
        console.print("[bold green]✅ Process completed successfully.[/bold green]")
        if result.stdout:
            console.print(result.stdout)
        return 0

def main():
    if len(sys.argv) < 2:
        console.print("[bold red]Usage:[/bold red]")
        console.print("  [dim]Wrapper mode:[/dim] omnitrace <python_script.py>")
        console.print("  [dim]Daemon mode:[/dim]  omnitrace --watch <log_file.log>")
        return 1

    # Check if user wants to run the daemon
    if sys.argv[1] == "--watch":
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