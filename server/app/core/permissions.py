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
    "dashboard.view", "errors.edit", "errors.delete", "reports.export",
    "daily_reports.view", "daily_reports.edit", "daily_reports.delete", "analytics.view",
    "exit_checkouts.view", "exit_checkouts.edit", "exit_checkouts.delete",
]
_NATIONAL = [
    "dashboard.view", "errors.edit", "errors.delete", "reports.export",
    "daily_reports.view", "daily_reports.create", "daily_reports.edit", "daily_reports.submit", "daily_reports.receive", "daily_reports.delete", "analytics.view",
    "exit_checkouts.view", "exit_checkouts.create", "exit_checkouts.edit", "exit_checkouts.submit", "exit_checkouts.sign", "exit_checkouts.clear", "exit_checkouts.delete",
    "devices.manage", "audit.view", "workload.assign",
]

DEFAULT_ROLE_PERMISSIONS: dict[Role, list[str]] = {
    Role.FIELD_MONITOR: ["sync.use"],
    Role.DISTRICT_DQM: _DISTRICT,
    Role.REGIONAL: _REGIONAL,
    Role.NATIONAL_DQM: _NATIONAL,
    Role.ME: ["me.view", "me.manage", "mefm.view", "mefm.review", "mefm.export", "mefm.manage"],
    Role.ME_DISTRICT: ["mefm.collect", "mefm.view", "sync.use"],
    Role.ME_REGIONAL: ["mefm.view", "mefm.review"],
    Role.ADMIN: [code for code in PERMISSIONS if code != "sync.use"],
}
