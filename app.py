"""Smart Travel Management System - Itinerary Management + Travel Booking (Flask + SQLite)."""
import os, sqlite3, math
from datetime import date, time as dtime
from flask import Flask, jsonify, request, g, send_from_directory

CATS = ("Flight", "Train", "Hotel", "Cab")
STATS = ("Pending", "Confirmed", "Cancelled")
SCHEMA = """
CREATE TABLE IF NOT EXISTS trips(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
 destination TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
 travelers INTEGER NOT NULL CHECK(travelers>0), description TEXT DEFAULT '', CHECK(end_date>=start_date));
CREATE TABLE IF NOT EXISTS activities(id INTEGER PRIMARY KEY AUTOINCREMENT,
 trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE, name TEXT NOT NULL, date TEXT NOT NULL,
 time TEXT NOT NULL, location TEXT NOT NULL, description TEXT DEFAULT '', cost REAL NOT NULL CHECK(cost>=0));
CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY AUTOINCREMENT,
 trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE RESTRICT,
 category TEXT NOT NULL CHECK(category IN ('Flight','Train','Hotel','Cab')), provider TEXT NOT NULL,
 reference TEXT NOT NULL, booking_date TEXT NOT NULL, travel_date TEXT NOT NULL,
 price REAL NOT NULL CHECK(price>=0), status TEXT NOT NULL CHECK(status IN ('Pending','Confirmed','Cancelled')),
 notes TEXT DEFAULT '');
"""

# ---------- validation helpers ----------
def pd(v):
    if not isinstance(v, str): return None
    try: return date.fromisoformat(v.strip())
    except ValueError: return None

def pint(v):
    if isinstance(v, bool): return None
    if isinstance(v, int): return v
    if isinstance(v, str) and v.strip().isdigit(): return int(v.strip())
    return None

def pmoney(v):
    if isinstance(v, bool) or v is None or v == "": return None
    try: f = float(v)
    except (TypeError, ValueError): return None
    return round(f, 2) if math.isfinite(f) else None

def text(x, k, label, e, v, required=True):
    s = str(x.get(k) or "").strip()
    if required and not s: e[k] = f"{label} is required."
    v[k] = s

def clean_trip(x):
    e, v = {}, {}
    text(x, "title", "Title", e, v); text(x, "destination", "Destination", e, v)
    text(x, "description", "Description", e, v, False)
    s, en = pd(x.get("start_date")), pd(x.get("end_date"))
    if not s: e["start_date"] = "Start date is required (YYYY-MM-DD)."
    if not en: e["end_date"] = "End date is required (YYYY-MM-DD)."
    if s and en and en < s: e["end_date"] = "End date cannot be before start date."
    t = pint(x.get("travelers"))
    if t is None or t < 1: e["travelers"] = "Travelers must be a positive whole number."
    v.update(start_date=s and s.isoformat(), end_date=en and en.isoformat(), travelers=t)
    return v, e

def clean_activity(x, trip):
    e, v = {}, {}
    text(x, "name", "Activity name", e, v); text(x, "location", "Location", e, v)
    text(x, "description", "Description", e, v, False)
    d = pd(x.get("date"))
    if not d: e["date"] = "Date is required (YYYY-MM-DD)."
    elif not (date.fromisoformat(trip["start_date"]) <= d <= date.fromisoformat(trip["end_date"])):
        e["date"] = f"Date must be within the trip dates ({trip['start_date']} to {trip['end_date']})."
    try: tm = dtime.fromisoformat(str(x.get("time")).strip()).strftime("%H:%M")
    except ValueError: tm = None; e["time"] = "Time is required (HH:MM)."
    c = pmoney(x.get("cost"))
    if c is None: e["cost"] = "Estimated cost is required and must be a number."
    elif c < 0: e["cost"] = "Estimated cost cannot be negative."
    v.update(date=d and d.isoformat(), time=tm, cost=c)
    return v, e

def clean_booking(x):
    e, v = {}, {}
    text(x, "provider", "Provider name", e, v); text(x, "reference", "Booking reference", e, v)
    text(x, "notes", "Notes", e, v, False)
    for k, l in (("booking_date", "Booking date"), ("travel_date", "Travel date")):
        d = pd(x.get(k)); v[k] = d and d.isoformat()
        if not d: e[k] = f"{l} is required (YYYY-MM-DD)."
    if x.get("category") not in CATS: e["category"] = "Category must be Flight, Train, Hotel or Cab."
    if x.get("status") not in STATS: e["status"] = "Status must be Pending, Confirmed or Cancelled."
    p = pmoney(x.get("price"))
    if p is None: e["price"] = "Price is required and must be a number."
    elif p < 0: e["price"] = "Price cannot be negative."
    v.update(category=x.get("category"), status=x.get("status"), price=p, trip_id=pint(x.get("trip_id")))
    return v, e

def create_app(db_path=None):
    app = Flask(__name__, static_folder="static")
    path = db_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "tms.db")
    with sqlite3.connect(path) as c: c.executescript(SCHEMA)

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(path); g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys=ON")
        return g.db
    @app.teardown_appcontext
    def _close(_):
        d = g.pop("db", None)
        if d: d.close()
    def run(sql, a=()):
        c = db().execute(sql, a); db().commit(); return c
    def rows(sql, a=()): return [dict(r) for r in db().execute(sql, a)]
    def row(sql, a=()):
        r = db().execute(sql, a).fetchone(); return dict(r) if r else None
    def body(): return request.get_json(silent=True) or {}
    def bad(e, code=400): return jsonify(errors=e), code
    def nf(what): return jsonify(error=f"{what} not found."), 404

    TRIP_Q = ("SELECT t.*, COALESCE((SELECT ROUND(SUM(cost),2) FROM activities WHERE trip_id=t.id),0) "
              "AS est_cost FROM trips t")

    @app.get("/")
    def index(): return send_from_directory(app.static_folder, "index.html")

    # ----- Module 1: trips -----
    @app.get("/api/trips")
    def trips(): return jsonify(rows(TRIP_Q + " ORDER BY start_date, id"))

    @app.post("/api/trips")
    def trip_add():
        v, e = clean_trip(body())
        if e: return bad(e)
        c = run("INSERT INTO trips(title,destination,start_date,end_date,travelers,description) "
                "VALUES(:title,:destination,:start_date,:end_date,:travelers,:description)", v)
        return jsonify(row(TRIP_Q + " WHERE t.id=?", (c.lastrowid,))), 201

    @app.get("/api/trips/<int:i>")
    def trip_get(i):
        t = row(TRIP_Q + " WHERE t.id=?", (i,)); return jsonify(t) if t else nf("Trip")

    @app.put("/api/trips/<int:i>")
    def trip_edit(i):
        if not row("SELECT id FROM trips WHERE id=?", (i,)): return nf("Trip")
        v, e = clean_trip(body())
        if not e:
            n = row("SELECT COUNT(*) n FROM activities WHERE trip_id=? AND (date<? OR date>?)",
                    (i, v["start_date"], v["end_date"]))["n"]
            if n: e["end_date"] = f"{n} existing activit{'y falls' if n == 1 else 'ies fall'} outside the new dates."
        if e: return bad(e)
        v["id"] = i
        run("UPDATE trips SET title=:title,destination=:destination,start_date=:start_date,end_date=:end_date,"
            "travelers=:travelers,description=:description WHERE id=:id", v)
        return jsonify(row(TRIP_Q + " WHERE t.id=?", (i,)))

    @app.delete("/api/trips/<int:i>")
    def trip_del(i):
        if not row("SELECT id FROM trips WHERE id=?", (i,)): return nf("Trip")
        try: run("DELETE FROM trips WHERE id=?", (i,))
        except sqlite3.IntegrityError:
            return jsonify(error="This trip has booking records (kept for history) and cannot be deleted."), 409
        return jsonify(deleted=i)

    # ----- Module 1: activities -----
    @app.get("/api/trips/<int:i>/activities")
    def acts(i):
        if not row("SELECT id FROM trips WHERE id=?", (i,)): return nf("Trip")
        return jsonify(rows("SELECT * FROM activities WHERE trip_id=? ORDER BY date,time,id", (i,)))

    @app.post("/api/trips/<int:i>/activities")
    def act_add(i):
        t = row("SELECT * FROM trips WHERE id=?", (i,))
        if not t: return nf("Trip")
        v, e = clean_activity(body(), t)
        if e: return bad(e)
        v["trip_id"] = i
        c = run("INSERT INTO activities(trip_id,name,date,time,location,description,cost) "
                "VALUES(:trip_id,:name,:date,:time,:location,:description,:cost)", v)
        return jsonify(row("SELECT * FROM activities WHERE id=?", (c.lastrowid,))), 201

    @app.put("/api/activities/<int:i>")
    def act_edit(i):
        a = row("SELECT * FROM activities WHERE id=?", (i,))
        if not a: return nf("Activity")
        v, e = clean_activity(body(), row("SELECT * FROM trips WHERE id=?", (a["trip_id"],)))
        if e: return bad(e)
        v["id"] = i
        run("UPDATE activities SET name=:name,date=:date,time=:time,location=:location,"
            "description=:description,cost=:cost WHERE id=:id", v)
        return jsonify(row("SELECT * FROM activities WHERE id=?", (i,)))

    @app.delete("/api/activities/<int:i>")
    def act_del(i):
        if not row("SELECT id FROM activities WHERE id=?", (i,)): return nf("Activity")
        run("DELETE FROM activities WHERE id=?", (i,)); return jsonify(deleted=i)

    # ----- Module 2: bookings -----
    def where():
        w, a = [], []
        for k in ("trip_id", "category", "status"):
            val = request.args.get(k)
            if val: w.append(f"b.{k}=?"); a.append(val)
        return (" WHERE " + " AND ".join(w) if w else ""), a

    @app.get("/api/bookings")
    def bk_list():
        w, a = where()
        return jsonify(rows("SELECT b.*, t.title trip_title FROM bookings b JOIN trips t ON t.id=b.trip_id"
                            + w + " ORDER BY b.travel_date, b.id", a))

    @app.get("/api/bookings/summary")
    def bk_summary():
        w, a = where()
        r = row("SELECT COALESCE(SUM(price),0) total_value,"
                "COALESCE(SUM(CASE WHEN status='Confirmed' THEN price END),0) confirmed_total,"
                "COALESCE(SUM(CASE WHEN status='Pending' THEN price END),0) pending_total,"
                "COALESCE(SUM(CASE WHEN status='Cancelled' THEN price END),0) cancelled_total,"
                "COUNT(*) count FROM bookings b" + w, a)
        return jsonify({k: round(x, 2) if isinstance(x, float) else x for k, x in r.items()})

    def bk_valid(x):
        v, e = clean_booking(x)
        if v["trip_id"] is None or not row("SELECT id FROM trips WHERE id=?", (v["trip_id"],)):
            e["trip_id"] = "Select a valid existing trip."
        return v, e

    @app.post("/api/bookings")
    def bk_add():
        v, e = bk_valid(body())
        if e: return bad(e)
        c = run("INSERT INTO bookings(trip_id,category,provider,reference,booking_date,travel_date,price,status,notes)"
                " VALUES(:trip_id,:category,:provider,:reference,:booking_date,:travel_date,:price,:status,:notes)", v)
        return jsonify(row("SELECT * FROM bookings WHERE id=?", (c.lastrowid,))), 201

    @app.get("/api/bookings/<int:i>")
    def bk_get(i):
        b = row("SELECT b.*, t.title trip_title FROM bookings b JOIN trips t ON t.id=b.trip_id WHERE b.id=?", (i,))
        return jsonify(b) if b else nf("Booking")

    @app.put("/api/bookings/<int:i>")
    def bk_edit(i):
        if not row("SELECT id FROM bookings WHERE id=?", (i,)): return nf("Booking")
        v, e = bk_valid(body())
        if e: return bad(e)
        v["id"] = i
        run("UPDATE bookings SET trip_id=:trip_id,category=:category,provider=:provider,reference=:reference,"
            "booking_date=:booking_date,travel_date=:travel_date,price=:price,status=:status,notes=:notes "
            "WHERE id=:id", v)
        return jsonify(row("SELECT * FROM bookings WHERE id=?", (i,)))

    @app.post("/api/bookings/<int:i>/cancel")
    def bk_cancel(i):
        if not row("SELECT id FROM bookings WHERE id=?", (i,)): return nf("Booking")
        run("UPDATE bookings SET status='Cancelled' WHERE id=?", (i,))  # soft cancel: record is kept
        return jsonify(row("SELECT * FROM bookings WHERE id=?", (i,)))

    return app

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
