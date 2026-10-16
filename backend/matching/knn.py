# CampusNest — Phase 6, Stage 2: nearest-neighbour retrieval with scikit-learn.
#
# IMPORTANT: this is NOT a trained classifier. Nothing is "learned" and no success label exists.
# NearestNeighbors just stores the eligible candidates' vectors and finds which ones are closest
# to the logged-in user's vector.
#
# Why the index is rebuilt for each request: Stage 1 gives every user a DIFFERENT eligible set, so
# there is no single shared set to fit once. For brute-force search "fit" only stores the array
# (no training), so with a few hundred students the cost is negligible, and results always use
# the CURRENT users and preferences (no stale cache to invalidate).
import numpy as np
from sklearn.neighbors import NearestNeighbors

DEFAULT_K = 10          # show at most the 10 closest eligible candidates


def nearest_candidates(me_vector, candidate_vectors, candidate_ids, k=DEFAULT_K):
    """Return [(user_id, distance), ...] sorted from closest to furthest, at most k long.

    * 0 candidates -> []
    * fewer candidates than k -> all of them (never an error)
    * k=None -> every candidate
    * Ties in distance are broken by user id, so the order is the same on every run.
    The search asks for ALL candidates and then keeps the first k, so a tie at the cut-off
    cannot make the result depend on scikit-learn's internal ordering."""
    count = len(candidate_ids)
    if count == 0:
        return []
    if k is None:
        k = count
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        k = DEFAULT_K

    matrix = np.vstack(candidate_vectors)
    index = NearestNeighbors(n_neighbors=count, metric="euclidean", algorithm="brute")
    index.fit(matrix)
    distances, positions = index.kneighbors(np.asarray(me_vector).reshape(1, -1), n_neighbors=count)

    pairs = [(int(candidate_ids[pos]), float(dist)) for dist, pos in zip(distances[0], positions[0])]
    pairs.sort(key=lambda pair: (round(pair[1], 9), pair[0]))
    return pairs[:min(k, count)]
