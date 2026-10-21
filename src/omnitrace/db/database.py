# src/omnitrace/db/database.py
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from rich.console import Console

console = Console()

# We will store the database in the user's home directory so it persists across projects
DB_PATH = os.path.expanduser("~/.omnitrace.db")

def init_db():
    """Initializes the SQLite database and creates the logs table if it doesn't exist."""
    if Path(DB_PATH).is_symlink():
        raise OSError("refusing to use a symbolic link for the local diagnostic database")
    if os.name == "posix":
        try:
            db_fd = os.open(DB_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if Path(DB_PATH).is_symlink():
                raise OSError("refusing to use a symbolic link for the local diagnostic database")
            os.chmod(DB_PATH, 0o600)
        else:
            os.close(db_fd)
    with closing(sqlite3.connect(DB_PATH, timeout=5)) as conn, conn:
        conn.execute("""
                CREATE TABLE IF NOT EXISTS error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    error_trace TEXT NOT NULL,
                    ai_diagnosis TEXT NOT NULL
                )
            """)

def log_error(error_trace: str, ai_diagnosis: str):
    """Inserts a new crash report into the database."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with closing(sqlite3.connect(DB_PATH, timeout=5)) as conn, conn:
            conn.execute(
                "INSERT INTO error_logs (timestamp, error_trace, ai_diagnosis) VALUES (?, ?, ?)",
                (timestamp, error_trace[:200_000], ai_diagnosis[:200_000]),
            )
        console.print("[dim]✓ Crash saved to local SQLite database.[/dim]")
    except sqlite3.Error as exc:
        console.print(f"[bold red]Failed to save crash to local database ({type(exc).__name__}).[/bold red]")
