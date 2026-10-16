# CampusNest — Phase 6: build the API response from ranked results. PURE Python (no database),
# so it can be tested without Flask. See service.py for the database side.
#
# A match dict contains ONLY: user_id (needed for the request button), rank, first_name,
# department, year, compatibility_band, reasons, differences, can_view_shared_preferences and
# the state of any request. It never contains email, exact budget, area, a preference value or
# a numeric score.
from .engine import rank_candidates
from .knn import DEFAULT_K
from .scoring import explain

DISCLAIMER = ("Bands are an estimate based on the current matching rules and hand-chosen weights. "
              "They are not a prediction that you will get along, and the rules have not yet been "
              "checked against real roommate outcomes.")

MESSAGES = {
    "needs_profile": "Please complete your profile first.",
    "needs_preferences": "Please save your roommate preferences first.",
    "needs_roommate_gender": "Please choose which gender of roommate you prefer and save your preferences again.",
    "invalid_preferences": "Some of your saved preferences are incomplete. Please review and save them again.",
    "no_matches": "No students match your essential requirements right now. "
                  "Check back later as more students join.",
    "ok": "",
}


def first_name(full_name):
    parts = (full_name or "").strip().split()
    return parts[0] if parts else "Student"


def assemble_matches(me_record, candidates, authorized_lookup, relationship_lookup, k=DEFAULT_K):
    """Pure function (no database). `candidates` is a list of dicts:
         {"record": PreferenceRecord, "first_name": str, "department": str|None, "year": str|None}
    `authorized_lookup(user_id)` -> list of preference fields shared with the viewer.
    `relationship_lookup(user_id)` -> None or {"request_id", "status", "direction"}."""
    info_by_id = {c["record"].user_id: c for c in candidates}
    ranked = rank_candidates(me_record, [c["record"] for c in candidates], k)

    matches = []
    for item in ranked:
        info = info_by_id[item.user_id]
        authorized = authorized_lookup(item.user_id)
        reasons, differences = explain(item.block_similarities, authorized)
        matches.append({
            "user_id": item.user_id,
            "rank": item.rank,
            "first_name": info["first_name"],
            "department": info["department"],
            "year": info["year"],
            "compatibility_band": item.band,
            "reasons": reasons,
            "differences": differences,
            "can_view_shared_preferences": bool(authorized),
            "request": relationship_lookup(item.user_id),
        })
    return matches
