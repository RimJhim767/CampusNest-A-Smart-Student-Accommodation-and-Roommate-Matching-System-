# CampusNest — quick database check (prints table names, columns and row COUNTS only).
# Run from the backend folder:   python check_db.py
# It never prints passwords or anyone's preference values.
import os
import sqlite3

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "campusnest.db")
if not os.path.exists(path):
    raise SystemExit("No database found at " + path + " - start the app once first.")

conn = sqlite3.connect(path)
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
for table in tables:
    columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table}: {count} row(s)")
    print("   columns:", ", ".join(columns))
conn.close()
