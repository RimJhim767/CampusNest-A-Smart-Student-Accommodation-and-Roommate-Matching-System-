# CampusNest — Phase 6: roommate matching.
#
# Pipeline (see docs/PHASE6.md):
#   records.py      raw preference data  ->  a checked PreferenceRecord (or "invalid")
#   hard_filter.py  Stage 1: essential rules (gender, area, budget). Pure yes/no.
#   features.py     turns a record into numbers (one-hot / multi-hot / scaled budget)
#   knn.py          Stage 2: scikit-learn NearestNeighbors finds the closest eligible candidates
#   scoring.py      turns distances into a coarse band + honest, privacy-safe reasons
#   engine.py       runs the pipeline on plain Python objects (no database, easy to test)
#   service.py      the ONLY file that touches the database / Phase 5 permissions
#
# This is a distance-based recommendation prototype. It is NOT a trained classifier and it
# has NOT been validated against real roommate outcomes.
