# CampusNest — Phase 6: the whole matching pipeline on plain Python objects.
# No database, no Flask: give it PreferenceRecords, get ranked results. That makes it easy to test.
from dataclasses import dataclass

from .features import encode_record
from .hard_filter import hard_filter
from .knn import DEFAULT_K, nearest_candidates
from .scoring import band_for, block_similarities, similarity_from_distance


@dataclass(frozen=True)
class RankedMatch:
    user_id: int
    rank: int                    # 1 = closest
    band: str                    # "Strong" / "Good" / "Fair"
    similarity: float            # INTERNAL ONLY. Never put this in an API response.
    block_similarities: dict     # INTERNAL ONLY. Only used to write authorized explanations.


def rank_candidates(me, candidates, k=DEFAULT_K):
    """Stage 1 (hard filter) -> Stage 2 (KNN ranking). Returns a list of RankedMatch.

    `me` and `candidates` are PreferenceRecords. Candidates that fail a hard rule are dropped
    before any distance is computed, and are never returned or counted."""
    eligible = hard_filter(me, candidates)
    if not eligible:
        return []

    me_vector = encode_record(me)
    vectors = {c.user_id: encode_record(c) for c in eligible}
    ids = [c.user_id for c in eligible]

    neighbours = nearest_candidates(me_vector, [vectors[i] for i in ids], ids, k)

    ranked = []
    for position, (user_id, distance) in enumerate(neighbours, start=1):
        similarity = similarity_from_distance(distance)
        ranked.append(RankedMatch(
            user_id=user_id,
            rank=position,
            band=band_for(similarity),
            similarity=similarity,
            block_similarities=block_similarities(me_vector, vectors[user_id]),
        ))
    return ranked
