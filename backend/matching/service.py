# CampusNest — Phase 6: the ONLY matching file that reads the database.
# It loads real registered users, runs the pipeline (engine.py), and builds a response that
# contains ONLY what the logged-in student is allowed to see:
#     user id (needed for the request button), FIRST NAME, department, year, a coarse band,
#     safe reasons, and the state of any request between the two students.
# It never returns: email, exact budget, area, any preference value, or a numeric score.
# Reasons about a specific preference are added only when permissions.get_authorized_fields()
# (Phase 5, unchanged) says the other student shared that field with the viewer.
from models import db, Preference, Profile, User
from permissions import find_active_request, get_authorized_fields

from .knn import DEFAULT_K
from .records import MISSING_ROOMMATE_GENDER, NO_PREFERENCES, build_record
from .response import DISCLAIMER, MESSAGES, assemble_matches, first_name

def _relationship(me_id, other_id):
    req = find_active_request(me_id, other_id)      # pending or accepted only
    if req is None:
        return None
    return {"request_id": req.id, "status": req.status,
            "direction": "sent" if req.requester_id == me_id else "received"}


def _load_candidates(exclude_user_id):
    """Every OTHER user who has both a profile and a complete, valid preference record.
    Users with missing/invalid data are skipped (never fixed up, never counted)."""
    rows = (db.session.query(Preference, Profile, User)
            .join(User, User.id == Preference.user_id)
            .join(Profile, Profile.user_id == Preference.user_id)
            .filter(Preference.user_id != exclude_user_id)
            .all())
    candidates = []
    for pref, profile, user in rows:
        record, problem = build_record(user.id, pref.to_dict())
        if record is None:
            continue
        candidates.append({"record": record, "first_name": first_name(user.name),
                           "department": profile.department, "year": profile.year})
    return candidates


def _run(user, k):
    """Returns (status, matches). status is 'ok', 'no_matches' or a 'needs_...' code."""
    if user.profile is None:
        return "needs_profile", []
    if user.preference is None:
        return "needs_preferences", []
    me, problem = build_record(user.id, user.preference.to_dict())
    if problem == MISSING_ROOMMATE_GENDER:
        return "needs_roommate_gender", []
    if problem == NO_PREFERENCES:
        return "needs_preferences", []
    if problem:
        return "invalid_preferences", []

    matches = assemble_matches(
        me, _load_candidates(user.id),
        authorized_lookup=lambda other_id: get_authorized_fields(user.id, other_id),
        relationship_lookup=lambda other_id: _relationship(user.id, other_id),
        k=k)
    return ("ok" if matches else "no_matches"), matches


def build_recommendations(user, k=DEFAULT_K):
    """Payload for GET /api/matches (the logged-in user only)."""
    status, matches = _run(user, k)
    return {"status": status, "message": MESSAGES[status], "matches": matches,
            "disclaimer": DISCLAIMER}


def build_match_detail(user, other_user_id):
    """Payload for GET /api/matches/<id>, or None if that person is not one of this user's
    eligible matches. None is returned for 'no such user', 'yourself' and 'not eligible' alike,
    so the route cannot be used to find out who exists or why someone was excluded."""
    status, matches = _run(user, None)
    if status not in ("ok", "no_matches"):
        return {"status": status, "message": MESSAGES[status], "match": None,
                "disclaimer": DISCLAIMER}
    for match in matches:
        if match["user_id"] == other_user_id:
            return {"status": "ok", "message": "", "match": match, "disclaimer": DISCLAIMER}
    return None
