# CampusNest — database models
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

# One shared database object. app.py connects it to Flask.
db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


# The four states of a roommate request (Phase 5)
STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"
STATUS_CANCELLED = "cancelled"
REQUEST_STATUSES = (STATUS_PENDING, STATUS_ACCEPTED, STATUS_REJECTED, STATUS_CANCELLED)


def make_pair_key(user_a_id, user_b_id):
    """Same text for (3, 7) and (7, 3). Used to stop two active requests between the same two people."""
    low, high = sorted((int(user_a_id), int(user_b_id)))
    return f"{low}-{high}"


class User(db.Model):
    """One row = one registered student (Phase 2). Columns are unchanged in Phase 4.
    The relationships below only tell SQLAlchemy how the new tables connect to it;
    they do not add columns to the existing users table."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # One user has at most one profile and one set of preferences.
    profile = db.relationship("Profile", back_populates="user", uselist=False,
                              cascade="all, delete-orphan")
    preference = db.relationship("Preference", back_populates="user", uselist=False,
                                 cascade="all, delete-orphan")

    def profile_dict(self):
        """Profile data for the owner. Never includes email, password or preferences."""
        p = self.profile
        return {
            "full_name": self.name,
            "department": p.department if p else None,
            "year": p.year if p else None,
            "gender": p.gender if p else None,
            "area": p.area if p else None,
            "budget": p.budget if p else None,
            "about": p.about if p else "",
        }

    def __repr__(self):
        return f"<User {self.email}>"


class Profile(db.Model):
    """The fields of the profile page (profile.html). Full name lives in users.name."""

    __tablename__ = "profiles"

    id = db.Column(db.Integer, primary_key=True)
    # unique=True makes this one-to-one: a user can have only one profile row.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    department = db.Column(db.String(100), nullable=False)
    year = db.Column(db.String(20), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    area = db.Column(db.String(50), nullable=False)
    budget = db.Column(db.Integer, nullable=False)          # whole taka
    about = db.Column(db.Text, nullable=False, default="")

    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", back_populates="profile")


class Preference(db.Model):
    """PRIVATE roommate preferences (the 10 data fields from the Google Form).
    No route may return this to anyone except its owner."""

    __tablename__ = "preferences"
    __table_args__ = (
        db.CheckConstraint("min_budget >= 0", name="ck_pref_min_budget_nonneg"),
        db.CheckConstraint("max_budget >= min_budget", name="ck_pref_max_ge_min"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    gender = db.Column(db.String(10), nullable=False)
    preferred_area = db.Column(db.String(30), nullable=False)
    min_budget = db.Column(db.Integer, nullable=False)       # whole taka
    max_budget = db.Column(db.Integer, nullable=False)       # whole taka
    lifestyle_qualities = db.Column(db.JSON, nullable=False) # e.g. ["Quiet", "Clean"]
    sleep_schedule = db.Column(db.String(20), nullable=False)
    cooking_preference = db.Column(db.String(30), nullable=False)
    expense_preference = db.Column(db.String(40), nullable=False)
    guest_preference = db.Column(db.String(40), nullable=False)
    pet_preference = db.Column(db.String(30), nullable=False)

    # Phase 6. nullable=True ON PURPOSE: rows saved before Phase 6 have no value, and they must
    # keep existing. NULL means "not answered yet" -> that user is not eligible for matching.
    preferred_roommate_gender = db.Column(db.String(10), nullable=True)

    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", back_populates="preference")

    def to_dict(self):
        data = {
            "gender": self.gender,
            "preferred_area": self.preferred_area,
            "min_budget": self.min_budget,
            "max_budget": self.max_budget,
            "lifestyle_qualities": list(self.lifestyle_qualities or []),
            "sleep_schedule": self.sleep_schedule,
            "cooking_preference": self.cooking_preference,
            "expense_preference": self.expense_preference,
            "guest_preference": self.guest_preference,
            "pet_preference": self.pet_preference,
        }
        # Phase 6: only included once the owner has answered it. Leaving the key out (instead of
        # sending null) keeps the Phase 4/5 responses exactly as they were for everyone else.
        if self.preferred_roommate_gender:
            data["preferred_roommate_gender"] = self.preferred_roommate_gender
        return data


class RoommateRequest(db.Model):
    """One roommate request from one student (requester) to another (receiver).
    It stores ONLY who and what state - never anyone's profile or preference data."""

    __tablename__ = "roommate_requests"
    __table_args__ = (
        db.CheckConstraint("requester_id != receiver_id", name="ck_request_not_self"),
        db.CheckConstraint("status IN ('pending', 'accepted', 'rejected', 'cancelled')",
                           name="ck_request_status"),
        # At most ONE active (pending or accepted) request per pair of students, in either
        # direction. Rejected and cancelled rows are history and do not count.
        db.Index("uq_active_request_pair", "pair_key", unique=True,
                 sqlite_where=db.text("status IN ('pending', 'accepted')"),
                 postgresql_where=db.text("status IN ('pending', 'accepted')")),
    )

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    pair_key = db.Column(db.String(32), nullable=False)

    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)


class PreferenceShare(db.Model):
    """Permission slip: 'owner lets viewer see THESE preference fields'.
    Created only by the owner (when accepting a request, or later through the sharing
    endpoint). It is useless unless the linked request is still 'accepted'.
    Deleting the row (or having an empty list) removes the permission."""

    __tablename__ = "preference_shares"
    __table_args__ = (
        db.UniqueConstraint("request_id", "owner_id", name="uq_share_request_owner"),
    )

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("roommate_requests.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    viewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    fields = db.Column(db.JSON, nullable=False)     # e.g. ["preferred_area", "sleep_schedule"]

    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)


class WhatsAppShare(db.Model):
    """One owner's explicitly consented WhatsApp contact for one accepted request.

    Numbers are kept out of User/Profile and are only returned by the request-scoped
    authorization endpoint. The value is stored in normalized international digits.
    """

    __tablename__ = "whatsapp_shares"
    __table_args__ = (
        db.UniqueConstraint("request_id", "owner_id", name="uq_whatsapp_request_owner"),
        db.CheckConstraint("owner_id != viewer_id", name="ck_whatsapp_share_not_self"),
    )

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("roommate_requests.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    viewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    phone_number = db.Column(db.String(15), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
