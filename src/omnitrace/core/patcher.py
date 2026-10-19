# src/omnitrace/core/patcher.py
import os
import shutil
import re
from rich.console import Console

console = Console()

def extract_and_apply_patch(diagnosis: str):
    """Parses the LLM output for a patch block and applies it intelligently."""
    file_match = re.search(r'<<<FILEPATH:\s*(.+?)>>>', diagnosis)
    search_match = re.search(r'<<<SEARCH>>>\n(.*?)\n<<<REPLACE>>>', diagnosis, re.DOTALL)
    replace_match = re.search(r'<<<REPLACE>>>\n(.*?)\n<<<END>>>', diagnosis, re.DOTALL)

    if not (file_match and search_match and replace_match):
        console.print("[bold red]❌ Failed to parse patch block from AI output.[/bold red]")
        return False

    filepath = file_match.group(1).strip()
    
    # Extract lines and ignore empty whitespace lines at the edges
    search_lines = [line.strip() for line in search_match.group(1).split('\n') if line.strip() and not line.startswith("```")]
    replace_lines = [line for line in replace_match.group(1).split('\n') if not line.startswith("```")]

    if not os.path.exists(filepath):
        console.print(f"[bold red]❌ Target file '{filepath}' not found.[/bold red]")
        return False

    # Safety backup
    backup_path = filepath + ".bak"
    shutil.copy2(filepath, backup_path)
    
    with open(filepath, 'r') as f:
        file_lines = f.readlines()
    
    new_lines = []
    patched = False
    
    # Smart line-by-line replacement
    if search_lines:
        target_snippet = search_lines[0] # Look for the core text of the first search line
        
        for line in file_lines:
            if target_snippet in line and not patched:
                # We found the broken line! 
                # 1. Capture the original indentation of the file
                indent = line[:len(line) - len(line.lstrip())]
                
                # 2. Inject the replacement lines with the correct original indentation
                for r_line in replace_lines:
                    # Only add the indent if the replacement line actually has code
                    clean_r = r_line.lstrip()
                    if clean_r:
                        new_lines.append(indent + clean_r + '\n')
                    else:
                        new_lines.append('\n')
                patched = True
            else:
                new_lines.append(line)

    if patched:
        with open(filepath, 'w') as f:
            f.writelines(new_lines)
        console.print(f"[bold green]✓ Successfully patched {filepath}[/bold green]")
        return True
    else:
        console.print("[bold red]❌ Safety abort: Could not locate the target code snippet in the file.[/bold red]")
        console.print(f"[dim]Debug: The AI told me to look for this exact line:[/dim] [yellow]'{target_snippet}'[/yellow]")
        return False