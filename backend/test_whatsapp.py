"""Database-isolated API tests for consent-based WhatsApp contact sharing."""
import os
import sqlite3
import sys
import tempfile
import unittest

TEMP_DIR = tempfile.mkdtemp(prefix="campusnest_whatsapp_test_")
os.environ["CAMPUSNEST_DB_URI"] = "sqlite:///" + os.path.join(TEMP_DIR, "whatsapp_test.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app  # noqa: E402
from migrate_whatsapp_sharing import migrate  # noqa: E402
from models import WhatsAppShare, db  # noqa: E402
from validation import normalize_whatsapp_number  # noqa: E402


SYNTHETIC_NUMBER = "+1 (555) 555-0123"
NORMALIZED_NUMBER = "15555550123"


def call(client, method, url, body=None):
    if body is None:
        return client.open(url, method=method)
    return client.open(url, method=method, json=body)


class WhatsAppSharingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True, SECRET_KEY="test-only-secret")

    def setUp(self):
        with app.app_context():
            db.drop_all()
            db.create_all()
        self.a = app.test_client()
        self.b = app.test_client()
        self.c = app.test_client()
        self.anon = app.test_client()
        for client, name, email in (
                (self.a, "Student A", "wa-a@example.test"),
                (self.b, "Student B", "wa-b@example.test"),
                (self.c, "Student C", "wa-c@example.test")):
            response = call(client, "POST", "/api/register", {
                "name": name, "email": email, "password": "secret123",
                "confirm_password": "secret123",
            })
            assert response.status_code == 201
            assert call(client, "POST", "/api/login", {
                "email": email, "password": "secret123",
            }).status_code == 200
        self.a_id = self.a.get("/api/me").json["user"]["id"]
        self.b_id = self.b.get("/api/me").json["user"]["id"]
        self.c_id = self.c.get("/api/me").json["user"]["id"]

    def make_accepted_request(self, requester, receiver, receiver_id, body=None):
        sent = call(requester, "POST", "/api/requests", {"receiver_id": receiver_id})
        self.assertEqual(sent.status_code, 201)
        request_id = sent.json["request"]["id"]
        accepted = call(receiver, "PUT", f"/api/requests/{request_id}/accept", body or {})
        self.assertEqual(accepted.status_code, 200)
        return request_id

    def test_accept_without_consent_keeps_contact_private(self):
        sent = call(self.a, "POST", "/api/requests", {"receiver_id": self.b_id})
        self.assertEqual(sent.status_code, 201)
        request_id = sent.json["request"]["id"]
        accepted = call(self.b, "PUT", f"/api/requests/{request_id}/accept", {})
        self.assertEqual(accepted.status_code, 200)
        self.assertFalse(accepted.json["request"]["i_share_whatsapp"])
        contact = self.a.get(f"/api/requests/{request_id}/whatsapp")
        self.assertEqual(contact.status_code, 200)
        self.assertEqual(contact.json, {"success": True, "shared": False})
        self.assertNotIn(NORMALIZED_NUMBER, contact.get_data(as_text=True))

    def test_accept_with_consent_exposes_number_only_to_requester(self):
        sent = call(self.b, "POST", "/api/requests", {"receiver_id": self.c_id})
        self.assertEqual(sent.status_code, 201)
        request_id = sent.json["request"]["id"]
        accepted = call(self.c, "PUT", f"/api/requests/{request_id}/accept", {
            "share_whatsapp": True,
            "phone_number": SYNTHETIC_NUMBER,
        })
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json["request"]["i_share_whatsapp"])
        contact = self.b.get(f"/api/requests/{request_id}/whatsapp")
        self.assertEqual(contact.status_code, 200)
        self.assertEqual(contact.json["phone_number"], NORMALIZED_NUMBER)
        self.assertTrue(contact.json["shared"])

        unrelated = self.a.get(f"/api/requests/{request_id}/whatsapp")
        self.assertEqual(unrelated.status_code, 404)
        self.assertNotIn(NORMALIZED_NUMBER, unrelated.get_data(as_text=True))
        self.assertNotIn(NORMALIZED_NUMBER,
                         self.c.get(f"/api/requests/{request_id}/whatsapp").get_data(as_text=True))
        self.assertNotIn(NORMALIZED_NUMBER,
                         self.c.get("/api/profile").get_data(as_text=True))
        self.assertNotIn(NORMALIZED_NUMBER,
                         self.c.get("/api/preferences").get_data(as_text=True))
        request_list = self.b.get("/api/requests/received")
        self.assertNotIn(NORMALIZED_NUMBER, request_list.get_data(as_text=True))

    def test_contact_endpoints_require_login_and_accepted_relationship(self):
        request_id = self.make_accepted_request(self.b, self.c, self.c_id)
        self.assertEqual(self.anon.get(f"/api/requests/{request_id}/whatsapp").status_code, 401)
        self.assertEqual(self.anon.put(f"/api/requests/{request_id}/whatsapp", json={
            "share": False,
        }).status_code, 401)

        pending = call(self.a, "POST", "/api/requests", {"receiver_id": self.c_id})
        pending_id = pending.json["request"]["id"]
        self.assertEqual(self.a.get(f"/api/requests/{pending_id}/whatsapp").status_code, 409)
        self.assertEqual(call(self.a, "PUT", f"/api/requests/{pending_id}/whatsapp", {
            "share": True, "phone_number": SYNTHETIC_NUMBER,
        }).status_code, 409)

    def test_consent_can_be_added_and_revoked(self):
        request_id = self.make_accepted_request(self.b, self.c, self.c_id)
        saved = call(self.b, "PUT", f"/api/requests/{request_id}/whatsapp", {
            "share": True, "phone_number": SYNTHETIC_NUMBER,
        })
        self.assertEqual(saved.status_code, 200)
        self.assertTrue(self.c.get(f"/api/requests/{request_id}/whatsapp").json["shared"])

        revoked = call(self.b, "PUT", f"/api/requests/{request_id}/whatsapp", {"share": False})
        self.assertEqual(revoked.status_code, 200)
        contact = self.c.get(f"/api/requests/{request_id}/whatsapp")
        self.assertEqual(contact.json, {"success": True, "shared": False})
        self.assertNotIn(NORMALIZED_NUMBER, contact.get_data(as_text=True))
        self.assertFalse(self.b.get("/api/requests/sent").json["requests"][0]["i_share_whatsapp"])

    def test_invalid_numbers_do_not_accept_or_save_sharing(self):
        for invalid in ("", "5555550123", "+123", "+012345678", "+1234567890123456",
                        "+1 555 call me", "++15555550123"):
            self.assertIsNone(normalize_whatsapp_number(invalid))

        sent = call(self.a, "POST", "/api/requests", {"receiver_id": self.c_id})
        request_id = sent.json["request"]["id"]
        response = call(self.c, "PUT", f"/api/requests/{request_id}/accept", {
            "share_whatsapp": True, "phone_number": "5555550123",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.c.get("/api/requests/received").json["requests"][0]["status"],
                         "pending")
        with app.app_context():
            self.assertEqual(WhatsAppShare.query.count(), 0)

        accepted_id = self.make_accepted_request(self.b, self.c, self.c_id)
        response = call(self.b, "PUT", f"/api/requests/{accepted_id}/whatsapp", {
            "share": True, "phone_number": "not a number",
        })
        self.assertEqual(response.status_code, 400)

    def test_number_normalization_requires_explicit_international_prefix(self):
        self.assertEqual(normalize_whatsapp_number(SYNTHETIC_NUMBER), NORMALIZED_NUMBER)
        self.assertIsNone(normalize_whatsapp_number("15555550123"))

    def test_migration_is_additive_and_idempotent_on_temporary_database(self):
        migration_db = os.path.join(TEMP_DIR, "migration_test.db")
        connection = sqlite3.connect(migration_db)
        connection.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY);
            CREATE TABLE roommate_requests (id INTEGER PRIMARY KEY);
            INSERT INTO users VALUES (1);
            INSERT INTO roommate_requests VALUES (1);
        """)
        connection.commit()
        connection.close()

        result = migrate(migration_db, make_backup=False)
        self.assertTrue(result["added"])
        result_again = migrate(migration_db, make_backup=False)
        self.assertFalse(result_again["added"])
        connection = sqlite3.connect(migration_db)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM roommate_requests").fetchone()[0], 1)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM whatsapp_shares").fetchone()[0], 0)
        connection.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
