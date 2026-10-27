"""Black-box tests through the HTTP API. Docstring tag = technique: [EP] equivalence partitioning, [BVA] boundary value analysis,
[ST] state transition, [FT] functional, [IT] integration, [EG] error guessing, [VT] validation."""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app

TRIP = dict(title="Goa Trip", origin="Nagpur", destination="Goa", start_date="2026-12-01", end_date="2026-12-05", travelers=2, budget=50000, preferences="", notes="")
ACT = dict(name="Beach", date="2026-12-02", time="09:30", location="Baga", description="", cost=500)
BK = dict(service_type="Flight", provider="IndiGo", reference="AB123", from_location="Nagpur", to_location="Goa", travel_date="2026-12-01",
          traveler_name="Asha", travelers_count=2, price=5000, status="Confirmed")
HOTEL = dict(BK, service_type="Hotel", provider="Sea View", from_location="", to_location="Calangute", end_date="2026-12-04", price=9000)

class Base(unittest.TestCase):
    def setUp(self):
        fd, self.p = tempfile.mkstemp(suffix=".db"); os.close(fd); os.remove(self.p)
        self.c = create_app(self.p).test_client()
    def tearDown(self):
        if os.path.exists(self.p): os.remove(self.p)
    def trip(self, **k): return self.c.post("/api/trips", json={**TRIP, **k}).get_json()
    def act(self, t, **k): return self.c.post(f"/api/trips/{t}/activities", json={**ACT, **k})
    def get(self, t): return self.c.get(f"/api/trips/{t}").get_json()
    def status(self, t): return self.get(t)["status"]
    def submit(self, t): return self.c.post(f"/api/trips/{t}/submit")
    def approve(self, t, **k): return self.c.post(f"/api/review/{t}/approve", json=k)
    def reject(self, t, **k): return self.c.post(f"/api/review/{t}/reject", json=k)
    def pending(self, _ad=None, **k):
        t = self.trip(**k)["id"]; self.act(t, **({"date": _ad} if _ad else {})); self.submit(t); return t
    def approved(self, **k):
        t = self.pending(**k); self.approve(t); return t
    def book(self, t, **k): return self.c.post("/api/bookings", json={**BK, "trip_id": t, **k})
    def bud(self, t): return self.c.get(f"/api/trips/{t}/budget").get_json()
    def exp(self, t, **k): return self.c.post(f"/api/trips/{t}/expenses", json={**dict(category="Food", description="Lunch", amount=500, expense_date="2026-12-02"), **k})

class Trips(Base):
    def test_ITN_01_create_trip(self):
        """[FT] Create a valid trip: saved as Draft with all fields"""
        r = self.c.post("/api/trips", json={**TRIP, "preferences": "Beach", "notes": "n"}); t = r.get_json()
        self.assertEqual(r.status_code, 201); self.assertEqual((t["status"], t["origin"], t["budget"], t["preferences"]), ("Draft", "Nagpur", 50000, "Beach"))
    def test_ITN_02_required_fields(self):
        """[VT] Blank title / origin / destination / dates are rejected and nothing is saved"""
        for k in ("title", "origin", "destination", "start_date", "end_date"):
            r = self.c.post("/api/trips", json={**TRIP, k: " "}); self.assertEqual(r.status_code, 400, k); self.assertIn(k, r.get_json()["errors"])
        self.assertEqual(self.c.get("/api/trips").get_json(), [])
    def test_ITN_03_end_before_start(self):
        """[BVA] End date one day before start is rejected"""
        self.assertEqual(self.c.post("/api/trips", json={**TRIP, "end_date": "2026-11-30"}).status_code, 400)
    def test_ITN_04_same_day_trip(self):
        """[BVA] End date equal to start date is accepted"""
        self.assertEqual(self.c.post("/api/trips", json={**TRIP, "end_date": "2026-12-01"}).status_code, 201)
    def test_ITN_05_travelers_invalid(self):
        """[EP] Travellers 0, -1, 2.5, text, blank, null, true, 1001 are rejected"""
        for v in (0, -1, "2.5", "abc", "", None, True, 1001):
            self.assertEqual(self.c.post("/api/trips", json={**TRIP, "travelers": v}).status_code, 400, v)
    def test_ITN_06_travelers_boundaries(self):
        """[BVA] Travellers 1 and 1000 are accepted"""
        for v in (1, 1000): self.assertEqual(self.c.post("/api/trips", json={**TRIP, "travelers": v}).status_code, 201, v)
    def test_ITN_07_budget_rules(self):
        """[BVA] Budget -0.01 / text / blank rejected; 0 and decimal accepted"""
        for v, code in ((-0.01, 400), ("x", 400), ("", 400), (None, 400), (0, 201), (999.99, 201)):
            self.assertEqual(self.c.post("/api/trips", json={**TRIP, "budget": v}).status_code, code, v)
    def test_ITN_08_bad_dates(self):
        """[EP] Invalid date strings are rejected"""
        for v in ("2026-13-01", "01/12/2026", "abc", 20261201, None):
            self.assertEqual(self.c.post("/api/trips", json={**TRIP, "start_date": v}).status_code, 400, v)
    def test_ITN_09_view_edit_list(self):
        """[FT] View, list and edit a trip"""
        t = self.trip()["id"]; self.assertEqual(self.get(t)["title"], "Goa Trip")
        r = self.c.put(f"/api/trips/{t}", json={**TRIP, "title": "Goa 2", "budget": 60000}).get_json()
        self.assertEqual((r["title"], r["budget"]), ("Goa 2", 60000)); self.assertEqual(len(self.c.get("/api/trips").get_json()), 1)
    def test_ITN_10_edit_validation_keeps_data(self):
        """[VT] Invalid edit is rejected and the stored trip is unchanged"""
        t = self.trip()["id"]; self.assertEqual(self.c.put(f"/api/trips/{t}", json={**TRIP, "travelers": 0}).status_code, 400)
        self.assertEqual(self.get(t)["travelers"], 2)
    def test_ITN_11_delete_trip_cascades(self):
        """[IT] Deleting a trip removes its activities, approvals and expenses"""
        t = self.pending(); self.exp(t); self.assertEqual(self.c.delete(f"/api/trips/{t}").status_code, 200)
        self.assertEqual(self.c.get(f"/api/trips/{t}").status_code, 404)
        import sqlite3; d = sqlite3.connect(self.p)
        for tb in ("activities", "approvals", "expenses"): self.assertEqual(d.execute(f"SELECT COUNT(*) FROM {tb}").fetchone()[0], 0, tb)
    def test_ITN_12_delete_trip_with_bookings_blocked(self):
        """[IT] A trip with booking history cannot be deleted"""
        t = self.approved(); self.book(t); self.assertEqual(self.c.delete(f"/api/trips/{t}").status_code, 409); self.assertEqual(self.c.get(f"/api/trips/{t}").status_code, 200)
    def test_ITN_13_missing_trip(self):
        """[EG] Unknown trip id -> 404 on get/put/delete; non-numeric id -> 404"""
        for m in ("get", "delete"): self.assertEqual(getattr(self.c, m)("/api/trips/999").status_code, 404)
        self.assertEqual(self.c.put("/api/trips/999", json=TRIP).status_code, 404); self.assertEqual(self.c.get("/api/trips/abc").status_code, 404)

class Templates(Base):
    def test_TPL_01_ten_templates_all_categories(self):
        """[FT] At least 10 templates covering the 10 required categories"""
        ts = self.c.get("/api/templates").get_json(); self.assertGreaterEqual(len(ts), 10)
        need = {"City Exploration", "Weekend Getaway", "Sightseeing", "Nature & Adventure", "Historical Tour", "Food Trip", "Family Vacation", "Hill Station", "Beach Holiday", "Relaxing Vacation"}
        self.assertTrue(need <= {t["category"] for t in ts})
    def test_TPL_02_template_content_complete(self):
        """[FT] Every template has destination, duration, budget and day-wise activities with time, location, cost"""
        for s in self.c.get("/api/templates").get_json():
            t = self.c.get(f"/api/templates/{s['id']}").get_json()
            self.assertTrue(t["destination"] and t["suggested_budget"] > 0 and t["duration_days"] >= 2, t["title"])
            self.assertEqual({a["day_number"] for a in t["activities"]}, set(range(1, t["duration_days"] + 1)), t["title"])
            for a in t["activities"]: self.assertTrue(a["name"] and a["location"] and ":" in a["start_time"] and a["cost"] >= 0)
    def test_TPL_03_filter_by_category(self):
        """[FT] Category filter returns only matching templates"""
        r = self.c.get("/api/templates?category=Food Trip").get_json(); self.assertTrue(r and all(t["category"] == "Food Trip" for t in r))
    def test_TPL_04_use_template_creates_draft(self):
        """[FT] Using a template creates a Draft trip with activities dated start+day-1 and end = start+duration-1"""
        tpl = self.c.get("/api/templates/1").get_json()
        r = self.c.post("/api/templates/1/use", json=dict(origin="Nagpur", start_date="2027-01-10", travelers=3, budget=40000, title="My Jaipur")); t = r.get_json()
        self.assertEqual(r.status_code, 201); self.assertEqual((t["status"], t["title"], t["travelers"], t["template_id"]), ("Draft", "My Jaipur", 3, 1))
        self.assertEqual(t["end_date"], "2027-01-12"); self.assertEqual(len(t["activities"]), len(tpl["activities"]))
        self.assertEqual(t["activities"][0]["date"], "2027-01-10"); self.assertEqual(t["activities"][-1]["date"], "2027-01-12")
    def test_TPL_05_customising_does_not_change_template(self):
        """[IT] Editing / deleting the copy's activities and details leaves the template unchanged"""
        before = self.c.get("/api/templates/2").get_json()
        t = self.c.post("/api/templates/2/use", json=dict(origin="Pune", start_date="2027-02-01", travelers=2)).get_json()
        a = t["activities"][0]; self.c.put(f"/api/activities/{a['id']}", json={**a, "name": "Changed", "cost": 99999})
        self.c.delete(f"/api/activities/{t['activities'][1]['id']}"); self.c.put(f"/api/trips/{t['id']}", json={**TRIP, "start_date": "2027-02-01", "end_date": "2027-02-02"})
        self.assertEqual(before, self.c.get("/api/templates/2").get_json())
    def test_TPL_06_copies_have_separate_approval(self):
        """[ST] Template is pre-approved but each copy is Draft; approving one copy does not affect another"""
        self.assertEqual(self.c.get("/api/templates/3").get_json()["approval_status"], "Approved")
        a = self.c.post("/api/templates/3/use", json=dict(origin="X", start_date="2027-03-01", travelers=2)).get_json()
        b = self.c.post("/api/templates/3/use", json=dict(origin="X", start_date="2027-04-01", travelers=2)).get_json()
        self.assertEqual((a["status"], b["status"]), ("Draft", "Draft")); self.submit(a["id"]); self.approve(a["id"])
        self.assertEqual((self.status(a["id"]), self.status(b["id"])), ("Approved", "Draft")); self.assertEqual(self.get(b["id"])["approvals"], [])
    def test_TPL_07_use_template_validation(self):
        """[VT] Missing origin / start date / bad travellers -> 400; unknown template -> 404; nothing created"""
        ok = dict(origin="X", start_date="2027-03-01", travelers=2)
        for k, v in (("origin", ""), ("start_date", ""), ("start_date", "bad"), ("travelers", 0), ("budget", -5)):
            self.assertEqual(self.c.post("/api/templates/1/use", json={**ok, k: v}).status_code, 400, (k, v))
        self.assertEqual(self.c.post("/api/templates/999/use", json=ok).status_code, 404); self.assertEqual(self.c.get("/api/trips").get_json(), [])
    def test_TPL_08_default_budget_from_template(self):
        """[FT] Budget defaults to the template's suggested budget when left blank"""
        t = self.c.post("/api/templates/1/use", json=dict(origin="X", start_date="2027-03-01", travelers=2, budget="")).get_json()
        self.assertEqual(t["budget"], self.c.get("/api/templates/1").get_json()["suggested_budget"])

class Activities(Base):
    def test_ACT_01_crud(self):
        """[FT] Add, view, edit and delete an activity"""
        t = self.trip()["id"]; a = self.act(t, description="fun").get_json()
        self.assertEqual(self.c.get(f"/api/trips/{t}/activities").get_json()[0]["name"], "Beach")
        self.assertEqual(self.c.put(f"/api/activities/{a['id']}", json={**ACT, "name": "Fort"}).get_json()["name"], "Fort")
        self.assertEqual(self.c.delete(f"/api/activities/{a['id']}").status_code, 200); self.assertEqual(self.c.get(f"/api/trips/{t}/activities").get_json(), [])
    def test_ACT_02_chronological_order(self):
        """[FT] Activities are listed by date then time"""
        t = self.trip()["id"]; self.act(t, name="B", date="2026-12-03", time="08:00"); self.act(t, name="C", time="14:00"); self.act(t, name="A", time="09:00")
        self.assertEqual([a["name"] for a in self.c.get(f"/api/trips/{t}/activities").get_json()], ["A", "C", "B"])
    def test_ACT_03_date_within_trip(self):
        """[BVA] Activity date: day before start 400, start 201, end 201, day after end 400"""
        t = self.trip()["id"]
        for d, code in (("2026-11-30", 400), ("2026-12-01", 201), ("2026-12-05", 201), ("2026-12-06", 400)): self.assertEqual(self.act(t, date=d).status_code, code, d)
    def test_ACT_04_cost_rules(self):
        """[BVA] Cost -0.01 / text / blank rejected; 0 accepted"""
        t = self.trip()["id"]
        for v, code in ((-0.01, 400), ("abc", 400), ("", 400), (0, 201)): self.assertEqual(self.act(t, cost=v).status_code, code, v)
    def test_ACT_05_required_and_time(self):
        """[VT] Blank name/location and invalid time give field errors"""
        t = self.trip()["id"]; e = self.act(t, name="", location=" ", time="25:99").get_json()["errors"]; self.assertTrue({"name", "location", "time"} <= set(e))
    def test_ACT_06_trip_dates_vs_activities(self):
        """[IT] Shrinking trip dates past an existing activity is rejected"""
        t = self.trip()["id"]; self.act(t, date="2026-12-05"); self.assertEqual(self.c.put(f"/api/trips/{t}", json={**TRIP, "end_date": "2026-12-04"}).status_code, 400)
    def test_ACT_07_estimated_cost_recalculates(self):
        """[IT] Estimated activity cost updates after add, edit, delete"""
        t = self.trip()["id"]; est = lambda: self.bud(t)["estimated_activity_cost"]; self.assertEqual(est(), 0)
        a = self.act(t, cost=500.5).get_json(); self.act(t, cost=1000); self.assertEqual(est(), 1500.5)
        self.c.put(f"/api/activities/{a['id']}", json={**ACT, "cost": 200}); self.assertEqual(est(), 1200)
        self.c.delete(f"/api/activities/{a['id']}"); self.assertEqual(est(), 1000)
    def test_ACT_08_missing_activity(self):
        """[EG] Unknown activity / trip -> 404"""
        self.assertEqual(self.c.put("/api/activities/999", json=ACT).status_code, 404); self.assertEqual(self.c.delete("/api/activities/999").status_code, 404)
        self.assertEqual(self.act(999).status_code, 404)

class Approval(Base):
    def test_APR_01_submit(self):
        """[ST] Draft + activity -> Pending Approval with submission record and timestamp"""
        t = self.trip()["id"]; self.act(t); r = self.submit(t); g = r.get_json()
        self.assertEqual((r.status_code, g["status"]), (200, "Pending Approval")); self.assertTrue(g["submitted_at"]); self.assertEqual(g["approvals"][0]["action"], "Submitted")
    def test_APR_02_submit_needs_activity(self):
        """[VT] Submitting an itinerary with no activities is rejected"""
        t = self.trip()["id"]; self.assertEqual(self.submit(t).status_code, 400); self.assertEqual(self.status(t), "Draft")
    def test_APR_03_approve(self):
        """[ST] Approve: status Approved, feedback + decision time + reviewer stored"""
        t = self.pending(); r = self.approve(t, feedback="Looks good"); g = r.get_json(); a = g["approvals"][-1]
        self.assertEqual((r.status_code, g["status"], a["action"], a["feedback"]), (200, "Approved", "Approved", "Looks good")); self.assertTrue(g["decided_at"] and a["created_at"] and "simulated" in a["actor"])
    def test_APR_04_reject_requires_reason(self):
        """[VT] Reject with missing / blank reason -> 400 and trip stays Pending Approval"""
        t = self.pending()
        for body in ({}, {"reason": ""}, {"reason": "   "}, {"feedback": "only feedback"}): self.assertEqual(self.reject(t, **body).status_code, 400, body)
        self.assertEqual(self.status(t), "Pending Approval")
    def test_APR_05_reject_stores_reason_feedback(self):
        """[ST] Reject: reason and feedback stored and visible"""
        t = self.pending(); g = self.reject(t, reason="Too expensive", feedback="Cut hotel cost").get_json()
        self.assertEqual((g["status"], g["last_reason"], g["last_feedback"], g["last_decision"]), ("Rejected", "Too expensive", "Cut hotel cost", "Rejected"))
    def test_APR_06_rejected_editable_and_resubmittable(self):
        """[ST] Rejected itinerary can be edited, then resubmitted, then approved"""
        t = self.pending(); self.reject(t, reason="Fix dates")
        self.assertEqual(self.c.put(f"/api/trips/{t}", json={**TRIP, "end_date": "2026-12-06"}).status_code, 200); self.assertEqual(self.act(t, date="2026-12-06").status_code, 201)
        self.assertEqual(self.status(t), "Rejected"); self.assertEqual(self.submit(t).get_json()["status"], "Pending Approval")
        self.assertEqual(self.approve(t).get_json()["status"], "Approved")
    def test_APR_07_invalid_transitions(self):
        """[ST] Approve/reject/submit from the wrong state -> 409 and status unchanged"""
        d = self.trip()["id"]; self.act(d)
        self.assertEqual(self.approve(d).status_code, 409); self.assertEqual(self.reject(d, reason="x").status_code, 409)
        p = self.pending(); self.assertEqual(self.submit(p).status_code, 409)
        a = self.approved(); self.assertEqual(self.submit(a).status_code, 409); self.assertEqual(self.approve(a).status_code, 409); self.assertEqual(self.reject(a, reason="x").status_code, 409)
        r = self.pending(); self.reject(r, reason="x"); self.assertEqual(self.approve(r).status_code, 409); self.assertEqual(self.reject(r, reason="y").status_code, 409)
        self.assertEqual([self.status(i) for i in (d, p, a, r)], ["Draft", "Pending Approval", "Approved", "Rejected"])
    def test_APR_08_pending_is_locked(self):
        """[ST] While pending, trip edit and activity add/edit/delete are blocked"""
        t = self.trip()["id"]; a = self.act(t).get_json(); self.submit(t)
        self.assertEqual(self.c.put(f"/api/trips/{t}", json=TRIP).status_code, 409); self.assertEqual(self.act(t).status_code, 409)
        self.assertEqual(self.c.put(f"/api/activities/{a['id']}", json=ACT).status_code, 409); self.assertEqual(self.c.delete(f"/api/activities/{a['id']}").status_code, 409)
    def test_APR_09_material_trip_changes_require_reapproval(self):
        """[ST] Changing destination/origin/dates/travellers/budget of an Approved trip -> Draft + reset record"""
        for k, v in (("destination", "Pune"), ("origin", "Mumbai"), ("start_date", "2026-11-30"), ("end_date", "2026-12-06"), ("travelers", 5), ("budget", 70000)):
            t = self.approved(); r = self.c.put(f"/api/trips/{t}", json={**TRIP, k: v}).get_json()
            self.assertEqual((r["status"], r["approval_reset"]), ("Draft", True), k); self.assertEqual(r["approvals"][-1]["action"], "Reset to Draft")
    def test_APR_10_non_material_changes_keep_approval(self):
        """[ST] Changing title / preferences / notes keeps Approved status"""
        t = self.approved(); r = self.c.put(f"/api/trips/{t}", json={**TRIP, "title": "New name", "notes": "bring hats", "preferences": "veg"}).get_json()
        self.assertEqual((r["status"], r["approval_reset"]), ("Approved", False))
    def test_APR_11_material_activity_changes(self):
        """[ST] Add/delete/edit(name,date,time,location,cost) on Approved -> Draft; description-only edit keeps Approved"""
        t = self.approved(); self.assertEqual(self.act(t).get_json()["approval_reset"], True); self.assertEqual(self.status(t), "Draft")
        t = self.approved(); aid = self.get(t)["activities"][0]["id"]; self.assertTrue(self.c.delete(f"/api/activities/{aid}").get_json()["approval_reset"])
        for k, v in (("name", "Other"), ("date", "2026-12-03"), ("time", "10:00"), ("location", "Elsewhere"), ("cost", 999)):
            t = self.approved(); aid = self.get(t)["activities"][0]["id"]
            self.assertTrue(self.c.put(f"/api/activities/{aid}", json={**ACT, k: v}).get_json()["approval_reset"], k)
        t = self.approved(); aid = self.get(t)["activities"][0]["id"]
        self.assertFalse(self.c.put(f"/api/activities/{aid}", json={**ACT, "description": "just a note"}).get_json()["approval_reset"]); self.assertEqual(self.status(t), "Approved")
    def test_APR_12_reapproval_cycle(self):
        """[ST] Approved -> material change -> Draft -> submit -> approve again, with full history"""
        t = self.approved(); self.c.put(f"/api/trips/{t}", json={**TRIP, "destination": "Pune"}); self.assertEqual(self.submit(t).get_json()["status"], "Pending Approval")
        g = self.approve(t).get_json(); self.assertEqual(g["status"], "Approved")
        self.assertEqual([a["action"] for a in g["approvals"]], ["Submitted", "Approved", "Reset to Draft", "Submitted", "Approved"])
    def test_APR_13_review_queue_and_history(self):
        """[FT] Pending list shows only pending trips; history shows decisions newest first with reason/feedback"""
        d = self.trip()["id"]; p = self.pending(); a = self.approved(); r = self.pending(); self.reject(r, reason="No", feedback="fb")
        self.assertEqual([x["id"] for x in self.c.get("/api/review/pending").get_json()], [p])
        h = self.c.get("/api/review/history").get_json(); self.assertEqual([x["action"] for x in h], ["Rejected", "Approved"]); self.assertEqual((h[0]["reason"], h[0]["feedback"]), ("No", "fb"))
    def test_APR_14_decision_unknown_trip_or_bad_body(self):
        """[EG] Decision on unknown trip -> 404; malformed JSON -> 400 and no state change"""
        self.assertEqual(self.approve(999).status_code, 404); t = self.pending()
        self.assertEqual(self.c.post(f"/api/review/{t}/approve", data="{oops", content_type="application/json").status_code, 400); self.assertEqual(self.status(t), "Pending Approval")

class Bookings(Base):
    def test_BKG_01_all_five_service_types(self):
        """[FT] Flight, Train, Bus, Hotel, Local Transport can each be created; multiple bookings per trip"""
        t = self.approved()
        for s, k in (("Flight", {}), ("Train", {}), ("Bus", {}), ("Local Transport", {}), ("Hotel", HOTEL)): self.assertEqual(self.book(t, **{**k, "service_type": s}).status_code, 201, s)
        self.assertEqual(len(self.c.get(f"/api/bookings?trip_id={t}").get_json()), 5)
    def test_BKG_02_blocked_unless_approved(self):
        """[ST] Booking is blocked (409) for Draft, Pending and Rejected itineraries"""
        d = self.trip()["id"]; self.act(d); self.assertEqual(self.book(d).status_code, 409)
        self.submit(d); self.assertEqual(self.book(d).status_code, 409); self.reject(d, reason="no"); self.assertEqual(self.status(d), "Rejected"); self.assertEqual(self.book(d).status_code, 409)
        self.assertEqual(self.c.get("/api/bookings").get_json(), [])
    def test_BKG_03_allowed_after_approval_and_blocked_after_reset(self):
        """[ST] Allowed once approved; blocked again after a material change resets approval"""
        t = self.approved(); self.assertEqual(self.book(t).status_code, 201); self.c.put(f"/api/trips/{t}", json={**TRIP, "destination": "Pune"}); self.assertEqual(self.book(t).status_code, 409)
    def test_BKG_04_trip_must_exist(self):
        """[VT] Missing / unknown / non-numeric trip id -> 400"""
        for v in (None, 999, "abc", ""): self.assertEqual(self.c.post("/api/bookings", json={**BK, "trip_id": v}).status_code, 400, v)
    def test_BKG_05_field_validation(self):
        """[EP] Invalid price, type, status, missing provider/traveller/from, bad dates, bad count are rejected"""
        t = self.approved()
        for k in (dict(price=-1), dict(price="x"), dict(price=""), dict(service_type="Boat"), dict(status="Cancelled"), dict(status="Done"), dict(provider=""), dict(traveler_name=" "),
                  dict(from_location=""), dict(to_location=""), dict(travel_date=""), dict(end_date="2026-11-01"), dict(travelers_count=0), dict(travelers_count="x"), dict(booking_date="bad")):
            self.assertEqual(self.book(t, **k).status_code, 400, k)
        self.assertEqual(self.book(t, price=0).status_code, 201)
    def test_BKG_06_hotel_rules(self):
        """[BVA] Hotel needs check-out after check-in; from-location not required"""
        t = self.approved()
        for k, code in ((dict(end_date=None), 400), (dict(end_date="2026-12-01"), 400), (dict(end_date="2026-12-02"), 201)): self.assertEqual(self.book(t, **{**HOTEL, **k}).status_code, code, k)
    def test_BKG_07_reference(self):
        """[FT] Reference auto-generated (DEMO-...) when blank, kept when supplied"""
        t = self.approved(); self.assertTrue(self.book(t, reference="").get_json()["reference"].startswith("DEMO-FL-")); self.assertEqual(self.book(t, reference="PNR9").get_json()["reference"], "PNR9")
    def test_BKG_08_view_and_edit(self):
        """[FT] View and edit a booking; trip approval status shown"""
        t = self.approved(); b = self.book(t).get_json(); g = self.c.get(f"/api/bookings/{b['id']}").get_json(); self.assertEqual((g["trip_status"], g["provider"]), ("Approved", "IndiGo"))
        r = self.c.put(f"/api/bookings/{b['id']}", json={**BK, "price": 7000, "provider": "Air India"}).get_json(); self.assertEqual((r["price"], r["provider"]), (7000, "Air India"))
    def test_BKG_09_edit_blocked_when_not_approved(self):
        """[ST] Existing booking cannot be edited while its itinerary is not Approved"""
        t = self.approved(); b = self.book(t).get_json(); self.c.put(f"/api/trips/{t}", json={**TRIP, "destination": "Pune"})
        self.assertEqual(self.c.put(f"/api/bookings/{b['id']}", json=BK).status_code, 409)
    def test_BKG_10_cancel_keeps_history(self):
        """[FT] Cancel keeps the record, sets cancelled_at; second cancel 409; edit of cancelled 409"""
        t = self.approved(); b = self.book(t).get_json(); g = self.c.post(f"/api/bookings/{b['id']}/cancel").get_json()
        self.assertEqual(g["status"], "Cancelled"); self.assertTrue(g["cancelled_at"]); self.assertEqual(len(self.c.get("/api/bookings").get_json()), 1)
        self.assertEqual(self.c.post(f"/api/bookings/{b['id']}/cancel").status_code, 409); self.assertEqual(self.c.put(f"/api/bookings/{b['id']}", json=BK).status_code, 409)
    def test_BKG_11_cancel_allowed_when_trip_not_approved(self):
        """[ST] A booking can still be cancelled after its itinerary loses approval"""
        t = self.approved(); b = self.book(t).get_json(); self.c.put(f"/api/trips/{t}", json={**TRIP, "destination": "Pune"})
        self.assertEqual(self.c.post(f"/api/bookings/{b['id']}/cancel").status_code, 200)
    def test_BKG_12_filters(self):
        """[FT] Filter bookings by trip, service type and status"""
        a, b = self.approved(), self.approved(title="Two"); self.book(a); self.book(a, service_type="Bus", status="Pending"); self.book(b, service_type="Bus")
        n = lambda q: len(self.c.get("/api/bookings?" + q).get_json())
        self.assertEqual((n(f"trip_id={a}"), n("service_type=Bus"), n("status=Pending"), n(f"trip_id={a}&service_type=Bus"), n("trip_id=999")), (2, 2, 1, 1, 0))
    def test_BKG_13_cancel_status_via_put_rejected(self):
        """[EG] Cannot set status Cancelled through edit; missing booking -> 404"""
        t = self.approved(); b = self.book(t).get_json(); self.assertEqual(self.c.put(f"/api/bookings/{b['id']}", json={**BK, "status": "Cancelled"}).status_code, 400)
        for m, u in (("get", "/api/bookings/999"), ("post", "/api/bookings/999/cancel")): self.assertEqual(getattr(self.c, m)(u).status_code, 404)

class Budget(Base):
    def test_BUD_01_empty_trip(self):
        """[FT] New trip: everything 0, remaining = planned budget, no warnings"""
        b = self.bud(self.trip()["id"]); self.assertEqual((b["planned_budget"], b["actual_expenses"], b["active_booking_cost"], b["remaining_budget"], b["warnings"]), (50000, 0, 0, 50000, []))
    def test_BUD_02_active_bookings_exclude_cancelled(self):
        """[FT] Active booking cost counts Pending+Confirmed and excludes Cancelled"""
        t = self.approved(); self.book(t, price=1000); self.book(t, price=2000.5, status="Pending"); c = self.book(t, price=4000).get_json(); self.c.post(f"/api/bookings/{c['id']}/cancel")
        self.assertEqual(self.bud(t)["active_booking_cost"], 3000.5)
    def test_BUD_03_remaining_is_budget_minus_actual(self):
        """[FT] Remaining = planned budget - recorded actual expenses (bookings alone do not reduce it)"""
        t = self.approved(); self.book(t, price=10000); self.assertEqual(self.bud(t)["remaining_budget"], 50000); self.exp(t, amount=1200.5); self.exp(t, description="Taxi", amount=300)
        b = self.bud(t); self.assertEqual((b["actual_expenses"], b["remaining_budget"]), (1500.5, 48499.5))
    def test_BUD_04_no_double_counting(self):
        """[IT] Recording a booking as an expense moves it from 'unrecorded' to 'actual'; projected total stays 1000"""
        t = self.approved(); b = self.book(t, price=1000).get_json(); x = self.bud(t); self.assertEqual((x["actual_expenses"], x["unrecorded_booking_cost"], x["projected_total"]), (0, 1000, 1000))
        e = self.c.post(f"/api/bookings/{b['id']}/record-expense"); self.assertEqual((e.status_code, e.get_json()["amount"], e.get_json()["category"]), (201, 1000, "Flight"))
        x = self.bud(t); self.assertEqual((x["actual_expenses"], x["unrecorded_booking_cost"], x["projected_total"], x["active_booking_cost"]), (1000, 0, 1000, 1000))
    def test_BUD_05_record_expense_rules(self):
        """[ST] Duplicate / Pending / Cancelled / zero-price bookings cannot be recorded as expenses"""
        t = self.approved(); b = self.book(t).get_json(); self.assertEqual(self.c.post(f"/api/bookings/{b['id']}/record-expense").status_code, 201); self.assertEqual(self.c.post(f"/api/bookings/{b['id']}/record-expense").status_code, 409)
        p = self.book(t, status="Pending").get_json(); self.assertEqual(self.c.post(f"/api/bookings/{p['id']}/record-expense").status_code, 409)
        z = self.book(t, price=0).get_json(); self.assertEqual(self.c.post(f"/api/bookings/{z['id']}/record-expense").status_code, 409)
        c = self.book(t).get_json(); self.c.post(f"/api/bookings/{c['id']}/cancel"); self.assertEqual(self.c.post(f"/api/bookings/{c['id']}/record-expense").status_code, 409); self.assertEqual(self.c.post("/api/bookings/999/record-expense").status_code, 404)
    def test_BUD_06_duplicate_manual_expense(self):
        """[EG] Identical expense rejected (case-insensitive); different date/amount accepted"""
        t = self.trip()["id"]; self.assertEqual(self.exp(t).status_code, 201); self.assertEqual(self.exp(t, description="LUNCH").status_code, 409)
        self.assertEqual(self.exp(t, expense_date="2026-12-03").status_code, 201); self.assertEqual(self.exp(t, amount=501).status_code, 201)
    def test_BUD_07_expense_validation(self):
        """[BVA] Amount 0 / negative / text, bad category, blank description, bad date rejected; 0.01 accepted"""
        t = self.trip()["id"]
        for k in (dict(amount=0), dict(amount=-1), dict(amount="x"), dict(category="Gold"), dict(description=" "), dict(expense_date="31-12-2026")): self.assertEqual(self.exp(t, **k).status_code, 400, k)
        self.assertEqual(self.exp(t, amount=0.01).status_code, 201)
    def test_BUD_08_edit_delete_expense(self):
        """[FT] Editing and deleting expenses updates totals; edit cannot create a duplicate"""
        t = self.trip()["id"]; a = self.exp(t).get_json(); self.exp(t, description="Dinner", amount=800)
        self.assertEqual(self.c.put(f"/api/expenses/{a['id']}", json={**a, "amount": 700}).status_code, 200); self.assertEqual(self.bud(t)["actual_expenses"], 1500)
        self.assertEqual(self.c.put(f"/api/expenses/{a['id']}", json={**a, "description": "Dinner", "amount": 800}).status_code, 409)
        self.c.delete(f"/api/expenses/{a['id']}"); self.assertEqual(self.bud(t)["actual_expenses"], 800); self.assertEqual(self.c.put("/api/expenses/999", json=a).status_code, 404)
    def test_BUD_09_category_breakdown(self):
        """[FT] Breakdown by category sums correctly, largest first"""
        t = self.trip()["id"]; self.exp(t, amount=100); self.exp(t, description="Dinner", amount=250); self.exp(t, category="Hotel", description="Stay", amount=900)
        self.assertEqual(self.bud(t)["by_category"], [{"category": "Hotel", "amount": 900}, {"category": "Food", "amount": 350}])
    def test_BUD_10_warnings(self):
        """[BVA] No warning at exactly the budget; warnings when actual, projected or estimated costs exceed it"""
        t = self.trip(budget=1000)["id"]; self.exp(t, amount=1000); self.assertEqual(self.bud(t)["warnings"], []); self.exp(t, description="More", amount=0.01)
        b = self.bud(t); self.assertTrue(b["over_budget"] and "Actual expenses exceed" in b["warnings"][0]); self.assertEqual(b["remaining_budget"], -0.01)
        a = self.approved(budget=1000); self.book(a, price=1500); self.assertIn("unrecorded active bookings", self.bud(a)["warnings"][0])
        e = self.trip(budget=100)["id"]; self.act(e, cost=101); self.assertIn("Estimated activity costs", self.bud(e)["warnings"][0])
    def test_BUD_11_dashboard_numbers(self):
        """[IT] Dashboard counts and totals match the underlying data; no data -> zeros"""
        z = self.c.get("/api/dashboard").get_json(); self.assertEqual((z["trips_total"], z["pending_approvals"], z["bookings"]["total"], z["totals"]["planned_budget"], z["upcoming"]), (0, 0, 0, 0, []))
        a = self.approved(start_date="2030-01-01", end_date="2030-01-05", budget=1000, _ad="2030-01-02"); self.pending(); self.trip()
        b = self.book(a, price=300, travel_date="2030-01-01").get_json(); self.book(a, price=200); self.c.post(f"/api/bookings/{b['id']}/cancel"); self.exp(a, amount=1500)
        d = self.c.get("/api/dashboard").get_json()
        self.assertEqual((d["trips_total"], d["by_status"]["Approved"], d["by_status"]["Pending Approval"], d["by_status"]["Draft"], d["pending_approvals"]), (3, 1, 1, 1, 1))
        self.assertEqual((d["bookings"]["active"], d["bookings"]["cancelled"], d["totals"]["actual_expenses"], d["totals"]["active_booking_cost"]), (1, 1, 1500, 200)); self.assertEqual([x["id"] for x in d["over_budget_trips"]], [a])

class Errors(Base):
    def test_ERR_01_malformed_json(self):
        """[EG] Malformed JSON body -> 400 JSON error on every write endpoint"""
        t = self.approved()
        for u in ("/api/trips", f"/api/trips/{t}/activities", "/api/bookings", f"/api/trips/{t}/expenses", "/api/templates/1/use"):
            r = self.c.post(u, data="{bad json", content_type="application/json"); self.assertEqual(r.status_code, 400, u); self.assertIn("error", r.get_json())
    def test_ERR_02_non_object_body(self):
        """[EG] JSON array / string / null body -> 400"""
        for b in ([1, 2], "text", None): self.assertEqual(self.c.post("/api/trips", json=b).status_code, 400, b)
    def test_ERR_03_unknown_route_and_method(self):
        """[EG] Unknown route -> 404 JSON; wrong method -> 405 JSON"""
        r = self.c.get("/api/nothing"); self.assertEqual((r.status_code, "error" in r.get_json()), (404, True)); self.assertEqual(self.c.patch("/api/trips").status_code, 405)
    def test_ERR_04_overlong_text(self):
        """[BVA] Title of 120 characters accepted, 121 rejected"""
        self.assertEqual(self.c.post("/api/trips", json={**TRIP, "title": "a" * 120}).status_code, 201); self.assertEqual(self.c.post("/api/trips", json={**TRIP, "title": "a" * 121}).status_code, 400)
    def test_ERR_05_sql_injection_text_is_stored_literally(self):
        """[EG] SQL-like text is stored as plain text; tables survive; filters are parameterised"""
        evil = "x'); DROP TABLE trips;--"; t = self.trip(title=evil); self.assertEqual(self.get(t["id"])["title"], evil)
        self.assertEqual(self.c.get("/api/bookings?status=' OR '1'='1").get_json(), []); self.assertEqual(len(self.c.get("/api/trips").get_json()), 1)
    def test_ERR_06_wrong_types(self):
        """[EP] Numbers/objects where strings expected don't crash the server"""
        for k, v in (("title", 123), ("origin", ["a"]), ("destination", {"a": 1}), ("travelers", [2]), ("budget", {"x": 1})):
            self.assertIn(self.c.post("/api/trips", json={**TRIP, k: v}).status_code, (201, 400), k)
    def test_ERR_07_home_page_served(self):
        """[FT] Front-end page and assets are served"""
        self.assertEqual(self.c.get("/").status_code, 200)
        for f in ("app.js", "style.css"): self.assertEqual(self.c.get("/static/" + f).status_code, 200, f)

if __name__ == "__main__": unittest.main()
