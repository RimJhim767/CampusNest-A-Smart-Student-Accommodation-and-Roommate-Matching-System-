# CampusNest — Phase 6 tests for the matching logic (no Flask, no real database).
# Run from the backend folder:   python test_matching.py
#
# What this checks: hard filtering, feature encoding, KNN ranking, explanations, the response
# shape, validation of the new field, and the database migration (on a TEMPORARY copy).
# What it does NOT check: whether recommendations are "good". No roommate-outcome data exists,
# so these tests only prove that the code does what the written rules say.
import os
import sqlite3
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from matching.engine import rank_candidates                                  # noqa: E402
from matching.features import (                                              # noqa: E402
    BLOCK_SLICES, BLOCK_WEIGHTS, BUDGET_SCALE, CATEGORICAL_BLOCKS, TOTAL_WEIGHT, VECTOR_LENGTH,
    encode_area, encode_budget, encode_categorical, encode_qualities, encode_record,
)
from matching.hard_filter import (                                           # noqa: E402
    budgets_overlap, failed_rules, hard_filter, is_eligible,
)
from matching.knn import nearest_candidates                                  # noqa: E402
from matching.records import build_record                                    # noqa: E402
from matching.response import assemble_matches                               # noqa: E402
from matching.scoring import (                                               # noqa: E402
    ESSENTIALS_REASON, band_for, explain, similarity_from_distance,
)
import migrate_phase6                                                        # noqa: E402
import validation                                                            # noqa: E402

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


def raises(function, *args):
    try:
        function(*args)
    except ValueError:
        return True
    except Exception:
        return False
    return False


BASE = {
    "gender": "Female", "preferred_roommate_gender": "Female", "preferred_area": "Dhonia",
    "min_budget": 3000, "max_budget": 5000,
    "lifestyle_qualities": ["Quiet", "Clean"], "sleep_schedule": "Early Sleeper",
    "cooking_preference": "Prefer to cook", "expense_preference": "Prefer sharing expenses",
    "guest_preference": "Prefer no/few guests", "pet_preference": "Prefer no pets",
}


def rec(user_id, **changes):
    """Build a valid PreferenceRecord from BASE with some fields changed."""
    record, problem = build_record(user_id, dict(BASE, **changes))
    assert record is not None, problem
    return record


# ---------------------------------------------------------------- A. hard matching
print("\nA1: mutually compatible genders + same area + overlapping budget -> eligible")
me = rec(1)
check("female/wants-female with female/wants-female passes", is_eligible(me, rec(2)))
check("female wants male + male wants female passes (own gender is not roommate gender)",
      is_eligible(rec(1, gender="Female", preferred_roommate_gender="Male"),
                  rec(2, gender="Male", preferred_roommate_gender="Female")))

print("\nA2: gender-incompatible pairs are excluded")
male_wants_female = rec(2, gender="Male", preferred_roommate_gender="Female")
check("female wants female, male candidate -> excluded", not is_eligible(me, male_wants_female))
check("failure is reported as 'gender' only", failed_rules(me, male_wants_female) == ["gender"])
one_way = rec(3, gender="Male", preferred_roommate_gender="Male")
check("A accepts B's gender but B refuses A's gender -> excluded (rule is mutual)",
      not is_eligible(rec(1, gender="Female", preferred_roommate_gender="Male"), one_way))
check("and the other direction too",
      not is_eligible(one_way, rec(1, gender="Female", preferred_roommate_gender="Male")))

print("\nA3: different preferred areas are excluded")
other_area = rec(2, preferred_area="Niribili")
check("Dhonia vs Niribili -> excluded", not is_eligible(me, other_area))
check("failure is reported as 'area' only", failed_rules(me, other_area) == ["area"])

print("\nA4/A5: budget overlap rule")
check("[3000,5000] vs [6000,8000] do not overlap", not budgets_overlap(3000, 5000, 6000, 8000))
check("[3000,4000] vs [4000,5000] touch at 4000 -> overlap (equal endpoints are valid)",
      budgets_overlap(3000, 4000, 4000, 5000))
check("touching works in the other order", budgets_overlap(4000, 5000, 3000, 4000))
check("[3000,3999] vs [4000,5000] do not overlap (one taka apart)",
      not budgets_overlap(3000, 3999, 4000, 5000))
check("a single-point budget inside a range overlaps", budgets_overlap(4000, 4000, 3000, 5000))
check("one range fully inside another overlaps", budgets_overlap(3000, 9000, 4000, 5000))
no_budget_overlap = rec(2, min_budget=6000, max_budget=8000)
check("pair with non-overlapping budgets is excluded", not is_eligible(me, no_budget_overlap))
check("failure is reported as 'budget' only", failed_rules(me, no_budget_overlap) == ["budget"])

print("\nA6: you are never your own roommate")
check("same user id is excluded even though every rule would pass", not is_eligible(me, rec(1)))
check("hard_filter removes the user from their own candidate list",
      [c.user_id for c in hard_filter(me, [rec(1), rec(2)])] == [2])
check("rank_candidates never returns the user",
      [m.user_id for m in rank_candidates(me, [rec(1), rec(2)])] == [2])

print("\nA7: no candidates -> empty result, no exception")
check("empty candidate list -> []", rank_candidates(me, []) == [])
check("only ineligible candidates -> []", rank_candidates(me, [other_area, male_wants_female]) == [])

print("\nA8: other preferences are NOT hard rules")
very_different = rec(2, lifestyle_qualities=["Social"], sleep_schedule="Night Owl",
                     cooking_preference="Prefer not to cook", expense_preference="Prefer separate expenses",
                     guest_preference="Frequent guests are okay", pet_preference="Pet-friendly")
check("opposite sleep/cooking/expenses/guests/pets/qualities still eligible", is_eligible(me, very_different))
check("and still appears in the ranking (it is ranked last, not removed)",
      [m.user_id for m in rank_candidates(me, [very_different])] == [2])

# ---------------------------------------------------------------- B. records / validation
print("\nB-records: invalid or missing data is rejected, never silently fixed")
check("valid data builds a record", build_record(1, BASE)[0] is not None)
check("None -> no_preferences", build_record(1, None) == (None, "no_preferences"))
legacy = {k: v for k, v in BASE.items() if k != "preferred_roommate_gender"}
check("pre-Phase-6 row (no roommate gender) -> missing_roommate_gender, so NOT eligible",
      build_record(1, legacy) == (None, "missing_roommate_gender"))
check("roommate gender None -> missing", build_record(1, dict(BASE, preferred_roommate_gender=None))[1]
      == "missing_roommate_gender")
check("roommate gender 'Other' -> invalid", build_record(1, dict(BASE, preferred_roommate_gender="Other"))[1]
      == "invalid_preferences")
check("max below min -> invalid", build_record(1, dict(BASE, min_budget=5000, max_budget=3000))[1]
      == "invalid_preferences")
check("negative budget -> invalid", build_record(1, dict(BASE, min_budget=-1))[1] == "invalid_preferences")
check("boolean budget -> invalid", build_record(1, dict(BASE, min_budget=True))[1] == "invalid_preferences")
check("unknown area -> invalid", build_record(1, dict(BASE, preferred_area="Mars"))[1] == "invalid_preferences")
check("unknown sleep value -> invalid", build_record(1, dict(BASE, sleep_schedule="Insomniac"))[1]
      == "invalid_preferences")
check("empty qualities -> invalid", build_record(1, dict(BASE, lifestyle_qualities=[]))[1]
      == "invalid_preferences")
check("unknown quality -> invalid", build_record(1, dict(BASE, lifestyle_qualities=["Loud"]))[1]
      == "invalid_preferences")

print("\nB-validation: the new field is optional and does not disturb Phase 4/5")
clean, errors = validation.validate_preferences(legacy)
check("a payload WITHOUT the new field is still valid (old clients/tests keep working)",
      not errors and "preferred_roommate_gender" not in clean)
clean, errors = validation.validate_preferences(BASE)
check("a payload WITH a valid value is accepted", not errors and clean["preferred_roommate_gender"] == "Female")
check("an invalid value is rejected",
      "preferred_roommate_gender" in validation.validate_preferences(dict(BASE, preferred_roommate_gender="Alien"))[1])
check("Phase 5 shareable-field list is unchanged (still the original 10 fields)",
      len(validation.PREFERENCE_FIELD_ORDER) == 10 and len(validation.PREFERENCE_KEYS) == 10
      and "preferred_roommate_gender" not in validation.PREFERENCE_KEYS)
check("the form may SEND the new field", "preferred_roommate_gender" in validation.PREFERENCE_WRITE_KEYS)
check("allowed roommate genders are the survey options", validation.PREFERRED_ROOMMATE_GENDERS == ["Female", "Male"])

# ---------------------------------------------------------------- C. features
print("\nB1: the encoder handles every allowed category")
ok = True
for block, (field, specific, neutral) in CATEGORICAL_BLOCKS.items():
    for answer in specific + [neutral]:
        vector = encode_categorical(answer, specific, neutral)
        ok = ok and len(vector) == len(specific)
check("every specific and neutral answer of every categorical block encodes", ok)
ok = all(len(encode_record(rec(1, **{field: answer}))) == VECTOR_LENGTH
         for block, (field, specific, neutral) in CATEGORICAL_BLOCKS.items()
         for answer in specific + [neutral])
check("every allowed value gives a vector of the same length", ok)
check("every allowed area encodes", all(encode_area(a).sum() == 1.0 for a in validation.AREAS))
check("every allowed value comes from validation.py (no category missing)",
      all(sorted(spec[1] + [spec[2]]) == sorted(getattr(validation, name))
          for spec, name in [(CATEGORICAL_BLOCKS["sleep"], "SLEEP_SCHEDULES"),
                             (CATEGORICAL_BLOCKS["cooking"], "COOKING_PREFERENCES"),
                             (CATEGORICAL_BLOCKS["expenses"], "EXPENSE_PREFERENCES"),
                             (CATEGORICAL_BLOCKS["guests"], "GUEST_PREFERENCES"),
                             (CATEGORICAL_BLOCKS["pets"], "PET_PREFERENCES")]))
check("an unknown category raises ValueError", raises(encode_categorical, "Insomniac", ["A", "B"], "C"))
check("an unknown area raises ValueError", raises(encode_area, "Mars"))
check("nominal answers are one-hot (exactly one 1)",
      list(encode_categorical("Night Owl", ["Early Sleeper", "Night Owl"], "Flexible")) == [0.0, 1.0])
check("neutral answer is spread evenly (sits between the specific answers)",
      list(encode_categorical("Flexible", ["Early Sleeper", "Night Owl"], "Flexible")) == [0.5, 0.5])

print("\nB2: lifestyle qualities are multi-hot")
v = encode_qualities(["Quiet", "Clean"])
order = validation.LIFESTYLE_QUALITIES
check("non-zero exactly at the chosen qualities",
      [order[i] for i in range(len(order)) if v[i] > 0] == ["Quiet", "Clean"])
check("chosen entries are equal, the rest are 0", v[0] == v[1] and all(x == 0 for x in v[2:]))
check("vector is scaled to length 1", abs(np.linalg.norm(v) - 1.0) < 1e-12)
check("choosing all five qualities works", abs(np.linalg.norm(encode_qualities(order)) - 1.0) < 1e-12)
check("no qualities raises ValueError", raises(encode_qualities, []))
check("an unknown quality raises ValueError", raises(encode_qualities, ["Loud"]))
check("order of choosing does not matter", list(encode_qualities(["Clean", "Quiet"])) == list(v))

print("\nB3: budgets are scaled consistently")
check("budget is divided by the fixed scale", list(encode_budget(3000, 5000)) == [0.3, 0.5])
check("the scale is a fixed number, not learned from users", BUDGET_SCALE == 10000.0)
check("budget above the scale is clipped to 1.0", list(encode_budget(9000, 50000)) == [0.9, 1.0])
check("same budget -> same numbers every time", list(encode_budget(4000, 4000)) == list(encode_budget(4000, 4000)))
check("max below min raises ValueError", raises(encode_budget, 5000, 3000))
check("negative raises ValueError", raises(encode_budget, -1, 3000))
check("text raises ValueError", raises(encode_budget, "abc", 3000))
check("boolean raises ValueError", raises(encode_budget, True, 3000))

print("\nB-distance: squared distance = sum of weight x block difference")
early, night = rec(1, sleep_schedule="Early Sleeper"), rec(2, sleep_schedule="Night Owl")
d2 = float(np.sum((encode_record(early) - encode_record(night)) ** 2))
check("opposite sleep schedules (everything else equal) cost exactly the sleep weight",
      abs(d2 - BLOCK_WEIGHTS["sleep"]) < 1e-9)
check("identical records have distance 0", float(np.sum((encode_record(me) - encode_record(rec(2))) ** 2)) == 0.0)
check("identical records -> similarity 1.0", similarity_from_distance(0.0) == 1.0)
check("sleep opposite -> similarity = 1 - sleep_weight / total_weight",
      abs(similarity_from_distance(d2 ** 0.5) - (1 - BLOCK_WEIGHTS["sleep"] / TOTAL_WEIGHT)) < 1e-9)
flex = rec(2, sleep_schedule="Flexible")
d_flex = float(np.sum((encode_record(early) - encode_record(flex)) ** 2))
check("'Flexible' sleep is closer to Early Sleeper than Night Owl is", 0 < d_flex < d2)
area_a, area_b = rec(1, preferred_area="Dhonia"), rec(2, preferred_area="Niribili")
check("area has weight 0, so it never changes a distance",
      BLOCK_WEIGHTS["area"] == 0.0 and np.allclose(encode_record(area_a)[BLOCK_SLICES["area"]], 0.0)
      and np.allclose(encode_record(area_a), encode_record(area_b)))
check("gender is not part of the vector (same vector for different genders)",
      np.allclose(encode_record(rec(1, gender="Female", preferred_roommate_gender="Female")),
                  encode_record(rec(1, gender="Male", preferred_roommate_gender="Male"))))
check("user id is not part of the vector", np.allclose(encode_record(rec(1)), encode_record(rec(99))))
check("bands: >= 0.80 Strong, >= 0.60 Good, else Fair",
      band_for(0.80) == "Strong" and band_for(0.7999) == "Good"
      and band_for(0.60) == "Good" and band_for(0.5999) == "Fair")

# ---------------------------------------------------------------- D. KNN ranking
print("\nB5: KNN handles zero, one, fewer than k, and invalid k")
me_vec = encode_record(me)
check("zero candidates -> []", nearest_candidates(me_vec, [], [], 10) == [])
one = nearest_candidates(me_vec, [encode_record(rec(2))], [2], 10)
check("one candidate -> that one candidate", [i for i, _ in one] == [2])
three_ids = [2, 3, 4]
three_vecs = [encode_record(rec(i)) for i in three_ids]
check("fewer candidates than k (3 < 10) -> all 3, no error",
      len(nearest_candidates(me_vec, three_vecs, three_ids, 10)) == 3)
check("k smaller than the pool is respected", len(nearest_candidates(me_vec, three_vecs, three_ids, 2)) == 2)
check("k=None means everybody", len(nearest_candidates(me_vec, three_vecs, three_ids, None)) == 3)
check("k=0 or a bad k falls back to the default instead of crashing",
      len(nearest_candidates(me_vec, three_vecs, three_ids, 0)) == 3
      and len(nearest_candidates(me_vec, three_vecs, three_ids, "x")) == 3)
check("ties are broken by user id (deterministic)",
      [i for i, _ in nearest_candidates(me_vec, three_vecs[::-1], three_ids[::-1], 10)] == [2, 3, 4])

print("\nB6: ranking on a small fixed dataset with a known order")
closest = rec(10)                                                   # identical answers
middle = rec(11, sleep_schedule="Flexible", pet_preference="No preference",
             lifestyle_qualities=["Quiet", "Clean", "Social"])      # partly similar
far = rec(12, lifestyle_qualities=["Social"], sleep_schedule="Night Owl",
          cooking_preference="Prefer not to cook", expense_preference="Prefer separate expenses",
          guest_preference="Frequent guests are okay", pet_preference="Pet-friendly",
          min_budget=5000, max_budget=9000)                         # touches at 5000, opposite otherwise
pool = [far, closest, middle]
ranked = rank_candidates(me, pool)
check("order is closest, middle, far", [m.user_id for m in ranked] == [10, 11, 12])
check("ranks are 1, 2, 3", [m.rank for m in ranked] == [1, 2, 3])
check("identical answers -> Strong band", ranked[0].band == "Strong" and ranked[0].similarity == 1.0)
check("opposite answers -> Fair band", ranked[2].band == "Fair")
check("similarity never increases down the list", ranked[0].similarity >= ranked[1].similarity >= ranked[2].similarity)
check("same input twice -> same output", [m.user_id for m in rank_candidates(me, pool)] == [10, 11, 12])
check("input order does not matter",
      [m.user_id for m in rank_candidates(me, [middle, far, closest])] == [10, 11, 12])
check("k limits the list", [m.user_id for m in rank_candidates(me, pool, k=2)] == [10, 11])

print("\nB7: changing / adding a candidate updates the result")
before = [m.user_id for m in rank_candidates(me, [middle, far])]
# user 12 re-saves preferences with answers identical to mine (budget and the rest stay as in BASE)
upgraded_far = rec(12)
after = [m.user_id for m in rank_candidates(me, [middle, upgraded_far])]
check("before: the far candidate (12) is ranked below the middle one (11)", before == [11, 12])
check("after user 12 changes to identical answers they move to first place", after == [12, 11])
check("and their band becomes Strong", rank_candidates(me, [upgraded_far])[0].band == "Strong")
check("a new eligible candidate appears", [m.user_id for m in rank_candidates(me, [closest, rec(13)])] == [10, 13])
moved = rec(10, preferred_area="Niribili")
check("a candidate who changes area disappears", [m.user_id for m in rank_candidates(me, [moved, middle])] == [11])
check("a candidate who changes budget out of range disappears",
      [m.user_id for m in rank_candidates(me, [rec(10, min_budget=9000, max_budget=9500), middle])] == [11])
check("a candidate whose roommate-gender preference changes to exclude me disappears",
      [m.user_id for m in rank_candidates(me, [rec(10, preferred_roommate_gender="Male"), middle])] == [11])

# ---------------------------------------------------------------- E. explanations and response shape
print("\nB8: explanations match the rules and respect consent")
sims_same = rank_candidates(me, [closest])[0].block_similarities
reasons, diffs = explain(sims_same, [])
check("nothing shared -> only the essentials sentence", reasons == [ESSENTIALS_REASON] and diffs == [])
reasons, diffs = explain(rank_candidates(me, [far])[0].block_similarities, [])
check("nothing shared -> still nothing about their private preferences, even when they differ a lot",
      reasons == [ESSENTIALS_REASON] and diffs == [])
reasons, diffs = explain(sims_same, ["sleep_schedule"])
check("sleep shared + compatible -> sleep sentence only",
      reasons == [ESSENTIALS_REASON, "Sleeping schedules look compatible."])
reasons, diffs = explain(rank_candidates(me, [far])[0].block_similarities, ["sleep_schedule", "pet_preference"])
check("sleep+pets shared and clashing -> two 'may differ' sentences",
      diffs == ["Sleeping schedules may differ.", "Pet preferences may differ."])
check("but cooking (not shared) is not mentioned", not any("Cooking" in d for d in diffs))
reasons, diffs = explain(rank_candidates(me, [far])[0].block_similarities,
                         ["gender", "min_budget", "max_budget", "preferred_area"])
check("sharing budget/area/gender fields adds no sentences (those are never explained)",
      reasons == [ESSENTIALS_REASON] and diffs == [])
check("explain() tolerates None for authorized fields", explain(sims_same, None)[0] == [ESSENTIALS_REASON])

print("\nResponse shape and privacy of the API payload")
infos = [{"record": c, "first_name": "Sam", "department": "Textile Engineering", "year": "2nd Year"}
         for c in (closest, far)]
matches = assemble_matches(me, infos, lambda uid: ["sleep_schedule"] if uid == 10 else [],
                           lambda uid: {"request_id": 5, "status": "pending", "direction": "sent"} if uid == 12 else None)
allowed_keys = {"user_id", "rank", "first_name", "department", "year", "compatibility_band",
                "reasons", "differences", "can_view_shared_preferences", "request"}
check("each match has exactly the allowed keys", all(set(m.keys()) == allowed_keys for m in matches))
text = repr(matches).lower()
check("no private data or numeric score appears anywhere in the payload",
      not any(word in text for word in ["min_budget", "max_budget", "dhonia", "similarity", "@", "email",
                                        "password", "pet_preference", "5000", "3000", "9000"]))
check("consent flag is true only for the student who shared something",
      [m["can_view_shared_preferences"] for m in matches] == [True, False])
check("the student who shared sleep gets the sleep sentence; the other does not",
      "Sleeping schedules look compatible." in matches[0]["reasons"] and matches[1]["reasons"] == [ESSENTIALS_REASON])
check("request state is passed through", matches[1]["request"] == {"request_id": 5, "status": "pending", "direction": "sent"}
      and matches[0]["request"] is None)
check("empty pool -> empty list", assemble_matches(me, [], lambda u: [], lambda u: None) == [])

# ---------------------------------------------------------------- F. migration (on a TEMPORARY database)
print("\nMigration: preserves existing data, never resets")
tmp = tempfile.mkdtemp()
db_path = os.path.join(tmp, "campusnest.db")
conn = sqlite3.connect(db_path)
conn.executescript("""
CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(100), email VARCHAR(120), password_hash VARCHAR(255));
CREATE TABLE preferences (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, gender VARCHAR(10),
    preferred_area VARCHAR(30), min_budget INTEGER, max_budget INTEGER, lifestyle_qualities JSON,
    sleep_schedule VARCHAR(20), cooking_preference VARCHAR(30), expense_preference VARCHAR(40),
    guest_preference VARCHAR(40), pet_preference VARCHAR(30));
INSERT INTO users VALUES (1, 'Old User', 'old@niter.edu.bd', 'hash1'), (2, 'Other Old', 'o2@niter.edu.bd', 'hash2');
INSERT INTO preferences VALUES (1, 1, 'Female', 'Dhonia', 3000, 5000, '["Quiet"]', 'Flexible', 'No preference', 'Flexible', 'Flexible', 'No preference');
INSERT INTO preferences VALUES (2, 2, 'Male', 'Jalalabad', 4000, 7000, '["Social"]', 'Night Owl', 'Prefer to cook', 'Flexible', 'Flexible', 'Pet-friendly');
""")
conn.commit()
conn.close()
result = migrate_phase6.migrate(db_path)
check("migration reports it added the column", result["added"] is True)
check("a timestamped backup file was created", result["backup"] and os.path.exists(result["backup"]))
conn = sqlite3.connect(db_path)
cols = [r[1] for r in conn.execute("PRAGMA table_info(preferences)")]
check("new column exists", "preferred_roommate_gender" in cols)
check("both users still exist", conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2)
check("both preference rows still exist", conn.execute("SELECT COUNT(*) FROM preferences").fetchone()[0] == 2)
row = conn.execute("SELECT gender, preferred_area, min_budget, max_budget, lifestyle_qualities, pet_preference "
                   "FROM preferences WHERE user_id=2").fetchone()
check("old values are untouched", row == ("Male", "Jalalabad", 4000, 7000, '["Social"]', "Pet-friendly"))
check("existing users' new value is NULL (so they stay ineligible)",
      conn.execute("SELECT COUNT(*) FROM preferences WHERE preferred_roommate_gender IS NOT NULL").fetchone()[0] == 0)
check("passwords untouched", conn.execute("SELECT password_hash FROM users WHERE id=1").fetchone()[0] == "hash1")
conn.close()
second = migrate_phase6.migrate(db_path)
check("running it a second time changes nothing (idempotent)", second["added"] is False)
check("and makes no needless second backup, and never overwrites the first",
      second["backup"] is None and os.path.exists(result["backup"]))
backup = sqlite3.connect(result["backup"])
check("the backup still has the ORIGINAL schema (no new column)",
      "preferred_roommate_gender" not in [r[1] for r in backup.execute("PRAGMA table_info(preferences)")])
backup.close()
try:
    migrate_phase6.migrate(os.path.join(tmp, "nope.db"))
    check("missing database raises FileNotFoundError", False)
except FileNotFoundError:
    check("missing database raises FileNotFoundError (and does not create one)",
          not os.path.exists(os.path.join(tmp, "nope.db")))

print("\n%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
