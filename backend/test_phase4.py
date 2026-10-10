# CampusNest — automatic Phase 4 tests.
# Run from the backend folder:   python test_phase4.py
# It uses a TEMPORARY database, so your real campusnest.db is never touched.
import os
import sys
import tempfile

TEMP_DIR = tempfile.mkdtemp()
os.environ["CAMPUSNEST_DB_URI"] = "sqlite:///" + os.path.join(TEMP_DIR, "test.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app  # noqa: E402

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print("  PASS  " + name)
    else:
        failed += 1
        print("  FAIL  " + name)


def call(client, method, url, body=None, raw=None, content_type="application/json"):
    if raw is not None:
        return client.open(url, method=method, data=raw, content_type=content_type)
    if body is not None:
        return client.open(url, method=method, json=body)
    return client.open(url, method=method)


def register_and_login(client, name, email):
    call(client, "POST", "/api/register", {"name": name, "email": email,
         "password": "secret123", "confirm_password": "secret123"})
    return call(client, "POST", "/api/login", {"email": email, "password": "secret123"})


PROFILE_A = {"full_name": "Student A", "department": "Textile Engineering", "year": "2nd Year",
             "gender": "Female", "area": "Dhonia", "budget": 4500, "about": "Quiet student."}

PREFS_A = {"gender": "Female", "preferred_area": "Dhonia", "min_budget": 3000, "max_budget": 5000,
           "lifestyle_qualities": ["Study-friendly", "Quiet", "Non-smoker"],
           "sleep_schedule": "Early Sleeper", "cooking_preference": "Prefer to cook",
           "expense_preference": "Prefer sharing expenses",
           "guest_preference": "Prefer no/few guests", "pet_preference": "Prefer no pets"}

PREFS_B = {"gender": "Male", "preferred_area": "Jalalabad", "min_budget": 4000, "max_budget": 7000,
           "lifestyle_qualities": ["Social"], "sleep_schedule": "Night Owl",
           "cooking_preference": "No preference", "expense_preference": "Flexible",
           "guest_preference": "Frequent guests are okay", "pet_preference": "Pet-friendly"}

anon = app.test_client()
a = app.test_client()
b = app.test_client()

print("\nTest E: not logged in")
for method, url in [("GET", "/api/profile"), ("PUT", "/api/profile"),
                    ("GET", "/api/preferences"), ("PUT", "/api/preferences"),
                    ("GET", "/api/users/1/shared-preferences")]:
    r = call(anon, method, url, {} if method == "PUT" else None)
    check(f"{method} {url} -> 401", r.status_code == 401)

print("\nSetup: register + login two students")
check("A logs in", register_and_login(a, "Student A", "a@niter.edu.bd").status_code == 200)
check("B logs in", register_and_login(b, "Student B", "b@niter.edu.bd").status_code == 200)

print("\nTest A: profile persistence")
r = call(a, "GET", "/api/profile")
check("new profile is empty but loads (200)", r.status_code == 200 and r.json["profile"]["department"] is None)
r = call(a, "PUT", "/api/profile", PROFILE_A)
check("PUT profile -> 200", r.status_code == 200)
r = call(a, "GET", "/api/profile")
check("profile restored", r.json["profile"] == {**PROFILE_A})
check("profile response has no password / email / preferences",
      all(word not in r.get_data(as_text=True) for word in
          ["password", "email", "lifestyle_qualities", "min_budget"]))
bad = dict(PROFILE_A, department="Made Up Dept")
check("invalid department rejected (400)", call(a, "PUT", "/api/profile", bad).status_code == 400)
check("old area (Mirpur) rejected on profile (400)", call(a, "PUT", "/api/profile", dict(PROFILE_A, area="Mirpur")).status_code == 400)
check("profile budget -5 rejected", call(a, "PUT", "/api/profile", dict(PROFILE_A, budget=-5)).status_code == 400)

print("\nTest B: preference persistence")
r = call(a, "GET", "/api/preferences")
check("no preferences yet -> has_preferences False", r.status_code == 200 and r.json["has_preferences"] is False)
r = call(a, "PUT", "/api/preferences", PREFS_A)
check("first save -> 201 (created)", r.status_code == 201)
r = call(a, "GET", "/api/preferences")
expected = dict(PREFS_A, lifestyle_qualities=["Quiet", "Study-friendly", "Non-smoker"])
check("all 10 fields restored (multi-select in fixed order)", r.json["preferences"] == expected)
r = call(a, "PUT", "/api/preferences", dict(PREFS_A, max_budget=6000))
check("second save -> 200 (updated, not duplicated)", r.status_code == 200)
check("update stored", call(a, "GET", "/api/preferences").json["preferences"]["max_budget"] == 6000)
call(a, "PUT", "/api/preferences", PREFS_A)  # put back

print("\nTest C: validation")
cases = {
    "invalid gender": dict(PREFS_A, gender="Any"),
    "unsupported area": dict(PREFS_A, preferred_area="Nayarhat"),
    "bad sleep option": dict(PREFS_A, sleep_schedule="Sometimes"),
    "bad cooking option": dict(PREFS_A, cooking_preference="Always"),
    "bad expense option": dict(PREFS_A, expense_preference="Maybe"),
    "bad guest option": dict(PREFS_A, guest_preference="Never"),
    "bad pet option": dict(PREFS_A, pet_preference="Snakes"),
    "invalid lifestyle quality": dict(PREFS_A, lifestyle_qualities=["Quiet", "Loud"]),
    "empty lifestyle list": dict(PREFS_A, lifestyle_qualities=[]),
    "lifestyle not a list": dict(PREFS_A, lifestyle_qualities="Quiet"),
    "negative budget": dict(PREFS_A, min_budget=-1),
    "max below min": dict(PREFS_A, min_budget=5000, max_budget=3000),
    "text budget": dict(PREFS_A, min_budget="abc"),
    "decimal budget": dict(PREFS_A, max_budget=5000.5),
    "boolean budget": dict(PREFS_A, max_budget=True),
    "missing field": {k: v for k, v in PREFS_A.items() if k != "pet_preference"},
    "unknown field": dict(PREFS_A, favourite_colour="red"),
}
for label, body in cases.items():
    check(label + " -> 400", call(a, "PUT", "/api/preferences", body).status_code == 400)
check("malformed JSON -> 400", call(a, "PUT", "/api/preferences", raw="{not json").status_code == 400)
check("JSON list instead of object -> 400", call(a, "PUT", "/api/preferences", raw="[1,2]").status_code == 400)
check("wrong content-type -> 400", call(a, "PUT", "/api/preferences",
      raw="gender=Male", content_type="application/x-www-form-urlencoded").status_code == 400)
check("A's saved data survived all the bad requests",
      call(a, "GET", "/api/preferences").json["preferences"] == expected)

print("\nTest C/E: attempts to touch another user's record")
for key in ["user_id", "id", "owner_id", "email", "password_hash"]:
    r = call(a, "PUT", "/api/preferences", dict(PREFS_A, **{key: 2}))
    check(f"'{key}' in preferences body -> 403", r.status_code == 403)
    r = call(a, "PUT", "/api/profile", dict(PROFILE_A, **{key: 2}))
    check(f"'{key}' in profile body -> 403", r.status_code == 403)

print("\nTest D: user isolation")
r = call(b, "PUT", "/api/preferences", PREFS_B)
check("B saves different preferences (201)", r.status_code == 201)
check("B sees only B's values", call(b, "GET", "/api/preferences").json["preferences"] == PREFS_B)
check("A's preferences unchanged", call(a, "GET", "/api/preferences").json["preferences"] == expected)
call(b, "PUT", "/api/profile", dict(PROFILE_A, full_name="Student B", gender="Male", area="Nobinagar"))
check("A's profile unchanged", call(a, "GET", "/api/profile").json["profile"]["full_name"] == "Student A")

print("\nTest E: direct requests for another user's data")
check("GET /api/preferences?user_id=2 as A -> 403", call(a, "GET", "/api/preferences?user_id=2").status_code == 403)
check("GET /api/profile?user_id=2 as A -> 403", call(a, "GET", "/api/profile?user_id=2").status_code == 403)
r1 = call(a, "GET", "/api/users/2/shared-preferences")
r2 = call(a, "GET", "/api/users/999/shared-preferences")
check("shared-preferences denied (403) for B's id", r1.status_code == 403)
check("identical answer for a user that does not exist", r2.status_code == 403 and r1.json == r2.json)
check("no preference values leaked there", "lifestyle_qualities" not in r1.get_data(as_text=True))

print("\nTest F: request acceptance (no request system exists yet)")
print("  SKIP  pending / rejected / accepted / revoked tests wait for the request system")

print("\nTest G: admin / user-list privacy")
paths = sorted(rule.rule for rule in app.url_map.iter_rules())
check("no admin routes", not any("admin" in p for p in paths))
check("no user-list route", "/api/users" not in paths and "/api/users/" not in paths)
check("no debug/diagnostic API routes", not any(w in p for p in paths for w in ("debug", "dump", "export")))
print("  Routes:", ", ".join(p for p in paths if p.startswith("/api")))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
