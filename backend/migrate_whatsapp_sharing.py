"""Add the per-accepted-request WhatsApp consent table without rewriting existing data.

Run from the backend directory:
    python migrate_whatsapp_sharing.py

The Flask app also creates missing tables via SQLAlchemy create_all() at startup. This
standalone migration makes a timestamped database backup before creating the new table.
"""
import os
import shutil
import sqlite3
from datetime import datetime

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BACKEND_DIR, "database", "campusnest.db")

CREATE_TABLE_SQL = """
CREATE TABLE whatsapp_shares (
    id INTEGER NOT NULL PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES roommate_requests (id),
    owner_id INTEGER NOT NULL REFERENCES users (id),
    viewer_id INTEGER NOT NULL REFERENCES users (id),
    phone_number VARCHAR(15) NOT NULL,
    created_at DATETIME,
    updated_at DATETIME,
    CONSTRAINT uq_whatsapp_request_owner UNIQUE (request_id, owner_id),
    CONSTRAINT ck_whatsapp_share_not_self CHECK (owner_id != viewer_id)
)
"""


def migrate(db_path=DEFAULT_DB_PATH, make_backup=True):
    if not os.path.exists(db_path):
        raise FileNotFoundError("No database found at " + db_path)

    connection = sqlite3.connect(db_path)
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='whatsapp_shares'"
        ).fetchone() is not None
        if exists:
            return {"added": False, "backup": None}
        required = {"users", "roommate_requests"}
        existing = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not required.issubset(existing):
            raise RuntimeError("Required application tables are missing; no changes were made.")
    finally:
        connection.close()

    backup = None
    if make_backup:
        backup_dir = os.path.join(os.path.dirname(db_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = os.path.join(backup_dir, "campusnest_before_whatsapp_" + stamp + ".db")
        suffix = 1
        while os.path.exists(backup):
            backup = os.path.join(
                backup_dir, "campusnest_before_whatsapp_" + stamp + "_" + str(suffix) + ".db")
            suffix += 1
        shutil.copy2(db_path, backup)

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(CREATE_TABLE_SQL)
        connection.commit()
    finally:
        connection.close()
    return {"added": True, "backup": backup}


if __name__ == "__main__":
    result = migrate()
    if result["backup"]:
        print("Backup saved before adding WhatsApp sharing storage.")
    print("WhatsApp sharing table added." if result["added"]
          else "WhatsApp sharing table already exists; no changes made.")
