# CampusNest — Phase 5 backend: roommate requests + consent-based preference sharing
import os
import re
from functools import wraps

from flask import Flask, g, jsonify, request, send_from_directory, session
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from models import (
    db, User, Profile, Preference, RoommateRequest, PreferenceShare, WhatsAppShare,
    STATUS_PENDING, STATUS_ACCEPTED, STATUS_REJECTED, STATUS_CANCELLED,
    make_pair_key, utc_now,
)
from permissions import (
    find_active_request, get_authorized_fields, get_authorized_whatsapp_share,
    get_share_fields, get_whatsapp_share,
)
from matching.service import build_match_detail, build_recommendations   # Phase 6
from migrate_phase6 import ensure_phase6_schema                          # Phase 6
from validation import (
    PREFERENCE_KEYS, PREFERENCE_WRITE_KEYS, PROFILE_KEYS,
    find_protected_keys, find_unknown_keys,
    normalize_whatsapp_number, parse_user_id, validate_field_list,
    validate_preferences, validate_profile,
)

# ---------- Paths ----------
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
DATABASE_DIR = os.path.join(BACKEND_DIR, "database")
DATABASE_PATH = os.path.join(DATABASE_DIR, "campusnest.db")

os.makedirs(DATABASE_DIR, exist_ok=True)

# ---------- App setup ----------
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
# CAMPUSNEST_DB_URI is only used by test_phase4.py so tests never touch your real database.
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "CAMPUSNEST_DB_URI", "sqlite:///" + DATABASE_PATH
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# The secret key is used to sign the session cookie so nobody can fake it.
# For this project the fallback below is fine. For a real launch, set a
# long random SECRET_KEY environment variable and never share it.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-secret")
app.config["SESSION_COOKIE_HTTPONLY"] = True    # JavaScript cannot read the cookie
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"   # basic protection against cross-site requests

db.init_app(app)

with app.app_context():
    db.create_all()
    # Phase 6: an existing database gets the one new (empty) column added. Additive only: no row
    # is changed or removed. For a backup first, run `python migrate_phase6.py` (see docs).
    ensure_phase6_schema(db.engine)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- Login check (reusable) ----------
def get_current_user():
    """Return the logged-in User, or None.
    The session only stores the user's id; we look the user up in the database."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    user = db.session.get(User, user_id)
    if user is None:
        # The account no longer exists, so the session is stale.
        session.clear()
    return user


def login_required(view):
    """Put @login_required under @app.route to protect an API route.
    Logged-out visitors get a 401 JSON response instead of the data."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"success": False, "message": "Please log in first."}), 401
        g.user = user
        return view(*args, **kwargs)
    return wrapped


# ---------- Pages ----------
@app.route("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")


# ---------- API: register ----------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid request."}), 400

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or ""

    errors = {}
    if not name:
        errors["name"] = "Please enter your full name."
    if not email:
        errors["email"] = "Please enter your NITER email."
    elif not EMAIL_PATTERN.match(email):
        errors["email"] = "Please enter a valid email address."
    if len(password) < 6:
        errors["password"] = "Password must be at least 6 characters."
    if confirm_password != password or not confirm_password:
        errors["confirm_password"] = "Passwords do not match."

    if errors:
        return jsonify({
            "success": False,
            "message": "Please fix the highlighted fields.",
            "errors": errors,
        }), 400

    if User.query.filter_by(email=email).first():
        return jsonify({
            "success": False,
            "message": "An account with this email already exists.",
            "errors": {"email": "This email is already registered."},
        }), 409

    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "An account with this email already exists.",
            "errors": {"email": "This email is already registered."},
        }), 409

    return jsonify({"success": True, "message": "Account created successfully!"}), 201


# ---------- API: login ----------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid request."}), 400

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    errors = {}
    if not email:
        errors["email"] = "Please enter your NITER email."
    if not password:
        errors["password"] = "Please enter your password."
    if errors:
        return jsonify({
            "success": False,
            "message": "Please fill in both fields.",
            "errors": errors,
        }), 400

    user = User.query.filter_by(email=email).first()

    # Same message for "no such email" and "wrong password", so nobody can
    # use the login form to find out which emails are registered.
    if user is None or not check_password_hash(user.password_hash, password):
        return jsonify({"success": False, "message": "Incorrect email or password."}), 401

    session.clear()                 # start from a fresh session
    session["user_id"] = user.id    # this line is what "logs the user in"

    return jsonify({
        "success": True,
        "message": "Welcome back!",
        "user": {"id": user.id, "name": user.name, "email": user.email},
    }), 200


# ---------- API: logout ----------
@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "You have been logged out."}), 200


# ---------- API: current user ----------
@app.route("/api/me", methods=["GET"])
@login_required
def me():
    user = g.user
    return jsonify({
        "success": True,
        "user": {"id": user.id, "name": user.name, "email": user.email},
    }), 200


# ---------- Small helpers for the Phase 4 routes ----------
def get_json_dict():
    """Return the JSON body as a dict, or None.
    request.get_json(silent=True) returns None for bad JSON AND for requests whose
    Content-Type is not application/json. Browsers cannot send application/json
    from another website without permission (CORS), so this also gives basic
    CSRF protection on top of SameSite=Lax cookies."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def reject_bad_body(data, allowed_keys):
    """Return an error response if the body is unusable, otherwise None."""
    if data is None:
        return jsonify({"success": False, "message": "Invalid request."}), 400

    protected = find_protected_keys(data)
    if protected:
        # The client tried to name an owner / change credentials.
        return jsonify({
            "success": False,
            "message": "You can only change your own data. These fields cannot be set: "
                       + ", ".join(protected) + ".",
        }), 403

    unknown = find_unknown_keys(data, allowed_keys)
    if unknown:
        return jsonify({
            "success": False,
            "message": "Unknown field(s): " + ", ".join(unknown) + ".",
        }), 400
    return None


def foreign_user_id_requested():
    """True if the query string names a different user (?user_id=2).
    We NEVER use such a parameter to pick whose data to return; we only use the
    session. A different id is treated as an attempt to read someone else's data."""
    for key in ("user_id", "id", "owner_id"):
        value = request.args.get(key)
        if value is not None and value != str(g.user.id):
            return True
    return False


def forbidden_response():
    return jsonify({"success": False, "message": "You can only access your own data."}), 403


# ---------- API: profile (owner only) ----------
@app.route("/api/profile", methods=["GET"])
@login_required
def get_profile():
    if foreign_user_id_requested():
        return forbidden_response()
    return jsonify({"success": True, "profile": g.user.profile_dict()}), 200


@app.route("/api/profile", methods=["PUT"])
@login_required
def update_profile():
    data = get_json_dict()
    bad = reject_bad_body(data, PROFILE_KEYS)
    if bad:
        return bad

    clean, errors = validate_profile(data)
    if errors:
        return jsonify({
            "success": False,
            "message": "Please fix the highlighted fields.",
            "errors": errors,
        }), 400

    user = g.user                      # the owner comes from the session, never from the request
    user.name = clean["full_name"]
    profile = user.profile
    if profile is None:
        profile = Profile(user_id=user.id)
        db.session.add(profile)
    profile.department = clean["department"]
    profile.year = clean["year"]
    profile.gender = clean["gender"]
    profile.area = clean["area"]
    profile.budget = clean["budget"]
    profile.about = clean["about"]

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Could not save your profile. Please try again."}), 409

    return jsonify({
        "success": True,
        "message": "Profile saved!",
        "profile": user.profile_dict(),
    }), 200


# ---------- API: PRIVATE roommate preferences (owner only) ----------
@app.route("/api/preferences", methods=["GET"])
@login_required
def get_preferences():
    if foreign_user_id_requested():
        return forbidden_response()

    pref = g.user.preference           # the logged-in user's own record only
    if pref is None:
        return jsonify({"success": True, "has_preferences": False, "preferences": None}), 200
    return jsonify({"success": True, "has_preferences": True, "preferences": pref.to_dict()}), 200


@app.route("/api/preferences", methods=["PUT"])
@login_required
def update_preferences():
    data = get_json_dict()
    bad = reject_bad_body(data, PREFERENCE_WRITE_KEYS)      # Phase 6: includes the new field
    if bad:
        return bad

    clean, errors = validate_preferences(data)
    if errors:
        return jsonify({
            "success": False,
            "message": "Please fix the highlighted fields.",
            "errors": errors,
        }), 400

    user = g.user                      # owner = logged-in user, always
    pref = user.preference
    created = pref is None
    if created:
        pref = Preference(user_id=user.id)
        db.session.add(pref)

    pref.gender = clean["gender"]
    pref.preferred_area = clean["preferred_area"]
    pref.min_budget = clean["min_budget"]
    pref.max_budget = clean["max_budget"]
    pref.lifestyle_qualities = clean["lifestyle_qualities"]
    pref.sleep_schedule = clean["sleep_schedule"]
    pref.cooking_preference = clean["cooking_preference"]
    pref.expense_preference = clean["expense_preference"]
    pref.guest_preference = clean["guest_preference"]
    pref.pet_preference = clean["pet_preference"]
    # Phase 6: only changed when the client sent it. If it was not sent, the old value stays.
    if "preferred_roommate_gender" in clean:
        pref.preferred_roommate_gender = clean["preferred_roommate_gender"]

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Could not save your preferences. Please try again."}), 409

    return jsonify({
        "success": True,
        "message": "Preferences saved!",
        "preferences": pref.to_dict(),
    }), (201 if created else 200)


# =====================================================================
# Phase 5: roommate requests + consent-based preference sharing
# =====================================================================

def get_optional_json_dict():
    """Like get_json_dict(), but an empty body is fine and means {}.
    Used by accept / reject / cancel, which may be sent with no body at all."""
    if not request.get_data().strip():
        return {}
    return get_json_dict()


def not_found_request_response():
    return jsonify({"success": False, "message": "Request not found."}), 404


def load_my_request(request_id):
    """Return the request only if the logged-in user is the requester or the receiver.
    Anyone else gets None, so request ids of other people's requests look like they do not exist."""
    req = db.session.get(RoommateRequest, request_id)
    if req is None or g.user.id not in (req.requester_id, req.receiver_id):
        return None
    return req


def change_status(request_id, from_status, to_status):
    """Move a request from one status to another in ONE atomic database step.
    It only works if the request is STILL in from_status, so two people clicking at the
    same moment cannot both succeed. Returns True if this call made the change.
    The caller must commit (or roll back) afterwards."""
    changed = (RoommateRequest.query
               .filter_by(id=request_id, status=from_status)
               .update({"status": to_status, "updated_at": utc_now()},
                       synchronize_session=False))
    return changed == 1


def request_to_dict(req, me_id):
    """What the browser may know about a request: who, state, and sharing status.
    Only the OTHER person's id and name are included - no email, profile or preferences."""
    other_id = req.receiver_id if req.requester_id == me_id else req.requester_id
    other = db.session.get(User, other_id)
    is_accepted = (req.status == STATUS_ACCEPTED)
    own_whatsapp_share = get_whatsapp_share(req.id, me_id) if is_accepted else None
    other_whatsapp_share = get_whatsapp_share(req.id, other_id) if is_accepted else None
    return {
        "id": req.id,
        "status": req.status,
        "direction": "sent" if req.requester_id == me_id else "received",
        "other_user": {"id": other_id, "name": other.name if other else "Unknown student"},
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "updated_at": req.updated_at.isoformat() if req.updated_at else None,
        # fields I currently share with them / whether they share anything with me
        "i_share": get_share_fields(req.id, me_id) if is_accepted else [],
        "they_share": bool(get_share_fields(req.id, other_id)) if is_accepted else False,
        "i_share_whatsapp": own_whatsapp_share is not None,
        "they_share_whatsapp": other_whatsapp_share is not None,
    }


# ---------- API: send a request ----------
@app.route("/api/requests", methods=["POST"])
@login_required
def send_request():
    data = get_json_dict()
    bad = reject_bad_body(data, {"receiver_id"})
    if bad:
        return bad

    receiver_id = parse_user_id(data.get("receiver_id"))
    if receiver_id is None:
        return jsonify({
            "success": False,
            "message": "Please enter a valid student ID.",
            "errors": {"receiver_id": "Enter the student ID as a whole number, 1 or higher."},
        }), 400

    me = g.user                        # the requester is ALWAYS the logged-in user
    if receiver_id == me.id:
        return jsonify({"success": False, "message": "You cannot send a request to yourself."}), 400

    if db.session.get(User, receiver_id) is None:
        return jsonify({"success": False, "message": "That student was not found."}), 404

    # Re-request policy: only ONE active (pending/accepted) request per pair, in either
    # direction. After a rejection or a cancellation a new request may be sent.
    existing = find_active_request(me.id, receiver_id)
    if existing is not None:
        if existing.status == STATUS_ACCEPTED:
            message = "You are already connected with this student."
        elif existing.requester_id == me.id:
            message = "You already sent this student a request."
        else:
            message = "This student already sent you a request. Check your received requests."
        return jsonify({"success": False, "message": message}), 409

    req = RoommateRequest(requester_id=me.id, receiver_id=receiver_id,
                          status=STATUS_PENDING, pair_key=make_pair_key(me.id, receiver_id))
    db.session.add(req)
    try:
        db.session.commit()
    except IntegrityError:
        # The database itself refused a second active request (e.g. a double click).
        db.session.rollback()
        return jsonify({"success": False, "message": "A request between you already exists."}), 409

    return jsonify({
        "success": True,
        "message": "Roommate request sent!",
        "request": request_to_dict(req, me.id),
    }), 201


# ---------- API: my received / sent requests ----------
@app.route("/api/requests/received", methods=["GET"])
@login_required
def received_requests():
    if foreign_user_id_requested():
        return forbidden_response()
    rows = (RoommateRequest.query.filter_by(receiver_id=g.user.id)
            .order_by(RoommateRequest.id.desc()).all())
    return jsonify({"success": True, "requests": [request_to_dict(r, g.user.id) for r in rows]}), 200


@app.route("/api/requests/sent", methods=["GET"])
@login_required
def sent_requests():
    if foreign_user_id_requested():
        return forbidden_response()
    rows = (RoommateRequest.query.filter_by(requester_id=g.user.id)
            .order_by(RoommateRequest.id.desc()).all())
    return jsonify({"success": True, "requests": [request_to_dict(r, g.user.id) for r in rows]}), 200


# ---------- API: accept (receiver only) ----------
@app.route("/api/requests/<int:request_id>/accept", methods=["PUT"])
@login_required
def accept_request(request_id):
    data = get_optional_json_dict()
    bad = reject_bad_body(data, {"share_fields", "share_whatsapp", "phone_number"})
    if bad:
        return bad

    req = load_my_request(request_id)
    if req is None:
        return not_found_request_response()
    if req.receiver_id != g.user.id:
        return jsonify({"success": False,
                        "message": "Only the student who received a request can accept it."}), 403

    # Accepting does NOT share anything by itself. The receiver chooses the fields here;
    # no share_fields (or an empty list) means "accept, but share nothing yet".
    share_fields = []
    if "share_fields" in data:
        share_fields, error = validate_field_list(data["share_fields"])
        if error:
            return jsonify({"success": False, "message": error,
                            "errors": {"share_fields": error}}), 400

    share_whatsapp = data.get("share_whatsapp", False)
    if not isinstance(share_whatsapp, bool):
        return jsonify({"success": False,
                        "message": "WhatsApp sharing consent must be true or false."}), 400
    phone_number = None
    if share_whatsapp:
        phone_number = normalize_whatsapp_number(data.get("phone_number"))
        if phone_number is None:
            return jsonify({
                "success": False,
                "message": "Enter a valid international WhatsApp number beginning with +.",
                "errors": {"phone_number": "Use an international number with its country calling code."},
            }), 400
    elif "phone_number" in data:
        return jsonify({"success": False,
                        "message": "A WhatsApp number is accepted only when sharing is enabled."}), 400

    if req.status != STATUS_PENDING:
        return jsonify({"success": False, "message": "This request is no longer pending."}), 409

    try:
        if not change_status(req.id, STATUS_PENDING, STATUS_ACCEPTED):
            db.session.rollback()
            return jsonify({"success": False, "message": "This request is no longer pending."}), 409
        if share_fields:
            db.session.add(PreferenceShare(request_id=req.id, owner_id=g.user.id,
                                           viewer_id=req.requester_id, fields=share_fields))
        if share_whatsapp:
            db.session.add(WhatsAppShare(
                request_id=req.id, owner_id=g.user.id, viewer_id=req.requester_id,
                phone_number=phone_number))
        db.session.commit()            # status change + permission are saved together, or not at all
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Could not accept the request. Please try again."}), 409

    req = db.session.get(RoommateRequest, request_id)
    return jsonify({"success": True, "message": "Request accepted.",
                    "request": request_to_dict(req, g.user.id)}), 200


@app.route("/api/requests/<int:request_id>/whatsapp", methods=["GET", "PUT"])
@login_required
def whatsapp_contact(request_id):
    req = load_my_request(request_id)
    if req is None:
        return not_found_request_response()
    if req.status != STATUS_ACCEPTED:
        return jsonify({"success": False,
                        "message": "WhatsApp sharing is available only for accepted requests."}), 409

    if request.method == "GET":
        owner_id = req.receiver_id if req.requester_id == g.user.id else req.requester_id
        share = get_authorized_whatsapp_share(request_id, g.user.id, owner_id)
        if share is None:
            return jsonify({"success": True, "shared": False}), 200
        return jsonify({
            "success": True,
            "shared": True,
            "phone_number": share.phone_number,
        }), 200

    data = get_json_dict()
    bad = reject_bad_body(data, {"share", "phone_number"})
    if bad:
        return bad
    if "share" not in data or not isinstance(data["share"], bool):
        return jsonify({"success": False,
                        "message": "WhatsApp sharing consent must be true or false."}), 400

    share = data["share"]
    phone_number = None
    if share:
        phone_number = normalize_whatsapp_number(data.get("phone_number"))
        if phone_number is None:
            return jsonify({
                "success": False,
                "message": "Enter a valid international WhatsApp number beginning with +.",
                "errors": {"phone_number": "Use an international number with its country calling code."},
            }), 400
    elif "phone_number" in data:
        return jsonify({"success": False,
                        "message": "A WhatsApp number is accepted only when sharing is enabled."}), 400

    owner_id = g.user.id
    viewer_id = req.receiver_id if req.requester_id == owner_id else req.requester_id
    stored_share = WhatsAppShare.query.filter_by(
        request_id=req.id, owner_id=owner_id).first()
    if share:
        if stored_share is None:
            db.session.add(WhatsAppShare(
                request_id=req.id, owner_id=owner_id, viewer_id=viewer_id,
                phone_number=phone_number))
        else:
            stored_share.viewer_id = viewer_id
            stored_share.phone_number = phone_number
    elif stored_share is not None:
        db.session.delete(stored_share)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False,
                        "message": "Could not update WhatsApp sharing. Please try again."}), 409

    return jsonify({
        "success": True,
        "message": "WhatsApp sharing updated." if share else "WhatsApp sharing withdrawn.",
        "shared": share,
    }), 200


# ---------- API: reject (receiver only) ----------
@app.route("/api/requests/<int:request_id>/reject", methods=["PUT"])
@login_required
def reject_request(request_id):
    data = get_optional_json_dict()
    bad = reject_bad_body(data, set())
    if bad:
        return bad

    req = load_my_request(request_id)
    if req is None:
        return not_found_request_response()
    if req.receiver_id != g.user.id:
        return jsonify({"success": False,
                        "message": "Only the student who received a request can reject it."}), 403
    if req.status != STATUS_PENDING:
        return jsonify({"success": False, "message": "This request is no longer pending."}), 409

    if not change_status(req.id, STATUS_PENDING, STATUS_REJECTED):
        db.session.rollback()
        return jsonify({"success": False, "message": "This request is no longer pending."}), 409
    PreferenceShare.query.filter_by(request_id=req.id).delete()   # remove any permission slips
    db.session.commit()

    req = db.session.get(RoommateRequest, request_id)
    return jsonify({"success": True, "message": "Request rejected.",
                    "request": request_to_dict(req, g.user.id)}), 200


# ---------- API: cancel (requester only, pending only) ----------
@app.route("/api/requests/<int:request_id>/cancel", methods=["PUT"])
@login_required
def cancel_request(request_id):
    data = get_optional_json_dict()
    bad = reject_bad_body(data, set())
    if bad:
        return bad

    req = load_my_request(request_id)
    if req is None:
        return not_found_request_response()
    if req.requester_id != g.user.id:
        return jsonify({"success": False,
                        "message": "Only the student who sent a request can cancel it."}), 403
    if req.status != STATUS_PENDING:
        return jsonify({"success": False, "message": "Only pending requests can be cancelled."}), 409

    if not change_status(req.id, STATUS_PENDING, STATUS_CANCELLED):
        db.session.rollback()
        return jsonify({"success": False, "message": "Only pending requests can be cancelled."}), 409
    PreferenceShare.query.filter_by(request_id=req.id).delete()
    db.session.commit()

    req = db.session.get(RoommateRequest, request_id)
    return jsonify({"success": True, "message": "Request cancelled.",
                    "request": request_to_dict(req, g.user.id)}), 200


# ---------- API: choose / change / revoke what I share (either person, accepted only) ----------
@app.route("/api/requests/<int:request_id>/sharing", methods=["PUT"])
@login_required
def update_sharing(request_id):
    """The logged-in user decides which of THEIR OWN preference fields the other person
    may see. An empty list revokes sharing. Nobody can change what the other person shares."""
    data = get_json_dict()
    bad = reject_bad_body(data, {"fields"})
    if bad:
        return bad

    req = load_my_request(request_id)
    if req is None:
        return not_found_request_response()
    if req.status != STATUS_ACCEPTED:
        return jsonify({"success": False,
                        "message": "Sharing can only be changed while the request is accepted."}), 409

    if "fields" not in data:
        return jsonify({"success": False, "message": "Send the list of fields to share.",
                        "errors": {"fields": "Required."}}), 400
    fields, error = validate_field_list(data["fields"])
    if error:
        return jsonify({"success": False, "message": error, "errors": {"fields": error}}), 400

    me = g.user
    other_id = req.receiver_id if req.requester_id == me.id else req.requester_id
    share = PreferenceShare.query.filter_by(request_id=req.id, owner_id=me.id).first()

    if not fields:                                   # revoke
        if share is not None:
            db.session.delete(share)
    elif share is None:
        db.session.add(PreferenceShare(request_id=req.id, owner_id=me.id,
                                       viewer_id=other_id, fields=fields))
    else:
        share.fields = fields
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Could not update sharing. Please try again."}), 409

    return jsonify({
        "success": True,
        "message": "Sharing updated." if fields else "You stopped sharing your preferences.",
        "i_share": fields,
    }), 200


# ---------- API: view the preferences someone shared with me ----------
@app.route("/api/users/<int:user_id>/shared-preferences", methods=["GET"])
@login_required
def shared_preferences(user_id):
    """Returns ONLY the fields that user_id (the owner) chose to share with the logged-in user.

    get_authorized_fields() re-checks everything in the database on every call (see
    permissions.py). If anything is missing the answer is the same 403 - for a user who
    does not exist, for yourself, for a pending/rejected/cancelled request, and for
    sharing that was revoked - so this route cannot be used to probe who exists."""
    allowed = get_authorized_fields(g.user.id, user_id)
    if not allowed:
        return jsonify({"success": False,
                        "message": "You do not have permission to view these preferences."}), 403

    owner = db.session.get(User, user_id)
    pref = owner.preference if owner else None
    shared = {}
    if pref is not None:
        everything = pref.to_dict()
        shared = {name: everything[name] for name in allowed}    # only permitted fields

    return jsonify({
        "success": True,
        "owner": {"id": user_id, "name": owner.name},
        "shared_fields": allowed,
        "has_preferences": pref is not None,
        "preferences": shared if pref is not None else None,
    }), 200


# =====================================================================
# Phase 6: roommate recommendations (hard matching, then KNN ranking)
# The logged-in user is ALWAYS taken from the session. Nothing in the URL, query string or body
# can choose whose matches are computed. All the logic lives in the matching/ package.
# =====================================================================
def matching_failed_response():
    # No exception text or trace is ever sent to the browser.
    return jsonify({"success": False,
                    "message": "Could not load recommendations right now. Please try again."}), 500


@app.route("/api/matches", methods=["GET"])
@login_required
def list_matches():
    if foreign_user_id_requested():
        return forbidden_response()
    try:
        payload = build_recommendations(g.user)
    except Exception:
        db.session.rollback()
        app.logger.exception("Phase 6 matching failed")
        return matching_failed_response()
    return jsonify({"success": True, **payload}), 200


@app.route("/api/matches/<int:user_id>", methods=["GET"])
@login_required
def match_detail(user_id):
    """One eligible match. Anyone who is not in the logged-in user's eligible list (including
    yourself or an id that does not exist) gets the same 404, so ids cannot be probed."""
    if foreign_user_id_requested():
        return forbidden_response()
    try:
        payload = build_match_detail(g.user, user_id)
    except Exception:
        db.session.rollback()
        app.logger.exception("Phase 6 match detail failed")
        return matching_failed_response()
    if payload is None:
        return jsonify({"success": False, "message": "Match not found."}), 404
    return jsonify({"success": True, **payload}), 200


if __name__ == "__main__":
    app.run(debug=True)
