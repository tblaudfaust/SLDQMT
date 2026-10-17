# 2026 SLPHC Census Incident Log — design proposal

Stage 0 deliverable, 16 October 2026, revised 17 October 2026 with tablet distribution and custody.

**Built on 17 October 2026 (web):** the register, handling actions with the dated log, district scoping, the District Statistician and Incident Viewer roles, the public reporting page by SA code (censusme.statistics.sl/report-incident) with tracking by number, SA code upload, the dashboard, Excel and PDF exports, and the warning on exit checkouts. Decisions taken: no automatic escalation (the dashboard lists what needs action), default owner is the District Statistician, exit clearance only warns, nothing is hidden by category. **Not yet built:** reporting from the Android app with photos and GPS (stage 2), attachments, one-click "raise as incident" from the other modules, tablet distribution and custody (section 8).

## 1. Purpose

A single, national register of everything that goes wrong during the 2026 Population and Housing
Census and threatens coverage, data quality, staff safety, assets or the timetable, from the first day
of training to the close of field operations, together with the custody of every tablet from HQ to
the district, to the supervisor and the enumerator, and back (section 8). Every incident is logged once, where it happens, is
visible to the right level within minutes, carries an owner and a deadline, and is closed with a
recorded resolution. Management sees the same picture from every district, every day, and can act
before an incident reaches the data.

The log replaces WhatsApp threads, phone calls and paper notes as the record of incidents. Calls still
happen for urgent matters; the log is where the incident and its follow-up are written down.

## 2. What already exists, and how the log fits

| Existing module | What it records | Relation to the incident log |
|---|---|---|
| Field Monitor error follow-up (tablet) | Data errors a DQM found, followed up by a Field Monitor | A data error is **not** an incident. An incident is the event behind errors (a lost tablet, a flooded EA, an enumerator who left). The log can link to error records when relevant. |
| Daily DQM report | Per-district daily data-quality figures | Its "system issues" rows (outliers, GPS, sync) stay there; a serious one can be raised as an incident with one click. |
| M&E field monitoring (Android) | Observation of an EA visit; ⚑ items create a Critical issue | A ⚑ issue of the kind "security concern" (C15), "team not in EA" (A16), "money asked" (G10) can be escalated into an incident from the dashboard. |
| Daily Facilitator Report | Training-day escalations (section H) | Section H rows can be promoted to incidents so they are tracked to closure after training ends. |
| Field exit protocol | End-of-field checkout per team | Open incidents on a team block its clearance until resolved or waived. |

The log therefore becomes the **one place where an open problem is tracked to closure**, whatever module first noticed it.

## 3. Who reports, who acts

| Role (existing) | Reports incidents | Sees | Acts |
|---|---|---|---|
| Field Monitor (tablet, offline) | Yes, from the field | Own incidents and those of their SAs | Adds updates; cannot close |
| District M&E Officer (app, offline) | Yes | Own district | Adds updates |
| District DQM / District Coordinator (web) | Yes | Own district | Assign owner, set deadline, close, escalate to region |
| Regional staff / Regional M&E | Yes | Own region | Same as district plus reassign across districts, escalate to national |
| National DQM, National M&E, Admin | Yes | Everything | Everything, plus categories, SLA settings, exports |
| New: **Incident Desk** (optional role) | — | Everything | Triage and follow-up at HQ without other rights |

Rights (new permission codes, registry-driven like the others): `incidents.report`, `incidents.view`,
`incidents.manage` (assign, close, reopen), `incidents.escalate`, `incidents.export`,
`incidents.settings`. Defaults follow the table above; an administrator can grant any right to any
account from the user rights dialog, as today.

Supervisors and enumerators have no accounts. Their incidents are reported by the Field Monitor, DQM
or M&E officer who received them; the form records who originally raised it (name, role, phone).

## 4. The incident record

### 4.1 Identification (set automatically where possible)
- Incident number: `INC-<district abbreviation>-<yyyymm>-<nnnn>`, e.g. INC-Bo-202611-0042.
- Reported by (account), on behalf of (name, role, phone, optional), date and time of the incident, date and time reported.
- Where: region → district → chiefdom → section → SA → EA (any level; the lower levels are optional), locality text, GPS point (captured by the app, optional on the web).
- Phase: pre-field, training, listing, enumeration, mop-up, post-enumeration.

### 4.2 Classification
- **Category** (one) and **sub-category**, from a list the national level maintains. Proposed starting list:

| Category | Sub-categories |
|---|---|
| Security and safety | Threat or assault on staff, theft or robbery, road accident, civil unrest, animal attack, health emergency, harassment (incl. PSEAH), other |
| Staff | Absent or abandoned post, resignation, misconduct, impersonation, death or serious illness, payment or allowance dispute, dismissal |
| Equipment and systems | Tablet lost or stolen, tablet damaged or dead, power bank or charger, SIM or data bundle, CAPI application fault, sync failure, wrong application version, GPS not working |
| Maps and geography | Wrong or missing map, boundary dispute between EAs, EA too large or split, settlement missing from map, locality inaccessible |
| Community and respondents | Refusal (household), refusal (community), misinformation or rumour, political interference, chief or leader not informed, demand for payment |
| Data quality | Fabrication suspected, interviews outside EA, duplicated households, systematic error found by DQM, data loss on device |
| Logistics | Transport, fuel, accommodation, materials and stationery, food, venue, late deployment |
| Environment | Flooding, impassable road, river crossing, weather, fire |
| Training | Trainee or trainer issue not resolved in the Daily Facilitator Report |
| Other | Free text |

- **Severity**: Critical (stops enumeration or endangers people), Major (disrupts a team or an SA), Minor (local, workaround in place). Severity sets the default deadline.
- **Impact**: teams affected, enumerators affected, households or EAs affected (counts), estimated days lost, assets involved (tablet IDs).

### 4.3 Narrative and evidence
- Description (what happened), immediate action taken, help needed.
- Attachments: photos (from the app camera or upload), documents (police report, memo), up to 10 per incident, 5 MB each.
- Links: error records, M&E visit, DQM report, daily facilitator report, exit checkout, another incident (duplicate or related).

### 4.4 Handling
- **Status**: New → Acknowledged → In progress → Resolved → Closed; plus Rejected (not an incident, with reason) and Reopened.
- **Owner** (an account) and **owner level** (district, region, national); **due date**; escalation level.
- **Updates**: a dated log of comments, status changes, reassignments and attachments, each with the author. Nothing is edited in place after submission; corrections are updates.
- **Resolution**: what was done, by whom, when, cost if any, and whether the root cause is fixed or a workaround is in place.
- **Lessons**: optional free text used in the daily brief.

### 4.5 Service levels (settings, editable nationally)
| Severity | Acknowledge within | Resolve within | Escalate automatically if not acknowledged |
|---|---|---|---|
| Critical | 1 hour | 24 hours | to region after 1 hour, to national after 4 hours |
| Major | 4 hours | 3 days | to region after 24 hours |
| Minor | 24 hours | 7 days | none |

"Overdue" and "breached" flags are computed from these; the dashboard shows them in red.

## 5. How an incident is reported

- **Android app** (Field Monitors, District M&E Officers): a new "Report incident" entry on the home screen; works offline, queues and syncs like errors and visit forms; captures GPS and photos; the categories list comes down at sync. The reporter sees their incidents and their status.
- **Web** (DQM, coordinators, regional and national staff): Incidents page with a New incident form; the same fields; also "Raise as incident" buttons on the DQM report system-issue rows, the M&E issue log, the Daily Facilitator Report escalations and the exit checkout.
- **Public page** (optional, for discussion): a censusme.statistics.sl link for supervisors without accounts to report, anonymous or with a phone number, landing in the district queue as "unverified". Recommended only if supervisors are expected to report directly.

## 6. Follow-up workflow

1. The incident arrives in the district queue (and, if Critical, is shown immediately at region and national level).
2. A district manager **acknowledges** it, sets the owner and confirms severity and due date (defaults from the SLA).
3. The owner records **updates** until it is **resolved**; the person who reported it is told through the app at the next sync (and sees the resolution).
4. The district manager **closes** it, or **escalates** it to region or national when the fix is beyond the district (missing tablets from stock, a security decision, a boundary ruling).
5. A closed incident can be **reopened** within 14 days.
6. Critical incidents unacknowledged within the SLA appear on the regional and national "needs attention" lists; email or SMS alerts are out of scope for now (same decision as for field monitoring), but the daily brief carries them.

## 7. Dashboards and reports

Scope rules as everywhere: district users see their district, regional users their region, national users everything.

- **Overview**: open incidents by severity, new today, overdue, breached SLA, average time to acknowledge and to resolve, resolved this week; a trend by day; a map of incidents with GPS points (Critical in red).
- **By district / region**: counts by status and severity, overdue, median resolution time, incidents per 100 EAs (to compare districts fairly).
- **By category**: what is going wrong most, where, and whether it is rising or falling.
- **Teams and assets**: SAs with repeated incidents; tablets involved in incidents (links to the device register).
- **Incident register**: filterable table (status, severity, category, district, phase, dates, owner, overdue), full detail drawer with the update log and attachments.
- **Daily incident brief** (PDF and Excel): the last 24 hours by district, Critical and overdue first, with owners and due dates, for the morning coordination call.
- **Exports**: Excel with Register, Updates, By district, By category, SLA sheets; PDF for the brief.
- **Audit**: every change is in the existing audit log.

## 8. Tablet distribution and custody

Tablets (and their power banks, chargers, SIM cards and cases) move from HQ to the districts, from the
district to the supervisory areas, and from supervisors to enumerators, then back the same way at the
end of fieldwork. The log tracks every step, so at any moment HQ knows where each tablet is, who signed
for it, in what condition, and where the numbers do not add up. Damage, loss and shortfalls become
incidents automatically, linked to the device.

### 8.1 Asset register
- One row per tablet: asset tag (Stats SL sticker number), serial number, IMEI, model, batch and
  supplier delivery note, date received at HQ, initial condition, accessories issued (power bank,
  charger, case, SIM with number, screen protector), current custodian and level, current condition,
  status (in store, in transit, issued, in use, returned, under repair, lost, stolen, written off).
- Loaded once by HQ from the supplier's list (Excel upload: asset tag, serial, IMEI, model, batch),
  then kept up to date by the hand-overs below. Tablets the app registers (the existing device
  register, which records the device ID, model and Android version when a Field Monitor or M&E officer
  signs in) are matched to the asset register by serial or IMEI, so a tablet that syncs is known to be
  the one issued.

### 8.2 Planned allocation
- HQ records the plan: tablets per district, then per SA (one per enumerator and supervisor plus the
  reserve), from the workload frame already in the system (SAs, enumerators, Field Monitors, DQMs).
- The plan is the baseline every later count is compared with.

### 8.3 Hand-overs (chain of custody)
Each movement is a **hand-over** with: from (level and person), to (level and person, with phone),
date, place, the list of asset tags (scanned or typed; bulk by range or by Excel), accessories per
tablet, condition at hand-over (working, screen cracked, battery weak, not powering on, other), and a
signature or photo of the signed paper form. Levels:

| Step | From | To | Who records it |
|---|---|---|---|
| 1 | HQ store | District Census Office (coordinator or officer) | HQ logistics on the web; the district confirms receipt |
| 2 | District office | SA supervisor | District on the web, or the Field Monitor on the tablet app |
| 3 | Supervisor | Enumerator | Field Monitor or DQM on the app or web, on the supervisor's behalf |
| 4 | Enumerator to supervisor to district to HQ (return) | reverse of 1 to 3 | same |
| Any time | Swap or replacement | between any two custodians | whoever issues it |

A hand-over is **pending** until the receiving side confirms (on the web or at the next app sync);
HQ sees pending hand-overs older than 48 hours. Confirming with a different count than sent raises a
**shortfall** automatically (8.5).

### 8.4 Damage, faults and loss
- Reported from the app or the web against a specific asset tag: damaged (screen, battery, charging
  port, water, other), faulty (will not start, application, SIM, GPS), lost, stolen (with police report
  attachment), returned to HQ for repair, replaced (new asset tag linked to the old one).
- Each report **is an incident** of the "Equipment and systems" category with the asset linked, so it
  carries severity, owner, deadline, updates and closure like any other incident. The asset's status
  and condition change at the same time.
- Repairs: HQ records repair sent, repaired and reissued, or written off; the history stays on the
  asset.

### 8.5 Gaps and reconciliation
Computed, not typed, at every level:
- **Allocation gap**: planned minus issued, per district and SA (tablets, power banks, SIMs).
- **Transit gap**: sent minus confirmed received, per hand-over.
- **Custody gap**: issued minus accounted for (in use, returned, under repair, reported lost or stolen).
- **Working gap**: enumerators without a working tablet today (from the device condition and the
  fault incidents), the figure that decides whether enumeration can proceed.
- **Return gap** at the end of fieldwork: issued minus returned, per SA, with the names of custodians
  who have not returned, linked to the exit checkout so a team is not cleared with tablets outstanding.
- A nightly check compares the asset register with the device register (tablets that synced in the
  last 24 hours but are recorded as in store or returned, tablets recorded as issued that never synced).

### 8.6 Pages and reports
- **Tablet register** (national, regional and district views, scoped): search by asset tag, serial,
  IMEI, custodian, status; detail with the full custody chain and incidents.
- **Hand-over form** on the web and in the app, with bulk entry by tag range, Excel or scanning the
  barcode on the sticker with the tablet camera.
- **Distribution dashboard**: planned, issued, received, in use, faulty, lost and returned per district
  and SA; the five gaps above; a map of districts coloured by working gap; ageing of pending hand-overs.
- **Reports**: distribution status (Excel and PDF), custody chain per tablet (for audits and insurance),
  damage and loss register, end-of-field return reconciliation per district.
- The **daily incident brief** gains a tablets block: faulty, lost, stolen and short today, by district.

### 8.7 Data model (additional tables)
- `asset`: the register row of 8.1 (asset tag unique, serial, IMEI, model, batch, accessories as flags
  and SIM number, status, condition, current custodian id or name, current level, district, SA, notes).
- `asset_handover` and `asset_handover_item`: one hand-over with its list of tags and per-tag
  condition; sent_at, sent_by, received_at, received_by, confirmation status, signature or photo
  attachment.
- `asset_allocation`: planned numbers per district and SA by item type.
- `asset_event`: status and condition changes with the linked incident and attachment.
- The existing `device` table is linked by serial or IMEI once the app reports them (the app will send
  the serial and IMEI at registration from the next version).

### 8.8 Roles
- HQ logistics (national): loads the register and the plan, records HQ hand-overs, repairs and
  write-offs; new right `assets.manage`.
- District office: receives from HQ, issues to SAs, records returns; `assets.handover` within the
  district.
- Field Monitors, DQMs and M&E officers: hand-overs between supervisors and enumerators and damage or
  loss reports from the field, for their SAs or district; `assets.handover` and `incidents.report`.
- Everyone with `assets.view` sees the register and dashboards in their scope.

### 8.9 Additional questions
11. Is there a supplier list with serial and IMEI per tablet that HQ can upload, and is a Stats SL
    asset sticker (barcode) on every tablet?
12. Which accessories must be tracked individually (SIM numbers), and which only as counts?
13. Who signs for tablets at the district: the Census Coordinator, the Census Officer, or both?
14. Should enumerators be named in the custody chain (names come from the frame) or is custody held at
    supervisor level only?
15. Should a team with tablets not returned be blocked from exit clearance, or flagged?
16. Is a lost or stolen tablet always Critical, or Major unless data on it was not synced?

## 9. Data model (new tables)

- `incident` — the record of section 4 (columns for identification, classification, impact counts, status, owner, due, escalation level, GPS, timestamps, reporter, on_behalf_of, resolution fields, soft delete).
- `incident_update` — dated updates: type (comment, status, assignment, escalation, attachment, link), text, author, old and new values.
- `incident_attachment` — file metadata; files stored on the server under `/opt/sldqmt/uploads/incidents/` (not in the database), served through authenticated links like the manuals.
- `incident_link` — links to error, M&E visit, DQM report, facilitator report, checkout or another incident.
- `incident_category` — category and sub-category list, active flag, default severity, sort order; editable on the web by the national level.
- Settings: SLA hours per severity, auto-escalation delays, reopen window, attachment limits.

Numbering uses the district abbreviations already used for staff codes (Bo, Kai, WAU …).

## 10. Build stages

| Stage | Content | Shown working with |
|---|---|---|
| 1 | Tables, categories, rights, web form and register, detail with updates, close and reopen, district scoping, audit | A district DQM reports and closes an incident; a regional user sees it; another district cannot |
| 2 | Android: report incident offline with GPS and photos, sync, see status; attachments on the web | A Field Monitor reports from the tablet in airplane mode; it appears on the web after sync |
| 3 | Escalation, SLA, owners and deadlines, overdue flags, "raise as incident" from the four existing modules, link to exit clearance | A Critical incident escalates on time; an open incident blocks a team's clearance |
| 4 | Dashboards (overview, by district, by category, map), daily brief, exports | National overview with real districts |
| 5 | Categories and SLA settings pages, optional public reporting link, user guide, training note | Admin edits a category; a guide for reporters and for managers |
| 6 | Tablet register and allocation plan upload, hand-overs HQ to district to SA to enumerator with confirmation, damage and loss as incidents, the five gaps, distribution dashboard and reports, return reconciliation linked to exit clearance; app: hand-over and damage report with barcode scan | HQ issues 50 tablets to Bo; Bo confirms 48 and a shortfall incident opens; a Field Monitor reports a cracked screen from the tablet; the dashboard shows the working gap per SA |

Each stage is tested like the other modules (server tests, dashboard build, emulator run for stage 2) and deployed to sldqm-fm.statistics.sl.

## 11. Questions before stage 1

1. **Who reports from the field**: Field Monitors and District M&E Officers through the app, or should Supervisors have a way to report without an account (public link)?
2. **Categories**: is the list in 4.2 the right starting point, and who at HQ owns it?
3. **Severity and service levels**: are the SLA hours in 4.5 acceptable, and should automatic escalation go to region, to national, or both?
4. **Ownership**: should the District Census Coordinator (technical) or the District Census Officer (administration) be the default owner, or does it depend on the category (security to the officer, data to the coordinator)?
5. **Exit clearance**: should an open Major or Critical incident block a team's exit clearance, or only be shown as a warning?
6. **Attachments**: photos only from the app, or also documents on the web? Any storage limit per district?
7. **Alerts**: keep to the in-system lists and the daily brief (as for field monitoring), or add SMS or email for Critical incidents?
8. **Sensitive incidents**: PSEAH and misconduct cases may need a restricted view (only the reporter, the national focal point and HQ). Should these categories be hidden from district and regional lists?
9. **Numbering**: INC-<district>-<yyyymm>-<nnnn> as proposed, or a national running number?
10. **Where in the menu**: its own group "Incidents" visible to every web role, or under Daily DQM reporting?
