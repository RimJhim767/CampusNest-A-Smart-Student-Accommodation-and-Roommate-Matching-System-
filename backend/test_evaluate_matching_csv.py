"""Synthetic, database-free tests for the CSV evaluation adapter."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluate_matching_csv import diagnose_eligibility, evaluate_records, parse_csv_text
from matching.engine import rank_candidates
from matching.features import BLOCK_WEIGHTS, encode_record
from matching.scoring import (
    BAND_FAIR, BAND_GOOD, BAND_STRONG, GOOD_AT, STRONG_AT, band_for,
    block_similarities, similarity_from_distance,
)
import numpy as np


HEADERS = [
    "Timestamp",
    "What is your gender?",
    "What gender roommate do you prefer?",
    "Which area do you prefer for living?",
    "What is your minimum monthly roommate/accommodation budget? (\u09f3)",
    "What is your maximum monthly roommate/accommodation budget? (\u09f3)",
    "Which lifestyle qualities are important to you in a roommate?",
    "What is your usual sleeping schedule?",
    "What is your preference regarding cooking?",
    "What is your preference regarding shared household expenses?",
    "What is your preference regarding guests in the shared living space?",
    "What is your preference regarding pets?",
]


def csv_row(timestamp="t1", **changes):
    values = {
        "Timestamp": timestamp,
        HEADERS[1]: "Female",
        HEADERS[2]: "Female",
        HEADERS[3]: "Dhonia",
        HEADERS[4]: "3,000",
        HEADERS[5]: "\u09f35,000",
        HEADERS[6]: "Quiet, Clean",
        HEADERS[7]: "Early Sleeper",
        HEADERS[8]: "Prefer to cook",
        HEADERS[9]: "Prefer sharing expenses",
        HEADERS[10]: "Prefer no/few guests",
        HEADERS[11]: "Prefer no pets",
    }
    values.update(changes)
    return ",".join('"' + str(values[h]).replace('"', '""') + '"' for h in HEADERS)


class CsvEvaluationTests(unittest.TestCase):
    def test_csv_values_map_to_existing_preference_record(self):
        text = ",".join('"' + header + '"' for header in HEADERS) + "\n"
        text += csv_row() + "\n"
        quality, records = parse_csv_text(text)

        self.assertEqual(quality["record_count"], 1)
        self.assertEqual(quality["usable_record_count"], 1)
        self.assertEqual(records[0].min_budget, 3000)
        self.assertEqual(records[0].max_budget, 5000)
        self.assertEqual(records[0].lifestyle_qualities, ("Quiet", "Clean"))
        self.assertEqual(records[0].preferred_area, "Dhonia")

    def test_invalid_budget_and_category_are_reported_without_record(self):
        text = ",".join('"' + header + '"' for header in HEADERS) + "\n"
        text += csv_row(**{
            HEADERS[1]: "female",
            HEADERS[4]: "6,000",
            HEADERS[5]: "5,000",
        }) + "\n"
        quality, records = parse_csv_text(text)

        self.assertEqual(records, [])
        self.assertEqual(quality["budget_reversed_range_count"], 1)
        self.assertEqual(quality["invalid_values_by_field"]["gender"], 1)

    def test_mutual_eligibility_and_unique_pairs_are_distinguished(self):
        text = ",".join('"' + header + '"' for header in HEADERS) + "\n"
        text += csv_row(timestamp="t1") + "\n"
        text += csv_row(timestamp="t2") + "\n"
        quality, records = parse_csv_text(text)
        result = evaluate_records(records)

        self.assertEqual(quality["usable_record_count"], 2)
        self.assertEqual(result["eligible_directed_recommendation_count"], 2)
        self.assertEqual(result["unique_eligible_pair_count"], 1)
        self.assertEqual(result["recommendation_count"], 2)
        diagnostics = result["eligibility_diagnostics"]
        self.assertEqual(diagnostics["self_match_exclusion_count"], 2)
        self.assertEqual(diagnostics["unique_pair_failure_combinations"]["eligible"], 1)
        self.assertEqual(diagnostics["ordered_unique_pair_funnel"]["eligible_after_budget"], 1)

    def test_diagnostic_uses_production_gender_rule_and_reports_combinations(self):
        text = ",".join('"' + header + '"' for header in HEADERS) + "\n"
        text += csv_row(timestamp="t1") + "\n"
        text += csv_row(timestamp="t2", **{
            HEADERS[1]: "Male",
            HEADERS[2]: "Male",
            HEADERS[3]: "Niribili",
            HEADERS[4]: "6,000",
            HEADERS[5]: "7,000",
        }) + "\n"
        _, records = parse_csv_text(text)
        diagnostics = diagnose_eligibility(records)

        self.assertEqual(diagnostics["nonexclusive_unique_pair_failure_counts"], {
            "gender": 1, "area": 1, "budget": 1,
        })
        self.assertEqual(diagnostics["unique_pair_failure_combinations"], {
            "gender+area+budget": 1,
        })
        self.assertEqual(diagnostics["ordered_unique_pair_funnel"]["eliminated_by_gender"], 1)
        self.assertEqual(diagnostics["ordered_unique_pair_funnel"]["passed_gender"], 0)

    def test_zero_match_last_filter_identifies_area_and_budget_bottlenecks(self):
        header = ",".join('"' + value + '"' for value in HEADERS) + "\n"
        area_text = header + csv_row(timestamp="t1") + "\n" + csv_row(
            timestamp="t2", **{HEADERS[3]: "Niribili"}
        ) + "\n"
        _, area_records = parse_csv_text(area_text)
        area_diagnosis = diagnose_eligibility(area_records)
        self.assertEqual(
            area_diagnosis["zero_match_last_filter_elimination_counts"]["area_after_gender"], 2)

        budget_text = header + csv_row(timestamp="t1") + "\n" + csv_row(
            timestamp="t2", **{HEADERS[4]: "6,000", HEADERS[5]: "7,000"}
        ) + "\n"
        _, budget_records = parse_csv_text(budget_text)
        budget_diagnosis = diagnose_eligibility(budget_records)
        self.assertEqual(
            budget_diagnosis["zero_match_last_filter_elimination_counts"]
            ["budget_after_gender_and_area"], 2)

    def test_touching_budget_endpoint_is_still_eligible(self):
        header = ",".join('"' + value + '"' for value in HEADERS) + "\n"
        text = header + csv_row(timestamp="t1", **{
            HEADERS[4]: "3,000", HEADERS[5]: "4,000",
        }) + "\n"
        text += csv_row(timestamp="t2", **{
            HEADERS[4]: "4,000", HEADERS[5]: "5,000",
        }) + "\n"
        _, records = parse_csv_text(text)
        diagnostics = diagnose_eligibility(records)
        result = evaluate_records(records)

        self.assertEqual(diagnostics["budget_overlap_unique_pair_count"], 1)
        self.assertEqual(diagnostics["touching_budget_unique_pair_count"], 1)
        self.assertEqual(result["unique_eligible_pair_count"], 1)

    def test_gender_mismatch_is_ineligible(self):
        text = ",".join('"' + header + '"' for header in HEADERS) + "\n"
        text += csv_row(timestamp="t1") + "\n"
        text += csv_row(timestamp="t2", **{
            HEADERS[1]: "Male",
            HEADERS[2]: "Male",
        }) + "\n"
        _, records = parse_csv_text(text)
        result = evaluate_records(records)

        self.assertEqual(result["zero_eligible_candidate_count"], 2)
        self.assertEqual(result["eligible_directed_recommendation_count"], 0)
        self.assertEqual(result["unique_eligible_pair_count"], 0)

    def test_distance_similarity_and_explanation_blocks_reconcile(self):
        text = ",".join('"' + header + '"' for header in HEADERS) + "\n"
        text += csv_row(timestamp="t1") + "\n"
        text += csv_row(timestamp="t2", **{
            HEADERS[4]: "4,000",
            HEADERS[5]: "6,000",
            HEADERS[6]: "Social",
            HEADERS[7]: "Night Owl",
            HEADERS[8]: "Prefer not to cook",
            HEADERS[9]: "Prefer separate expenses",
            HEADERS[10]: "Frequent guests are okay",
            HEADERS[11]: "Pet-friendly",
        }) + "\n"
        _, records = parse_csv_text(text)
        first, second = records
        vector_a, vector_b = encode_record(first), encode_record(second)
        distance = float(np.linalg.norm(vector_a - vector_b))
        block_scores = block_similarities(vector_a, vector_b)
        weighted_block_score = sum(
            BLOCK_WEIGHTS[name] * value for name, value in block_scores.items()
        ) / sum(BLOCK_WEIGHTS.values())
        ranked = rank_candidates(first, [second])[0]

        self.assertAlmostEqual(ranked.similarity, similarity_from_distance(distance))
        self.assertAlmostEqual(ranked.similarity, weighted_block_score)
        self.assertEqual(set(block_scores), {name for name, weight in BLOCK_WEIGHTS.items() if weight > 0})

    def test_compatibility_threshold_boundaries(self):
        self.assertEqual(band_for(STRONG_AT), BAND_STRONG)
        self.assertEqual(band_for(GOOD_AT), BAND_GOOD)
        self.assertEqual(band_for(GOOD_AT - 0.0001), BAND_FAIR)


if __name__ == "__main__":
    unittest.main()
