# CampusNest — Phase 4 validation rules
# Every value the browser sends is checked here on the server.
# (Frontend checks are only for convenience — never for security.)

# ----- Roommate preferences: values taken from the Google Form -----
GENDERS = ["Female", "Male"]
# Phase 6: the gender of roommate the user is willing to live with (survey question
# "What gender roommate do you prefer?"). Same two options as the survey.
PREFERRED_ROOMMATE_GENDERS = ["Female", "Male"]
AREAS = ["Dhonia", "Niribili", "Jalalabad", "Islampur", "Nobinagar"]
LIFESTYLE_QUALITIES = ["Quiet", "Clean", "Study-friendly", "Social", "Non-smoker"]
SLEEP_SCHEDULES = ["Early Sleeper", "Flexible", "Night Owl"]
COOKING_PREFERENCES = ["Prefer to cook", "Occasionally cook", "Prefer not to cook", "No preference"]
EXPENSE_PREFERENCES = ["Prefer sharing expenses", "Prefer separate expenses", "Flexible"]
GUEST_PREFERENCES = ["Prefer no/few guests", "Occasional guests are okay",
                     "Frequent guests are okay", "Flexible"]
PET_PREFERENCES = ["Pet-friendly", "Prefer no pets", "No preference"]

# Display / storage order of the ten shareable preference fields.
PREFERENCE_FIELD_ORDER = [
    "gender", "preferred_area", "min_budget", "max_budget", "lifestyle_qualities",
    "sleep_schedule", "cooking_preference", "expense_preference",
    "guest_preference", "pet_preference",
]

PREFERENCE_KEYS = {
    "gender", "preferred_area", "min_budget", "max_budget", "lifestyle_qualities",
    "sleep_schedule", "cooking_preference", "expense_preference",
    "guest_preference", "pet_preference",
}

# Phase 6: keys the preferences form may SEND. This is PREFERENCE_KEYS plus the new field.
# PREFERENCE_KEYS itself is deliberately NOT changed: Phase 5 uses it as the list of fields a
# student may share, and the roommate-gender preference stays private to its owner.
PREFERENCE_WRITE_KEYS = PREFERENCE_KEYS | {"preferred_roommate_gender"}

# ----- Profile page: values taken from your existing profile.html -----
PROFILE_DEPARTMENTS = [
    "Computer Science & Engineering",
    "Textile Engineering",
    "Industrial & Production Engineering",
    "Electrical & Electronic Engineering",
    "Other",
]
PROFILE_YEARS = ["1st Year", "2nd Year", "3rd Year", "4th Year"]
PROFILE_GENDERS = ["Male", "Female", "Other"]
PROFILE_AREAS = AREAS   # same five areas as the Google Form / preferences page

PROFILE_KEYS = {"full_name", "department", "year", "gender", "area", "budget", "about"}

# Fields a client must never be able to set (ownership / credentials).
PROTECTED_KEYS = {"id", "user_id", "owner_id", "email", "password",
                  "password_hash", "is_admin",
                  # Phase 5: the server decides who is asking and what state a request is in
                  "requester_id", "sender_id", "viewer_id", "status", "request_id"}

MAX_BUDGET_TAKA = 1_000_000   # sanity limit for a monthly amount
MAX_ABOUT_LENGTH = 500
MAX_NAME_LENGTH = 100


def find_protected_keys(data):
    """Return the protected keys present in the request body."""
    return sorted(PROTECTED_KEYS.intersection(data.keys()))


def find_unknown_keys(data, allowed_keys):
    """Return keys in the request body that this endpoint does not accept."""
    return sorted(set(data.keys()) - set(allowed_keys))


def parse_taka(value):
    """Turn a budget into a whole number of taka, or return None if invalid.
    Accepts 5000 or "5000". Rejects negatives, decimals, text, True/False."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():
        number = int(value.strip())
    else:
        return None
    if number < 0 or number > MAX_BUDGET_TAKA:
        return None
    return number


def normalize_whatsapp_number(value):
    """Validate a user-supplied international number and return digits-only form.

    A leading plus sign is required so the application never guesses a country code.
    Common visual separators are accepted but not persisted.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.startswith("+") or text.count("+") != 1:
        return None
    if any(character not in "0123456789 +-()." for character in text):
        return None
    digits = "".join(character for character in text if character.isdigit())
    if not 8 <= len(digits) <= 15 or digits.startswith("0"):
        return None
    return digits


def _check_choice(data, key, allowed, label, clean, errors):
    value = data.get(key)
    if isinstance(value, str) and value in allowed:
        clean[key] = value
    else:
        errors[key] = "Please choose a valid option for " + label + "."


def validate_preferences(data):
    """Return (clean_data, errors). If errors is not empty, nothing should be saved."""
    clean, errors = {}, {}

    _check_choice(data, "gender", GENDERS, "gender", clean, errors)
    _check_choice(data, "preferred_area", AREAS, "preferred area", clean, errors)
    _check_choice(data, "sleep_schedule", SLEEP_SCHEDULES, "sleeping schedule", clean, errors)
    _check_choice(data, "cooking_preference", COOKING_PREFERENCES, "cooking", clean, errors)
    _check_choice(data, "expense_preference", EXPENSE_PREFERENCES, "shared expenses", clean, errors)
    _check_choice(data, "guest_preference", GUEST_PREFERENCES, "guests", clean, errors)
    _check_choice(data, "pet_preference", PET_PREFERENCES, "pets", clean, errors)

    # Phase 6 (OPTIONAL on purpose, so Phase 4/5 clients that do not know about it still work).
    # If it is sent it must be valid. If it is not sent, the stored value is left as it is,
    # and a user who has never set it simply stays ineligible for matching.
    if "preferred_roommate_gender" in data:
        _check_choice(data, "preferred_roommate_gender", PREFERRED_ROOMMATE_GENDERS,
                      "preferred roommate gender", clean, errors)

    # Multi-select: a list of allowed values, at least one, no duplicates.
    qualities = data.get("lifestyle_qualities")
    if not isinstance(qualities, list) or len(qualities) == 0:
        errors["lifestyle_qualities"] = "Select at least one roommate quality."
    elif any((not isinstance(q, str)) or q not in LIFESTYLE_QUALITIES for q in qualities):
        errors["lifestyle_qualities"] = "One or more selected qualities are not valid."
    else:
        # Save in a fixed order and without duplicates.
        clean["lifestyle_qualities"] = [q for q in LIFESTYLE_QUALITIES if q in qualities]

    budget_message = "Enter a whole amount in taka between 0 and {:,}.".format(MAX_BUDGET_TAKA)
    min_budget = parse_taka(data.get("min_budget"))
    max_budget = parse_taka(data.get("max_budget"))
    if min_budget is None:
        errors["min_budget"] = "Minimum budget: " + budget_message
    if max_budget is None:
        errors["max_budget"] = "Maximum budget: " + budget_message
    if min_budget is not None and max_budget is not None:
        if max_budget < min_budget:
            errors["max_budget"] = "Maximum budget must be at least the minimum budget."
        else:
            clean["min_budget"] = min_budget
            clean["max_budget"] = max_budget

    return clean, errors


def validate_profile(data):
    """Return (clean_data, errors) for the profile form."""
    clean, errors = {}, {}

    name = data.get("full_name")
    if isinstance(name, str) and 0 < len(name.strip()) <= MAX_NAME_LENGTH:
        clean["full_name"] = name.strip()
    else:
        errors["full_name"] = "Please enter your full name (up to 100 characters)."

    _check_choice(data, "department", PROFILE_DEPARTMENTS, "department", clean, errors)
    _check_choice(data, "year", PROFILE_YEARS, "year", clean, errors)
    _check_choice(data, "gender", PROFILE_GENDERS, "gender", clean, errors)
    _check_choice(data, "area", PROFILE_AREAS, "preferred area", clean, errors)

    budget = parse_taka(data.get("budget"))
    if budget is None:
        errors["budget"] = "Enter a whole amount in taka between 0 and {:,}.".format(MAX_BUDGET_TAKA)
    else:
        clean["budget"] = budget

    about = data.get("about")
    if about is None:
        clean["about"] = ""
    elif isinstance(about, str) and len(about.strip()) <= MAX_ABOUT_LENGTH:
        clean["about"] = about.strip()
    else:
        errors["about"] = "About me must be text of up to 500 characters."

    return clean, errors


# ----- Phase 5: roommate requests -----
def parse_user_id(value):
    """A user id must be a real whole number >= 1 (not text, not True/False, not 1.5)."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def validate_field_list(value):
    """Check a list of preference field names the owner wants to share.
    Returns (clean_list, error_message). An empty list is allowed (= share nothing)."""
    if not isinstance(value, list):
        return None, "Send a list of preference field names."
    for item in value:
        if not isinstance(item, str) or item not in PREFERENCE_KEYS:
            return None, "One or more field names are not shareable preference fields."
    return [f for f in PREFERENCE_FIELD_ORDER if f in value], None
