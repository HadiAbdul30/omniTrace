# src/omnitrace/db/database.py
import sqlite3
import os
from datetime import datetime
from rich.console import Console

console = Console()

# We will store the database in the user's home directory so it persists across projects
DB_PATH = os.path.expanduser("~/.omnitrace.db")

def init_db():
    """Initializes the SQLite database and creates the logs table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS error_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            error_trace TEXT NOT NULL,
            ai_diagnosis TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()

def log_error(error_trace: str, ai_diagnosis: str):
    """Inserts a new crash report into the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute(
            "INSERT INTO error_logs (timestamp, error_trace, ai_diagnosis) VALUES (?, ?, ?)",
            (timestamp, error_trace, ai_diagnosis)
        )
        
        conn.commit()
        conn.close()
        console.print("[dim]✓ Crash saved to local SQLite database.[/dim]")
    except Exception as e:
        console.print(f"[bold red]Failed to save to database: {e}[/bold red]")