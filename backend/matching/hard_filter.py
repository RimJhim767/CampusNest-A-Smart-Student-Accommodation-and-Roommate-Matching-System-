# CampusNest — Phase 6, Stage 1: HARD matching.
# A candidate must pass ALL three rules below, otherwise they are removed before any ranking.
# Nothing here is ever relaxed to "fill the page". No other preference is a hard rule.


def gender_compatible(a, b):
    """Rule A. MUTUAL: each person must accept the other's gender.
    a.gender = A's own gender; a.preferred_roommate_gender = the gender A will live with."""
    return (a.preferred_roommate_gender == b.gender
            and b.preferred_roommate_gender == a.gender)


def area_compatible(a, b):
    """Rule B. Initial rule: both chose the same preferred area."""
    return a.preferred_area == b.preferred_area


def budgets_overlap(a_min, a_max, b_min, b_max):
    """Rule C. Intervals [a_min, a_max] and [b_min, b_max] overlap when
    max(a_min, b_min) <= min(a_max, b_max).  '<=' means touching at one value counts
    (example: [3000, 4000] and [4000, 5000] overlap at 4000)."""
    return max(a_min, b_min) <= min(a_max, b_max)


def failed_rules(me, other):
    """Names of the rules this pair FAILS. Used by tests only. Never sent to a browser,
    because it would reveal why somebody was excluded."""
    failed = []
    if not gender_compatible(me, other):
        failed.append("gender")
    if not area_compatible(me, other):
        failed.append("area")
    if not budgets_overlap(me.min_budget, me.max_budget, other.min_budget, other.max_budget):
        failed.append("budget")
    return failed


def is_eligible(me, other):
    """True only for a DIFFERENT person who passes rules A, B and C."""
    if me.user_id == other.user_id:
        return False                       # never recommend yourself
    return not failed_rules(me, other)


def hard_filter(me, candidates):
    """Return the candidates that pass every hard rule (original order kept)."""
    return [c for c in candidates if is_eligible(me, c)]
