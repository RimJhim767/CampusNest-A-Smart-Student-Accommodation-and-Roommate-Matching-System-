# CampusNest — Phase 6: turn stored preference data into a checked, immutable record.
# Bad or incomplete data is REJECTED (returns a problem code). It is never "fixed" silently.
from dataclasses import dataclass

from validation import PREFERRED_ROOMMATE_GENDERS, validate_preferences


@dataclass(frozen=True)
class PreferenceRecord:
    """Only the fields matching needs. No name, email, password or timestamp lives here."""
    user_id: int
    gender: str                      # the person's OWN gender (Preference.gender)
    preferred_roommate_gender: str   # the gender of roommate they are willing to live with
    preferred_area: str
    min_budget: int
    max_budget: int
    lifestyle_qualities: tuple
    sleep_schedule: str
    cooking_preference: str
    expense_preference: str
    guest_preference: str
    pet_preference: str


# Problem codes returned by build_record (the API turns them into friendly messages).
NO_PREFERENCES = "no_preferences"
MISSING_ROOMMATE_GENDER = "missing_roommate_gender"
INVALID_PREFERENCES = "invalid_preferences"


def build_record(user_id, data):
    """Return (PreferenceRecord, None) if `data` is complete and valid, else (None, problem_code).

    `data` is a dict shaped like Preference.to_dict() (preferred_roommate_gender may be absent).
    Phase 4's validate_preferences() is reused, so there is ONE definition of "valid"."""
    if not isinstance(data, dict):
        return None, NO_PREFERENCES

    roommate_gender = data.get("preferred_roommate_gender")
    if roommate_gender is None or roommate_gender == "":
        # Pre-Phase-6 rows end up here: they stay ineligible until the user saves again.
        return None, MISSING_ROOMMATE_GENDER
    if not isinstance(roommate_gender, str) or roommate_gender not in PREFERRED_ROOMMATE_GENDERS:
        return None, INVALID_PREFERENCES

    others = {key: value for key, value in data.items() if key != "preferred_roommate_gender"}
    clean, errors = validate_preferences(others)
    if errors:
        return None, INVALID_PREFERENCES

    record = PreferenceRecord(
        user_id=user_id,
        gender=clean["gender"],
        preferred_roommate_gender=roommate_gender,
        preferred_area=clean["preferred_area"],
        min_budget=clean["min_budget"],
        max_budget=clean["max_budget"],
        lifestyle_qualities=tuple(clean["lifestyle_qualities"]),
        sleep_schedule=clean["sleep_schedule"],
        cooking_preference=clean["cooking_preference"],
        expense_preference=clean["expense_preference"],
        guest_preference=clean["guest_preference"],
        pet_preference=clean["pet_preference"],
    )
    return record, None
