"""Privacy-preserving exploratory evaluation of a roommate-preferences CSV.

Run from the backend directory:
    python evaluate_matching_csv.py
    python evaluate_matching_csv.py path\to\roommate_preferences.csv

This reads the CSV only; it never connects to the application database.
"""
import argparse
import csv
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from matching.engine import rank_candidates
from matching.hard_filter import (
    area_compatible, budgets_overlap, gender_compatible, is_eligible,
)
from matching.records import build_record
from matching.features import BLOCK_WEIGHTS
from matching.scoring import COMPATIBLE_AT, GOOD_AT, STRONG_AT
from validation import (
    AREAS, COOKING_PREFERENCES, EXPENSE_PREFERENCES, GENDERS, GUEST_PREFERENCES,
    LIFESTYLE_QUALITIES, PET_PREFERENCES, PREFERRED_ROOMMATE_GENDERS, SLEEP_SCHEDULES,
)


DEFAULT_CSV = (BACKEND_DIR / "data" /
               "CampusNest Roommate Preferences (Responses) - Form Responses 1.csv")

CSV_FIELDS = {
    "gender": "What is your gender?",
    "preferred_roommate_gender": "What gender roommate do you prefer?",
    "preferred_area": "Which area do you prefer for living?",
    "min_budget": "What is your minimum monthly roommate/accommodation budget? (\u09f3)",
    "max_budget": "What is your maximum monthly roommate/accommodation budget? (\u09f3)",
    "lifestyle_qualities": "Which lifestyle qualities are important to you in a roommate?",
    "sleep_schedule": "What is your usual sleeping schedule?",
    "cooking_preference": "What is your preference regarding cooking?",
    "expense_preference": "What is your preference regarding shared household expenses?",
    "guest_preference": "What is your preference regarding guests in the shared living space?",
    "pet_preference": "What is your preference regarding pets?",
}
TIMESTAMP_FIELD = "Timestamp"
REQUIRED_COLUMNS = [TIMESTAMP_FIELD, *CSV_FIELDS.values()]
CATEGORY_VALUES = {
    "gender": GENDERS,
    "preferred_roommate_gender": PREFERRED_ROOMMATE_GENDERS,
    "preferred_area": AREAS,
    "sleep_schedule": SLEEP_SCHEDULES,
    "cooking_preference": COOKING_PREFERENCES,
    "expense_preference": EXPENSE_PREFERENCES,
    "guest_preference": GUEST_PREFERENCES,
    "pet_preference": PET_PREFERENCES,
}


def _parse_budget(value):
    """Parse whole taka amounts, tolerating common currency marks and grouping commas."""
    text = (value or "").strip()
    text = text.replace("\u09f3", "").replace("\u09f2", "").replace("৳", "").strip()
    if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)", text):
        return None
    return int(text.replace(",", ""))


def _row_to_preferences(row):
    data = {}
    for name, column in CSV_FIELDS.items():
        value = (row.get(column) or "").strip()
        if name == "min_budget" or name == "max_budget":
            data[name] = _parse_budget(value)
        elif name == "lifestyle_qualities":
            data[name] = [part.strip() for part in value.split(",") if part.strip()]
        else:
            data[name] = value
    return data


def parse_csv_text(text):
    """Return aggregate quality information and valid PreferenceRecords.

    No source row values, timestamps, or identities are returned.
    """
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    expected_set = set(REQUIRED_COLUMNS)
    header_errors = len(expected_set - set(headers)) + len(set(headers) - expected_set)

    raw_rows = list(reader)
    quality = {
        "record_count": len(raw_rows),
        "column_count": len(headers),
        "header_error_count": header_errors,
        "malformed_row_count": 0,
        "missing_values_by_field": Counter(),
        "invalid_values_by_field": Counter(),
        "duplicate_timestamp_excess": 0,
        "duplicate_submission_excess": 0,
        "missing_timestamp_count": 0,
        "budget_valid_range_count": 0,
        "budget_reversed_range_count": 0,
        "budget_invalid_value_count": 0,
        "utf8_replacement_character_count": text.count("\ufffd"),
    }
    timestamp_counts = Counter()
    submission_counts = Counter()
    records = []
    all_required_present = header_errors == 0

    for index, row in enumerate(raw_rows, start=1):
        if None in row:
            quality["malformed_row_count"] += 1
        for name, column in CSV_FIELDS.items():
            if not (row.get(column) or "").strip():
                quality["missing_values_by_field"][name] += 1

        timestamp = (row.get(TIMESTAMP_FIELD) or "").strip()
        if not timestamp:
            quality["missing_timestamp_count"] += 1
        timestamp_counts[timestamp] += 1
        submission_counts[tuple((row.get(column) or "").strip()
                                for column in CSV_FIELDS.values())] += 1

        data = _row_to_preferences(row)
        min_budget, max_budget = data["min_budget"], data["max_budget"]
        if min_budget is None or max_budget is None:
            quality["budget_invalid_value_count"] += 1
        elif max_budget < min_budget:
            quality["budget_reversed_range_count"] += 1
        else:
            quality["budget_valid_range_count"] += 1

        for name, allowed in CATEGORY_VALUES.items():
            if data[name] not in allowed:
                quality["invalid_values_by_field"][name] += 1
        qualities = data["lifestyle_qualities"]
        if (not qualities or any(item not in LIFESTYLE_QUALITIES for item in qualities)):
            quality["invalid_values_by_field"]["lifestyle_qualities"] += 1

        if not all_required_present or None in row or any(
                not (row.get(column) or "").strip() for column in REQUIRED_COLUMNS):
            continue
        record, problem = build_record(index, data)
        if problem:
            quality["invalid_values_by_field"][problem] += 1
            continue
        records.append(record)

    quality["duplicate_timestamp_excess"] = sum(n - 1 for n in timestamp_counts.values() if n > 1)
    quality["duplicate_submission_excess"] = sum(n - 1 for n in submission_counts.values() if n > 1)
    quality["usable_record_count"] = len(records)
    quality["unusable_record_count"] = len(raw_rows) - len(records)
    quality["missing_values_by_field"] = dict(sorted(quality["missing_values_by_field"].items()))
    quality["invalid_values_by_field"] = dict(sorted(quality["invalid_values_by_field"].items()))
    return quality, records


def _band_counts(records):
    counts = Counter()
    recommendation_count = 0
    for me in records:
        recommendations = rank_candidates(me, [other for other in records if other.user_id != me.user_id])
        recommendation_count += len(recommendations)
        counts.update(item.band for item in recommendations)
    return {
        "recommendation_count": recommendation_count,
        "compatibility_band_counts": {
            band: counts.get(band, 0) for band in ("Strong", "Good", "Fair")
        },
    }


def diagnose_eligibility(records):
    """Aggregate hard-filter eliminations without retaining or returning pair identities."""
    pair_count = len(records) * (len(records) - 1) // 2
    failure_counts = Counter()
    ordered = {
        "distinct_unique_pairs_before_filters": pair_count,
        "passed_gender": 0,
        "eliminated_by_gender": 0,
        "passed_gender_and_area": 0,
        "eliminated_by_area_after_gender": 0,
        "eligible_after_budget": 0,
        "eliminated_by_budget_after_gender_and_area": 0,
    }
    budget_overlaps = 0
    touching_budgets = 0

    # Pair-level diagnostics use unordered pairs because every hard rule is mutual/symmetric.
    for left_index, left in enumerate(records):
        for right in records[left_index + 1:]:
            gender_ok = gender_compatible(left, right)
            area_ok = area_compatible(left, right)
            budget_ok = budgets_overlap(
                left.min_budget, left.max_budget, right.min_budget, right.max_budget)
            if budget_ok:
                budget_overlaps += 1
                if max(left.min_budget, right.min_budget) == min(left.max_budget, right.max_budget):
                    touching_budgets += 1

            failed = tuple(name for name, passed in (
                ("gender", gender_ok), ("area", area_ok), ("budget", budget_ok)
            ) if not passed)
            failure_counts["+".join(failed) if failed else "eligible"] += 1

            if gender_ok:
                ordered["passed_gender"] += 1
                if area_ok:
                    ordered["passed_gender_and_area"] += 1
                    if budget_ok:
                        ordered["eligible_after_budget"] += 1
                    else:
                        ordered["eliminated_by_budget_after_gender_and_area"] += 1
                else:
                    ordered["eliminated_by_area_after_gender"] += 1
            else:
                ordered["eliminated_by_gender"] += 1

    zero_records = []
    for me in records:
        others = [candidate for candidate in records if candidate.user_id != me.user_id]
        gender_count = sum(gender_compatible(me, other) for other in others)
        area_after_gender = sum(
            gender_compatible(me, other) and area_compatible(me, other) for other in others
        )
        eligible_count = sum(is_eligible(me, other) for other in others)
        if eligible_count == 0:
            zero_records.append({
                "gender": gender_count,
                "area": area_after_gender,
                "eligible": eligible_count,
            })

    terminal_counts = Counter()
    zero_availability = Counter()
    for item in zero_records:
        if item["gender"] > 0:
            zero_availability["has_gender_compatible_candidate"] += 1
        if item["area"] > 0:
            zero_availability["has_candidate_after_gender_and_area"] += 1
        if item["gender"] == 0:
            terminal_counts["gender"] += 1
        elif item["area"] == 0:
            terminal_counts["area_after_gender"] += 1
        else:
            terminal_counts["budget_after_gender_and_area"] += 1

    return {
        "unique_distinct_candidate_pair_count": pair_count,
        "self_match_exclusion_count": len(records),
        "nonexclusive_unique_pair_failure_counts": {
            name: sum(count for combination, count in failure_counts.items()
                      if name in combination.split("+"))
            for name in ("gender", "area", "budget")
        },
        "unique_pair_failure_combinations": {
            name: failure_counts[name]
            for name in (
                "eligible", "gender", "area", "budget", "gender+area",
                "gender+budget", "area+budget", "gender+area+budget",
            )
            if failure_counts[name]
        },
        "ordered_unique_pair_funnel": ordered,
        "budget_overlap_unique_pair_count": budget_overlaps,
        "touching_budget_unique_pair_count": touching_budgets,
        "zero_match_student_count": len(zero_records),
        "zero_match_candidate_availability": {
            "with_any_gender_compatible_candidate":
                zero_availability["has_gender_compatible_candidate"],
            "with_any_candidate_after_gender_and_area":
                zero_availability["has_candidate_after_gender_and_area"],
        },
        "zero_match_last_filter_elimination_counts": {
            name: terminal_counts[name]
            for name in ("gender", "area_after_gender", "budget_after_gender_and_area")
        },
    }


def evaluate_records(records):
    """Run production eligibility and ranking against validated PreferenceRecords."""
    candidate_counts = {}
    eligible_directed = 0
    eligible_unique = 0
    for me in records:
        count = sum(is_eligible(me, other) for other in records)
        candidate_counts[me.user_id] = count
        eligible_directed += count
    for left_index, left in enumerate(records):
        for right in records[left_index + 1:]:
            if is_eligible(left, right):
                eligible_unique += 1

    distribution = Counter(candidate_counts.values())
    eligibility_diagnostics = diagnose_eligibility(records)
    result = {
        "usable_record_count": len(records),
        "eligibility_diagnostics": eligibility_diagnostics,
        "zero_eligible_candidate_count": sum(count == 0 for count in candidate_counts.values()),
        "eligible_directed_recommendation_count": eligible_directed,
        "unique_eligible_pair_count": eligible_unique,
        "candidate_count_distribution": {
            str(count): distribution[count] for count in sorted(distribution)
        },
    }
    result.update(_band_counts(records))

    examples = []
    best_by_band = {}
    for me in records:
        ranked = rank_candidates(me, [other for other in records if other.user_id != me.user_id])
        for item in ranked:
            if item.band not in best_by_band:
                closer = sorted(
                    (name for name, value in item.block_similarities.items() if value >= 0.8),
                )
                less_close = sorted(
                    (name for name, value in item.block_similarities.items() if value < 0.6),
                )
                best_by_band[item.band] = {
                    "band": item.band,
                    "rank": item.rank,
                    "closer_feature_blocks": closer,
                    "less_close_feature_blocks": less_close,
                    "explanation": (
                        "Both records passed mutual-gender, same-area and overlapping-budget "
                        "eligibility. The listed blocks are relative encoding similarities; "
                        "underlying answers and identities are omitted."
                    ),
                }
            if len(best_by_band) == 3:
                break
        if len(best_by_band) == 3:
            break
    examples = [best_by_band[band] for band in ("Strong", "Good", "Fair") if band in best_by_band]
    result["anonymized_examples"] = examples
    return result


def evaluate_csv(path):
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8-sig")
    quality, records = parse_csv_text(text)
    quality["encoding"] = "UTF-8"
    quality["utf8_bom_present"] = raw.startswith(b"\xef\xbb\xbf")
    quality["student_identity_assessable"] = False
    quality["student_identity_note"] = (
        "No stable student identifier is present; timestamps and identical preferences "
        "cannot establish student identity."
    )
    evaluation = evaluate_records(records)
    return {"data_quality": quality, "evaluation": evaluation}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", type=Path, default=DEFAULT_CSV,
                        help="CSV to evaluate (defaults to the located survey export)")
    args = parser.parse_args()
    try:
        report = evaluate_csv(args.csv_path)
    except UnicodeDecodeError:
        parser.error("Unable to decode the requested CSV as UTF-8.")
    except (OSError, csv.Error):
        parser.error("Unable to read the requested CSV.")
    report["feature_mapping"] = {
        "csv_to_application_fields": CSV_FIELDS,
        "hard_filters": ["different student", "mutually compatible gender preferences",
                         "same preferred area", "overlapping budget intervals (touching counts)"],
        "budget_scale_taka": 10000,
        "encoding": {
            "budget": "minimum and maximum divided by the fixed scale, clipped to 0..1",
            "lifestyle_qualities": "multi-hot then normalized to unit length",
            "sleep_cooking_expenses_guests_pets":
                "nominal one-hot blocks; neutral answers are evenly distributed",
        },
        "weighted_feature_blocks": {
            name: weight for name, weight in BLOCK_WEIGHTS.items() if weight > 0
        },
        "zero_weight_area_block": "Area is a hard filter and contributes no ranking weight.",
        "band_thresholds": {
            "Strong": "similarity >= " + str(STRONG_AT),
            "Good": str(GOOD_AT) + " <= similarity < " + str(STRONG_AT),
            "Fair": "similarity < " + str(GOOD_AT),
            "explanation_compatible_at": COMPATIBLE_AT,
        },
        "not_numeric_features": [
            "gender and preferred roommate gender are eligibility-only",
            "student identity is used only to exclude self-matches",
        ],
    }
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
