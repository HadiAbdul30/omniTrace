import sqlite3

print("Connecting to database...")
conn = sqlite3.connect(':memory:')
cursor = conn.cursor()

cursor.execute("CREATE TABLE users (id INTEGER, name TEXT)")

print("Executing query...")
# Intentional Crash: 'email' column does not exist
cursor.execute("SELECT id, name, email FROM users")