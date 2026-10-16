# CampusNest — automatic Phase 6 tests: the matching API, privacy and the database migration.
# Run from the backend folder:   python test_phase6.py
# It uses a TEMPORARY database, so your real campusnest.db is never touched.
# At the end it also runs test_matching.py and test_phase5.py (which runs test_phase4.py)
# to prove that the matching logic and Phases 1-5 still pass.
import logging
import os
import sqlite3
import subprocess
import sys
import tempfile

TEMP_DIR = tempfile.mkdtemp()
os.environ["CAMPUSNEST_DB_URI"] = "sqlite:///" + os.path.join(TEMP_DIR, "test6.db")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sqlalchemy import create_engine  # noqa: E402

import app as app_module  # noqa: E402
from app import app  # noqa: E402
from migrate_phase6 import ensure_phase6_schema  # noqa: E402
from models import db  # noqa: E402

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


def profile(name, gender, department="Textile Engineering", year="2nd Year"):
    return {"full_name": name, "department": department, "year": year, "gender": gender,
            "area": "Dhonia", "budget": 4000, "about": "Private about text."}


def prefs(roommate_gender="Female", **changes):
    """A complete, valid preference payload (including the Phase 6 field)."""
    data = {"gender": "Female", "preferred_roommate_gender": roommate_gender,
            "preferred_area": "Dhonia", "min_budget": 3000, "max_budget": 5000,
            "lifestyle_qualities": ["Quiet", "Clean", "Study-friendly"],
            "sleep_schedule": "Early Sleeper", "cooking_preference": "Prefer to cook",
            "expense_preference": "Prefer sharing expenses",
            "guest_preference": "Prefer no/few guests", "pet_preference": "Prefer no pets"}
    if roommate_gender is None:
        del data["preferred_roommate_gender"]      # a pre-Phase-6 style payload
    data.update(changes)
    return data


def match_ids(response):
    return [m["user_id"] for m in response.json["matches"]]


def find(response, user_id):
    for m in response.json["matches"]:
        if m["user_id"] == user_id:
            return m
    return None


ESSENTIALS = "Meets all your essential requirements (gender preference, area and budget range)."

# Words that must NEVER appear in a matches response (they are other people's private data,
# or the viewer's own private data). Values below are unique so a leak cannot be a coincidence.
LEAK_WORDS = ["4123", "5987", "bina.secret", "password", "Akter", "Rahman", "Jalalabad", "Niribili",
              "Dhonia", "Early Sleeper", "Night Owl", "Study-friendly", "Prefer to cook",
              "Pet-friendly", "min_budget", "max_budget", "similarity", "score", "Private about"]

anon = app.test_client()
clients = {name: app.test_client() for name in
           ["alice", "bina", "carol", "dina", "eva", "farid", "gita", "hana", "ivy", "jane"]}
alice, bina, carol, dina, eva, farid, gita, hana, ivy, jane = (clients[n] for n in clients)

# ----------------------------------------------------------------------------- Setup
print("\nSetup: ten students")
people = [
    (alice, "Alice Rahman", "alice@niter.edu.bd"), (bina, "Bina Akter", "bina.secret@niter.edu.bd"),
    (carol, "Carol Das", "carol@niter.edu.bd"), (dina, "Dina Roy", "dina@niter.edu.bd"),
    (eva, "Eva Khan", "eva@niter.edu.bd"), (farid, "Farid Hasan", "farid@niter.edu.bd"),
    (gita, "Gita Paul", "gita@niter.edu.bd"), (hana, "Hana Noor", "hana@niter.edu.bd"),
    (ivy, "Ivy Sen", "ivy@niter.edu.bd"), (jane, "Jane Roy", "jane@niter.edu.bd"),
]
for client, name, email in people:
    check(name + " logs in", register_and_login(client, name, email).status_code == 200)
ID = {name.split()[0].lower(): call(client, "GET", "/api/me").json["user"]["id"] for client, name, _ in people}

# profile saves (everybody except Hana and Jane)
for client, name, gender in [(alice, "Alice Rahman", "Female"), (bina, "Bina Akter", "Female"),
                             (carol, "Carol Das", "Female"), (dina, "Dina Roy", "Female"),
                             (eva, "Eva Khan", "Female"), (farid, "Farid Hasan", "Male"),
                             (gita, "Gita Paul", "Female"), (ivy, "Ivy Sen", "Female")]:
    r = call(client, "PUT", "/api/profile", profile(name, gender))
    check(name + " saves profile", r.status_code == 200)

SAVES = [
    (alice, prefs("Female")),
    (bina, prefs("Female", min_budget=4123, max_budget=5987)),                       # overlaps Alice
    (carol, prefs("Female", min_budget=5000, max_budget=7000, lifestyle_qualities=["Social"],
                  sleep_schedule="Night Owl", pet_preference="Pet-friendly")),        # touches Alice at 5000
    (dina, prefs("Female", preferred_area="Niribili")),                               # different area
    (eva, prefs("Female", min_budget=6500, max_budget=8000)),                         # no budget overlap
    (farid, prefs("Female", gender="Male")),                                          # Alice would not accept a man
    (gita, prefs(None)),                                                              # LEGACY: no roommate gender
    (hana, prefs("Female")),                                                          # prefs but NO profile
]
for client, payload in SAVES:
    r = call(client, "PUT", "/api/preferences", payload)
    check("preferences saved (201)", r.status_code == 201)
# Ivy has a profile but no preferences. Jane has neither.

# ----------------------------------------------------------------------------- 1. Authentication
print("\nTest 1: not logged in")
for url in ["/api/matches", f"/api/matches/{ID['bina']}"]:
    r = call(anon, "GET", url)
    check("GET " + url + " -> 401", r.status_code == 401)
    check("and no data leaks", "matches" not in r.get_data(as_text=True) and "Bina" not in r.get_data(as_text=True))

print("\nTest 2: nobody can pick whose matches are computed")
for key in ("user_id", "id", "owner_id"):
    r = call(alice, "GET", f"/api/matches?{key}={ID['bina']}")
    check(f"?{key}=<someone else> -> 403", r.status_code == 403)
check("?user_id=<my own id> is fine", call(alice, "GET", f"/api/matches?user_id={ID['alice']}").status_code == 200)
check("the same ?user_id trick is refused on the detail route",
      call(alice, "GET", f"/api/matches/{ID['bina']}?user_id={ID['carol']}").status_code == 403)
check("a user id in the request body is ignored (matches never read a body)",
      call(alice, "GET", "/api/matches", {"user_id": ID["bina"]}).json["matches"] ==
      call(alice, "GET", "/api/matches").json["matches"])
for method in ("POST", "PUT", "DELETE"):
    check(method + " /api/matches is not allowed (405)", call(alice, method, "/api/matches", {}).status_code == 405)
check("Alice's list never depends on who else is logged in",
      match_ids(call(alice, "GET", "/api/matches")) != match_ids(call(bina, "GET", "/api/matches")))

# ----------------------------------------------------------------------------- 3. Missing data
print("\nTest 3: missing or incomplete data is handled safely")
r = call(jane, "GET", "/api/matches")
check("no profile, no preferences -> 200 needs_profile, empty list",
      r.status_code == 200 and r.json["status"] == "needs_profile" and r.json["matches"] == [])
r = call(ivy, "GET", "/api/matches")
check("profile but no preferences -> needs_preferences", r.json["status"] == "needs_preferences" and r.json["matches"] == [])
r = call(hana, "GET", "/api/matches")
check("preferences but no profile -> needs_profile", r.json["status"] == "needs_profile")
r = call(gita, "GET", "/api/matches")
check("LEGACY user (no roommate gender) -> needs_roommate_gender and no matches",
      r.status_code == 200 and r.json["status"] == "needs_roommate_gender" and r.json["matches"] == [])
check("a message explains what to do", "roommate" in r.json["message"].lower())
check("none of these responses contain a traceback", "Traceback" not in r.get_data(as_text=True))

print("\nTest 3b: the legacy user's saved data is unchanged and the new field only appears once set")
saved = call(gita, "GET", "/api/preferences").json["preferences"]
check("legacy preferences still return exactly the original 10 fields", set(saved.keys()) == {
      "gender", "preferred_area", "min_budget", "max_budget", "lifestyle_qualities", "sleep_schedule",
      "cooking_preference", "expense_preference", "guest_preference", "pet_preference"})
check("once set, the owner sees the new field in their own preferences",
      call(alice, "GET", "/api/preferences").json["preferences"]["preferred_roommate_gender"] == "Female")
check("an invalid roommate gender is rejected (400)",
      call(alice, "PUT", "/api/preferences", prefs("Alien")).status_code == 400)
check("a user_id in the preference body is still refused (403, Phase 4 rule)",
      call(alice, "PUT", "/api/preferences", dict(prefs("Female"), user_id=ID["bina"])).status_code == 403)
check("Alice's saved roommate gender survived those failed saves",
      call(alice, "GET", "/api/preferences").json["preferences"]["preferred_roommate_gender"] == "Female")
check("saving WITHOUT the field keeps the stored value (Alice re-saves old-style)",
      call(alice, "PUT", "/api/preferences", prefs(None)).status_code == 200
      and call(alice, "GET", "/api/preferences").json["preferences"]["preferred_roommate_gender"] == "Female")

# ----------------------------------------------------------------------------- 4. Hard matching via the API
print("\nTest 4: hard matching through the API")
r = call(alice, "GET", "/api/matches")
check("200 and status ok", r.status_code == 200 and r.json["success"] and r.json["status"] == "ok")
check("Alice is matched with exactly Bina and Carol", sorted(match_ids(r)) == sorted([ID["bina"], ID["carol"]]))
check("Carol is included: budgets [3000,5000] and [5000,7000] touch at 5000", find(r, ID["carol"]) is not None)
check("different area (Dina) is excluded", find(r, ID["dina"]) is None)
check("non-overlapping budget (Eva) is excluded", find(r, ID["eva"]) is None)
check("gender-incompatible (Farid) is excluded", find(r, ID["farid"]) is None)
check("legacy user without roommate gender (Gita) is excluded", find(r, ID["gita"]) is None)
check("user without a profile (Hana) is not shown", find(r, ID["hana"]) is None)
check("Alice is never her own match", find(r, ID["alice"]) is None)
check("ranking: Bina (very similar) before Carol (opposite lifestyle)",
      match_ids(r) == [ID["bina"], ID["carol"]] and [m["rank"] for m in r.json["matches"]] == [1, 2])
check("the bands make sense: Bina Strong/Good, Carol Fair",
      find(r, ID["bina"])["compatibility_band"] in ("Strong", "Good")
      and find(r, ID["carol"])["compatibility_band"] == "Fair")
text = r.get_data(as_text=True)
check("excluded students' names and ids are not mentioned at all",
      all(word not in text for word in ["Dina", "Eva", "Farid", "Gita", "Hana"]))
check("the other direction: Bina's list contains Alice and Carol",
      sorted(match_ids(call(bina, "GET", "/api/matches"))) == sorted([ID["alice"], ID["carol"]]))
r = call(dina, "GET", "/api/matches")
check("nobody qualifies for Dina -> 200, status no_matches, empty list, clear message",
      r.status_code == 200 and r.json["status"] == "no_matches" and r.json["matches"] == []
      and "No students" in r.json["message"])
check("incompatible people are not 'filled in' to pad an empty page",
      all(word not in r.get_data(as_text=True) for word in ["Alice", "Bina", "Carol"]))

# ----------------------------------------------------------------------------- 5. What a match card may contain
print("\nTest 5: only authorized information is returned")
r = call(alice, "GET", "/api/matches")
card = find(r, ID["bina"])
check("each card has exactly the allowed fields",
      set(card.keys()) == {"user_id", "rank", "first_name", "department", "year", "compatibility_band",
                           "reasons", "differences", "can_view_shared_preferences", "request"})
check("first name only (no surname)", card["first_name"] == "Bina")
check("department and year are shown", card["department"] == "Textile Engineering" and card["year"] == "2nd Year")
text = r.get_data(as_text=True)
check("no private value, email, password, exact budget, area or numeric score anywhere in the response",
      all(word not in text for word in LEAK_WORDS))
check("a disclaimer says the band is an estimate", "estimate" in r.json["disclaimer"].lower())
check("before any consent: only the essentials sentence, no per-preference claims",
      card["reasons"] == [ESSENTIALS] and card["differences"] == [] and card["can_view_shared_preferences"] is False)
check("no request yet", card["request"] is None)

print("\nTest 6: the detail route shows only eligible matches, with one identical refusal for everything else")
r = call(alice, "GET", f"/api/matches/{ID['bina']}")
check("eligible match -> 200 with the same card", r.status_code == 200 and r.json["match"]["user_id"] == ID["bina"]
      and r.json["match"]["first_name"] == "Bina")
check("detail API returns only the same privacy-approved fields as a match card",
      set(r.json["match"].keys()) == {"user_id", "rank", "first_name", "department", "year",
                                     "compatibility_band", "reasons", "differences",
                                     "can_view_shared_preferences", "request"})
check("detail response leaks nothing private", all(word not in r.get_data(as_text=True) for word in LEAK_WORDS))
refusals = [call(alice, "GET", f"/api/matches/{ID['dina']}"),       # real user, not eligible (area)
            call(alice, "GET", f"/api/matches/{ID['farid']}"),      # real user, not eligible (gender)
            call(alice, "GET", f"/api/matches/{ID['alice']}"),      # myself
            call(alice, "GET", "/api/matches/999999")]              # does not exist
check("ineligible / myself / non-existent all give 404", all(x.status_code == 404 for x in refusals))
check("and the exact same body, so ids cannot be probed",
      len({x.get_data(as_text=True) for x in refusals}) == 1)

# ----------------------------------------------------------------------------- 7. Live data changes
print("\nTest 7: results follow the CURRENT preferences")
check("Gita saves her preferences again, now choosing a roommate gender -> 200",
      call(gita, "PUT", "/api/preferences", prefs("Female")).status_code == 200)
check("she now appears for Alice (she was ineligible before)",
      ID["gita"] in match_ids(call(alice, "GET", "/api/matches")))
check("and her own status is ok", call(gita, "GET", "/api/matches").json["status"] == "ok")
call(gita, "PUT", "/api/preferences", prefs("Female", preferred_area="Niribili"))
check("Gita moves to Niribili -> she disappears from Alice's list",
      ID["gita"] not in match_ids(call(alice, "GET", "/api/matches")))
check("and Dina (Niribili) now has Gita as a match",
      match_ids(call(dina, "GET", "/api/matches")) == [ID["gita"]])
call(gita, "PUT", "/api/preferences", prefs("Female", min_budget=9000, max_budget=9500))
check("Gita back in Dhonia but with a far-away budget -> still not Alice's match",
      ID["gita"] not in match_ids(call(alice, "GET", "/api/matches")))
call(gita, "PUT", "/api/preferences", prefs("Male"))
check("Gita now only wants a male roommate -> not Alice's match (mutual gender rule)",
      ID["gita"] not in match_ids(call(alice, "GET", "/api/matches")))
call(gita, "PUT", "/api/preferences", prefs("Female"))
check("Gita restored -> she is back", ID["gita"] in match_ids(call(alice, "GET", "/api/matches")))

# ----------------------------------------------------------------------------- 8. Phase 5 consent still rules
print("\nTest 8: Phase 5 consent controls what is explained")
check("Alice can not read Bina's preferences yet (403)", view(alice, ID["bina"]).status_code == 403)
r = call(alice, "POST", "/api/requests", {"receiver_id": ID["bina"]})
check("the existing request endpoint works for the real request button (201)", r.status_code == 201)
req_ab = r.json["request"]["id"]
check("a repeated request for the same active pair is rejected (409)",
      call(alice, "POST", "/api/requests", {"receiver_id": ID["bina"]}).status_code == 409)
check("the other student cannot create a reverse duplicate while it is pending (409)",
      call(bina, "POST", "/api/requests", {"receiver_id": ID["alice"]}).status_code == 409)
check("match detail reflects the real pending request state",
      call(alice, "GET", f"/api/matches/{ID['bina']}").json["match"]["request"]
      == {"request_id": req_ab, "status": "pending", "direction": "sent"})
card = find(call(alice, "GET", "/api/matches"), ID["bina"])
check("the card shows the pending request that Alice sent",
      card["request"] == {"request_id": req_ab, "status": "pending", "direction": "sent"})
card_bina_side = find(call(bina, "GET", "/api/matches"), ID["alice"])
check("Bina sees it as received", card_bina_side["request"]["direction"] == "received"
      and card_bina_side["request"]["status"] == "pending")
check("PENDING grants nothing: still the essentials sentence only",
      card["reasons"] == [ESSENTIALS] and card["can_view_shared_preferences"] is False)
check("PENDING grants nothing: shared-preferences still 403", view(alice, ID["bina"]).status_code == 403)

check("Bina accepts and shares ONLY her sleep schedule",
      call(bina, "PUT", f"/api/requests/{req_ab}/accept", {"share_fields": ["sleep_schedule"]}).status_code == 200)
check("the roommate-gender preference can NOT be shared (it is not a Phase 5 shareable field) -> 400",
      call(bina, "PUT", f"/api/requests/{req_ab}/sharing", {"fields": ["preferred_roommate_gender"]}).status_code == 400)
check("and that refused attempt did not change what Bina shares",
      view(alice, ID["bina"]).json["preferences"] == {"sleep_schedule": "Early Sleeper"})
r = call(alice, "GET", "/api/matches")
card = find(r, ID["bina"])
check("now Alice's card for Bina mentions sleep (and only sleep)",
      card["reasons"] == [ESSENTIALS, "Sleeping schedules look compatible."] and card["differences"] == [])
check("card says shared preferences can be viewed", card["can_view_shared_preferences"] is True)
check("request state is accepted", card["request"]["status"] == "accepted")
check("the response STILL leaks no private value", all(word not in r.get_data(as_text=True) for word in LEAK_WORDS))
check("Phase 5 endpoint returns exactly the one shared field",
      view(alice, ID["bina"]).json["preferences"] == {"sleep_schedule": "Early Sleeper"})
check("accepting did NOT unlock Bina's other preferences for Alice",
      set(view(alice, ID["bina"]).json["preferences"].keys()) == {"sleep_schedule"})
check("Bina shared nothing about Alice's side: Bina's card for Alice has no per-preference sentences",
      find(call(bina, "GET", "/api/matches"), ID["alice"])["reasons"] == [ESSENTIALS])
check("Alice cannot see Bina's budget or area through any matches route",
      "4123" not in call(alice, "GET", f"/api/matches/{ID['bina']}").get_data(as_text=True))

print("\nTest 9: revoking sharing takes effect on the next request")
check("Bina revokes", call(bina, "PUT", f"/api/requests/{req_ab}/sharing", {"fields": []}).status_code == 200)
card = find(call(alice, "GET", "/api/matches"), ID["bina"])
check("sentence disappears and the consent flag turns off",
      card["reasons"] == [ESSENTIALS] and card["can_view_shared_preferences"] is False)
check("shared-preferences is 403 again", view(alice, ID["bina"]).status_code == 403)

print("\nTest 10: a clashing preference is reported only when it is shared")
r = call(alice, "POST", "/api/requests", {"receiver_id": ID["carol"]})
req_ac = r.json["request"]["id"]
call(carol, "PUT", f"/api/requests/{req_ac}/accept", {"share_fields": ["sleep_schedule"]})
card = find(call(alice, "GET", "/api/matches"), ID["carol"])
check("Carol (Night Owl) shared sleep -> 'may differ' is listed",
      card["differences"] == ["Sleeping schedules may differ."] and card["reasons"] == [ESSENTIALS])
check("her pet/lifestyle clashes (not shared) are NOT mentioned",
      all("Pet" not in s and "Lifestyle" not in s for s in card["reasons"] + card["differences"]))

print("\nTest 11: rejected and cancelled requests grant nothing")
r = call(alice, "POST", "/api/requests", {"receiver_id": ID["gita"]})
req_ag = r.json["request"]["id"]
check("Gita rejects", call(gita, "PUT", f"/api/requests/{req_ag}/reject").status_code == 200)
card = find(call(alice, "GET", "/api/matches"), ID["gita"])
check("rejected -> no active request on the card, no consent, essentials only",
      card["request"] is None and card["can_view_shared_preferences"] is False and card["reasons"] == [ESSENTIALS])
check("rejected -> shared-preferences 403", view(alice, ID["gita"]).status_code == 403)
r = call(alice, "POST", "/api/requests", {"receiver_id": ID["gita"]})
req_ag2 = r.json["request"]["id"]
check("Alice sends again and cancels", call(alice, "PUT", f"/api/requests/{req_ag2}/cancel").status_code == 200)
check("cancelled -> still no access", view(alice, ID["gita"]).status_code == 403
      and find(call(alice, "GET", "/api/matches"), ID["gita"])["can_view_shared_preferences"] is False)

print("\nTest 12: matching adds no new way to read private data")
paths = sorted(rule.rule for rule in app.url_map.iter_rules())
check("no user-list route exists", "/api/users" not in paths and "/api/users/" not in paths)
check("the only new routes are /api/matches and /api/matches/<id>",
      [p for p in paths if "match" in p] == ["/api/matches", "/api/matches/<int:user_id>"])
check("an unrelated student (Ivy, no preferences) can not use Alice's id to get anything",
      call(ivy, "GET", f"/api/matches?user_id={ID['alice']}").status_code == 403)

# ----------------------------------------------------------------------------- 13. Errors are safe
print("\nTest 13: server errors never leak details")
logging.disable(logging.CRITICAL)
original = app_module.build_recommendations
original_detail = app_module.build_match_detail


def boom(*args, **kwargs):
    raise RuntimeError("SECRET-DB-DETAIL /home/me/campusnest.db")


app_module.build_recommendations = boom
app_module.build_match_detail = boom
r = call(alice, "GET", "/api/matches")
text = r.get_data(as_text=True)
check("list route -> 500 with a generic message", r.status_code == 500 and r.json["success"] is False)
check("no exception text, path or traceback in the response",
      "SECRET-DB-DETAIL" not in text and "Traceback" not in text and "campusnest.db" not in text)
r = call(alice, "GET", f"/api/matches/{ID['bina']}")
check("detail route -> 500, also generic", r.status_code == 500 and "SECRET-DB-DETAIL" not in r.get_data(as_text=True))
app_module.build_recommendations = original
app_module.build_match_detail = original_detail
logging.disable(logging.NOTSET)
check("after the fault, the API works again", call(alice, "GET", "/api/matches").status_code == 200)

# ----------------------------------------------------------------------------- 14. Migration with SQLAlchemy
print("\nTest 14: the start-up schema upgrade keeps existing data")
with app.app_context():
    up_to_date_result = ensure_phase6_schema(db.engine)
check("on the up-to-date test database it does nothing", up_to_date_result is False)
legacy_path = os.path.join(TEMP_DIR, "legacy.db")
conn = sqlite3.connect(legacy_path)
conn.executescript("""
CREATE TABLE preferences (id INTEGER PRIMARY KEY, user_id INTEGER, gender VARCHAR(10), preferred_area VARCHAR(30));
INSERT INTO preferences VALUES (1, 7, 'Female', 'Dhonia');
""")
conn.commit()
conn.close()
engine = create_engine("sqlite:///" + legacy_path)
check("on a database from before Phase 6 it adds the column", ensure_phase6_schema(engine) is True)
check("a second call does nothing", ensure_phase6_schema(engine) is False)
conn = sqlite3.connect(legacy_path)
check("the old row is untouched and the new value is NULL",
      conn.execute("SELECT user_id, gender, preferred_area, preferred_roommate_gender FROM preferences").fetchall()
      == [(7, "Female", "Dhonia", None)])
conn.close()
engine.dispose()

# ----------------------------------------------------------------------------- 15. Earlier phases
print("\nTest 15: matching logic tests and Phases 1-5 still pass (running them)")
for script in ("test_matching.py", "test_phase5.py"):
    result = subprocess.run([sys.executable, os.path.join(HERE, script)], capture_output=True, text=True)
    summary = [line for line in result.stdout.splitlines() if "passed," in line]
    print("  " + script + " says:", summary[-1].strip() if summary else "(no summary line)")
    check(script + " exits with success", result.returncode == 0)
    if result.returncode != 0:
        print(result.stdout[-2500:])
        print(result.stderr[-2500:])

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
