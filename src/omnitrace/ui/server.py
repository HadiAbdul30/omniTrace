# src/omnitrace/ui/server.py
import os
import sqlite3
from contextlib import closing

from flask import Flask, render_template_string
from rich.console import Console

console = Console()
app = Flask(__name__)
DB_PATH = os.path.expanduser("~/.omnitrace.db")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>OmniTrace Dashboard</title>
    <style>
        body { background:#111827; color:#f3f4f6; font:16px sans-serif; margin:2rem auto; max-width:60rem; }
        article { background:#1f2937; border:1px solid #374151; border-radius:.5rem; margin:1rem 0; padding:1.25rem; }
        pre { background:#030712; border-radius:.3rem; overflow-wrap:anywhere; white-space:pre-wrap; padding:1rem; }
        a { color:#93c5fd; } h1 { color:#60a5fa; }
    </style>
</head>
<body class="bg-gray-900 text-gray-100 font-sans p-8 antialiased">
    <div class="max-w-5xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <h1 class="text-3xl font-bold text-blue-400">OmniTrace Debug Ledger</h1>
            <a href="/" class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded shadow transition">
                Refresh Logs
            </a>
        </div>
        
        <div class="space-y-6">
            {% for log in logs %}
            <div class="bg-gray-800 rounded-lg p-6 border border-gray-700 shadow-lg">
                <div class="flex justify-between items-center mb-4 border-b border-gray-700 pb-2">
                    <span class="text-sm font-mono text-gray-400">Crash ID: #{{ log[0] }}</span>
                    <span class="text-sm font-mono text-blue-300">{{ log[1] }}</span>
                </div>
                <div class="mb-4">
                    <h3 class="text-red-400 font-bold mb-2 text-sm uppercase tracking-wider">Raw Stack Trace</h3>
                    <pre class="bg-gray-950 p-4 rounded text-sm text-red-300 overflow-x-auto border border-red-900/30"><code>{{ log[2] }}</code></pre>
                </div>
                <div>
                    <h3 class="text-green-400 font-bold mb-2 text-sm uppercase tracking-wider">AI Diagnosis & Fix</h3>
                    <pre class="bg-gray-950 p-4 rounded text-sm text-gray-300 whitespace-pre-wrap border border-green-900/30 font-sans">{{ log[3] }}</pre>
                </div>
            </div>
            {% else %}
            <div class="bg-gray-800 rounded-lg p-8 text-center border border-gray-700">
                <p class="text-gray-400 italic">No crashes recorded in the SQLite database yet.</p>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    try:
        with closing(sqlite3.connect(DB_PATH, timeout=5)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, timestamp, substr(error_trace, 1, 20000), substr(ai_diagnosis, 1, 20000) FROM error_logs ORDER BY id DESC LIMIT 25")
            logs = cursor.fetchall()
    except sqlite3.Error as exc:
        app.logger.error("Could not read local debug ledger: %s", type(exc).__name__)
        logs = []
        
    return render_template_string(HTML_TEMPLATE, logs=logs)

def start_ui(port=5000):
    # Disable Flask's default noisy startup logs
    import logging
    log = logging.getLogger('werkzeug')
    log.disabled = True
    app.logger.disabled = True
    
    app.run(host='127.0.0.1', port=port, debug=False)
