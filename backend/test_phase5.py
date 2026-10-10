# CampusNest — automatic Phase 5 tests: roommate requests + consent-based preference sharing.
# Run from the backend folder:   python test_phase5.py
# It uses a TEMPORARY database, so your real campusnest.db is never touched.
# At the end it also runs test_phase4.py to prove Phase 4 still works.
import os
import subprocess
import sys
import tempfile

TEMP_DIR = tempfile.mkdtemp()
os.environ["CAMPUSNEST_DB_URI"] = "sqlite:///" + os.path.join(TEMP_DIR, "test5.db")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sqlalchemy.exc import IntegrityError  # noqa: E402

from app import app  # noqa: E402
from models import PreferenceShare, RoommateRequest, db, make_pair_key  # noqa: E402

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


def view(client, owner_id):
    return call(client, "GET", f"/api/users/{owner_id}/shared-preferences")


PREFS_A = {"gender": "Female", "preferred_area": "Dhonia", "min_budget": 3000, "max_budget": 5000,
           "lifestyle_qualities": ["Quiet", "Study-friendly"], "sleep_schedule": "Early Sleeper",
           "cooking_preference": "Prefer to cook", "expense_preference": "Prefer sharing expenses",
           "guest_preference": "Prefer no/few guests", "pet_preference": "Prefer no pets"}
PREFS_B = {"gender": "Male", "preferred_area": "Jalalabad", "min_budget": 4000, "max_budget": 7000,
           "lifestyle_qualities": ["Social"], "sleep_schedule": "Night Owl",
           "cooking_preference": "No preference", "expense_preference": "Flexible",
           "guest_preference": "Frequent guests are okay", "pet_preference": "Pet-friendly"}
PREFS_C = {"gender": "Female", "preferred_area": "Niribili", "min_budget": 3500, "max_budget": 4500,
           "lifestyle_qualities": ["Clean", "Non-smoker"], "sleep_schedule": "Flexible",
           "cooking_preference": "Occasionally cook", "expense_preference": "Prefer separate expenses",
           "guest_preference": "Occasional guests are okay", "pet_preference": "No preference"}

anon = app.test_client()
a = app.test_client()
b = app.test_client()
c = app.test_client()

print("\nTest 1: not logged in")
for method, url, body in [
        ("POST", "/api/requests", {"receiver_id": 2}),
        ("GET", "/api/requests/received", None),
        ("GET", "/api/requests/sent", None),
        ("PUT", "/api/requests/1/accept", {}),
        ("PUT", "/api/requests/1/reject", {}),
        ("PUT", "/api/requests/1/cancel", {}),
        ("PUT", "/api/requests/1/sharing", {"fields": []}),
        ("GET", "/api/users/2/shared-preferences", None)]:
    check(f"{method} {url} -> 401", call(anon, method, url, body).status_code == 401)

print("\nSetup: three students, each with saved preferences")
for client, name, email, prefs in [(a, "Student A", "a@niter.edu.bd", PREFS_A),
                                   (b, "Student B", "b@niter.edu.bd", PREFS_B),
                                   (c, "Student C", "c@niter.edu.bd", PREFS_C)]:
    check(f"{name} logs in", register_and_login(client, name, email).status_code == 200)
    check(f"{name} saves preferences", call(client, "PUT", "/api/preferences", prefs).status_code == 201)
A = call(a, "GET", "/api/me").json["user"]["id"]
B = call(b, "GET", "/api/me").json["user"]["id"]
C = call(c, "GET", "/api/me").json["user"]["id"]

print("\nTest 2: sending a request - validation")
check("request to yourself -> 400", call(a, "POST", "/api/requests", {"receiver_id": A}).status_code == 400)
check("request to a student that does not exist -> 404", call(a, "POST", "/api/requests", {"receiver_id": 999}).status_code == 404)
for label, value in [("zero", 0), ("negative", -1), ("text", "2"), ("true", True),
                     ("decimal", 1.5), ("null", None), ("a list", [2])]:
    check(f"receiver_id = {label} -> 400", call(a, "POST", "/api/requests", {"receiver_id": value}).status_code == 400)
check("missing receiver_id -> 400", call(a, "POST", "/api/requests", {}).status_code == 400)
check("malformed JSON -> 400", call(a, "POST", "/api/requests", raw="{oops").status_code == 400)
for key in ["requester_id", "sender_id", "user_id", "status", "viewer_id"]:
    r = call(a, "POST", "/api/requests", {"receiver_id": B, key: C})
    check(f"client-supplied '{key}' -> 403", r.status_code == 403)
check("unknown field -> 400", call(a, "POST", "/api/requests", {"receiver_id": B, "note": "hi"}).status_code == 400)
check("none of those bad calls created a request", call(b, "GET", "/api/requests/received").json["requests"] == [])

print("\nTest 3: sending a request - rules")
r = call(a, "POST", "/api/requests", {"receiver_id": B})
check("A sends a request to B -> 201", r.status_code == 201)
req1 = r.json["request"]["id"]
check("request starts as pending, from A", r.json["request"]["status"] == "pending"
      and r.json["request"]["direction"] == "sent" and r.json["request"]["other_user"]["id"] == B)
check("duplicate A -> B while pending -> 409", call(a, "POST", "/api/requests", {"receiver_id": B}).status_code == 409)
check("reverse B -> A while pending -> 409", call(b, "POST", "/api/requests", {"receiver_id": A}).status_code == 409)
rb = call(b, "GET", "/api/requests/received")
check("B sees 1 received request", len(rb.json["requests"]) == 1 and rb.json["requests"][0]["id"] == req1)
check("A sees 1 sent request, 0 received", len(call(a, "GET", "/api/requests/sent").json["requests"]) == 1
      and call(a, "GET", "/api/requests/received").json["requests"] == [])
check("unrelated C sees nothing", call(c, "GET", "/api/requests/received").json["requests"] == []
      and call(c, "GET", "/api/requests/sent").json["requests"] == [])
text = rb.get_data(as_text=True)
check("request lists contain no email / password / preference data",
      all(word not in text for word in ["@niter", "password", "lifestyle_qualities", "min_budget"]))
check("?user_id= for someone else on a list -> 403", call(a, "GET", f"/api/requests/sent?user_id={B}").status_code == 403)

print("\nTest 4: a PENDING request grants nothing")
check("A cannot view B's preferences", view(a, B).status_code == 403)
check("B cannot view A's preferences", view(b, A).status_code == 403)
check("C cannot view A's or B's", view(c, A).status_code == 403 and view(c, B).status_code == 403)
check("nobody can view their own through the sharing route", view(a, A).status_code == 403)

print("\nTest 5: who may answer a request")
check("requester A cannot accept their own request -> 403", call(a, "PUT", f"/api/requests/{req1}/accept", {}).status_code == 403)
check("requester A cannot reject their own request -> 403", call(a, "PUT", f"/api/requests/{req1}/reject", {}).status_code == 403)
check("receiver B cannot 'cancel' (only the requester) -> 403", call(b, "PUT", f"/api/requests/{req1}/cancel", {}).status_code == 403)
check("unrelated C cannot accept -> 404", call(c, "PUT", f"/api/requests/{req1}/accept", {}).status_code == 404)
check("unrelated C cannot reject -> 404", call(c, "PUT", f"/api/requests/{req1}/reject", {}).status_code == 404)
check("unrelated C cannot cancel -> 404", call(c, "PUT", f"/api/requests/{req1}/cancel", {}).status_code == 404)
check("unrelated C cannot change sharing -> 404", call(c, "PUT", f"/api/requests/{req1}/sharing", {"fields": ["gender"]}).status_code == 404)
check("sharing cannot be changed while pending -> 409", call(a, "PUT", f"/api/requests/{req1}/sharing", {"fields": ["gender"]}).status_code == 409)
check("request id that does not exist -> 404", call(b, "PUT", "/api/requests/9999/accept", {}).status_code == 404)

print("\nTest 6: bad accept bodies do nothing")
check("share_fields with a non-preference name -> 400", call(b, "PUT", f"/api/requests/{req1}/accept", {"share_fields": ["password"]}).status_code == 400)
check("share_fields as text -> 400", call(b, "PUT", f"/api/requests/{req1}/accept", {"share_fields": "all"}).status_code == 400)
check("share_fields with a number inside -> 400", call(b, "PUT", f"/api/requests/{req1}/accept", {"share_fields": [1]}).status_code == 400)
check("unknown field -> 400", call(b, "PUT", f"/api/requests/{req1}/accept", {"x": 1}).status_code == 400)
check("'requester_id' in body -> 403", call(b, "PUT", f"/api/requests/{req1}/accept", {"requester_id": C}).status_code == 403)
check("'status' in body -> 403", call(b, "PUT", f"/api/requests/{req1}/accept", {"status": "accepted"}).status_code == 403)
check("request is still pending", call(b, "GET", "/api/requests/received").json["requests"][0]["status"] == "pending")
check("A still cannot view B", view(a, B).status_code == 403)

print("\nTest 7: B accepts and shares three fields")
r = call(b, "PUT", f"/api/requests/{req1}/accept",
         {"share_fields": ["sleep_schedule", "preferred_area", "lifestyle_qualities"]})
check("B accepts -> 200, status accepted", r.status_code == 200 and r.json["request"]["status"] == "accepted")
r = view(a, B)
check("A can now view B's shared preferences (200)", r.status_code == 200)
check("A sees exactly the three permitted fields",
      r.json["shared_fields"] == ["preferred_area", "lifestyle_qualities", "sleep_schedule"]
      and set(r.json["preferences"].keys()) == {"preferred_area", "lifestyle_qualities", "sleep_schedule"})
check("and they are B's real values", r.json["preferences"] == {
      "preferred_area": "Jalalabad", "lifestyle_qualities": ["Social"], "sleep_schedule": "Night Owl"})
text = r.get_data(as_text=True)
check("no other preference, email or password data in that response",
      all(word not in text for word in ["min_budget", "max_budget", "cooking", "guest", "pet_preference",
                                        "expense", "gender", "email", "password", "department"]))
check("direction: B still cannot view A's preferences (A shared nothing)", view(b, A).status_code == 403)
check("unrelated C cannot view A or B", view(c, A).status_code == 403 and view(c, B).status_code == 403)

print("\nTest 8: owners keep full control of their own preferences")
check("B reads all own preferences", call(b, "GET", "/api/preferences").json["preferences"] == PREFS_B)
check("B edits own preferences", call(b, "PUT", "/api/preferences", dict(PREFS_B, sleep_schedule="Flexible")).status_code == 200)
check("A sees the updated shared value (live data)", view(a, B).json["preferences"]["sleep_schedule"] == "Flexible")
call(b, "PUT", "/api/preferences", PREFS_B)
check("A cannot touch B's preferences through any preferences route",
      call(a, "GET", f"/api/preferences?user_id={B}").status_code == 403
      and call(a, "PUT", "/api/preferences", dict(PREFS_A, user_id=B)).status_code == 403)
check("A's own preferences are unchanged", call(a, "GET", "/api/preferences").json["preferences"] == PREFS_A)

print("\nTest 9: states cannot be changed twice")
check("accept again -> 409", call(b, "PUT", f"/api/requests/{req1}/accept", {}).status_code == 409)
check("reject an accepted request -> 409", call(b, "PUT", f"/api/requests/{req1}/reject", {}).status_code == 409)
check("cancel an accepted request -> 409", call(a, "PUT", f"/api/requests/{req1}/cancel", {}).status_code == 409)
check("duplicate request while accepted -> 409", call(a, "POST", "/api/requests", {"receiver_id": B}).status_code == 409)
lb = call(b, "GET", "/api/requests/received").json["requests"][0]
la = call(a, "GET", "/api/requests/sent").json["requests"][0]
check("B's list: i_share has 3 fields, they_share False", len(lb["i_share"]) == 3 and lb["they_share"] is False)
check("A's list: i_share empty, they_share True", la["i_share"] == [] and la["they_share"] is True)

print("\nTest 10: reciprocal sharing is a separate choice")
check("A chooses to share 'gender' -> 200", call(a, "PUT", f"/api/requests/{req1}/sharing", {"fields": ["gender"]}).status_code == 200)
r = view(b, A)
check("now B sees only A's gender", r.status_code == 200 and r.json["preferences"] == {"gender": "Female"})
check("A's view of B did not change", len(view(a, B).json["shared_fields"]) == 3)
check("sharing a non-preference field -> 400", call(b, "PUT", f"/api/requests/{req1}/sharing", {"fields": ["email"]}).status_code == 400)
check("sharing without 'fields' -> 400", call(b, "PUT", f"/api/requests/{req1}/sharing", {}).status_code == 400)
check("sharing 'fields' as text -> 400", call(b, "PUT", f"/api/requests/{req1}/sharing", {"fields": "gender"}).status_code == 400)
check("'viewer_id' in sharing body -> 403", call(b, "PUT", f"/api/requests/{req1}/sharing", {"fields": ["gender"], "viewer_id": C}).status_code == 403)
check("B changing own sharing does not change A's", call(b, "PUT", f"/api/requests/{req1}/sharing", {"fields": ["gender"]}).status_code == 200
      and view(a, B).json["preferences"] == {"gender": "Male"} and view(b, A).json["preferences"] == {"gender": "Female"})

print("\nTest 11: revoking sharing takes effect immediately")
check("B stops sharing -> 200", call(b, "PUT", f"/api/requests/{req1}/sharing", {"fields": []}).status_code == 200)
check("A is denied again (403)", view(a, B).status_code == 403)
check("B can still view what A shares (separate permission)", view(b, A).status_code == 200)
check("B shares one field again -> A sees only it",
      call(b, "PUT", f"/api/requests/{req1}/sharing", {"fields": ["pet_preference"]}).status_code == 200
      and view(a, B).json["preferences"] == {"pet_preference": "Pet-friendly"})
call(b, "PUT", f"/api/requests/{req1}/sharing", {"fields": []})
check("revoked again -> A denied", view(a, B).status_code == 403)
call(a, "PUT", f"/api/requests/{req1}/sharing", {"fields": []})
check("A revokes too -> B denied", view(b, A).status_code == 403)

print("\nTest 12: same answer for every denial (no probing)")
d1, d2, d3 = view(a, 999), view(a, C), view(a, B)
check("unknown user, unrelated user and revoked share all give the identical 403",
      d1.status_code == d2.status_code == d3.status_code == 403 and d1.json == d2.json == d3.json)

print("\nTest 13: using someone else's request id or user id does not help")
r = call(b, "POST", "/api/requests", {"receiver_id": C})
req_bc = r.json["request"]["id"]
check("B sends a request to C", r.status_code == 201)
check("A cannot accept B->C -> 404", call(a, "PUT", f"/api/requests/{req_bc}/accept", {}).status_code == 404)
check("A cannot reject B->C -> 404", call(a, "PUT", f"/api/requests/{req_bc}/reject", {}).status_code == 404)
check("A cannot cancel B->C -> 404", call(a, "PUT", f"/api/requests/{req_bc}/cancel", {}).status_code == 404)
check("A cannot set sharing on B->C -> 404", call(a, "PUT", f"/api/requests/{req_bc}/sharing", {"fields": ["gender"]}).status_code == 404)
check("A still cannot view C", view(a, C).status_code == 403)
check("B (the requester) cannot accept B->C -> 403", call(b, "PUT", f"/api/requests/{req_bc}/accept", {}).status_code == 403)
check("C rejects B->C (no request body at all)", call(c, "PUT", f"/api/requests/{req_bc}/reject").status_code == 200)

print("\nTest 14: rejected and cancelled requests grant nothing, and may be re-sent")
r = call(a, "POST", "/api/requests", {"receiver_id": C})
req2 = r.json["request"]["id"]
check("A sends a request to C", r.status_code == 201)
check("C rejects it", call(c, "PUT", f"/api/requests/{req2}/reject", {}).status_code == 200)
check("A cannot view C after rejection", view(a, C).status_code == 403)
check("C cannot view A after rejection", view(c, A).status_code == 403)
check("reject again -> 409", call(c, "PUT", f"/api/requests/{req2}/reject", {}).status_code == 409)
check("accept a rejected request -> 409", call(c, "PUT", f"/api/requests/{req2}/accept", {}).status_code == 409)
with app.app_context():
    check("no permission slips remain for the rejected request",
          PreferenceShare.query.filter_by(request_id=req2).count() == 0)
r = call(a, "POST", "/api/requests", {"receiver_id": C})
req3 = r.json["request"]["id"]
check("after a rejection a NEW request may be sent (201, new id)", r.status_code == 201 and req3 != req2)
check("A cancels the pending request", call(a, "PUT", f"/api/requests/{req3}/cancel", {}).status_code == 200)
check("cancel again -> 409", call(a, "PUT", f"/api/requests/{req3}/cancel", {}).status_code == 409)
check("accept a cancelled request -> 409", call(c, "PUT", f"/api/requests/{req3}/accept", {}).status_code == 409)
check("no access after cancellation", view(a, C).status_code == 403 and view(c, A).status_code == 403)

print("\nTest 15: accepting alone shares nothing")
r = call(a, "POST", "/api/requests", {"receiver_id": C})
req4 = r.json["request"]["id"]
check("after a cancellation a NEW request may be sent", r.status_code == 201)
check("C accepts with no body at all", call(c, "PUT", f"/api/requests/{req4}/accept").status_code == 200)
check("A still cannot view C (nothing shared yet)", view(a, C).status_code == 403)
check("C shares only 'gender'", call(c, "PUT", f"/api/requests/{req4}/sharing", {"fields": ["gender"]}).status_code == 200)
check("A sees only C's gender", view(a, C).json["preferences"] == {"gender": "Female"})
check("C still cannot view A", view(c, A).status_code == 403)

print("\nTest 16: the database itself enforces the rules")
with app.app_context():
    duplicate = RoommateRequest(requester_id=C, receiver_id=A, status="pending", pair_key=make_pair_key(A, C))
    db.session.add(duplicate)
    try:
        db.session.commit()
        blocked = False
    except IntegrityError:
        db.session.rollback()
        blocked = True
    check("a second active request for the same pair is refused by the database", blocked)

    to_self = RoommateRequest(requester_id=A, receiver_id=A, status="pending", pair_key=make_pair_key(A, A))
    db.session.add(to_self)
    try:
        db.session.commit()
        blocked = False
    except IntegrityError:
        db.session.rollback()
        blocked = True
    check("a request to yourself is refused by the database", blocked)

print("\nTest 17: no admin or user-list routes")
paths = sorted(rule.rule for rule in app.url_map.iter_rules())
check("no admin routes", not any("admin" in p for p in paths))
check("no user-list route", "/api/users" not in paths and "/api/users/" not in paths)
print("  Routes:", ", ".join(p for p in paths if p.startswith("/api")))

print("\nTest 18: Phase 4 still works (running test_phase4.py)")
result = subprocess.run([sys.executable, os.path.join(HERE, "test_phase4.py")],
                        capture_output=True, text=True)
summary = [line for line in result.stdout.splitlines() if "passed," in line]
print("  test_phase4.py says:", summary[-1].strip() if summary else "(no summary line)")
check("test_phase4.py exits with success", result.returncode == 0)
if result.returncode != 0:
    print(result.stdout[-2000:])
    print(result.stderr[-2000:])

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
