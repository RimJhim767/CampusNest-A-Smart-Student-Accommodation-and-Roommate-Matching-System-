# CampusNest — Phase 6: feature representation (turning a PreferenceRecord into numbers).
#
# The vector is built so that the plain Euclidean distance between two vectors equals
#         d(A, B)^2  =  sum over blocks of  weight[block] * (difference of that block, between 0 and 1)
# In words: every preference "block" contributes a difference between 0 (identical) and 1
# (as different as possible), multiplied by its weight. Change BLOCK_WEIGHTS to change how much
# each block matters.  THE WEIGHTS BELOW ARE HAND-CHOSEN STARTING POINTS. THEY HAVE NOT BEEN TUNED
# OR VALIDATED AGAINST ANY REAL ROOMMATE OUTCOME.
#
# Encodings
#   * Nominal categories (sleep, cooking, expenses, guests, pets): ONE-HOT. No category number is
#     ever used, so no order between categories is implied.
#     The "neutral" answers ("Flexible", "No preference") are spread evenly across the specific
#     answers, so they sit "in between" everyone instead of clashing with anyone.
#   * Lifestyle qualities (choose several): MULTI-HOT, then scaled to length 1, so that people who
#     share qualities are close, and someone who ticked 5 boxes is not unfairly far from
#     someone who ticked 3.
#   * Budget: min and max divided by a FIXED scale (BUDGET_SCALE), then clipped to 0..1. A fixed
#     scale (not one learned from the current users) keeps results stable when users join.
#   * Area: one-hot, but its weight is 0 because Stage 1 already forces everybody to share one area
#     (it would add the same constant to everyone). Raise the weight if you ever relax that rule.
#   * NOT used as features: gender (hard rule), user id, name, email, password, timestamps.
import numpy as np

from validation import (
    AREAS, COOKING_PREFERENCES, EXPENSE_PREFERENCES, GUEST_PREFERENCES,
    LIFESTYLE_QUALITIES, PET_PREFERENCES, SLEEP_SCHEDULES,
)

BUDGET_SCALE = 10000.0     # taka. Budgets above this are treated as this value when scaling.

# block name -> (record field, specific answers, neutral answer)
CATEGORICAL_BLOCKS = {
    "sleep":    ("sleep_schedule",
                 ["Early Sleeper", "Night Owl"], "Flexible"),
    "cooking":  ("cooking_preference",
                 ["Prefer to cook", "Occasionally cook", "Prefer not to cook"], "No preference"),
    "expenses": ("expense_preference",
                 ["Prefer sharing expenses", "Prefer separate expenses"], "Flexible"),
    "guests":   ("guest_preference",
                 ["Prefer no/few guests", "Occasional guests are okay", "Frequent guests are okay"],
                 "Flexible"),
    "pets":     ("pet_preference",
                 ["Pet-friendly", "Prefer no pets"], "No preference"),
}

# Importance of each block. Documented in docs/PHASE6.md. Easy to change.
BLOCK_WEIGHTS = {
    "budget": 2.0,      # how close the two budget ranges are (they already overlap)
    "lifestyle": 3.0,   # shared qualities matter most to daily life
    "sleep": 2.0,       # clashing sleep schedules are a common source of conflict
    "cooking": 1.0,
    "expenses": 1.5,
    "guests": 1.5,
    "pets": 1.5,
    "area": 0.0,        # constant after hard filtering (see above)
}

BLOCK_ORDER = ["budget", "lifestyle", "sleep", "cooking", "expenses", "guests", "pets", "area"]
TOTAL_WEIGHT = sum(BLOCK_WEIGHTS.values())

# How many numbers each block uses.
BLOCK_SIZES = {
    "budget": 2,
    "lifestyle": len(LIFESTYLE_QUALITIES),
    "area": len(AREAS),
}
for _name, (_field, _specific, _neutral) in CATEGORICAL_BLOCKS.items():
    BLOCK_SIZES[_name] = len(_specific)

BLOCK_SLICES = {}
_position = 0
for _name in BLOCK_ORDER:
    BLOCK_SLICES[_name] = slice(_position, _position + BLOCK_SIZES[_name])
    _position += BLOCK_SIZES[_name]
VECTOR_LENGTH = _position


def encode_categorical(value, specific, neutral):
    """One-hot for a specific answer; an even spread for the neutral answer; error otherwise."""
    size = len(specific)
    if value in specific:
        vector = np.zeros(size)
        vector[specific.index(value)] = 1.0
        return vector
    if value == neutral:
        return np.full(size, 1.0 / size)
    raise ValueError("Unknown category: " + repr(value))


def encode_area(value):
    if value not in AREAS:
        raise ValueError("Unknown area: " + repr(value))
    vector = np.zeros(len(AREAS))
    vector[AREAS.index(value)] = 1.0
    return vector


def encode_qualities(qualities):
    """Multi-hot (1 where a quality was chosen), scaled to length 1."""
    if not qualities:
        raise ValueError("At least one lifestyle quality is required.")
    vector = np.zeros(len(LIFESTYLE_QUALITIES))
    for quality in qualities:
        if quality not in LIFESTYLE_QUALITIES:
            raise ValueError("Unknown lifestyle quality: " + repr(quality))
        vector[LIFESTYLE_QUALITIES.index(quality)] = 1.0
    return vector / np.linalg.norm(vector)


def encode_budget(min_budget, max_budget):
    """Fixed-scale budget: [min, max] / BUDGET_SCALE, clipped to 0..1."""
    if isinstance(min_budget, bool) or isinstance(max_budget, bool):
        raise ValueError("Budget must be a number.")
    if (not isinstance(min_budget, (int, float)) or not isinstance(max_budget, (int, float))
            or min_budget < 0 or max_budget < min_budget):
        raise ValueError("Invalid budget range.")
    return np.clip(np.array([min_budget, max_budget], dtype=float) / BUDGET_SCALE, 0.0, 1.0)


def encode_record(record):
    """PreferenceRecord -> 1-D numpy vector of length VECTOR_LENGTH (same layout for everybody).
    Every block is multiplied by sqrt(weight / 2): the biggest possible raw difference inside a
    block is 2 (squared), so the biggest weighted difference becomes exactly `weight`."""
    raw = {
        "budget": encode_budget(record.min_budget, record.max_budget),
        "lifestyle": encode_qualities(record.lifestyle_qualities),
        "area": encode_area(record.preferred_area),
    }
    for name, (field, specific, neutral) in CATEGORICAL_BLOCKS.items():
        raw[name] = encode_categorical(getattr(record, field), specific, neutral)

    parts = [raw[name] * np.sqrt(BLOCK_WEIGHTS[name] / 2.0) for name in BLOCK_ORDER]
    return np.concatenate(parts)


def feature_names():
    """Human-readable column names (for the documentation and the survey report)."""
    names = ["budget_min_scaled", "budget_max_scaled"]
    names += ["quality=" + q for q in LIFESTYLE_QUALITIES]
    for block in ("sleep", "cooking", "expenses", "guests", "pets"):
        names += [block + "=" + answer for answer in CATEGORICAL_BLOCKS[block][1]]
    names += ["area=" + a for a in AREAS]
    return names


# Sanity check at import time: the category lists here must match the app's allowed values.
_ALLOWED = {
    "sleep_schedule": SLEEP_SCHEDULES, "cooking_preference": COOKING_PREFERENCES,
    "expense_preference": EXPENSE_PREFERENCES, "guest_preference": GUEST_PREFERENCES,
    "pet_preference": PET_PREFERENCES,
}
for _block, (_field, _specific, _neutral) in CATEGORICAL_BLOCKS.items():
    assert sorted(_specific + [_neutral]) == sorted(_ALLOWED[_field]), \
        "features.py is out of sync with validation.py for " + _field
