# src/omnitrace/__main__.py
import sys
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from omnitrace.core.ai_router import analyze_error

console = Console()

def main():
    if len(sys.argv) < 2:
        console.print("[bold red]Usage:[/bold red] omnitrace <python_script.py>")
        return 1

    target_script = sys.argv[1]
    console.print(f"[bold blue]OmniTrace[/bold blue] is now wrapping and executing: [bold yellow]{target_script}[/bold yellow]...\n")
    
    result = subprocess.run(
        [sys.executable, target_script], 
        capture_output=True, 
        text=True
    )

    if result.returncode != 0:
        error_trace = result.stderr.strip()
        
        # Print the error in a red panel
        console.print(Panel(error_trace, title="❌ CRASH DETECTED", border_style="red"))
        
        with console.status("[bold green]OmniTrace is analyzing the failure locally...", spinner="dots"):
            diagnosis = analyze_error(error_trace)
        
        # Render the LLM's markdown response beautifully
        console.print("\n[bold cyan]🩺 OMNITRACE DIAGNOSIS:[/bold cyan]\n")
        console.print(Markdown(diagnosis))
        
        return result.returncode
    else:
        console.print("[bold green]✅ Process completed successfully.[/bold green]")
        if result.stdout:
            console.print(result.stdout)
        return 0

if __name__ == "__main__":
    sys.exit(main())