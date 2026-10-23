"""Permission registry and the default rights of each role.

A permission is a short `area.action` code. Every role starts from the
defaults below; an administrator can change a role's rights on the Roles page
and grant or revoke single permissions for one user. Geographic scope
(district, region, national) is separate and always applies on top."""

from app.models.user import Role

# code -> (group, description)
PERMISSIONS: dict[str, tuple[str, str]] = {
    "dashboard.view": ("Field Monitor errors", "View the dashboard, error lists and error details in scope"),
    "errors.edit": ("Field Monitor errors", "Edit an error record from the dashboard"),
    "dashboard.whole_district": ("Field Monitor errors", "See every SA of the district, not only the SAs assigned in the workload"),
    "errors.delete": ("Field Monitor errors", "Delete and restore error records"),
    "reports.export": ("Field Monitor errors", "Generate the Excel and PDF reports"),
    "daily_reports.view": ("Daily DQM reporting", "View daily DQM reports in scope"),
    "daily_reports.create": ("Daily DQM reporting", "Create a daily DQM report"),
    "daily_reports.edit": ("Daily DQM reporting", "Edit a daily DQM report that is not yet received"),
    "daily_reports.submit": ("Daily DQM reporting", "Submit a daily DQM report to the NDQM"),
    "daily_reports.receive": ("Daily DQM reporting", "Mark a daily DQM report as received"),
    "daily_reports.delete": ("Daily DQM reporting", "Delete and restore daily DQM reports"),
    "analytics.view": ("Daily DQM reporting", "View DQM summaries and analytics"),
    "exit_checkouts.view": ("Field exit protocol", "View check-outs in scope"),
    "exit_checkouts.create": ("Field exit protocol", "Create a check-out"),
    "exit_checkouts.edit": ("Field exit protocol", "Edit a check-out that is not yet cleared"),
    "exit_checkouts.submit": ("Field exit protocol", "Certify (submit) a check-out"),
    "exit_checkouts.sign": ("Field exit protocol", "Countersign a check-out as National DQM"),
    "exit_checkouts.clear": ("Field exit protocol", "Record the Director's clearance decision"),
    "exit_checkouts.delete": ("Field exit protocol", "Delete and restore check-outs"),
    "users.manage": ("Administration", "Create and edit users and their scope"),
    "roles.manage": ("Administration", "Change what each role and user may do"),
    "devices.manage": ("Administration", "Block and unblock tablets"),
    "reference.manage": ("Administration", "Import and edit reference lists"),
    "workload.assign": ("Administration", "Reassign supervisory areas between Field Monitors and DQM officers of a district"),
    "settings.manage": ("Administration", "Change follow-up and session settings"),
    "audit.view": ("Administration", "View the audit log"),
    "sync.use": ("Tablet", "Synchronise a tablet (Field Monitor app)"),
    "me.view": ("Monitoring & Evaluation", "View training evaluations, respondents and results"),
    "me.manage": ("Monitoring & Evaluation", "Create, edit and close training evaluations; remove responses"),
    "me_daily.view": ("Daily Evaluation", "View daily trainer class evaluations, their reports and summaries"),
    "me_daily.manage": ("Daily Evaluation", "Create and close daily evaluations; edit and remove reports"),
    "me_fac.view": ("Facilitator assessment", "View the daily trainer ratings, the dashboard by district and hall, and exports"),
    "me_fac.manage": ("Facilitator assessment", "Create and close facilitator assessments, load the chapters per day; edit and remove ratings"),
    "me_kpi.collect": ("M&E Field Tool", "Collect KPI reports in the field (online or offline) for the districts in scope"),
    "me_kpi.view": ("M&E Field Tool", "View the KPI reports, the dashboard and the register in scope"),
    "me_kpi.manage": ("M&E Field Tool", "Edit and remove any KPI report in scope"),
    "me_kpi.export": ("M&E Field Tool", "Export KPI reports and the dashboard"),
    "me_kpi.accounts": ("M&E Field Tool", "Create and manage the District and Regional M&E Officer accounts that use the field tool"),
    "incidents.report": ("Census Incident Log", "Report an incident"),
    "incidents.view": ("Census Incident Log", "View the incident register and dashboard in scope"),
    "incidents.manage": ("Census Incident Log", "Acknowledge, assign, resolve, close, reject and reopen incidents"),
    "incidents.escalate": ("Census Incident Log", "Escalate an incident to region or national level"),
    "incidents.export": ("Census Incident Log", "Export the incident register and dashboard"),
    "incidents.settings": ("Census Incident Log", "Upload SA codes and change incident settings"),
    "mefm.collect": ("M&E field monitoring", "Fill and submit field monitoring forms (district officers)"),
    "mefm.view": ("M&E field monitoring", "View field monitoring dashboards and forms in scope"),
    "mefm.review": ("M&E field monitoring", "Review forms, comment and resolve issues"),
    "mefm.export": ("M&E field monitoring", "Export forms, indicators and daily briefs"),
    "mefm.manage": ("M&E field monitoring", "Upload the frame and change field monitoring settings"),
}

_DISTRICT = [
    "dashboard.view", "errors.edit", "errors.delete", "reports.export",
    "daily_reports.view", "daily_reports.create", "daily_reports.edit", "daily_reports.submit", "daily_reports.delete", "analytics.view",
    "exit_checkouts.view", "exit_checkouts.create", "exit_checkouts.edit", "exit_checkouts.submit", "exit_checkouts.delete",
]
_REGIONAL = [
    "dashboard.view", "dashboard.whole_district", "errors.edit", "errors.delete", "reports.export",
    "daily_reports.view", "daily_reports.edit", "daily_reports.delete", "analytics.view",
    "exit_checkouts.view", "exit_checkouts.edit", "exit_checkouts.delete",
]
_NATIONAL = [
    "dashboard.view", "dashboard.whole_district", "errors.edit", "errors.delete", "reports.export",
    "daily_reports.view", "daily_reports.create", "daily_reports.edit", "daily_reports.submit", "daily_reports.receive", "daily_reports.delete", "analytics.view",
    "exit_checkouts.view", "exit_checkouts.create", "exit_checkouts.edit", "exit_checkouts.submit", "exit_checkouts.sign", "exit_checkouts.clear", "exit_checkouts.delete",
    "devices.manage", "audit.view", "workload.assign",
]

DEFAULT_ROLE_PERMISSIONS: dict[Role, list[str]] = {
    Role.FIELD_MONITOR: ["sync.use"],
    Role.DISTRICT_DQM: _DISTRICT,
    Role.REGIONAL: _REGIONAL,
    Role.NATIONAL_DQM: _NATIONAL,
    Role.ME: ["me.view", "me.manage", "me_daily.view", "me_daily.manage", "me_fac.view", "me_fac.manage", "me_kpi.collect", "me_kpi.view", "me_kpi.manage", "me_kpi.export", "me_kpi.accounts", "mefm.view", "mefm.review", "mefm.export", "mefm.manage"],
    Role.ME_DISTRICT: ["mefm.collect", "mefm.view", "sync.use", "me_kpi.collect", "me_kpi.view"],
    Role.ME_REGIONAL: ["mefm.view", "mefm.review", "me_kpi.collect", "me_kpi.view", "me_kpi.export"],
    Role.ME_DAILY: ["me_daily.view", "me_daily.manage", "me_fac.view", "me_fac.manage"],
    Role.DISTRICT_STATISTICIAN: ["incidents.report", "incidents.view", "incidents.manage", "incidents.escalate", "incidents.export"],
    Role.INCIDENT_VIEWER: ["incidents.view"],
    Role.INCIDENT_ADMIN: [code for code in PERMISSIONS if code.startswith("incidents.")],
    Role.ADMIN: [code for code in PERMISSIONS if code != "sync.use"],
}
