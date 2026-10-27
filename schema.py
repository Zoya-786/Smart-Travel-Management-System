"""SQLite schema, v1->v2 upgrade handling and template seeding."""
import os, sqlite3, shutil, time
from templates_data import TEMPLATES

SCHEMA = """
CREATE TABLE IF NOT EXISTS templates(id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
 category TEXT NOT NULL, destination TEXT NOT NULL, duration_days INTEGER NOT NULL CHECK(duration_days>0), description TEXT NOT NULL,
 suggested_budget REAL NOT NULL CHECK(suggested_budget>=0), approval_status TEXT NOT NULL DEFAULT 'Approved');
CREATE TABLE IF NOT EXISTS template_activities(id INTEGER PRIMARY KEY AUTOINCREMENT,
 template_id INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE, day_number INTEGER NOT NULL CHECK(day_number>0),
 start_time TEXT NOT NULL, name TEXT NOT NULL, location TEXT NOT NULL, cost REAL NOT NULL CHECK(cost>=0));
CREATE TABLE IF NOT EXISTS trips(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, origin TEXT NOT NULL, destination TEXT NOT NULL,
 start_date TEXT NOT NULL, end_date TEXT NOT NULL, travelers INTEGER NOT NULL CHECK(travelers>0), budget REAL NOT NULL CHECK(budget>=0),
 preferences TEXT DEFAULT '', notes TEXT DEFAULT '',
 status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft','Pending Approval','Approved','Rejected')),
 template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 submitted_at TEXT, decided_at TEXT, CHECK(end_date>=start_date));
CREATE TABLE IF NOT EXISTS activities(id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
 name TEXT NOT NULL, date TEXT NOT NULL, time TEXT NOT NULL, location TEXT NOT NULL, description TEXT DEFAULT '', cost REAL NOT NULL CHECK(cost>=0));
CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
 action TEXT NOT NULL CHECK(action IN ('Submitted','Approved','Rejected','Reset to Draft')), reason TEXT DEFAULT '', feedback TEXT DEFAULT '',
 actor TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE RESTRICT,
 service_type TEXT NOT NULL CHECK(service_type IN ('Flight','Train','Bus','Hotel','Local Transport')), provider TEXT NOT NULL, reference TEXT NOT NULL,
 from_location TEXT DEFAULT '', to_location TEXT NOT NULL, booking_date TEXT NOT NULL, travel_date TEXT NOT NULL, end_date TEXT,
 traveler_name TEXT NOT NULL, travelers_count INTEGER NOT NULL CHECK(travelers_count>0), service_details TEXT DEFAULT '',
 price REAL NOT NULL CHECK(price>=0), status TEXT NOT NULL CHECK(status IN ('Pending','Confirmed','Cancelled')), notes TEXT DEFAULT '',
 created_at TEXT NOT NULL, cancelled_at TEXT);
CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
 booking_id INTEGER UNIQUE REFERENCES bookings(id) ON DELETE SET NULL, category TEXT NOT NULL, description TEXT NOT NULL,
 amount REAL NOT NULL CHECK(amount>0), expense_date TEXT NOT NULL, created_at TEXT NOT NULL);
"""

def init_db(path):
    if os.path.exists(path):                      # detect the v1 prototype database and keep a backup
        c = sqlite3.connect(path); cols = [r[1] for r in c.execute("PRAGMA table_info(bookings)")]; c.close()
        if cols and "service_type" not in cols:
            shutil.move(path, f"{path}.v1_backup_{int(time.time())}")
    c = sqlite3.connect(path); c.execute("PRAGMA foreign_keys=ON"); c.executescript(SCHEMA)
    if not c.execute("SELECT 1 FROM templates LIMIT 1").fetchone():
        for t in TEMPLATES:
            i = c.execute("INSERT INTO templates(slug,title,category,destination,duration_days,description,suggested_budget) VALUES(?,?,?,?,?,?,?)",
                          (t["slug"], t["title"], t["category"], t["destination"], t["days"], t["desc"], t["budget"])).lastrowid
            c.executemany("INSERT INTO template_activities(template_id,day_number,start_time,name,location,cost) VALUES(?,?,?,?,?,?)",
                          [(i, *a) for a in t["acts"]])
    c.commit(); c.close()
