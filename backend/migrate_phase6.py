# CampusNest — Phase 6 database migration (SAFE: additive only).
#
# What it does:  adds ONE new, empty (NULL) column to the existing `preferences` table:
#                    preferred_roommate_gender
# What it never does: delete, reset, rename or rewrite any table, user or preference.
#
# Run it from the backend folder:
#     python migrate_phase6.py
#
# Steps it performs for you:
#   1. finds database/campusnest.db (stops with a message if it does not exist yet)
#   2. if (and only if) a change is needed, makes a timestamped COPY of the database file in
#      database/backups/ (an existing backup is never overwritten)
#   3. adds the column only if it is missing (safe to run twice)
#   4. checks the row counts are exactly the same as before and prints the result
#
# Existing users keep every value they had. Their new column is NULL, which means
# "has not answered yet" -> they are NOT eligible for matching until they open the
# Preferences page, choose a roommate gender, and save.
import os
import shutil
import sqlite3
import sys
from datetime import datetime

TABLE = "preferences"
COLUMN = "preferred_roommate_gender"
ADD_COLUMN_SQL = "ALTER TABLE preferences ADD COLUMN preferred_roommate_gender VARCHAR(10)"

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BACKEND_DIR, "database", "campusnest.db")


def ensure_phase6_schema(engine):
    """Used by app.py at start-up (SQLAlchemy engine). Adds the column if it is missing.
    Returns True if it added the column, False if nothing needed doing.
    It is the same single additive ALTER TABLE as the command-line script below."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if TABLE not in inspector.get_table_names():
        return False                      # brand-new database: create_all() makes the full table
    existing = {col["name"] for col in inspector.get_columns(TABLE)}
    if COLUMN in existing:
        return False
    with engine.begin() as connection:
        connection.execute(text(ADD_COLUMN_SQL))
    return True


def _columns(connection, table):
    return [row[1] for row in connection.execute("PRAGMA table_info(" + table + ")")]


def _table_exists(connection, table):
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def _row_counts(connection):
    counts = {}
    for (name,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        counts[name] = connection.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
    return counts


def _unique_backup_path(backup_dir):
    """A backup file name that does not exist yet. An existing backup is NEVER overwritten."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(backup_dir, "campusnest_before_phase6_" + stamp + ".db")
    number = 1
    while os.path.exists(path):
        number += 1
        path = os.path.join(backup_dir, "campusnest_before_phase6_" + stamp + "_" + str(number) + ".db")
    return path


def migrate(db_path=DEFAULT_DB_PATH, make_backup=True):
    """Returns a dict describing what happened. Raises FileNotFoundError if there is no database.
    A backup copy is made only when a change is actually going to be made."""
    if not os.path.exists(db_path):
        raise FileNotFoundError("No database found at " + db_path +
                                " - start the app once first, then run this script.")

    result = {"backup": None, "added": False, "before": {}, "after": {}}

    connection = sqlite3.connect(db_path)
    try:
        result["before"] = _row_counts(connection)
        needs_change = (_table_exists(connection, TABLE)
                        and COLUMN not in _columns(connection, TABLE))
        if not needs_change:
            # Either the column is already there, or the table does not exist yet (the app then
            # creates the whole table, new column included).
            result["after"] = dict(result["before"])
            return result
    finally:
        connection.close()

    if make_backup:
        backup_dir = os.path.join(os.path.dirname(db_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = _unique_backup_path(backup_dir)
        shutil.copy2(db_path, backup_path)
        result["backup"] = backup_path

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(ADD_COLUMN_SQL)
        connection.commit()
        result["added"] = True
        result["after"] = _row_counts(connection)
    finally:
        connection.close()

    if result["before"] != result["after"]:
        raise RuntimeError("Row counts changed during the migration. Restore the backup: "
                           + str(result["backup"]))
    return result


if __name__ == "__main__":
    try:
        outcome = migrate()
    except FileNotFoundError as error:
        raise SystemExit(str(error))

    if outcome["backup"]:
        print("Backup saved to:", outcome["backup"])
    if outcome["added"]:
        print("Added column preferences." + COLUMN + " (existing rows keep all their data; new column is empty).")
    else:
        print("Nothing to change: the column already exists (or the table is not created yet).")
    print("Row counts before and after are identical:")
    for table, count in outcome["after"].items():
        print("   " + table + ": " + str(count) + " row(s)")
    sys.exit(0)
