# CampusNest — Phase 5: who may see which preference fields.
# ALL privacy decisions about shared preferences are made in this one file.
from models import (
    PreferenceShare, RoommateRequest, STATUS_ACCEPTED, WhatsAppShare, make_pair_key,
)
from validation import PREFERENCE_FIELD_ORDER


def find_active_request(user_a_id, user_b_id):
    """The pending or accepted request between two students (either direction), or None."""
    return (RoommateRequest.query
            .filter(RoommateRequest.pair_key == make_pair_key(user_a_id, user_b_id),
                    RoommateRequest.status.in_(("pending", "accepted")))
            .first())


def get_authorized_fields(viewer_id, owner_id):
    """Which of owner's preference fields may viewer see right now? ([] = none)

    Every one of these must be true, checked fresh from the database on every call:
      1. viewer and owner are two different people,
      2. an ACCEPTED request exists between them (either direction),
      3. the OWNER created a share for THIS viewer on that request,
      4. that share lists at least one field.
    Nothing is read from the browser, so a client cannot fake any of it."""
    if viewer_id == owner_id:
        return []                      # your own preferences come from /api/preferences

    accepted = (RoommateRequest.query
                .filter_by(pair_key=make_pair_key(viewer_id, owner_id), status=STATUS_ACCEPTED)
                .first())
    if accepted is None:
        return []

    share = PreferenceShare.query.filter_by(
        request_id=accepted.id, owner_id=owner_id, viewer_id=viewer_id).first()
    if share is None or not share.fields:
        return []

    return [f for f in PREFERENCE_FIELD_ORDER if f in share.fields]


def get_share_fields(request_id, owner_id):
    """What the owner currently shares on this request (for showing in the UI only).
    This is NOT an authorization check - use get_authorized_fields for that."""
    share = PreferenceShare.query.filter_by(request_id=request_id, owner_id=owner_id).first()
    if share is None or not share.fields:
        return []
    return [f for f in PREFERENCE_FIELD_ORDER if f in share.fields]


def get_whatsapp_share(request_id, owner_id):
    """Return the owner's contact-share row for a request, if consent is active."""
    req = RoommateRequest.query.filter_by(
        id=request_id, status=STATUS_ACCEPTED).first()
    if req is None or owner_id not in (req.requester_id, req.receiver_id):
        return None
    return WhatsAppShare.query.filter_by(request_id=request_id, owner_id=owner_id).first()


def get_authorized_whatsapp_share(request_id, viewer_id, owner_id):
    """Return a contact share only for the other participant in an accepted request."""
    if viewer_id == owner_id:
        return None
    req = RoommateRequest.query.filter_by(
        id=request_id, status=STATUS_ACCEPTED).first()
    if req is None or {viewer_id, owner_id} != {req.requester_id, req.receiver_id}:
        return None
    return WhatsAppShare.query.filter_by(
        request_id=request_id, owner_id=owner_id, viewer_id=viewer_id).first()
