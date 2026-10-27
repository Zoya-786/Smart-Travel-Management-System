"use strict";
/* ---------- helpers ---------- */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const inr = n => "₹" + Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fdate = d => d ? new Date(d + "T00:00:00Z").toLocaleDateString("en-IN", { timeZone: "UTC", day: "2-digit", month: "short", year: "numeric" }) : "—";
const fts = t => t ? new Date(t).toLocaleString("en-IN") : "—";
const ICON = { Flight: "✈️", Train: "🚆", Bus: "🚌", Hotel: "🏨", "Local Transport": "🚕" };
const SVC = Object.keys(ICON), EXPC = [...SVC, "Food", "Activities", "Shopping", "Other"];
const BCLS = { Draft: "gray", "Pending Approval": "amber", Approved: "green", Rejected: "red", Pending: "amber", Confirmed: "green", Cancelled: "gray", "Reset to Draft": "gray", Submitted: "amber" };
const badge = s => `<span class="badge ${BCLS[s] || "gray"}">${esc(s)}</span>`;
const view = h => { $("#view").innerHTML = h; };
const opts = (a, sel) => a.map(([k, l]) => `<option value="${esc(k)}"${String(sel) === String(k) ? " selected" : ""}>${esc(l)}</option>`).join("");
const empty = (ic, t, m, btn = "") => `<div class="card empty"><div class="ic">${ic}</div><h3>${esc(t)}</h3><p>${esc(m)}</p>${btn}</div>`;
const days = (a, b) => { const o = []; let d = new Date(a + "T00:00:00Z"); const e = new Date(b + "T00:00:00Z"); while (d <= e && o.length < 400) { o.push(d.toISOString().slice(0, 10)); d.setUTCDate(d.getUTCDate() + 1); } return o; };
const groupBy = (arr, k) => arr.reduce((m, x) => ((m[x[k]] ??= []).push(x), m), {});

async function api(m, u, b) {
  try {
    const r = await fetch(u, { method: m, headers: { "Content-Type": "application/json" }, body: b !== undefined ? JSON.stringify(b) : undefined });
    let d = {}; try { d = await r.json(); } catch { }
    return { ok: r.ok, d, status: r.status };
  } catch { return { ok: false, d: { error: "Cannot reach the server. Is it still running?" } }; }
}
const errTxt = d => d.errors ? Object.values(d.errors).join("\n") : (d.error || "Something went wrong.");
function toast(m, t = "ok") { const e = document.createElement("div"); e.className = "toast " + t; e.textContent = m; $("#toasts").append(e); setTimeout(() => e.remove(), t === "ok" ? 3500 : 6500); }
/* action wrapper: calls API, shows toast, refreshes */
async function act(method, url, body, okMsg) {
  const r = await api(method, url, body);
  if (!r.ok) { toast(errTxt(r.d), "err"); return r; }
  toast(okMsg); if (r.d.approval_reset) toast("Approved itinerary was materially changed - it is back to Draft and must be re-submitted for approval.", "warn");
  route(); return r;
}

/* ---------- dialogs ---------- */
const dlg = $("#dlg");
function modal(html, wide) { dlg.innerHTML = `<div class="mbox${wide ? " wide" : ""}">${html}</div>`; if (!dlg.open) dlg.showModal(); }
function closeModal() { if (dlg.open) dlg.close(); }
function confirmBox(title, msg, label = "Confirm", danger = false) {
  return new Promise(res => {
    modal(`<h3>${esc(title)}</h3><p>${esc(msg)}</p><div class="actions"><button class="btn" id="no">Cancel</button><button class="btn ${danger ? "bad" : "primary"}" id="yes">${esc(label)}</button></div>`);
    $("#yes").onclick = () => { closeModal(); res(true); }; $("#no").onclick = () => { closeModal(); res(false); }; dlg.oncancel = () => res(false);
  });
}
function fieldHtml([n, l, t, o, a], v) {
  const val = v[n] ?? "", id = "f_" + n;
  const inner = t === "select" ? `<select name="${n}" id="${id}" ${a || ""}>${opts(o, val)}</select>` : t === "textarea" ? `<textarea name="${n}" id="${id}" ${a || ""}>${esc(val)}</textarea>`
    : `<input name="${n}" id="${id}" type="${t}" ${t === "number" ? 'step="any"' : ""} value="${esc(val)}" ${a || ""}>`;
  return `<label id="l_${n}" class="${t === "textarea" ? "full" : ""}"><span>${l}</span>${inner}</label>`;
}
function formModal({ title, fields, values = {}, send, ok, after, wide, note, saveLabel = "Save" }) {
  modal(`<h3>${title}</h3>${note ? `<p class="muted">${note}</p>` : ""}<form novalidate><div class="fgrid">${fields.map(f => fieldHtml(f, values)).join("")}</div><div class="err"></div><div class="actions"><button type="button" class="btn" onclick="closeModal()">Cancel</button><button class="btn primary">${saveLabel}</button></div></form>`, wide);
  const f = $("#dlg form"); after?.(f);
  f.onsubmit = async e => {
    e.preventDefault(); const r = await send(Object.fromEntries(new FormData(f)));
    if (!r.ok) { $(".err", f).textContent = errTxt(r.d); return; }
    closeModal(); toast(ok); if (r.d.approval_reset) toast("Approved itinerary was materially changed - it is back to Draft and must be re-submitted for approval.", "warn");
    if (f._then) f._then(r.d); else route();
  };
  return f;
}

/* ---------- state & router ---------- */
let tripId = +localStorage.getItem("tms_trip") || null, trips = [], bkTrip = "", bkType = "", bkStatus = "", tripFilter = "", exCat = "", reviewTab = "pending";
async function loadTrips() { const r = await api("GET", "/api/trips"); trips = r.ok ? r.d : []; if (!trips.find(t => t.id == tripId)) tripId = trips[0]?.id || null; }
function setTrip(v) { tripId = v ? +v : null; localStorage.setItem("tms_trip", tripId || ""); route(); }
const picker = (all, cur, fn) => `<label class="picker"><b>Trip</b><select onchange="${fn}(this.value)">${all ? '<option value="">All trips</option>' : ""}${trips.map(t => `<option value="${t.id}"${t.id == cur ? " selected" : ""}>${esc(t.title)} (${esc(t.status)})</option>`).join("")}</select></label>`;
const go = h => { location.hash = h; };
const ROUTES = { dashboard: viewDashboard, trips: viewTrips, explore: viewExplore, planner: viewPlanner, bookings: viewBookings, budget: viewBudget, review: viewReview };
async function route() {
  const r = (location.hash || "#dashboard").slice(1).split("/")[0]; const fn = ROUTES[r] || viewDashboard;
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("on", a.dataset.r === (ROUTES[r] ? r : "dashboard")));
  view('<p class="muted">Loading…</p>');
  try { await fn(); } catch (e) { console.error(e); view(`<div class="banner err">Could not display this page: ${esc(e.message)}</div>`); }
}
window.addEventListener("hashchange", route);

/* ---------- Dashboard ---------- */
async function viewDashboard() {
  const r = await api("GET", "/api/dashboard"); if (!r.ok) return view(`<div class="banner err">${esc(errTxt(r.d))}</div>`);
  const d = r.d, t = d.totals;
  if (!d.trips_total) return view(`<h1>Dashboard</h1><p class="sub">Your trips, bookings and budgets at a glance.</p>` + empty("🧭", "No trips yet", "Start from one of the ready-made itineraries or create your own trip.",
    `<button class="btn primary" onclick="go('#explore')">Explore itineraries</button> <button class="btn" onclick="tripForm()">Create a trip</button>`));
  view(`<h1>Dashboard</h1><p class="sub">Live summary of your saved data.</p>
  <div class="grid k"><div class="kpi"><span>Total trips</span><b>${d.trips_total}</b></div><div class="kpi a"><span>Pending approvals</span><b>${d.pending_approvals}</b></div>
  <div class="kpi g"><span>Approved trips</span><b>${d.by_status.Approved}</b></div><div class="kpi"><span>Active bookings</span><b>${d.bookings.active}</b></div>
  <div class="kpi p"><span>Cancelled bookings</span><b>${d.bookings.cancelled}</b></div></div><br>
  <div class="grid k"><div class="kpi"><span>Total planned budget</span><b>${inr(t.planned_budget)}</b></div><div class="kpi"><span>Active booking cost</span><b>${inr(t.active_booking_cost)}</b></div>
  <div class="kpi ${t.actual_expenses > t.planned_budget ? "r" : "g"}"><span>Actual expenses</span><b>${inr(t.actual_expenses)}</b></div><div class="kpi ${t.remaining_budget < 0 ? "r" : "g"}"><span>Remaining (planned − actual)</span><b>${inr(t.remaining_budget)}</b></div></div><br>
  <div class="card"><h2>Trips by approval status</h2>${["Draft", "Pending Approval", "Approved", "Rejected"].map(s => `${badge(s)} <b>${d.by_status[s]}</b>&nbsp;&nbsp;`).join("")}</div>
  ${d.over_budget_trips.length ? `<div class="banner err"><b>Budget alerts</b><ul>${d.over_budget_trips.map(o => `<li><a href="#budget" onclick="setTrip(${o.id})"><b>${esc(o.title)}</b></a>: ${esc(o.warnings.join(" "))}</li>`).join("")}</ul></div>` : ""}
  <div class="card"><h2>Upcoming and current travel</h2>${d.upcoming.length ? `<div class="tw"><table><tr><th>Trip</th><th>Dates</th><th>Starts</th><th>Status</th><th></th></tr>${d.upcoming.map(u => `<tr><td><b>${esc(u.title)}</b><br><span class="muted">${esc(u.origin)} → ${esc(u.destination)}</span></td><td>${fdate(u.start_date)} – ${fdate(u.end_date)}</td><td>${u.days_until > 0 ? "in " + u.days_until + " day(s)" : u.days_until === 0 ? "today" : "in progress"}</td><td>${badge(u.status)}</td><td><button class="btn" onclick="setTrip(${u.id});go('#planner')">Open</button></td></tr>`).join("")}</table></div>` : '<p class="muted">No upcoming trips. All your trips are in the past.</p>'}</div>
  <div class="bar"><button class="btn primary" onclick="tripForm()">+ New trip</button><button class="btn" onclick="go('#explore')">Browse ${d.templates_available} itineraries</button>${d.pending_approvals ? `<button class="btn" onclick="go('#review')">Open Agency Review (demo)</button>` : ""}</div>`);
}

/* ---------- My Trips ---------- */
const TRIP_FIELDS = [["title", "Trip title", "text"], ["origin", "Starting location", "text"], ["destination", "Destination", "text"], ["travelers", "Number of travellers", "number", 0, 'min="1"'],
  ["start_date", "Start date", "date"], ["end_date", "End date", "date"], ["budget", "Total planned budget (₹)", "number", 0, 'min="0"'], ["preferences", "Preferences (optional)", "textarea"], ["notes", "Notes (optional)", "textarea"]];
async function viewTrips() {
  await loadTrips(); const list = trips.filter(t => !tripFilter || t.status === tripFilter);
  view(`<h1>My Trips</h1><p class="sub">Create, edit and submit itineraries for approval.</p>
  <div class="bar"><button class="btn primary" onclick="tripForm()">+ New trip</button><button class="btn" onclick="go('#explore')">Start from a template</button><span class="sp"></span>
  <label class="picker"><b>Status</b><select onchange="tripFilter=this.value;route()">${opts([["", "All"], ...["Draft", "Pending Approval", "Approved", "Rejected"].map(s => [s, s])], tripFilter)}</select></label></div>
  ${list.length ? `<div class="grid">${list.map(tripCard).join("")}</div>` : empty("🧳", trips.length ? "No trips with this status" : "No trips yet", trips.length ? "Change the status filter." : "Create your first trip or pick a template.", trips.length ? "" : `<button class="btn primary" onclick="tripForm()">Create a trip</button>`)}`);
}
function tripCard(t) {
  const can = t.status === "Draft" || t.status === "Rejected", lock = t.status === "Pending Approval";
  return `<div class="card tcard"><div class="bar" style="margin:0"><h3>${esc(t.title)}</h3><span class="sp"></span>${badge(t.status)}</div>
  <div class="meta">${esc(t.origin)} → ${esc(t.destination)}<br>${fdate(t.start_date)} – ${fdate(t.end_date)} · ${t.travelers} traveller(s)<br>Budget ${inr(t.budget)} · Activities ${inr(t.est_cost)} (${t.activity_count})</div>
  ${t.status === "Rejected" ? `<div class="banner err" style="margin:0">Rejected: ${esc(t.last_reason)}${t.last_feedback ? `<br>Feedback: ${esc(t.last_feedback)}` : ""}</div>` : ""}
  <div class="acts"><button class="btn primary" onclick="setTrip(${t.id});go('#planner')">Open planner</button><button class="btn" ${lock ? "disabled title='Locked while pending review'" : ""} onclick="tripForm(${t.id})">Edit</button>
  ${can ? `<button class="btn ok" onclick="submitTrip(${t.id})">${t.status === "Rejected" ? "Resubmit" : "Submit for approval"}</button>` : ""}<button class="btn danger" onclick="delTrip(${t.id})">Delete</button></div></div>`;
}
function tripForm(id, then) {
  const v = id ? trips.find(t => t.id == id) : { travelers: 1 };
  const f = formModal({ title: id ? "Edit trip" : "New trip", fields: TRIP_FIELDS, values: v, wide: true, ok: id ? "Trip updated." : "Trip created.",
    note: id ? "Changing origin, destination, dates, travellers or budget of an Approved itinerary requires approval again." : "New trips start as Draft.",
    send: b => api(id ? "PUT" : "POST", id ? `/api/trips/${id}` : "/api/trips", b) });
  if (!id) f._then = d => { setTrip(d.id); go("#planner"); };
}
async function submitTrip(id) { if (await confirmBox("Submit for agency review?", "The itinerary will be locked while the (simulated) agency reviews it.", "Submit")) { const r = await act("POST", `/api/trips/${id}/submit`, undefined, "Submitted for approval."); } }
async function delTrip(id) { if (await confirmBox("Delete this trip?", "The trip, its activities, expenses and approval history will be permanently deleted.", "Delete", true)) act("DELETE", `/api/trips/${id}`, undefined, "Trip deleted."); }

/* ---------- Explore templates ---------- */
async function viewExplore() {
  const all = (await api("GET", "/api/templates")).d, cats = [...new Set(all.map(t => t.category))], list = all.filter(t => !exCat || t.category === exCat);
  view(`<h1>Explore Itineraries</h1><p class="sub">${all.length} ready-made itineraries. Costs are illustrative estimates for 2 travellers. Choosing one creates your own editable copy; the original never changes.</p>
  <div class="chips"><span class="chip ${exCat ? "" : "on"}" onclick="exCat='';route()">All</span>${cats.map(c => `<span class="chip ${exCat === c ? "on" : ""}" onclick="exCat='${esc(c)}';route()">${esc(c)}</span>`).join("")}</div>
  <div class="grid">${list.map(t => `<div class="card tcard"><span class="badge gray" style="align-self:flex-start">${esc(t.category)}</span><h3 style="margin-top:8px">${esc(t.title)}</h3>
  <div class="meta">📍 ${esc(t.destination)} · ${t.duration_days} days<br>${esc(t.description)}<br>Activities ${inr(t.est_cost)} · Suggested budget <b>${inr(t.suggested_budget)}</b></div>
  <div class="acts"><button class="btn" onclick="tplDetail(${t.id})">View details</button><button class="btn primary" onclick="tplUse(${t.id})">Use this template</button></div></div>`).join("")}</div>`);
}
async function tplDetail(id) {
  const t = (await api("GET", `/api/templates/${id}`)).d, by = groupBy(t.activities, "day_number");
  modal(`<h3>${esc(t.title)}</h3><p class="muted">${badge(t.approval_status)} Pre-reviewed template (simulated). A copy you create gets its own approval process.</p><p>${esc(t.description)}</p>
  <dl class="kv"><dt>Destination</dt><dd>${esc(t.destination)}</dd><dt>Duration</dt><dd>${t.duration_days} days</dd><dt>Suggested budget</dt><dd>${inr(t.suggested_budget)}</dd><dt>Activity estimate</dt><dd>${inr(t.est_cost)}</dd></dl>
  ${Object.keys(by).map(d => `<div class="day"><h4>Day ${d}</h4>${by[d].map(a => `<div class="act"><span class="t">${a.start_time}</span><span class="b"><b>${esc(a.name)}</b><br><span class="muted">📍 ${esc(a.location)}</span></span><span class="c">${inr(a.cost)}</span></div>`).join("")}</div>`).join("")}
  <div class="actions"><button class="btn" onclick="closeModal()">Close</button><button class="btn primary" onclick="tplUse(${id})">Use this template</button></div>`, true);
}
async function tplUse(id) {
  const t = (await api("GET", `/api/templates/${id}`)).d;
  const f = formModal({ title: "Customise: " + esc(t.title), wide: true, ok: "Itinerary saved to My Trips as a Draft.", saveLabel: "Create my itinerary",
    note: `End date is set automatically (${t.duration_days} days). You can edit every activity and cost afterwards.`,
    fields: [["title", "Trip title", "text"], ["origin", "Starting location", "text"], ["destination", "Destination", "text"], ["travelers", "Number of travellers", "number", 0, 'min="1"'], ["start_date", "Start date", "date"],
      ["budget", "Total planned budget (₹)", "number", 0, 'min="0"'], ["preferences", "Preferences (optional)", "textarea"], ["notes", "Notes (optional)", "textarea"]],
    values: { title: t.title, destination: t.destination, travelers: 2, budget: t.suggested_budget }, send: b => api("POST", `/api/templates/${id}/use`, b) });
  f._then = d => { setTrip(d.id); go("#planner"); };
}

/* ---------- Daily Planner ---------- */
function approvalBanner(t) {
  const last = t.approvals.filter(a => a.action === "Approved" || a.action === "Rejected").at(-1);
  if (t.status === "Draft") return `<div class="banner info">This itinerary is a <b>Draft</b>. Add your activities, then submit it for agency review.${t.approvals.at(-1)?.action === "Reset to Draft" ? `<br><b>Approval was reset:</b> ${esc(t.approvals.at(-1).reason)}` : ""}</div>`;
  if (t.status === "Pending Approval") return `<div class="banner warn">⏳ <b>Pending Approval</b> (submitted ${fts(t.submitted_at)}). The itinerary is locked until the simulated agency decides.</div>`;
  if (t.status === "Rejected") return `<div class="banner err">❌ <b>Rejected</b> ${fts(last?.created_at)}<br>Reason: ${esc(last?.reason)}${last?.feedback ? `<br>Feedback: ${esc(last.feedback)}` : ""}<br>Edit the itinerary and resubmit.</div>`;
  return `<div class="banner ok">✅ <b>Approved</b> ${fts(last?.created_at)} by ${esc(last?.actor)}${last?.feedback ? `<br>Feedback: ${esc(last.feedback)}` : ""}<br><span class="muted">This is itinerary approval only - it is not a confirmed ticket or hotel reservation. Material changes require approval again.</span></div>`;
}
let curTrip = null;
async function viewPlanner() {
  await loadTrips(); if (!trips.length) return view("<h1>Daily Planner</h1>" + empty("📅", "No trips to plan", "Create a trip or use a template first.", `<button class="btn primary" onclick="go('#explore')">Explore itineraries</button>`));
  const t = curTrip = (await api("GET", `/api/trips/${tripId}`)).d, lock = t.status === "Pending Approval", by = groupBy(t.activities, "date");
  view(`<h1>Daily Planner</h1><div class="bar">${picker(false, tripId, "setTrip")}<span class="sp"></span>
  <button class="btn" ${lock ? "disabled" : ""} onclick="tripForm(${t.id})">Edit trip</button>${t.status === "Draft" || t.status === "Rejected" ? `<button class="btn ok" onclick="submitTrip(${t.id})">${t.status === "Rejected" ? "Resubmit for approval" : "Submit for approval"}</button>` : ""}
  <button class="btn primary" ${lock ? "disabled title='Locked while pending review'" : ""} onclick="actForm()">+ Add activity</button></div>
  ${approvalBanner(t)}<div class="card"><h2>${esc(t.title)} ${badge(t.status)}</h2><div class="muted">${esc(t.origin)} → ${esc(t.destination)} · ${fdate(t.start_date)} – ${fdate(t.end_date)} · ${t.travelers} traveller(s)${t.template_id ? " · from template" : ""}</div>
  ${t.preferences ? `<p><b>Preferences:</b> ${esc(t.preferences)}</p>` : ""}${t.notes ? `<p><b>Notes:</b> ${esc(t.notes)}</p>` : ""}
  <div class="grid k"><div class="kpi"><span>Planned budget</span><b>${inr(t.budget)}</b></div><div class="kpi p"><span>Estimated activity cost</span><b>${inr(t.est_cost)}</b></div></div></div>
  <div class="card"><h2>Day-by-day plan</h2>${t.activities.length ? "" : `<p class="muted">No activities yet. Click “Add activity” to start planning.</p>`}
  ${days(t.start_date, t.end_date).map((d, i) => `<div class="day"><h4>Day ${i + 1} · ${fdate(d)}</h4>${(by[d] || []).map(a => `<div class="act"><span class="t">${a.time}</span><span class="b"><b>${esc(a.name)}</b><br><span class="muted">📍 ${esc(a.location)}${a.description ? " · " + esc(a.description) : ""}</span></span><span class="c">${inr(a.cost)}</span>
  <button class="btn" ${lock ? "disabled" : ""} onclick="actForm(${a.id})">Edit</button><button class="btn danger" ${lock ? "disabled" : ""} onclick="delAct(${a.id})">Delete</button></div>`).join("") || '<p class="muted">Nothing planned.</p>'}</div>`).join("")}</div>
  <div class="card"><h2>Approval history</h2>${t.approvals.length ? `<div class="timeline">${t.approvals.map(a => `<div>${badge(a.action)} ${fts(a.created_at)} · ${esc(a.actor)}${a.reason ? `<br>Reason: ${esc(a.reason)}` : ""}${a.feedback ? `<br>Feedback: ${esc(a.feedback)}` : ""}</div>`).join("")}</div>` : '<p class="muted">Not submitted yet.</p>'}</div>`);
}
function actForm(id) {
  const t = curTrip, v = id ? t.activities.find(a => a.id == id) : { date: t.start_date };
  formModal({ title: id ? "Edit activity" : "Add activity", ok: id ? "Activity updated." : "Activity added.", values: v, note: t.status === "Approved" ? "Changing an Approved itinerary (except descriptions) requires approval again." : "",
    fields: [["name", "Activity name", "text"], ["date", "Date", "date", 0, `min="${t.start_date}" max="${t.end_date}"`], ["time", "Time", "time"], ["location", "Location", "text"], ["cost", "Estimated cost (₹)", "number", 0, 'min="0"'], ["description", "Description (optional)", "textarea"]],
    send: b => api(id ? "PUT" : "POST", id ? `/api/activities/${id}` : `/api/trips/${t.id}/activities`, b) });
}
async function delAct(id) { if (await confirmBox("Delete this activity?", "This removes it from the itinerary and the estimated cost.", "Delete", true)) act("DELETE", `/api/activities/${id}`, undefined, "Activity deleted."); }

/* ---------- Travel Bookings ---------- */
const BKL = { Flight: ["From (airport / city)", "To (airport / city)", "Return date (optional)", "Flight no. / class / seat"], Train: ["From station", "To station", "Return date (optional)", "Train no. / class / berth"],
  Bus: ["Boarding point", "Destination", "Return date (optional)", "Operator type / seat"], Hotel: [null, "Hotel location / area", "Check-out date", "Room type / meal plan"], "Local Transport": ["Pickup location", "Drop location", "End date (optional)", "Vehicle type"] };
function bkAfter(f) {
  const sv = f.elements.service_type;
  const upd = () => { const L = BKL[sv.value]; $("#l_from_location").style.display = L[0] ? "" : "none"; if (L[0]) $("#l_from_location span").textContent = L[0];
    $("#l_to_location span").textContent = L[1]; $("#l_end_date span").textContent = L[2]; $("#l_service_details span").textContent = L[3]; $("#l_travel_date span").textContent = sv.value === "Hotel" ? "Check-in date" : "Travel date"; };
  sv.onchange = upd; upd();
}
let bks = [];
async function viewBookings() {
  await loadTrips(); const q = new URLSearchParams(Object.entries({ trip_id: bkTrip, service_type: bkType, status: bkStatus }).filter(x => x[1])).toString();
  bks = (await api("GET", "/api/bookings?" + q)).d; const sel = trips.find(t => t.id == bkTrip), approved = trips.filter(t => t.status === "Approved");
  const active = bks.filter(b => b.status !== "Cancelled"), total = active.reduce((s, b) => s + b.price, 0);
  const gate = sel && sel.status !== "Approved" ? `<div class="banner ${sel.status === "Pending Approval" ? "warn" : "err"}">Itinerary <b>${esc(sel.title)}</b> is <b>${esc(sel.status)}</b>. ${{ Draft: "Submit it for approval before adding bookings.", "Pending Approval": "New bookings are blocked until the agency approves it.", Rejected: "New bookings are blocked. Revise and resubmit it." }[sel.status]}</div>` : "";
  view(`<h1>Travel Bookings</h1><div class="banner info">🧪 <b>Demo booking records only.</b> No real tickets are issued, no hotel rooms are reserved and no payment is taken. <b>Itinerary approval</b> (agency review) is separate from a booking's <b>status</b> (Pending / Confirmed / Cancelled).</div>
  <div class="bar">${picker(true, bkTrip, "setBkTrip")}<label class="picker"><b>Type</b><select onchange="bkType=this.value;route()">${opts([["", "All"], ...SVC.map(s => [s, s])], bkType)}</select></label>
  <label class="picker"><b>Status</b><select onchange="bkStatus=this.value;route()">${opts([["", "All"], ["Pending", "Pending"], ["Confirmed", "Confirmed"], ["Cancelled", "Cancelled"]], bkStatus)}</select></label><span class="sp"></span>
  <button class="btn primary" onclick="bkForm()" ${sel && sel.status !== "Approved" ? "disabled" : ""}>+ New booking</button></div>${gate}
  <div class="grid k"><div class="kpi"><span>Bookings shown</span><b>${bks.length}</b></div><div class="kpi"><span>Active (not cancelled)</span><b>${active.length}</b></div><div class="kpi g"><span>Active booking cost</span><b>${inr(total)}</b></div></div><br>
  ${bks.length ? `<div class="card tw"><table><tr><th>Service</th><th>Trip</th><th>Route / location</th><th>Dates</th><th>Traveller</th><th>Price</th><th>Status</th><th></th></tr>${bks.map(b => `<tr><td>${ICON[b.service_type]} <b>${esc(b.service_type)}</b><br>${esc(b.provider)}<br><span class="muted">${esc(b.reference)}</span></td>
  <td>${esc(b.trip_title)}<br>${badge(b.trip_status)}</td><td>${b.from_location ? esc(b.from_location) + " → " : ""}${esc(b.to_location)}</td><td>${fdate(b.travel_date)}${b.end_date ? "<br>→ " + fdate(b.end_date) : ""}</td><td>${esc(b.traveler_name)}<br><span class="muted">${b.travelers_count} traveller(s)</span></td>
  <td>${inr(b.price)}</td><td>${badge(b.status)}${b.expense_recorded ? '<br><span class="muted">expense recorded</span>' : ""}</td><td><button class="btn" onclick="bkView(${b.id})">View</button>
  ${b.status !== "Cancelled" ? `<button class="btn" ${b.trip_status !== "Approved" ? 'disabled title="Itinerary not approved"' : ""} onclick="bkForm(${b.id})">Edit</button><button class="btn danger" onclick="bkCancel(${b.id})">Cancel</button>` : ""}
  ${b.status === "Confirmed" && !b.expense_recorded && b.price > 0 ? `<button class="btn" onclick="bkExpense(${b.id})">Record as expense</button>` : ""}</td></tr>`).join("")}</table></div>`
    : empty("🎫", "No bookings found", approved.length ? "Add a demo booking for one of your approved itineraries." : "Bookings need an approved itinerary. Submit one for approval in the Daily Planner, then approve it in Agency Review (demo).", approved.length ? `<button class="btn primary" onclick="bkForm()">+ New booking</button>` : `<button class="btn" onclick="go('#planner')">Go to planner</button>`)}`);
}
function setBkTrip(v) { bkTrip = v; route(); }
function bkForm(id) {
  const approved = trips.filter(t => t.status === "Approved"); if (!id && !approved.length) return toast("No approved itineraries yet. Get an itinerary approved first.", "warn");
  const v = id ? bks.find(b => b.id == id) : { service_type: "Flight", trip_id: bkTrip || approved[0].id, status: "Pending" };
  const trip = id ? [] : [["trip_id", "Linked trip (approved only)", "select", approved.map(t => [t.id, t.title])]];
  formModal({ title: id ? "Edit booking" : "New demo booking", wide: true, ok: id ? "Booking updated." : "Booking saved (demo record).", values: v, after: bkAfter,
    fields: [...trip, ["service_type", "Service type", "select", SVC.map(s => [s, s])], ["provider", "Provider (airline / operator / hotel)", "text"], ["reference", "Booking reference (blank = auto)", "text"], ["from_location", "From", "text"], ["to_location", "To", "text"],
      ["travel_date", "Travel date", "date"], ["end_date", "End date", "date"], ["traveler_name", "Lead traveller name", "text"], ["travelers_count", "Number of travellers", "number", 0, 'min="1"'], ["price", "Price (₹)", "number", 0, 'min="0"'],
      ["status", "Status", "select", [["Pending", "Pending"], ["Confirmed", "Confirmed"]]], ["booking_date", "Booking date (blank = today)", "date"], ["service_details", "Service details", "textarea"], ["notes", "Notes", "textarea"]],
    send: b => api(id ? "PUT" : "POST", id ? `/api/bookings/${id}` : "/api/bookings", b) });
}
function bkView(id) {
  const b = bks.find(x => x.id == id); const row = (k, v) => `<dt>${k}</dt><dd>${v || "—"}</dd>`;
  modal(`<h3>${ICON[b.service_type]} ${esc(b.service_type)} booking ${badge(b.status)}</h3><div class="banner info">Demo record - not a real ticket or reservation.</div><dl class="kv">${row("Trip", esc(b.trip_title) + " " + badge(b.trip_status))}${row("Provider", esc(b.provider))}${row("Reference", esc(b.reference))}
  ${row("From", esc(b.from_location))}${row("To / location", esc(b.to_location))}${row("Travel date", fdate(b.travel_date))}${row("End date", b.end_date ? fdate(b.end_date) : "")}${row("Traveller", esc(b.traveler_name) + " (" + b.travelers_count + ")")}${row("Price", inr(b.price))}
  ${row("Booked on", fdate(b.booking_date))}${row("Details", esc(b.service_details))}${row("Notes", esc(b.notes))}${row("Cancelled at", b.cancelled_at ? fts(b.cancelled_at) : "")}${row("Expense recorded", b.expense_recorded ? "Yes" : "No")}</dl><div class="actions"><button class="btn" onclick="closeModal()">Close</button></div>`);
}
async function bkCancel(id) { if (await confirmBox("Cancel this booking?", "The booking stays in your history as Cancelled and stops counting towards active booking cost.", "Cancel booking", true)) act("POST", `/api/bookings/${id}/cancel`, undefined, "Booking cancelled and kept in history."); }
async function bkExpense(id) { act("POST", `/api/bookings/${id}/record-expense`, undefined, "Recorded as an actual expense."); }

/* ---------- Budget & Expenses ---------- */
async function viewBudget() {
  await loadTrips(); if (!trips.length) return view("<h1>Budget &amp; Expenses</h1>" + empty("💰", "No trips yet", "Budgets belong to trips. Create a trip first.", `<button class="btn primary" onclick="go('#trips')">Go to My Trips</button>`));
  const t = (await api("GET", `/api/trips/${tripId}`)).d, b = t.budget_summary, exps = (await api("GET", `/api/trips/${tripId}/expenses`)).d;
  const bk = (await api("GET", `/api/bookings?trip_id=${tripId}`)).d, unrec = bk.filter(x => x.status === "Confirmed" && !x.expense_recorded && x.price > 0);
  const pct = b.planned_budget ? Math.min(100, b.actual_expenses / b.planned_budget * 100) : (b.actual_expenses > 0 ? 100 : 0), max = Math.max(1, ...b.by_category.map(c => c.amount));
  window.curExp = exps; window.curBudgetTrip = t;
  view(`<h1>Budget &amp; Expenses</h1><div class="bar">${picker(false, tripId, "setTrip")}<span class="sp"></span><button class="btn primary" onclick="expForm()">+ Record expense</button></div>
  ${b.warnings.map(w => `<div class="banner err">⚠️ ${esc(w)}</div>`).join("")}
  <div class="grid k"><div class="kpi"><span>Planned budget</span><b>${inr(b.planned_budget)}</b></div><div class="kpi p"><span>Estimated activity costs</span><b>${inr(b.estimated_activity_cost)}</b></div>
  <div class="kpi a"><span>Active bookings (not cancelled)</span><b>${inr(b.active_booking_cost)}</b></div><div class="kpi ${b.actual_expenses > b.planned_budget ? "r" : "g"}"><span>Actual expenses</span><b>${inr(b.actual_expenses)}</b></div>
  <div class="kpi ${b.remaining_budget < 0 ? "r" : "g"}"><span>Remaining budget</span><b>${inr(b.remaining_budget)}</b></div></div><br>
  <div class="card"><b>Actual spend vs planned budget</b><div class="progress ${b.actual_expenses > b.planned_budget ? "over" : ""}" style="margin:8px 0"><i style="width:${pct}%"></i></div>
  <span class="muted">Remaining = planned budget − actual expenses. Active bookings are commitments (${inr(b.unrecorded_booking_cost)} not yet recorded as expenses) and are never counted twice: once recorded, a booking moves into actual expenses. Projected total: ${inr(b.projected_total)}.</span></div>
  <div class="card"><h2>Expense breakdown by category</h2>${b.by_category.length ? b.by_category.map(c => `<div class="cat"><span class="n">${esc(c.category)}</span><span class="l"><i style="width:${c.amount / max * 100}%"></i></span><b>${inr(c.amount)}</b></div>`).join("") : '<p class="muted">No expenses recorded yet.</p>'}</div>
  ${unrec.length ? `<div class="card"><h2>Confirmed bookings not yet in actual expenses</h2>${unrec.map(x => `<div class="act"><span class="b">${ICON[x.service_type]} <b>${esc(x.provider)}</b> · ${esc(x.reference)}</span><span class="c">${inr(x.price)}</span><button class="btn" onclick="bkExpense(${x.id})">Record as expense</button></div>`).join("")}</div>` : ""}
  <div class="card"><h2>Recorded expenses</h2>${exps.length ? `<div class="tw"><table><tr><th>Date</th><th>Category</th><th>Description</th><th>Amount</th><th></th></tr>${exps.map(e => `<tr><td>${fdate(e.expense_date)}</td><td>${esc(e.category)}</td><td>${esc(e.description)}${e.booking_id ? ' <span class="badge gray">from booking</span>' : ""}</td><td>${inr(e.amount)}</td>
  <td><button class="btn" onclick="expForm(${e.id})">Edit</button><button class="btn danger" onclick="delExp(${e.id})">Delete</button></td></tr>`).join("")}</table></div>` : '<p class="muted">Nothing recorded. Use “Record expense” to add what you actually spend.</p>'}</div>`);
}
function expForm(id) {
  const v = id ? curExp.find(e => e.id == id) : { expense_date: new Date().toISOString().slice(0, 10), category: "Food" };
  formModal({ title: id ? "Edit expense" : "Record actual expense", ok: id ? "Expense updated." : "Expense recorded.", values: v,
    fields: [["category", "Category", "select", EXPC.map(c => [c, c])], ["description", "Description", "text"], ["amount", "Amount (₹)", "number", 0, 'min="0.01"'], ["expense_date", "Date", "date"]],
    send: b => api(id ? "PUT" : "POST", id ? `/api/expenses/${id}` : `/api/trips/${tripId}/expenses`, b) });
}
async function delExp(id) { if (await confirmBox("Delete this expense?", "Your remaining budget will be recalculated.", "Delete", true)) act("DELETE", `/api/expenses/${id}`, undefined, "Expense deleted."); }

/* ---------- Agency Review (simulated) ---------- */
function tripDetail(t) {
  const by = groupBy(t.activities, "date"), b = t.budget_summary;
  return `<dl class="kv"><dt>Route</dt><dd>${esc(t.origin)} → ${esc(t.destination)}</dd><dt>Dates</dt><dd>${fdate(t.start_date)} – ${fdate(t.end_date)}</dd><dt>Travellers</dt><dd>${t.travelers}</dd><dt>Planned budget</dt><dd>${inr(b.planned_budget)}</dd>
  <dt>Activity estimate</dt><dd>${inr(b.estimated_activity_cost)} ${b.estimated_activity_cost > b.planned_budget ? '<span class="badge red">exceeds budget</span>' : ""}</dd><dt>Preferences</dt><dd>${esc(t.preferences) || "—"}</dd><dt>Notes</dt><dd>${esc(t.notes) || "—"}</dd><dt>Submitted</dt><dd>${fts(t.submitted_at)}</dd></dl>
  ${Object.keys(by).sort().map(d => `<div class="day"><h4>${fdate(d)}</h4>${by[d].map(a => `<div class="act"><span class="t">${a.time}</span><span class="b"><b>${esc(a.name)}</b><br><span class="muted">📍 ${esc(a.location)}${a.description ? " · " + esc(a.description) : ""}</span></span><span class="c">${inr(a.cost)}</span></div>`).join("")}</div>`).join("")}`;
}
async function viewReview() {
  const pend = (await api("GET", "/api/review/pending")).d, hist = (await api("GET", "/api/review/history")).d;
  view(`<h1>Travel Agency Review <span class="badge amber">DEMO MODE</span></h1>
  <div class="banner demo"><b>Simulated agency - for college demonstration only.</b> You are acting as “${"Demo Reviewer"}”. No real travel agency is contacted. Approving an itinerary is <u>not</u> a ticket, hotel or payment confirmation; it only unlocks demo booking records.</div>
  <div class="chips"><span class="chip ${reviewTab === "pending" ? "on" : ""}" onclick="reviewTab='pending';route()">Pending (${pend.length})</span><span class="chip ${reviewTab === "history" ? "on" : ""}" onclick="reviewTab='history';route()">Reviewed (${hist.length})</span></div>
  ${reviewTab === "pending" ? (pend.length ? `<div class="grid">${pend.map(t => `<div class="card tcard"><h3>${esc(t.title)}</h3><div class="meta">${esc(t.origin)} → ${esc(t.destination)}<br>${fdate(t.start_date)} – ${fdate(t.end_date)} · ${t.travelers} traveller(s)<br>Budget ${inr(t.budget)} · Activities ${inr(t.est_cost)} (${t.activity_count})<br>Submitted ${fts(t.submitted_at)}</div>
  <div class="acts"><button class="btn primary" onclick="reviewOpen(${t.id})">Review itinerary</button></div></div>`).join("")}</div>` : empty("📭", "Nothing waiting for review", "Submit an itinerary for approval from the Daily Planner or My Trips and it will appear here."))
  : (hist.length ? `<div class="card tw"><table><tr><th>Decided</th><th>Trip</th><th>Decision</th><th>Reason</th><th>Feedback</th><th>Reviewer</th><th>Trip status now</th></tr>${hist.map(h => `<tr><td>${fts(h.created_at)}</td><td><b>${esc(h.title)}</b><br><span class="muted">${esc(h.destination)}</span></td><td>${badge(h.action)}</td><td>${esc(h.reason) || "—"}</td><td>${esc(h.feedback) || "—"}</td><td>${esc(h.actor)}</td><td>${badge(h.trip_status)}</td></tr>`).join("")}</table></div>` : empty("🗂️", "No decisions yet", "Approved and rejected itineraries are listed here."))}`);
}
async function reviewOpen(id) {
  const t = (await api("GET", `/api/trips/${id}`)).d;
  modal(`<h3>Review: ${esc(t.title)} ${badge(t.status)}</h3><p class="muted">Simulated agency decision (demo).</p>${tripDetail(t)}
  <label><span>Feedback (optional)</span><textarea id="rv_fb"></textarea></label><label><span>Rejection reason (required only when rejecting)</span><textarea id="rv_rs"></textarea></label><div class="err" id="rv_err"></div>
  <div class="actions"><button class="btn" onclick="closeModal()">Close</button><button class="btn bad" onclick="decide(${id},'reject')">Reject</button><button class="btn ok" onclick="decide(${id},'approve')">Approve</button></div>`, true);
}
async function decide(id, kind) {
  const fb = $("#rv_fb").value, rs = $("#rv_rs").value, r = await api("POST", `/api/review/${id}/${kind}`, kind === "reject" ? { reason: rs, feedback: fb } : { feedback: fb });
  if (!r.ok) { $("#rv_err").textContent = errTxt(r.d); return; }
  closeModal(); toast(kind === "approve" ? "Itinerary approved (simulated decision)." : "Itinerary rejected; reason recorded."); route();
}
route();
