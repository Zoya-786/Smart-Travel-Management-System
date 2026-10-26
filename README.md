# Smart Travel Management System (PBL – Individual Project)
Modules implemented: **Itinerary Management** (Jira epic TMS-1) and **Travel Booking** (Jira epic TMS-2).
Stack: Python + Flask + SQLite (built in) + plain HTML/JS. No paid APIs, no API keys, no real payments.

## 1. Run on Windows
1. Install Python 3.10+ from python.org (tick **"Add Python to PATH"**).
2. Unzip this folder, double-click **run.bat**, open http://127.0.0.1:5000
3. Run automated tests: `python -m unittest discover -s tests -v` (inside the activated venv).
The database file `tms.db` is created automatically on first run. Delete it to reset all data.

## 2. Structure
`app.py` (backend: validation, database, API) · `static/index.html` (user interface) · `tests/test_app.py` (24 automated tests) · `run.bat`

## 3. Rules (state these in your demo)
**Validation (enforced on the server, and again by database CHECK constraints)**
- Trip: title, destination, dates required; end date >= start date (one-day trip allowed); travelers = whole number >= 1.
- Activity: name, date, time (HH:MM), location, cost required; date within trip dates (inclusive); cost >= 0 (0 allowed).
- Booking: trip (must exist), category (Flight/Train/Hotel/Cab), provider, reference, booking date, travel date, price >= 0, status (Pending/Confirmed/Cancelled) required; notes optional.
- Editing trip dates is rejected if existing activities would fall outside the new range.

**Calculations (done by the database at request time, never trusted from the browser)**
- Itinerary estimated cost of a trip = SUM(cost) of all its activities. Recalculated on every add/edit/delete.
- Booking *total value* = SUM(price) of all records matching the current filter, including cancelled ones.
- *Confirmed expenses* = SUM(price) where status = Confirmed. Pending and Cancelled are excluded.
- Pending and Cancelled totals are shown separately. Filters (trip/category/status) apply to the summary too.
- Cancel = status set to Cancelled; the record is never deleted.

## 4. Design decisions / assumptions (the brief was silent – tell your professor)
- A trip that has booking records **cannot be deleted** (returns an error), because cancelled bookings must be kept. Deleting a trip with no bookings also deletes its activities.
- Booking date vs travel date ordering is not validated (not in the requirements).
- Bookings may be edited by setting status to Cancelled, or via the Cancel button.
- Rupee (₹) display; amounts are rounded to 2 decimals.

## 5. Jira mapping (update Jira manually)
| Jira item | Implemented in | Test cases |
|---|---|---|
| TMS-1 Itinerary Management (epic) | Trips + activities + expense | ITN-01 … ITN-14 |
| TMS-3 Develop Trip Management | `/api/trips*`, Trips screen | ITN-01–07, 13, 14 |
| TMS-4 Implement Daily Itinerary | `/api/trips/<id>/activities`, `/api/activities/*`, Trip detail screen | ITN-08–12 |
| TMS-5 Test Itinerary Management | `tests/` (class Itinerary) | all ITN |
| TMS-2 Travel Booking (epic) | Bookings screen | BKG-01 … BKG-10 |
| TMS-6 Develop Booking Management | `/api/bookings*`, filters, cancel | BKG-01–06, 09, 10 |
| TMS-7 Implement Booking Expense Tracking | `/api/bookings/summary` | BKG-07, 08, 09 |
| TMS-8 Test Travel Booking | `tests/` (class Booking) | all BKG |

## 6. Test cases (PBL format) – automated run: 24/24 passed
| ID | Module | Test scenario | Test data | Expected | Actual | Status |
|---|---|---|---|---|---|---|
| ITN-01 | Itinerary | Create valid trip (Functional) | Goa, 1–5 Dec 2026, 2 travelers | 201, trip saved | As expected | Pass |
| ITN-02 | Itinerary | Required fields (Validation) | blank title/destination | 400, error on title, nothing saved | As expected | Pass |
| ITN-03 | Itinerary | End before start (BVA) | end 30 Nov, start 1 Dec | 400 | As expected | Pass |
| ITN-04 | Itinerary | Same-day trip (BVA) | start = end | 201 | As expected | Pass |
| ITN-05 | Itinerary | Invalid travelers (EP) | 0, -1, 2.5, abc, blank | all 400 | As expected | Pass |
| ITN-06 | Itinerary | Travelers lower boundary (BVA) | 1 | 201 | As expected | Pass |
| ITN-07 | Itinerary | View, edit, delete trip | edit title | updated; after delete → 404 | As expected | Pass |
| ITN-08 | Itinerary | Activities in chronological order | 3 activities, mixed order | sorted by date then time | As expected | Pass |
| ITN-09 | Itinerary | Activity date within trip (BVA) | 30 Nov, 6 Dec, 1 Dec, 5 Dec | 400, 400, 201, 201 | As expected | Pass |
| ITN-10 | Itinerary | Activity cost rules (BVA/EP) | -1, -0.01, 0, abc, blank | 400,400,201,400,400 | As expected | Pass |
| ITN-11 | Itinerary | Required activity fields / bad time | blank name, 25:99 | 400 with name & time errors | As expected | Pass |
| ITN-12 | Itinerary | Expense recalculation (Integration) | add 500.50+1000; edit→200; delete | 1500.50 → 1200 → 1000 | As expected | Pass |
| ITN-13 | Itinerary | Trip dates vs existing activities | shrink end date past activity | 400 | As expected | Pass |
| ITN-14 | Itinerary | Delete trip cascades (Integration) | delete trip with activity | activities removed | As expected | Pass |
| BKG-01 | Booking | Create and view booking | Flight, IndiGo, 5000 | 201; viewable | As expected | Pass |
| BKG-02 | Booking | Invalid trip (Integration) | trip 999 / none | 400 | As expected | Pass |
| BKG-03 | Booking | Price rules (BVA) | -1, x, blank, 0 | 400,400,400,201 | As expected | Pass |
| BKG-04 | Booking | Category/status/required fields | Bus, Done, blanks | all 400 | As expected | Pass |
| BKG-05 | Booking | Edit booking | price 7000, Train | updated | As expected | Pass |
| BKG-06 | Booking | Cancel keeps record | cancel | status Cancelled, still listed | As expected | Pass |
| BKG-07 | Booking | Expense rules | 1000C, 2000.50C, 500P, 4000X | total 7500.50; confirmed 3000.50 | As expected | Pass |
| BKG-08 | Booking | Cancel reduces confirmed total | cancel 1000 booking | confirmed = 0 | As expected | Pass |
| BKG-09 | Booking | Filters + per-trip summary | 2 trips, mixed | counts 2,1,2,1; trip total 300 | As expected | Pass |
| BKG-10 | Booking | Delete trip with bookings | delete | 409, trip kept | As expected | Pass |

**Manual UI cases to run and screenshot yourself** (Actual/Status are yours to record): UI-01 confirm dialog on trip delete; UI-02 error text appears under form for invalid input; UI-03 estimated cost on trip page updates after adding an activity; UI-04 booking filters change table and KPI cards; UI-05 Cancel button hides itself and record stays.

## 7. Bug template for Jira (issue type Bug)
Summary · Steps to reproduce · Expected vs Actual · Severity/Priority · Status (To Do → In Progress → Done) · Resolution (Fixed / Won't Fix / Duplicate) · link to the failing test ID · retest evidence after fix.
Tip: to create real bugs for your demo, make a change that breaks a test, log it in Jira, fix it, and re-run the tests.

## 8. Demo checklist (from the PBL guidelines)
Problem statement → module description → Jira project → backlog → user stories → run app → show source (`app.py`, `index.html`) → test cases and results → bugs in Jira → fix and retest → final demo → report and presentation.

## 9. Items the guidelines require that this ZIP does NOT cover
- Jira work (project description, requirements, user stories, tasks/sub-tasks, sprint planning, assignment, status updates, bugs): you do these manually in Jira.
- Project report and presentation (item 12 of the demonstration list): not generated here; ask if you want them.
- The guidelines do not specify a programming language, UI style, or minimum test-case count. The rubric numbering also skips item 2 (rows 1 and 3, total 10 marks); check with your faculty if a component is missing.
