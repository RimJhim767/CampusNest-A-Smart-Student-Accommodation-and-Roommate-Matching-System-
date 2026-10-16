# CampusNest Roommate Matching â€” Final Project Report

**Prepared:** 17 October 2026
**Scope:** Documentation of the implemented project and the exploratory 48-submission CSV evaluation. No application code, matching rules, weights, or database contents were changed to prepare this report.

## 1. Project overview

CampusNest is a university roommate-matching application. Students create accounts, save a profile and private roommate preferences, browse students who satisfy essential compatibility requirements, and rank those eligible candidates by preference similarity. Students can send roommate requests and, after a request is accepted, choose whether to share specific preference fields.

The matching objective is to narrow candidates using explicit eligibility requirements before ranking them. The displayed compatibility band is a heuristic estimate from hand-selected weights; it is not a prediction of whether two students will get along.

## 2. Architecture and technologies

- **Backend:** Python with Flask, Flask-SQLAlchemy/SQLAlchemy, and Werkzeug password hashing.
- **Database:** SQLite by default (`backend/database/campusnest.db`). The test suites configure temporary databases.
- **Matching:** NumPy feature vectors and scikit-learn `NearestNeighbors` using brute-force Euclidean distance.
- **Frontend:** Static HTML, CSS, and browser JavaScript under `frontend/`, served by Flask. Pages call JSON APIs with `fetch`; the matches and match-detail pages are `matches.html` and `match-profile.html`.
- **Dependencies:** See the root and backend `requirements.txt` files. The backend declares Flask, Flask-SQLAlchemy, scikit-learn, and NumPy.

The match pipeline is separated into pure matching modules (`backend/matching/`) and a database-facing service (`backend/matching/service.py`). Flask routes and authentication are in `backend/app.py`. The CSV evaluator is a standalone script and does not connect to Flask or the database.

## 3. Eligibility: hard filtering first

The existing implementation in `backend/matching/hard_filter.py` excludes a candidate unless all of the following hold:

1. The candidate is not the requesting student.
2. Gender preference is **mutually** compatible: each student's preferred roommate gender equals the other student's gender.
3. Both chose the same preferred living area.
4. Their budget intervals overlap. Intervals are inclusive: `max(minima) <= min(maxima)`, so ranges touching at one endpoint count as overlapping.

Lifestyle, sleep, cooking, expenses, guests, and pets are ranking features, not eligibility gates. A candidate who passes the hard rules remains eligible even if their other preferences differ substantially.

## 4. Ranking, feature weights, and bands

Eligible records are converted to weighted vectors in `backend/matching/features.py`. The current hand-selected block weights are:

| Feature block | Weight |
|---|---:|
| Budget | 2.0 |
| Lifestyle qualities | 3.0 |
| Sleeping schedule | 2.0 |
| Cooking | 1.0 |
| Shared expenses | 1.5 |
| Guests | 1.5 |
| Pets | 1.5 |
| Area | 0.0 |

Budget endpoints are divided by a fixed 10,000-taka scale and clipped to `[0, 1]`. Lifestyle qualities use a multi-hot vector normalized to unit length. Sleep, cooking, expenses, guests, and pets are nominal categorical blocks; neutral answers are spread evenly across the block. Area is represented but has zero ranking weight because same-area eligibility is already required. Gender and preferred roommate gender are hard-filter inputs, not ranking features.

`backend/matching/knn.py` uses scikit-learn's `NearestNeighbors` with Euclidean distance to retrieve up to the 10 nearest eligible candidates. This is nearest-neighbor search over manually weighted features, **not a trained classifier or supervised model**. The index is rebuilt using current eligible candidates. Ties are sorted deterministically.

`backend/matching/scoring.py` converts distance to an internal normalized similarity using `1 - distanceÂ² / total_weight`. Bands use the following cutoffs:

- **Strong:** similarity â‰¥ 0.80
- **Good:** 0.60 â‰¤ similarity < 0.80
- **Fair:** similarity < 0.60

These thresholds and weights are hand-selected and have not been validated against roommate outcomes. The API exposes the band, not the numeric score.

Match explanations always include the safe statement that the match meets essential requirements. Preference-specific explanations are only included when the other student has consented to share the corresponding field; they use a 0.65 per-block similarity cutoff. Consent controls disclosure, not ranking eligibility.

## 5. Frontend, APIs, and roommate requests

The frontend provides registration/login, profile and preference forms, a match list with compatibility-band filtering, a match-detail page, and a Requests page. The match list fetches the logged-in student's recommendations from `GET /api/matches`; detail is fetched from `GET /api/matches/<id>`. Missing setup, loading, errors, and empty results have separate page states. The match-detail action submits a real roommate request rather than reporting a local-only success.

During request acceptance, a receiver may separately consent to share an international-format WhatsApp number. Sharing can also be enabled later for an accepted request or withdrawn from the Requests page. The application stores the normalized number in a request-scoped `whatsapp_shares` table, not on a public profile. The recipient must be an authenticated participant in that accepted request to retrieve the contact. Request list responses contain only per-participant sharing booleans; they never include the number. The UI constructs a `https://wa.me/<digits>` link only after an authorized retrieval. No message is sent automatically.

Important API contracts in `backend/app.py`:

- Registration and login: `POST /api/register`, `POST /api/login`; current-session lookup: `GET /api/me`; logout: `POST /api/logout`.
- Owner profile and preferences: `GET`/`PUT /api/profile` and `GET`/`PUT /api/preferences`.
- Matching: authenticated `GET /api/matches` and `GET /api/matches/<user_id>`.
- Send a request: authenticated `POST /api/requests` with `{ "receiver_id": <student_id> }`. The server derives the requester from the session. Success returns `201`; invalid/conflicting requests return an appropriate error, including `409` for an active duplicate.
- Received and sent requests: `GET /api/requests/received` and `GET /api/requests/sent`.
- Respond to a request: receiver uses `PUT /api/requests/<id>/accept` (optionally choosing `share_fields`) or `/reject`; requester may `PUT /api/requests/<id>/cancel`.
- Manage consent after acceptance: `PUT /api/requests/<id>/sharing`; view only consented fields through `GET /api/users/<user_id>/shared-preferences`.
- WhatsApp consent: include `share_whatsapp: true` and `phone_number` when accepting, or use `PUT /api/requests/<id>/whatsapp` with `{ "share": true, "phone_number": "+<international number>" }`. The owner may revoke with `{ "share": false }`. The authenticated roommate retrieves consented contact through `GET /api/requests/<id>/whatsapp`; an unshared contact returns `shared: false` without a number. The API requires an explicit leading `+`, validates the international digit length, strips formatting, and stores digits only. The number is returned only to the other participant on that accepted request.

Request states are pending, accepted, rejected, and cancelled. A database uniqueness rule prevents more than one active (pending or accepted) request between a student pair, regardless of direction. Accepting a request does not automatically reveal preferences; the owner chooses fields, can update sharing, or revoke it.

The additive schema change is the `whatsapp_shares` table. SQLAlchemy creates the missing table on app startup; `backend/migrate_whatsapp_sharing.py` is also provided for an explicit migration and makes a timestamped backup before adding the table. No existing user/profile/preference rows are rewritten.

## 6. Dataset and evaluation methodology

The source CSV is `backend/data/CampusNest Roommate Preferences (Responses) - Form Responses 1.csv`. It contains 48 submissions and 12 columns: a timestamp plus gender, preferred roommate gender, preferred area, minimum and maximum budget, lifestyle qualities, sleep, cooking, expenses, guests, and pets. There is **no stable student identifier**, and the dataset contains no confirmed roommate-success outcome labels.

`backend/evaluate_matching_csv.py` reads the CSV as UTF-8, maps the survey headers into the application's preference fields, parses taka amounts, and calls the existing `build_record`, hard-filter, ranking, and scoring implementations. It does not insert records into any database. Its report contains aggregate counts and anonymized feature-block examples only.

For eligibility diagnostics, the evaluator enumerates unordered pairs of valid submissions, so each pair is counted once. It reports both non-exclusive rule failures (a pair may fail multiple rules) and an ordered funnel. Directed recommendation totals count both directions when a pair is mutually eligible. The CSV rows serve only as separate evaluation records; without stable IDs, this cannot detect whether a person submitted more than once.

## 7. Evaluation results

Observed with the evaluator against the CSV above:

- **48 total submissions**, of which **47 passed application validation**.
- **1 invalid submission** had a reversed budget interval (`max_budget < min_budget`); it was excluded rather than corrected silently.
- No missing required values or unrecognized category values were reported. The file decoded as UTF-8.
- **8 valid submissions had zero eligible candidates.**
- **68 unique eligible pairs** yielded **136 directed recommendations**.
- For those eight zero-match submissions, each had candidates passing mutual gender and area checks, but none of those candidates also passed budget overlap. The ordered pair funnel therefore identifies budget as the final constraint for all eight zero-match cases; this is consistent with the stated rules, not evidence of a mapping defect.
- Across 1,081 unordered pairs of valid submissions, 68 were eligible. In an ordered funnel, 552 were removed by gender, 423 more by area, and 38 more by budget. The non-exclusive failure counts were gender 552, area 855, and budget 436; these overlap because a pair can fail multiple rules.
- **47 self-match exclusions** are separate from the 1,081 distinct-pair count.
- Budget ranges overlapped for 645 unique pairs; 235 of those met at an endpoint. Endpoint contact counts as overlap under the implementation.

Compatibility-band totals across the 136 recommendations were 28 Strong, 78 Good, and 30 Fair. These summarize the current heuristic output only; they do not measure roommate satisfaction or predictive accuracy.

## 8. Testing and reproduction

Commands below are run from the `backend` directory. With the included Windows virtual environment, use `..\venv\Scripts\python.exe` in place of `python` if needed.

```powershell
python test_matching.py
python test_phase5.py
python test_phase6.py
python test_evaluate_matching_csv.py -v
python test_whatsapp.py
python evaluate_matching_csv.py
```

`test_phase6.py` uses a temporary SQLite database and also invokes the matching and Phase 5 suites (which includes Phase 4 checks). The reported latest results were:

- Combined regression suite: **130 passed, 0 failed**.
- CSV evaluator synthetic tests: **9 passed**.
- WhatsApp API tests: **7 passed**, including no-consent acceptance, consented acceptance, authorized/unrelated/logged-out retrieval, revocation, invalid numbers, and additive migration on temporary databases.
- The live end-to-end flow was reported as passing with two disposable accounts and an isolated SQLite database, including request acceptance/status refresh and duplicate-request handling. That live flow was not rerun while preparing this report.
- The WhatsApp flow was exercised through the Requests page on an isolated SQLite database using two disposable accounts and a synthetic number: request sent, optional consent accepted, recipient opened the generated `wa.me` link, and the owner revoked consent; the recipient no longer saw the contact action after refresh.

To start the application for a local demonstration, run `python app.py` from `backend`, then open the Flask-served frontend at `http://127.0.0.1:5000/`. The source currently invokes Flask's development server with debug enabled; it is for local demonstration, not production deployment.

## 9. Limitations

- The dataset is small: 48 submissions, 47 currently usable.
- No stable student ID means unique people and repeat submissions cannot be verified.
- One row has an invalid reversed budget range and is excluded.
- There are no verified roommate-success or satisfaction labels.
- The feature weights, neutral encodings, and compatibility thresholds are not empirically calibrated.
- KNN performs nearest-neighbor retrieval; it is not trained on this CSV.
- The report's pair counts describe this submission sample, not the full student population. They cannot establish fairness, generalization, or real-world compatibility.
- No supervised accuracy, causal effect, or predictive match-quality claim is supported by this dataset.

## 10. Security and ethical considerations

- Authentication-required API routes identify the current student from the authenticated Flask session (a signed cookie containing the user ID, then looked up in the database) and do not accept a browser-supplied owner ID for matching.
- Match responses omit exact budgets, preferred area, preference values that have not been shared, email, and numeric compatibility scores. Match detail returns the same not-found response for self, nonexistent, and ineligible IDs.
- Passwords are stored as hashes via Werkzeug, not as plaintext. The session cookie is configured `HttpOnly` and `SameSite=Lax`; JSON-only request bodies and this cookie setting provide the application's documented basic CSRF protections.
- Preference sharing is consent-based and may be updated or revoked. Only explicitly shared fields are returned by the shared-preferences API.
- The project includes a development fallback secret key and runs Flask with `debug=True` when started directly. Before any deployment beyond a local university demonstration, configure a strong secret from the environment, disable debug mode, use an appropriate production server and HTTPS, and review CSRF protections, account lifecycle, logging, and data-retention policies.
- WhatsApp contacts are stored as normalized digits in the SQLite database and protected by authenticated, per-request authorization; they are **not encrypted at the application level**. Restrict filesystem/database access, protect backups, use encrypted storage where appropriate, and consider application-level encryption with managed key rotation before deployment with real phone numbers. The current WhatsApp feature uses only synthetic numbers in its automated and browser tests.
- Preference and demographic data are sensitive. Limit access to the CSV and database, avoid including raw submissions in slides/logs, and obtain informed consent for collection, evaluation, and any future outcome feedback. Audit the effects of eligibility rules and ranking across groups before operational use.

## 11. Recommended future work (not implemented claims)

1. Confirm and correct the reversed budget range in the source of record, if the respondent can clarify it; preserve an audit trail rather than silently altering the CSV.
2. If repeat-submission analysis is needed, collect a consented, privacy-preserving stable identifier or a deduplication process; timestamps and preference similarity alone are not reliable identifiers.
3. Collect voluntary, appropriately consented post-match outcome feedback with a clearly defined measure. Distinguish contact/request/acceptance from a successful living arrangement.
4. Once sufficient outcome data exists, define an evaluation protocol before weight tuning (for example, holdout or time-based validation, subgroup analysis, and uncertainty reporting). Keep hard eligibility policy decisions separate from ranking experiments.
5. Reassess neutral-answer semantics, budget normalization, and the explanations with students and stakeholders. Any changes should be separately planned, reviewed for privacy/fairness impacts, and regression-tested.
6. Prepare a demonstration account/database with synthetic or explicitly authorized data, verify the demo environment and local run instructions, and avoid showing real student records.
