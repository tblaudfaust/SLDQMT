# 2026 SLPHC M&E Field Monitoring module: design report

Stage 0 deliverable, 7 October 2026, kept as the design record. Stage 1 (roles, scoped access, frame) and stage 2 (Android forms, GPS, sync) are live; see the stage notes at the end.

## (a) My understanding of the requirements

The module lets M&E officers record one structured visit per EA (the questionnaire of 7 October 2026, sections A to J) from a phone in the field, offline, with an automatic GPS point, and turns the submitted forms into district, regional and national dashboards with drill-down, an issues log with escalation, coverage tracking of chiefdoms and sections, GPS integrity checks, exports and a daily PDF brief. It lives inside the existing Statistics Sierra Leone system (same sign-in, same server, same Monitoring & Evaluation menu as the training evaluations) and must enforce geography on the server: a district officer can never see another district's data through the interface or the API.

Key rules I will implement exactly as written in the questionnaire:

- Response codes 1 Yes, 2 No, 3 Partly, 8 Not observed; ratings 4 to 1; ⚑ items answered 2 create a J-1 issue row automatically, Critical ones alert the District Statistician and the regional M&E officer.
- Routing by phase A12: P = sections A to C, then I and J (D, E, F, G, H skipped); L = A to E, then H to J (F and G skipped); E or M = A to D, F, G, H to J (E skipped). A16 = No: A17, then I and J only. B10 = No skips B11; C1 = No skips C2 to C7; C9 = 0 skips C10; H7 = No skips H8; I1 = No skips I2 and I3 for that respondent; I5 = No skips I6; special-population group not present leaves the arrangement blank; G2 = No skips G3 to G11 and logs a Critical issue; F household refusal skips F1 to F19; J9 = No skips the date.
- Section G is repeated for at least two households per visit in phases E and M; section I has three respondents (leader, resident 1, resident 2).
- Validation: EA code must exist in the frame, A3 and F8 times in order, counts not negative, D10 between 0 and 3, G7 match within 2 years, J7 computed as the rounded mean of the J1 to J6 dimensions rated.
- Submission is blocked without a GPS fix; location flags (outside district, chiefdom or section; repeated coordinates; impossible speed; poor accuracy; night-time submission) flag but never block.
- Annex indicators computed daily per officer, district, region and nation against configurable targets.

## (b) The frame

Source: `NATIONAL_FIELD_MONITORING_MASTER_FRAME.xlsx`, sheet ENUMERATION_AREA (one row per EA) plus LOCALITY, SUPERVISORY_AREA, BY_CHIEFDOM, FIELD_MONITOR and ENUMERATOR_ASSIGNMENT.

| Level | Rows / distinct codes | Code format |
|---|---|---|
| Regions | 5 (Eastern 1, Northern 2, North West 3, Southern 4, Western 5) | 1 digit |
| Districts | 16 | 2 digits (11 Kailahun … 52 Western Urban) |
| Chiefdoms (CHFDM_CODE) | 208 | 5 digits |
| Wards | none in the frame (WARD_CODE empty everywhere) | – |
| Sections (SECT_CODE) | 1,344 | 7 digits |
| Supervisory areas (SA_CODE) | 4,766 | 8 digits |
| EAs (EA_CODE) | 22,508 | 12 digits; POP_EA_CODE is the 10-digit form |
| Localities (LOC_CODE) | 8,723 distinct in the EA sheet; 16,754 rows in LOCALITY | 10 digits |

Per district (chiefdoms / sections / SAs / EAs): Bo 17/111/465/2,212; Bombali 13/91/264/1,252; Bonthe 12/78/212/944; Falaba 13/62/134/581; Kailahun 15/87/282/1,378; Kambia 10/64/224/1,023; Karene 13/99/147/586; Kenema 17/105/457/1,976; Koinadugu 10/44/136/630; Kono 15/82/274/1,404; Moyamba 14/142/348/1,397; Port Loko 14/116/312/1,442; Pujehun 14/93/253/1,231; Tonkolili 19/81/354/1,688; Western Rural 4/25/473/2,429; Western Urban 8/64/431/2,335.

Coordinates: every EA row carries LONGITUDE and LATITUDE (a reference locality point, not a centroid of the EA), all within Sierra Leone; every LOCALITY row has a point too. There are no boundary polygons in the workbook (no geometry, WKT or shape columns), so the location check will start with distance to the EA point and to the section's points; polygons can replace it the day the GIS unit provides them.

Quality: no missing codes at any level, no duplicate EA codes, every EA under exactly one SA, and every code maps to exactly one name (district, chiefdom, section, SA, EA). Two things to note: the questionnaire's A8 says "EA code (10 digits)" while the frame's primary EA code is 12 digits (the 10-digit POP_EA_CODE also exists and is unique); and "Chiefdom / Ward" in A6: the frame has chiefdoms only (Western Area is coded as chiefdoms too), so the pick list will say Chiefdom.

Other frame facts the module can use: TOT_HH (expected households per EA, feeds E3 and H9), LOC_STATUS 1 rural / 2 urban (feeds A9), SUP_ID and ENUM_ID (supervisor and enumerator IDs for A10 and A11), and the FIELD_MONITOR sheet (DQM and Field Monitor per SA), which is already loaded.

## (c) Proposed architecture and data model

**Stack.** Extend what is already running rather than add a second system: FastAPI on PostgreSQL (the production database), React dashboard, Caddy with automatic TLS, Docker Compose on the Stats SL VPS, GitHub deploy. For the field app I propose a mobile-first installable web app (PWA) served from the same site at censusme.statistics.sl: it runs offline from the phone's home screen, keeps forms in the phone's storage (IndexedDB) and syncs them when there is network, captures GPS through the phone's location service, and needs no APK distribution or Play Store. The existing Android app stays for Field Monitors; a second native app would double the maintenance for no field benefit. PostGIS is added to the PostgreSQL container for point-in-polygon when boundaries arrive; until then the check is distance to frame points. Maps on the dashboards use Leaflet with the frame points and tracks (polygons when provided). Everything is open source and stays behind the firewall.

**Roles and access.** Three new roles next to the existing ones: District M&E Officer (scope: one district), Regional M&E Officer (scope: one region), National M&E (everything; the existing Monitoring & Evaluation role becomes this, so it keeps the training evaluations). System Administrator is the existing Administrator. Scoping is enforced in the server on every query, exactly as for District DQM today, and I will add PostgreSQL row-level security policies on the new tables keyed on a per-request session variable, so even a direct database query under the application role sees only the user's geography. Each stage ships with a test that a district officer's API calls for another district return nothing.

**Data model (new tables, all prefixed mefm_).**

- Geography: `mefm_chiefdom` (code, name, district) and `mefm_section` (code, name, chiefdom); the existing `ea` table gains `pop_ea_code`, `chiefdom_code`, `section_code`, `loc_status`, `expected_households`, `supervisor_id`, `enumerator_id`. `mefm_frame_version` records each upload (file, rows, counts per level, differences from the previous version, who applied it, when); an upload is previewed as a diff before it is applied.
- Visits: `mefm_visit` (one per form: officer, EA, chiefdom, section, phase, visit type, dates and times, GPS latitude, longitude, accuracy and timestamp, status draft / submitted / locked, device id, client id for idempotent sync, all section answers as JSON validated against the questionnaire spec, plus typed columns for every annex indicator item so dashboards query columns, not JSON), `mefm_household_check` (one per G household), `mefm_community_interview` (one per I respondent), `mefm_issue` (J-1 rows: question, severity, action, referred to, deadline, status open / resolved, resolved by and when, comments), `mefm_issue_comment`.
- Movement: `mefm_checkin` (officer, chiefdom, section, point, accuracy, time, source form or move) and `mefm_flag` (type, severity, point or visit, explanation).
- Configuration: `mefm_setting` (indicator targets, distance threshold, accuracy threshold, speed threshold, night window, phase dates, alert recipients) editable on the Settings page without code.
- The questionnaire itself lives in code as a spec (sections, items, codes, ⚑, skips), the same technique as the training evaluation, so the app, the server validation and the indicator formulas cannot drift apart.

**Stages**, each shown working with test accounts for every role and the district-isolation check: 1 frame import with versioning and user management with the new roles and scopes; 2 the offline mobile form with every skip, GPS and sync; 3 district dashboard; 4 regional and national dashboards; 5 exports, alerts and audit. Deliverables at the end: source, deployment guide, admin guide, one-page field guide, known limitations.

## (d) Questions before I start

1. **EA code.** Use the 12-digit EA_CODE as the key and show the 10-digit POP_EA_CODE beside it, or make the officer type the 10-digit code as the questionnaire says?
2. **Boundaries.** Can the GIS unit provide EA (or section and chiefdom) polygons as shapefile or GeoJSON? If yes, point-in-polygon from day one; if not, distance to the EA point with a default threshold of 1 km (configurable).
3. **Alerts.** For Critical issues, in-app and email are straightforward; SMS needs a gateway (which provider and credentials?). Who exactly is the "District Statistician" per district: a user role to add, or an email per district in settings?
4. **Officers and assignment.** District officers are assigned to a whole district (1 to 5 per district) with free movement inside it, as the brief says; no SA assignment. Confirm.
5. **Locking.** "Edit their own forms until a supervisor locks them": the supervisor is the Regional M&E Officer (or National). Confirm, and whether locking is per form or per day.
6. **Field app.** Installable web app as proposed, or do you want the Android APK route?
7. **GPS and night defaults** to start with: accuracy worse than 50 m flagged, speed above 120 km/h between check-ins flagged, identical coordinates on two forms flagged, submissions between 20:00 and 05:00 flagged. Change any?
8. **Personal data.** Section G3 records the household head's name for the match. Store the name, or only whether it matched?
9. **National M&E** = the existing Monitoring & Evaluation role (training evaluations plus field monitoring), as proposed?
10. **Phase dates** for Pre-field, Listing, Enumeration and Mop-up, so the phase filter and "EAs on schedule" can be set up.

## Stage notes

### Stage 1 (live 7 October 2026)
District and Regional M&E roles with scoped access, active dates and a forced password change; frame import with chiefdoms, sections and the 10-digit EA code, previewed before it is applied and kept as versions; the scoped overview page under Monitoring & Evaluation › Field monitoring.

### Stage 2 (live 7 October 2026)
- The questionnaire lives on the server as data (`server/app/core/mefm_form.py`): sections A to J, codes, ⚑ items and every skip pattern (phase routing by A12, A16 team not found, A17, B10/B11, C1 and C9/C10, A14, D11 exclusive "None", F0 consent, G repeated per household with at least 2 in enumeration and mop-up, I asked of a community leader and two residents with I4 for the leader only, I5/I6, special populations present/arrangement, J9/J9_date, "other, specify"). The app renders the form from it and validates with the same rules, so the two cannot drift.
- Android app 0.4.0: District M&E Officers sign in to the same app as Field Monitors and get the M&E mode (home with counts, visit forms, check-ins, sync). The EA is typed as its 10-digit code and resolved from the district frame on the device (name, chiefdom, section, SA, supervisor, enumerators, expected households are shown and pre-filled). GPS is captured automatically when the form opens and again on request; a form cannot be submitted without a fix. Drafts are saved on every change; a submitted form is queued and uploaded at the next sync; the server's rejection messages are shown on the form so it can be corrected and resent. Works fully offline after the first sync.
- Server: `/mefm/sync/pull` (form, district frame, settings, state of the officer's forms) and `/mefm/sync/push` (forms and check-ins; idempotent on the tablet id; EA must be in the officer's district). Each form is stored with its answers, the indicators of the annex, the GPS checks (poor accuracy over 50 m, night 20:00 to 05:00, repeated point, implausible speed over 120 km/h, farther than 1 km from the EA point) and its issues log: typed rows plus a Critical row for every ⚑ item coded as a problem. `/mefm/visits` lists forms in the user's scope and `/mefm/visits/{id}` returns one with its issues; the web page shows the recent forms.
- Settings (Administration › Settings API): `mefm_ea_distance_m`, `mefm_gps_accuracy_m`, `mefm_max_speed_kmh`, `mefm_night_start`, `mefm_night_end`, and the phase dates `mefm_phase_*` for later.
