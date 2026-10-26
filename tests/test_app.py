import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app

TRIP = dict(title="Goa Trip", destination="Goa", start_date="2026-12-01", end_date="2026-12-05", travelers=2, description="")
def act(**k): return {**dict(name="Beach", date="2026-12-02", time="09:30", location="Baga", description="", cost=500), **k}
def bk(tid, **k): return {**dict(trip_id=tid, category="Flight", provider="IndiGo", reference="AB123",
                                 booking_date="2026-11-01", travel_date="2026-12-01", price=5000, status="Confirmed", notes=""), **k}

class Base(unittest.TestCase):
    def setUp(self):
        fd, self.p = tempfile.mkstemp(suffix=".db"); os.close(fd)
        self.c = create_app(self.p).test_client()
    def tearDown(self): os.remove(self.p)
    def trip(self, **k): return self.c.post("/api/trips", json={**TRIP, **k}).get_json()

class Itinerary(Base):
    def test_ITN_01_create_trip(self):
        r = self.c.post("/api/trips", json=TRIP); self.assertEqual(r.status_code, 201)
    def test_ITN_02_required_fields(self):
        r = self.c.post("/api/trips", json={**TRIP, "title": " ", "destination": ""}); self.assertEqual(r.status_code, 400)
        self.assertIn("title", r.get_json()["errors"]); self.assertEqual(self.c.get("/api/trips").get_json(), [])
    def test_ITN_03_end_before_start(self):
        self.assertEqual(self.c.post("/api/trips", json={**TRIP, "end_date": "2026-11-30"}).status_code, 400)
    def test_ITN_04_same_day_trip_ok(self):
        self.assertEqual(self.c.post("/api/trips", json={**TRIP, "end_date": "2026-12-01"}).status_code, 201)
    def test_ITN_05_travelers_invalid(self):
        for bad in (0, -1, "2.5", "abc", "", None, True):
            self.assertEqual(self.c.post("/api/trips", json={**TRIP, "travelers": bad}).status_code, 400, bad)
    def test_ITN_06_travelers_boundary_1(self):
        self.assertEqual(self.c.post("/api/trips", json={**TRIP, "travelers": 1}).status_code, 201)
    def test_ITN_07_view_edit_delete_trip(self):
        t = self.trip(); i = t["id"]
        self.assertEqual(self.c.get(f"/api/trips/{i}").get_json()["title"], "Goa Trip")
        r = self.c.put(f"/api/trips/{i}", json={**TRIP, "title": "Goa 2"}); self.assertEqual(r.get_json()["title"], "Goa 2")
        self.assertEqual(self.c.delete(f"/api/trips/{i}").status_code, 200)
        self.assertEqual(self.c.get(f"/api/trips/{i}").status_code, 404)
    def test_ITN_08_activity_crud_and_order(self):
        i = self.trip()["id"]
        self.c.post(f"/api/trips/{i}/activities", json=act(name="B", date="2026-12-03", time="08:00"))
        self.c.post(f"/api/trips/{i}/activities", json=act(name="C", time="14:00"))
        self.c.post(f"/api/trips/{i}/activities", json=act(name="A", time="09:00"))
        self.assertEqual([a["name"] for a in self.c.get(f"/api/trips/{i}/activities").get_json()], ["A", "C", "B"])
    def test_ITN_09_activity_date_range(self):
        i = self.trip()["id"]
        for d, code in (("2026-11-30", 400), ("2026-12-06", 400), ("2026-12-01", 201), ("2026-12-05", 201)):
            self.assertEqual(self.c.post(f"/api/trips/{i}/activities", json=act(date=d)).status_code, code, d)
    def test_ITN_10_activity_cost_rules(self):
        i = self.trip()["id"]
        for cost, code in ((-1, 400), (-0.01, 400), (0, 201), ("abc", 400), ("", 400)):
            self.assertEqual(self.c.post(f"/api/trips/{i}/activities", json=act(cost=cost)).status_code, code, cost)
    def test_ITN_11_activity_required_and_time(self):
        i = self.trip()["id"]
        r = self.c.post(f"/api/trips/{i}/activities", json=act(name="", time="25:99")); e = r.get_json()["errors"]
        self.assertEqual(r.status_code, 400); self.assertIn("name", e); self.assertIn("time", e)
    def test_ITN_12_expense_recalculation(self):
        i = self.trip()["id"]; est = lambda: self.c.get(f"/api/trips/{i}").get_json()["est_cost"]
        self.assertEqual(est(), 0)
        a = self.c.post(f"/api/trips/{i}/activities", json=act(cost=500.50)).get_json()
        self.c.post(f"/api/trips/{i}/activities", json=act(cost=1000))
        self.assertEqual(est(), 1500.50)
        self.c.put(f"/api/activities/{a['id']}", json=act(cost=200)); self.assertEqual(est(), 1200)
        self.c.delete(f"/api/activities/{a['id']}"); self.assertEqual(est(), 1000)
    def test_ITN_13_trip_edit_blocked_by_activities(self):
        i = self.trip()["id"]; self.c.post(f"/api/trips/{i}/activities", json=act(date="2026-12-05"))
        self.assertEqual(self.c.put(f"/api/trips/{i}", json={**TRIP, "end_date": "2026-12-04"}).status_code, 400)
    def test_ITN_14_delete_trip_removes_activities(self):
        i = self.trip()["id"]; self.c.post(f"/api/trips/{i}/activities", json=act())
        self.c.delete(f"/api/trips/{i}"); self.assertEqual(self.c.get(f"/api/trips/{i}/activities").status_code, 404)

class Booking(Base):
    def test_BKG_01_create_view(self):
        i = self.trip()["id"]; r = self.c.post("/api/bookings", json=bk(i)); self.assertEqual(r.status_code, 201)
        self.assertEqual(self.c.get(f"/api/bookings/{r.get_json()['id']}").get_json()["provider"], "IndiGo")
    def test_BKG_02_invalid_trip(self):
        self.assertEqual(self.c.post("/api/bookings", json=bk(999)).status_code, 400)
        self.assertEqual(self.c.post("/api/bookings", json=bk(None)).status_code, 400)
    def test_BKG_03_price_rules(self):
        i = self.trip()["id"]
        for p, code in ((-1, 400), ("x", 400), ("", 400), (0, 201)):
            self.assertEqual(self.c.post("/api/bookings", json=bk(i, price=p)).status_code, code, p)
    def test_BKG_04_category_status_required(self):
        i = self.trip()["id"]
        for k in (dict(category="Bus"), dict(status="Done"), dict(provider=""), dict(reference=" "), dict(travel_date="")):
            self.assertEqual(self.c.post("/api/bookings", json=bk(i, **k)).status_code, 400, k)
    def test_BKG_05_edit_booking(self):
        i = self.trip()["id"]; b = self.c.post("/api/bookings", json=bk(i)).get_json()
        r = self.c.put(f"/api/bookings/{b['id']}", json=bk(i, price=7000, category="Train")).get_json()
        self.assertEqual((r["price"], r["category"]), (7000, "Train"))
    def test_BKG_06_cancel_keeps_record(self):
        i = self.trip()["id"]; b = self.c.post("/api/bookings", json=bk(i)).get_json()
        self.assertEqual(self.c.post(f"/api/bookings/{b['id']}/cancel").get_json()["status"], "Cancelled")
        self.assertEqual(len(self.c.get("/api/bookings").get_json()), 1)
    def test_BKG_07_expense_rules(self):
        i = self.trip()["id"]
        for p, s in ((1000, "Confirmed"), (2000.50, "Confirmed"), (500, "Pending"), (4000, "Cancelled")):
            self.c.post("/api/bookings", json=bk(i, price=p, status=s))
        s = self.c.get("/api/bookings/summary").get_json()
        self.assertEqual((s["total_value"], s["confirmed_total"], s["pending_total"], s["cancelled_total"]),
                         (7500.50, 3000.50, 500, 4000))
    def test_BKG_08_cancel_updates_confirmed_total(self):
        i = self.trip()["id"]; b = self.c.post("/api/bookings", json=bk(i, price=1000)).get_json()
        self.c.post(f"/api/bookings/{b['id']}/cancel")
        self.assertEqual(self.c.get("/api/bookings/summary").get_json()["confirmed_total"], 0)
    def test_BKG_09_filters_and_trip_summary(self):
        a, b = self.trip()["id"], self.trip(title="Manali")["id"]
        self.c.post("/api/bookings", json=bk(a, price=100)); self.c.post("/api/bookings", json=bk(a, category="Hotel", status="Pending", price=200))
        self.c.post("/api/bookings", json=bk(b, category="Cab", price=50))
        n = lambda q: len(self.c.get("/api/bookings?" + q).get_json())
        self.assertEqual((n(f"trip_id={a}"), n("category=Hotel"), n("status=Confirmed"), n(f"trip_id={a}&status=Pending")), (2, 1, 2, 1))
        self.assertEqual(self.c.get(f"/api/bookings/summary?trip_id={a}").get_json()["total_value"], 300)
    def test_BKG_10_trip_with_bookings_cannot_be_deleted(self):
        i = self.trip()["id"]; self.c.post("/api/bookings", json=bk(i))
        self.assertEqual(self.c.delete(f"/api/trips/{i}").status_code, 409)

if __name__ == "__main__": unittest.main()
