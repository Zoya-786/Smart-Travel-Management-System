# Smart Travel Management System (PBL – Individual Project, v2)
Modules: **Itinerary Management** (Jira TMS-1) and **Travel Booking** (Jira TMS-2).
Stack (unchanged): Python + Flask + SQLite + plain HTML/CSS/JS. No paid APIs, no keys, no real payments or tickets.

## 1. Windows setup
1. Install Python 3.10+ from python.org (tick **Add Python to PATH**).
2. Unzip, open the folder, double-click **run.bat** (creates a venv, installs Flask, starts the server).
3. Open **http://127.0.0.1:5000**. Stop with Ctrl+C.
4. Tests: in a terminal inside the folder run `venv\Scripts\activate` then `python run_tests.py` (rewrites `TEST_RESULTS.md`).
Data lives in `tms.db` (created automatically; delete it to reset). If a v1 prototype `tms.db` is found, it is renamed `tms.db.v1_backup_*` and a fresh v2 database is created.

## 2. Architecture
```
Browser (static/index.html + app.js + style.css, hash-routed SPA)
   │  JSON over HTTP
Flask API (app.py)  ── validators.py (all input rules)
   │                ── schema.py + templates_data.py (tables, seed data)
SQLite (tms.db)  – one transaction per request: committed on success, rolled back on any error response
```
All business rules (validation, approval transitions, locking, budget maths) are enforced in the backend; the UI only reflects them.

## 3. Features
Dashboard · My Trips · Explore Itineraries (10 templates) · Daily Planner · Travel Bookings (Flight, Train, Bus, Hotel, Local Transport) · Budget & Expenses · Agency Review (demo mode, clearly labelled as simulated).
Template costs are illustrative estimates for 2 travellers, not live prices.

## 4. Approval workflow (enforced in `app.py`)
| From | Action | To | Rule |
|---|---|---|---|
| Draft / Rejected | Submit | Pending Approval | needs ≥1 activity |
| Pending Approval | Approve | Approved | optional feedback stored |
| Pending Approval | Reject | Rejected | **reason mandatory**, feedback optional |
| Approved | Material change | Draft (+ “Reset to Draft” record) | must be resubmitted |
| any other combination | – | – | HTTP 409, nothing changes |

* **Locked** while Pending Approval: trip edit and activity add/edit/delete return 409.
* **Material change** = origin, destination, dates, travellers, budget; any activity added/deleted; activity name/date/time/location/cost edited. Title, preferences, notes and activity descriptions are *not* material.
* Rejected itineraries stay editable and can be resubmitted.
* Templates are shown as “Approved” (pre-reviewed, simulated). **Using a template creates a separate Draft trip with copied activities**; the template is never modified.
* Every submission/decision/reset is stored in `approvals` with actor and UTC timestamp.
* **Approval ≠ booking confirmation.** Approval only unlocks creating demo booking records.

## 5. Booking rules
* Create/edit bookings only when the linked itinerary is **Approved** (Draft, Pending and Rejected return 409). Cancelling is always allowed.
* Cancel = status Cancelled + `cancelled_at`; record kept; cancelled bookings cannot be edited.
* Hotels need a check-out after check-in; other services need From and To. Reference auto-generated as `DEMO-xx-…` if blank.
* A trip that has booking history cannot be deleted (history is preserved).

## 6. Budget formulas (`GET /api/trips/{id}/budget`)
* Estimated activity cost = Σ activity costs.
* Active booking cost = Σ price of Pending + Confirmed bookings (**Cancelled excluded**).
* Actual expenses = Σ recorded expenses.
* **Remaining = planned budget − actual expenses.**
* No double counting: a Confirmed booking can be turned into exactly one linked expense (`UNIQUE(booking_id)`). Projected total = actual + active bookings *not yet* recorded as expenses. Identical manual expenses are rejected.
* Warnings: actual > budget; projected > budget; estimated activities > budget. A cancelled booking that already has a recorded expense keeps that expense (delete it manually if the money was refunded).

## 7. Database schema
| Table | Key columns |
|---|---|
| templates | id, slug, title, category, destination, duration_days, description, suggested_budget, approval_status |
| template_activities | id, template_id→templates (cascade), day_number, start_time, name, location, cost |
| trips | id, title, origin, destination, start_date, end_date, travelers, budget, preferences, notes, status, template_id→templates, created/updated/submitted/decided_at |
| activities | id, trip_id→trips (cascade), name, date, time, location, description, cost |
| approvals | id, trip_id→trips (cascade), action (Submitted/Approved/Rejected/Reset to Draft), reason, feedback, actor, created_at |
| bookings | id, trip_id→trips (restrict), service_type, provider, reference, from_location, to_location, booking_date, travel_date, end_date, traveler_name, travelers_count, service_details, price, status, notes, created_at, cancelled_at |
| expenses | id, trip_id→trips (cascade), booking_id UNIQUE→bookings, category, description, amount (>0), expense_date, created_at |
CHECK constraints back up the API validation (positive travellers, non-negative money, valid statuses, end ≥ start).

## 8. API
Errors are JSON: `{"errors": {field: msg}}` (400 validation), `{"error": msg}` (404 / 405 / 409 / 500).
| Method & path | Purpose |
|---|---|
| GET `/api/dashboard` | counts, upcoming trips, budget totals, alerts |
| GET `/api/templates[?category=]`, GET `/api/templates/{id}` | browse / details |
| POST `/api/templates/{id}/use` | create own Draft trip (body: origin, start_date, travelers, optional title/destination/budget/preferences/notes) |
| GET/POST `/api/trips`, GET/PUT/DELETE `/api/trips/{id}` | trip CRUD (`?status=` filter) |
| POST `/api/trips/{id}/submit` | submit for approval |
| GET/POST `/api/trips/{id}/activities`, PUT/DELETE `/api/activities/{id}` | daily planner |
| GET `/api/review/pending`, GET `/api/review/history` | agency review lists |
| POST `/api/review/{id}/approve` · `/reject` | decision (`reason` required for reject) |
| GET/POST `/api/bookings` (`?trip_id=&service_type=&status=`), GET/PUT `/api/bookings/{id}`, POST `/api/bookings/{id}/cancel` | bookings |
| POST `/api/bookings/{id}/record-expense` | link a Confirmed booking to one expense |
| GET `/api/trips/{id}/budget`, GET/POST `/api/trips/{id}/expenses`, PUT/DELETE `/api/expenses/{id}` | budget and expenses |

## 9. Testing
**Executed result (this build): 74 automated tests, 74 passed, 0 failed** – see **TEST_RESULTS.md** (generated by actually running `python run_tests.py`; each row = test ID, technique, scenario, result). Test data and expected values are in `tests/test_app.py`.
Coverage: trip validation and CRUD; templates (10 categories, content completeness, customisation without changing originals, independent approvals); activity CRUD/date/cost boundaries; approval submit/approve/reject/reason/resubmit, invalid transitions, locking, re-approval after material changes; bookings (5 types, multiple per trip, blocked unless approved, cancel history, filters); budget, no-double-counting, warnings, dashboard; malformed requests, wrong types, SQL-injection text.
Techniques: equivalence partitioning, boundary value analysis, state transition, error guessing, functional/integration.
**Not run / limits:** `run.bat` and the Windows install were not executed (tests were run on Linux, Python 3.12). The UI was exercised with an automated headless-DOM check (all 7 pages render with real data; booking form, validation message and trip creation worked) but **not in a real browser (Chrome/Edge) – use the manual checklist below.** The Software Engineering Lab practical report mentioned in your request was not attached to the conversation, so the black-box design uses standard techniques instead of that report’s format.

## 10. Manual testing checklist (tick in Chrome/Edge)
- [ ] Dashboard shows empty state on a fresh database; numbers change as you add data.
- [ ] Explore: filter by category; open details; “Use this template” with your dates → lands in Daily Planner as Draft; the template is unchanged afterwards.
- [ ] Planner: add/edit/delete activity; invalid date/cost shows an error; days shown in order.
- [ ] Submit for approval → locked; Add/Edit buttons disabled.
- [ ] Agency Review: open pending item; Reject with empty reason shows an error; Reject with reason; History shows it.
- [ ] Rejected trip: edit, resubmit, approve. Planner shows decision/feedback.
- [ ] Approved trip: change destination → toast says approval reset, status Draft; booking blocked.
- [ ] Bookings: try each of the 5 types; Hotel hides “From”; cancel keeps row; filters work; booking button disabled for non-approved trip.
- [ ] Budget: record expense; “Record as expense” on a confirmed booking (once only); cancelled bookings drop out of active cost; exceed budget → red warning.
- [ ] Narrow the browser window: menu becomes a top bar; confirm dialogs appear for delete/cancel/submit.

## 11. Known limitations
Single user, no login; the “reviewer” is a simulated role in the same app. Currency is ₹ only. A trip with bookings cannot be deleted. Bookings and expenses are not date-validated against the trip dates. Approving does not notify anyone. Template costs are examples. Data is local SQLite (not for multi-user use). Layout checked structurally but not visually on a real device.

## 12. Jira mapping (create/update in Jira yourself – nothing was created for you)
Existing items: TMS-1 Itinerary Management (epic) → TMS-3, TMS-4, TMS-5; TMS-2 Travel Booking (epic) → TMS-6, TMS-7, TMS-8. Suggested additional tasks/sub-tasks for the new scope:
| Epic | Task / sub-task | Acceptance criteria | Tests |
|---|---|---|---|
| TMS-1 | TMS-3 Develop Trip Management (+ sub-tasks: trip form, validation, edit, delete) | Trip with origin, budget, notes can be created/viewed/edited/deleted; invalid data rejected | ITN-01…13 |
| TMS-1 | TMS-4 Implement Daily Itinerary (+ sub-tasks: activity CRUD, date validation, day view) | Activities within trip dates, chronological, cost ≥ 0 | ACT-01…08 |
| TMS-1 | NEW Itinerary Templates (sub-tasks: seed 10 templates, browse/detail UI, customise & save copy) | ≥10 templates across 10 categories; copy is independent; template unchanged | TPL-01…08 |
| TMS-1 | NEW Approval Workflow (sub-tasks: submit, reviewer UI, reject-with-reason, lock, re-approval rule, history) | Transitions per section 4; invalid ones return 409; timestamps stored | APR-01…14 |
| TMS-1 | TMS-5 Test Itinerary Management | all ITN/TPL/ACT/APR tests pass; defects logged as Bugs | – |
| TMS-2 | TMS-6 Develop Booking Management (+ sub-tasks: 5 forms, approval gate, cancel history, filters) | Bookings only for Approved trips; cancel preserves record | BKG-01…13 |
| TMS-2 | TMS-7 Implement Booking Expense Tracking (+ sub-tasks: budget summary, expenses CRUD, duplicate prevention, warnings) | Formulas in section 6; no double counting; warnings shown | BUD-01…11 |
| TMS-2 | NEW Dashboard & UI polish | Cards use real data; empty states, toasts, confirmations | BUD-11, manual checklist |
| TMS-2 | TMS-8 Test Travel Booking | all BKG/BUD/ERR tests pass | – |
Bug workflow for the demo: break a rule on purpose, log a Bug (steps, severity, expected/actual), fix it, re-run `python run_tests.py`, attach the new TEST_RESULTS.md as retest evidence.

## 13. Still needed for the PBL submission (not part of this ZIP)
Jira project work (stories, sprints, assignments, bug records) and the project report/presentation – done by you.
