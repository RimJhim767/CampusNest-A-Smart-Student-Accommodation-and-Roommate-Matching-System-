# CampusNest — Phase 6: from distance to a coarse band and privacy-safe explanations.
#
# similarity = 1 - d^2 / TOTAL_WEIGHT      (1.0 = identical answers, 0.0 = as different as possible)
# This is exactly the weighted average of the per-block similarities. It is an ESTIMATED
# compatibility based on today's rules and hand-chosen weights. It is NOT a probability that two
# people will get along, and it has not been validated against real outcomes.
#
# The API sends only the coarse BAND, never the number (an exact number would let someone work
# out another student's private answers by experimenting with their own).
import numpy as np

from .features import BLOCK_SLICES, BLOCK_WEIGHTS, TOTAL_WEIGHT

# Band cut-offs. Hand-chosen, easy to change, not tuned on outcome data.
STRONG_AT = 0.80
GOOD_AT = 0.60
BAND_STRONG, BAND_GOOD, BAND_FAIR = "Strong", "Good", "Fair"

# Per-block cut-off for the wording of an explanation.
COMPATIBLE_AT = 0.65

# block -> (the preference field it comes from, label used in sentences)
EXPLAINABLE_BLOCKS = {
    "lifestyle": ("lifestyle_qualities", "Lifestyle qualities"),
    "sleep": ("sleep_schedule", "Sleeping schedules"),
    "cooking": ("cooking_preference", "Cooking preferences"),
    "expenses": ("expense_preference", "Shared-expense preferences"),
    "guests": ("guest_preference", "Guest preferences"),
    "pets": ("pet_preference", "Pet preferences"),
}

ESSENTIALS_REASON = "Meets all your essential requirements (gender preference, area and budget range)."


def similarity_from_distance(distance):
    return float(min(1.0, max(0.0, 1.0 - (float(distance) ** 2) / TOTAL_WEIGHT)))


def band_for(similarity):
    if similarity >= STRONG_AT:
        return BAND_STRONG
    if similarity >= GOOD_AT:
        return BAND_GOOD
    return BAND_FAIR


def block_similarities(vector_a, vector_b):
    """Similarity (0..1) of each block that has a weight above zero."""
    result = {}
    for name, block_slice in BLOCK_SLICES.items():
        weight = BLOCK_WEIGHTS[name]
        if weight <= 0:
            continue
        squared = float(np.sum((vector_a[block_slice] - vector_b[block_slice]) ** 2))
        result[name] = float(min(1.0, max(0.0, 1.0 - squared / weight)))
    return result


def explain(block_sims, authorized_fields):
    """Return (reasons, differences) as lists of sentences.

    PRIVACY RULE: the essentials sentence is always safe (the person only appears in the list if
    they passed the hard rules). A sentence about a specific preference is added ONLY if that
    preference field is in `authorized_fields`, i.e. the other student shared it with you through
    the Phase 5 consent system. Unshared preferences are never described, even vaguely."""
    reasons = [ESSENTIALS_REASON]
    differences = []
    allowed = set(authorized_fields or [])
    for block, (field, label) in EXPLAINABLE_BLOCKS.items():
        if field not in allowed or block not in block_sims:
            continue
        if block_sims[block] >= COMPATIBLE_AT:
            reasons.append(label + " look compatible.")
        else:
            differences.append(label + " may differ.")
    return reasons, differences
