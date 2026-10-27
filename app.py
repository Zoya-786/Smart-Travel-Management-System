"""Smart Travel Management System - Itinerary Management + Travel Booking (Flask + SQLite).
All business rules (validation, approval workflow, budget maths) are enforced here, not in the browser."""
import os, sqlite3, secrets
from datetime import date, datetime, timedelta, timezone
from flask import Flask, jsonify, request, g, send_from_directory
from schema import init_db
import validators as V

REVIEWER = "Demo Reviewer (simulated)"
STATUSES = ("Draft", "Pending Approval", "Approved", "Rejected")
MATERIAL_TRIP = ("origin", "destination", "start_date", "end_date", "travelers")
PREFIX = {"Flight": "FL", "Train": "TR", "Bus": "BU", "Hotel": "HT", "Local Transport": "LT"}
TRIP_Q = """SELECT t.*, COALESCE((SELECT ROUND(SUM(cost),2) FROM activities WHERE trip_id=t.id),0) AS est_cost,
 (SELECT COUNT(*) FROM activities WHERE trip_id=t.id) AS activity_count,
 (SELECT action FROM approvals WHERE trip_id=t.id AND action IN ('Approved','Rejected') ORDER BY id DESC LIMIT 1) AS last_decision,
 (SELECT reason FROM approvals WHERE trip_id=t.id AND action IN ('Approved','Rejected') ORDER BY id DESC LIMIT 1) AS last_reason,
 (SELECT feedback FROM approvals WHERE trip_id=t.id AND action IN ('Approved','Rejected') ORDER BY id DESC LIMIT 1) AS last_feedback
 FROM trips t"""
BK_Q = """SELECT b.*, t.title trip_title, t.status trip_status,
 EXISTS(SELECT 1 FROM expenses e WHERE e.booking_id=b.id) AS expense_recorded FROM bookings b JOIN trips t ON t.id=b.trip_id"""

def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

def create_app(db_path=None):
    app = Flask(__name__, static_folder="static")
    path = db_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "tms.db")
    init_db(path)

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(path); g.db.row_factory = sqlite3.Row; g.db.execute("PRAGMA foreign_keys=ON")
        return g.db
    def run(sql, a=()): return db().execute(sql, a)
    def rows(sql, a=()): return [dict(r) for r in db().execute(sql, a)]
    def row(sql, a=()):
        r = db().execute(sql, a).fetchone(); return dict(r) if r else None

    @app.teardown_appcontext
    def _close(_):
        d = g.pop("db", None)
        if d: d.close()
    @app.after_request
    def _finish(r):                       # one transaction per request: commit on success, roll back on any error
        d = g.get("db")
        if d: d.commit() if r.status_code < 400 else d.rollback()
        return r

    def err(msg, code): return jsonify(error=msg), code
    def bad(e): return jsonify(errors=e), 400
    def body(optional=False):
        if optional and not request.get_data(): return {}
        x = request.get_json(silent=True); return x if isinstance(x, dict) else None
    def badbody(): return err("Request body must be a valid JSON object.", 400)
    def nf(what): return err(f"{what} not found.", 404)

    @app.errorhandler(404)
    def _404(_): return nf("Resource")
    @app.errorhandler(405)
    def _405(_): return err("Method not allowed.", 405)
    @app.errorhandler(sqlite3.IntegrityError)
    def _ie(_): return err("The change conflicts with related records (database constraint).", 409)
    @app.errorhandler(sqlite3.Error)
    def _se(_): return err("Database error. Please try again.", 500)

    # ---------- shared rules ----------
    def touch(i): run("UPDATE trips SET updated_at=? WHERE id=?", (now(), i))
    def locked(t):
        if t["status"] == "Pending Approval":
            return err("This itinerary is locked while it is pending agency review.", 409)
    def maybe_reset(t, why):
        """Approved itineraries that are materially changed go back to Draft and need approval again."""
        if t["status"] != "Approved": return False
        run("UPDATE trips SET status='Draft' WHERE id=?", (t["id"],))
        run("INSERT INTO approvals(trip_id,action,reason,feedback,actor,created_at) VALUES(?,?,?,?,?,?)",
            (t["id"], "Reset to Draft", why, "", "System", now()))
        return True
    def need_approved(t):
        msg = {"Draft": "Submit the itinerary for approval before booking travel services.",
               "Pending Approval": "Booking is blocked while the itinerary is pending agency approval.",
               "Rejected": "Booking is blocked because the itinerary was rejected. Revise and resubmit it."}.get(t["status"])
        if msg: return err(msg, 409)

    def budget(i):
        t = row("SELECT budget FROM trips WHERE id=?", (i,))
        one = lambda sql: round(row(sql, (i,))["v"], 2)
        est = one("SELECT COALESCE(SUM(cost),0) v FROM activities WHERE trip_id=?")
        active = one("SELECT COALESCE(SUM(price),0) v FROM bookings WHERE trip_id=? AND status!='Cancelled'")
        actual = one("SELECT COALESCE(SUM(amount),0) v FROM expenses WHERE trip_id=?")
        unrec = one("SELECT COALESCE(SUM(price),0) v FROM bookings b WHERE trip_id=? AND status!='Cancelled' "
                    "AND NOT EXISTS(SELECT 1 FROM expenses e WHERE e.booking_id=b.id)")
        planned = round(t["budget"], 2); projected = round(actual + unrec, 2)
        w = []
        if actual > planned: w.append(f"Actual expenses exceed the planned budget by {actual - planned:.2f}.")
        elif projected > planned: w.append(f"Actual expenses plus unrecorded active bookings exceed the planned budget by {projected - planned:.2f}.")
        if est > planned: w.append(f"Estimated activity costs exceed the planned budget by {est - planned:.2f}.")
        return dict(planned_budget=planned, estimated_activity_cost=est, active_booking_cost=active, actual_expenses=actual,
                    unrecorded_booking_cost=unrec, projected_total=projected, remaining_budget=round(planned - actual, 2),
                    by_category=rows("SELECT category, ROUND(SUM(amount),2) amount FROM expenses WHERE trip_id=? GROUP BY category ORDER BY amount DESC", (i,)),
                    warnings=w, over_budget=bool(w))

    def trip_full(i):
        t = row(TRIP_Q + " WHERE t.id=?", (i,))
        if t:
            t["activities"] = rows("SELECT * FROM activities WHERE trip_id=? ORDER BY date,time,id", (i,))
            t["approvals"] = rows("SELECT * FROM approvals WHERE trip_id=? ORDER BY id", (i,))
            t["budget_summary"] = budget(i)
        return t

    @app.get("/")
    def index(): return send_from_directory(app.static_folder, "index.html")

    # ---------- dashboard ----------
    @app.get("/api/dashboard")
    def dashboard():
        ts = rows("SELECT id,title,origin,destination,start_date,end_date,status,budget FROM trips ORDER BY start_date,id")
        by = {s: 0 for s in STATUSES}; tot = dict(planned_budget=0, actual_expenses=0, active_booking_cost=0, remaining_budget=0); over = []
        for t in ts:
            by[t["status"]] += 1; b = budget(t["id"])
            for k in tot: tot[k] += b[k]
            if b["over_budget"]: over.append(dict(id=t["id"], title=t["title"], warnings=b["warnings"]))
        today = date.today()
        up = [dict(t, days_until=(date.fromisoformat(t["start_date"]) - today).days) for t in ts if t["end_date"] >= today.isoformat()][:5]
        bk = row("SELECT COALESCE(SUM(status!='Cancelled'),0) active, COALESCE(SUM(status='Cancelled'),0) cancelled, COUNT(*) total FROM bookings")
        return jsonify(trips_total=len(ts), by_status=by, pending_approvals=by["Pending Approval"], upcoming=up, bookings=bk,
                       totals={k: round(v, 2) for k, v in tot.items()}, over_budget_trips=over,
                       templates_available=row("SELECT COUNT(*) n FROM templates")["n"])

    # ---------- templates ----------
    @app.get("/api/templates")
    def tpl_list():
        w, a = ("WHERE category=?", [request.args["category"]]) if request.args.get("category") else ("", [])
        return jsonify(rows(f"""SELECT t.*, (SELECT COUNT(*) FROM template_activities WHERE template_id=t.id) activity_count,
            (SELECT COALESCE(SUM(cost),0) FROM template_activities WHERE template_id=t.id) est_cost FROM templates t {w} ORDER BY t.id""", a))
    @app.get("/api/templates/<int:i>")
    def tpl_get(i):
        t = row("SELECT * FROM templates WHERE id=?", (i,))
        if not t: return nf("Template")
        t["activities"] = rows("SELECT * FROM template_activities WHERE template_id=? ORDER BY day_number,start_time,id", (i,))
        t["est_cost"] = round(sum(a["cost"] for a in t["activities"]), 2)
        return jsonify(t)

    @app.post("/api/templates/<int:i>/use")
    def tpl_use(i):
        tpl = row("SELECT * FROM templates WHERE id=?", (i,))
        if not tpl: return nf("Template")
        x = body()
        if x is None: return badbody()
        sd = V.pd(x.get("start_date"))
        x = dict(x, title=x.get("title") or tpl["title"], destination=x.get("destination") or tpl["destination"],
                 budget=tpl["suggested_budget"] if x.get("budget") in (None, "") else x.get("budget"),
                 end_date=(sd + timedelta(days=tpl["duration_days"] - 1)).isoformat() if sd else "")
        v, e = V.clean_trip(x)
        if e: return bad(e)
        ts = now()
        tid = run("INSERT INTO trips(title,origin,destination,start_date,end_date,travelers,budget,preferences,notes,status,template_id,created_at,updated_at)"
                  " VALUES(?,?,?,?,?,?,?,?,?,'Draft',?,?,?)",
                  (v["title"], v["origin"], v["destination"], v["start_date"], v["end_date"], v["travelers"], v["budget"],
                   v["preferences"], v["notes"], i, ts, ts)).lastrowid
        for a in rows("SELECT * FROM template_activities WHERE template_id=?", (i,)):     # independent copies
            run("INSERT INTO activities(trip_id,name,date,time,location,description,cost) VALUES(?,?,?,?,?,?,?)",
                (tid, a["name"], (sd + timedelta(days=a["day_number"] - 1)).isoformat(), a["start_time"], a["location"],
                 f"From template: {tpl['title']} (day {a['day_number']})", a["cost"]))
        return jsonify(trip_full(tid)), 201

    # ---------- trips ----------
    @app.get("/api/trips")
    def trips():
        w, a = ("WHERE t.status=?", [request.args["status"]]) if request.args.get("status") else ("", [])
        return jsonify(rows(f"{TRIP_Q} {w} ORDER BY t.start_date, t.id", a))

    @app.post("/api/trips")
    def trip_add():
        x = body()
        if x is None: return badbody()
        v, e = V.clean_trip(x)
        if e: return bad(e)
        ts = now()
        i = run("INSERT INTO trips(title,origin,destination,start_date,end_date,travelers,budget,preferences,notes,status,created_at,updated_at)"
                " VALUES(:title,:origin,:destination,:start_date,:end_date,:travelers,:budget,:preferences,:notes,'Draft',:ts,:ts)",
                dict(v, ts=ts)).lastrowid
        return jsonify(trip_full(i)), 201

    @app.get("/api/trips/<int:i>")
    def trip_get(i):
        t = trip_full(i); return jsonify(t) if t else nf("Trip")

    @app.put("/api/trips/<int:i>")
    def trip_edit(i):
        t = row("SELECT * FROM trips WHERE id=?", (i,))
        if not t: return nf("Trip")
        if locked(t): return locked(t)
        x = body()
        if x is None: return badbody()
        v, e = V.clean_trip(x)
        if not e:
            n = row("SELECT COUNT(*) n FROM activities WHERE trip_id=? AND (date<? OR date>?)", (i, v["start_date"], v["end_date"]))["n"]
            if n: e["end_date"] = f"{n} existing activit{'y falls' if n == 1 else 'ies fall'} outside the new dates. Edit or delete them first."
        if e: return bad(e)
        mat = [k for k in MATERIAL_TRIP if v[k] != t[k]] + (["budget"] if abs(v["budget"] - t["budget"]) >= 0.005 else [])
        run("UPDATE trips SET title=:title,origin=:origin,destination=:destination,start_date=:start_date,end_date=:end_date,"
            "travelers=:travelers,budget=:budget,preferences=:preferences,notes=:notes,updated_at=:ts WHERE id=:id", dict(v, id=i, ts=now()))
        reset = maybe_reset(t, "Material change: " + ", ".join(mat)) if mat else False
        out = trip_full(i); out["approval_reset"] = reset
        return jsonify(out)

    @app.delete("/api/trips/<int:i>")
    def trip_del(i):
        if not row("SELECT id FROM trips WHERE id=?", (i,)): return nf("Trip")
        if row("SELECT COUNT(*) n FROM bookings WHERE trip_id=?", (i,))["n"]:
            return err("This trip has booking records, which are kept as history, so it cannot be deleted.", 409)
        run("DELETE FROM trips WHERE id=?", (i,)); return jsonify(deleted=i)

    # ---------- approval workflow ----------
    @app.post("/api/trips/<int:i>/submit")
    def submit(i):
        t = row("SELECT * FROM trips WHERE id=?", (i,))
        if not t: return nf("Trip")
        if t["status"] not in ("Draft", "Rejected"):
            return err(f"Only Draft or Rejected itineraries can be submitted (current status: {t['status']}).", 409)
        if not row("SELECT COUNT(*) n FROM activities WHERE trip_id=?", (i,))["n"]:
            return bad({"activities": "Add at least one activity before submitting for approval."})
        ts = now()
        run("UPDATE trips SET status='Pending Approval', submitted_at=?, updated_at=? WHERE id=?", (ts, ts, i))
        run("INSERT INTO approvals(trip_id,action,reason,feedback,actor,created_at) VALUES(?,?,?,?,?,?)", (i, "Submitted", "", "", "Traveller", ts))
        return jsonify(trip_full(i))

    @app.get("/api/review/pending")
    def rv_pending(): return jsonify(rows(TRIP_Q + " WHERE t.status='Pending Approval' ORDER BY t.submitted_at, t.id"))

    @app.get("/api/review/history")
    def rv_history():
        return jsonify(rows("SELECT a.*, t.title, t.destination, t.status trip_status FROM approvals a JOIN trips t ON t.id=a.trip_id "
                            "WHERE a.action IN ('Approved','Rejected') ORDER BY a.id DESC"))

    def decide(i, action):
        t = row("SELECT * FROM trips WHERE id=?", (i,))
        if not t: return nf("Trip")
        if t["status"] != "Pending Approval":
            return err(f"Only itineraries that are Pending Approval can be {action.lower()} (current status: {t['status']}).", 409)
        x = body(optional=True)
        if x is None: return badbody()
        e = {}
        reason = str(x.get("reason") or "").strip(); feedback = str(x.get("feedback") or "").strip()
        if action == "Rejected" and not reason: e["reason"] = "A rejection reason is required."
        if len(reason) > 1000: e["reason"] = "Reason must be at most 1000 characters."
        if len(feedback) > 1000: e["feedback"] = "Feedback must be at most 1000 characters."
        if e: return bad(e)
        ts = now()
        run("UPDATE trips SET status=?, decided_at=?, updated_at=? WHERE id=?", (action, ts, ts, i))
        run("INSERT INTO approvals(trip_id,action,reason,feedback,actor,created_at) VALUES(?,?,?,?,?,?)",
            (i, action, reason if action == "Rejected" else "", feedback, REVIEWER, ts))
        return jsonify(trip_full(i))
    @app.post("/api/review/<int:i>/approve")
    def rv_approve(i): return decide(i, "Approved")
    @app.post("/api/review/<int:i>/reject")
    def rv_reject(i): return decide(i, "Rejected")

    # ---------- activities ----------
    def act_trip(i):
        t = row("SELECT * FROM trips WHERE id=?", (i,))
        return t, (nf("Trip") if not t else locked(t))

    @app.get("/api/trips/<int:i>/activities")
    def acts(i):
        if not row("SELECT id FROM trips WHERE id=?", (i,)): return nf("Trip")
        return jsonify(rows("SELECT * FROM activities WHERE trip_id=? ORDER BY date,time,id", (i,)))

    @app.post("/api/trips/<int:i>/activities")
    def act_add(i):
        t, bl = act_trip(i)
        if bl: return bl
        x = body()
        if x is None: return badbody()
        v, e = V.clean_activity(x, t)
        if e: return bad(e)
        c = run("INSERT INTO activities(trip_id,name,date,time,location,description,cost) VALUES(?,?,?,?,?,?,?)",
                (i, v["name"], v["date"], v["time"], v["location"], v["description"], v["cost"]))
        touch(i); out = row("SELECT * FROM activities WHERE id=?", (c.lastrowid,)); out["approval_reset"] = maybe_reset(t, "Material change: activity added")
        return jsonify(out), 201

    @app.put("/api/activities/<int:i>")
    def act_edit(i):
        a = row("SELECT * FROM activities WHERE id=?", (i,))
        if not a: return nf("Activity")
        t, bl = act_trip(a["trip_id"])
        if bl: return bl
        x = body()
        if x is None: return badbody()
        v, e = V.clean_activity(x, t)
        if e: return bad(e)
        mat = [k for k in ("name", "date", "time", "location", "cost") if (abs(v[k] - a[k]) >= 0.005 if k == "cost" else v[k] != a[k])]
        run("UPDATE activities SET name=?,date=?,time=?,location=?,description=?,cost=? WHERE id=?",
            (v["name"], v["date"], v["time"], v["location"], v["description"], v["cost"], i))
        touch(t["id"]); out = row("SELECT * FROM activities WHERE id=?", (i,))
        out["approval_reset"] = maybe_reset(t, "Material change: activity edited (" + ", ".join(mat) + ")") if mat else False
        return jsonify(out)

    @app.delete("/api/activities/<int:i>")
    def act_del(i):
        a = row("SELECT * FROM activities WHERE id=?", (i,))
        if not a: return nf("Activity")
        t, bl = act_trip(a["trip_id"])
        if bl: return bl
        run("DELETE FROM activities WHERE id=?", (i,)); touch(t["id"])
        return jsonify(deleted=i, approval_reset=maybe_reset(t, "Material change: activity deleted"))

    # ---------- bookings (simulated records only: no tickets, rooms or payments) ----------
    @app.get("/api/bookings")
    def bk_list():
        w, a = [], []
        for k in ("trip_id", "service_type", "status"):
            if request.args.get(k): w.append(f"b.{k}=?"); a.append(request.args[k])
        return jsonify(rows(BK_Q + (" WHERE " + " AND ".join(w) if w else "") + " ORDER BY b.travel_date, b.id", a))

    @app.get("/api/bookings/<int:i>")
    def bk_get(i):
        b = row(BK_Q + " WHERE b.id=?", (i,)); return jsonify(b) if b else nf("Booking")

    @app.post("/api/bookings")
    def bk_add():
        x = body()
        if x is None: return badbody()
        tid = V.pint(x.get("trip_id")); t = row("SELECT * FROM trips WHERE id=?", (tid,)) if tid else None
        if not t: return bad({"trip_id": "Select a valid existing trip."})
        if need_approved(t): return need_approved(t)
        v, e = V.clean_booking(x, t)
        if e: return bad(e)
        if not v["reference"]: v["reference"] = f"DEMO-{PREFIX[v['service_type']]}-{secrets.token_hex(3).upper()}"
        v.update(trip_id=tid, created_at=now())
        c = run("INSERT INTO bookings(trip_id,service_type,provider,reference,from_location,to_location,booking_date,travel_date,end_date,"
                "traveler_name,travelers_count,service_details,price,status,notes,created_at) VALUES(:trip_id,:service_type,:provider,:reference,"
                ":from_location,:to_location,:booking_date,:travel_date,:end_date,:traveler_name,:travelers_count,:service_details,:price,:status,:notes,:created_at)", v)
        return jsonify(row(BK_Q + " WHERE b.id=?", (c.lastrowid,))), 201

    @app.put("/api/bookings/<int:i>")
    def bk_edit(i):
        b = row("SELECT * FROM bookings WHERE id=?", (i,))
        if not b: return nf("Booking")
        if b["status"] == "Cancelled": return err("Cancelled bookings are kept as history and cannot be edited.", 409)
        t = row("SELECT * FROM trips WHERE id=?", (b["trip_id"],))
        if need_approved(t): return need_approved(t)
        x = body()
        if x is None: return badbody()
        v, e = V.clean_booking(x, t)
        if e: return bad(e)
        if not v["reference"]: v["reference"] = b["reference"]
        v["id"] = i
        run("UPDATE bookings SET service_type=:service_type,provider=:provider,reference=:reference,from_location=:from_location,to_location=:to_location,"
            "booking_date=:booking_date,travel_date=:travel_date,end_date=:end_date,traveler_name=:traveler_name,travelers_count=:travelers_count,"
            "service_details=:service_details,price=:price,status=:status,notes=:notes WHERE id=:id", v)
        return jsonify(row(BK_Q + " WHERE b.id=?", (i,)))

    @app.post("/api/bookings/<int:i>/cancel")
    def bk_cancel(i):
        b = row("SELECT * FROM bookings WHERE id=?", (i,))
        if not b: return nf("Booking")
        if b["status"] == "Cancelled": return err("This booking is already cancelled.", 409)
        run("UPDATE bookings SET status='Cancelled', cancelled_at=? WHERE id=?", (now(), i))   # soft cancel: record kept
        return jsonify(row(BK_Q + " WHERE b.id=?", (i,)))

    # ---------- expenses ----------
    def dup(tid, v, skip=0):
        return row("SELECT id FROM expenses WHERE trip_id=? AND category=? AND LOWER(description)=LOWER(?) AND amount=? AND expense_date=? AND id!=?",
                   (tid, v["category"], v["description"], v["amount"], v["expense_date"], skip))

    @app.get("/api/trips/<int:i>/budget")
    def budget_get(i): return jsonify(budget(i)) if row("SELECT id FROM trips WHERE id=?", (i,)) else nf("Trip")

    @app.get("/api/trips/<int:i>/expenses")
    def exp_list(i):
        if not row("SELECT id FROM trips WHERE id=?", (i,)): return nf("Trip")
        return jsonify(rows("SELECT * FROM expenses WHERE trip_id=? ORDER BY expense_date DESC, id DESC", (i,)))

    @app.post("/api/trips/<int:i>/expenses")
    def exp_add(i):
        if not row("SELECT id FROM trips WHERE id=?", (i,)): return nf("Trip")
        x = body()
        if x is None: return badbody()
        v, e = V.clean_expense(x)
        if e: return bad(e)
        if dup(i, v): return err("An identical expense (same category, description, amount and date) is already recorded.", 409)
        c = run("INSERT INTO expenses(trip_id,category,description,amount,expense_date,created_at) VALUES(?,?,?,?,?,?)",
                (i, v["category"], v["description"], v["amount"], v["expense_date"], now()))
        return jsonify(row("SELECT * FROM expenses WHERE id=?", (c.lastrowid,))), 201

    @app.put("/api/expenses/<int:i>")
    def exp_edit(i):
        ex = row("SELECT * FROM expenses WHERE id=?", (i,))
        if not ex: return nf("Expense")
        x = body()
        if x is None: return badbody()
        v, e = V.clean_expense(x)
        if e: return bad(e)
        if dup(ex["trip_id"], v, i): return err("An identical expense is already recorded.", 409)
        run("UPDATE expenses SET category=?,description=?,amount=?,expense_date=? WHERE id=?", (v["category"], v["description"], v["amount"], v["expense_date"], i))
        return jsonify(row("SELECT * FROM expenses WHERE id=?", (i,)))

    @app.delete("/api/expenses/<int:i>")
    def exp_del(i):
        if not row("SELECT id FROM expenses WHERE id=?", (i,)): return nf("Expense")
        run("DELETE FROM expenses WHERE id=?", (i,)); return jsonify(deleted=i)

    @app.post("/api/bookings/<int:i>/record-expense")
    def bk_expense(i):
        b = row("SELECT * FROM bookings WHERE id=?", (i,))
        if not b: return nf("Booking")
        if b["status"] != "Confirmed": return err("Only Confirmed bookings can be recorded as actual expenses.", 409)
        if row("SELECT id FROM expenses WHERE booking_id=?", (i,)): return err("This booking has already been recorded as an expense.", 409)
        if b["price"] <= 0: return err("A booking with a price of 0 has nothing to record.", 409)
        c = run("INSERT INTO expenses(trip_id,booking_id,category,description,amount,expense_date,created_at) VALUES(?,?,?,?,?,?,?)",
                (b["trip_id"], i, b["service_type"], f"{b['service_type']}: {b['provider']} ({b['reference']})", b["price"], date.today().isoformat(), now()))
        return jsonify(row("SELECT * FROM expenses WHERE id=?", (c.lastrowid,))), 201

    return app

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
