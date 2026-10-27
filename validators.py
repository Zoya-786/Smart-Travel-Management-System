"""Input validation. Every function returns (clean_values, errors_dict)."""
import math
from datetime import date, time as dtime

SERVICES = ("Flight", "Train", "Bus", "Hotel", "Local Transport")
EXPENSE_CATS = SERVICES + ("Food", "Activities", "Shopping", "Other")

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
    return round(f, 2) if math.isfinite(f) and abs(f) < 1e10 else None

def text(x, k, label, e, v, required=True, mx=120):
    s = str(x.get(k) if x.get(k) is not None else "").strip()
    if required and not s: e[k] = f"{label} is required."
    elif len(s) > mx: e[k] = f"{label} must be at most {mx} characters."
    v[k] = s

def clean_trip(x):
    e, v = {}, {}
    text(x, "title", "Trip title", e, v); text(x, "origin", "Starting location", e, v); text(x, "destination", "Destination", e, v)
    text(x, "preferences", "Preferences", e, v, False, 1000); text(x, "notes", "Notes", e, v, False, 2000)
    s, en = pd(x.get("start_date")), pd(x.get("end_date"))
    if not s: e["start_date"] = "Start date is required (YYYY-MM-DD)."
    if not en: e["end_date"] = "End date is required (YYYY-MM-DD)."
    if s and en and en < s: e["end_date"] = "End date cannot be before start date."
    t = pint(x.get("travelers"))
    if t is None or t < 1 or t > 1000: e["travelers"] = "Travellers must be a whole number from 1 to 1000."
    b = pmoney(x.get("budget"))
    if b is None: e["budget"] = "Total planned budget is required and must be a number."
    elif b < 0: e["budget"] = "Budget cannot be negative."
    v.update(start_date=s and s.isoformat(), end_date=en and en.isoformat(), travelers=t, budget=b)
    return v, e

def clean_activity(x, trip):
    e, v = {}, {}
    text(x, "name", "Activity name", e, v); text(x, "location", "Location", e, v); text(x, "description", "Description", e, v, False, 1000)
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

def clean_booking(x, trip):
    e, v = {}, {}
    st = x.get("service_type")
    if st not in SERVICES: e["service_type"] = "Service type must be Flight, Train, Bus, Hotel or Local Transport."
    text(x, "provider", "Provider", e, v); text(x, "reference", "Reference", e, v, False, 60)
    text(x, "traveler_name", "Traveller name", e, v)
    text(x, "from_location", "From / pickup location", e, v, st not in (None, "Hotel") and st in SERVICES)
    text(x, "to_location", "To / location", e, v)
    text(x, "service_details", "Service details", e, v, False, 500); text(x, "notes", "Notes", e, v, False, 1000)
    td = pd(x.get("travel_date"))
    if not td: e["travel_date"] = "Travel / check-in date is required (YYYY-MM-DD)."
    raw_end = x.get("end_date"); ed = None
    if raw_end not in (None, ""):
        ed = pd(raw_end)
        if not ed: e["end_date"] = "End date is not a valid date."
        elif td and ed < td: e["end_date"] = "End date cannot be before the travel date."
    if st == "Hotel":
        if ed is None and "end_date" not in e: e["end_date"] = "Check-out date is required for hotels."
        elif ed and td and ed <= td: e["end_date"] = "Check-out must be after check-in."
    raw_bd = x.get("booking_date"); bd = pd(raw_bd) if raw_bd not in (None, "") else date.today()
    if not bd: e["booking_date"] = "Booking date is not a valid date."
    n = x.get("travelers_count"); n = trip["travelers"] if n in (None, "") else pint(n)
    if n is None or n < 1: e["travelers_count"] = "Number of travellers must be a whole number of at least 1."
    p = pmoney(x.get("price"))
    if p is None: e["price"] = "Price is required and must be a number."
    elif p < 0: e["price"] = "Price cannot be negative."
    status = x.get("status") or "Pending"
    if status not in ("Pending", "Confirmed"): e["status"] = "Status must be Pending or Confirmed (use Cancel to cancel a booking)."
    v.update(service_type=st, travel_date=td and td.isoformat(), end_date=ed and ed.isoformat(),
             booking_date=bd and bd.isoformat(), travelers_count=n, price=p, status=status)
    if st == "Hotel": v["from_location"] = ""
    return v, e

def clean_expense(x):
    e, v = {}, {}
    if x.get("category") not in EXPENSE_CATS: e["category"] = "Choose a valid expense category."
    text(x, "description", "Description", e, v)
    a = pmoney(x.get("amount"))
    if a is None: e["amount"] = "Amount is required and must be a number."
    elif a <= 0: e["amount"] = "Amount must be greater than 0."
    d = pd(x.get("expense_date"))
    if not d: e["expense_date"] = "Expense date is required (YYYY-MM-DD)."
    v.update(category=x.get("category"), amount=a, expense_date=d and d.isoformat())
    return v, e
