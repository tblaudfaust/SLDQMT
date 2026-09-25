from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.exit_checkout import CheckoutStatus, ClearanceDecision, StaffRole

CHECKLIST = [
    (1, "Assigned workload completed at 100%."),
    (2, "All assigned areas, structures, buildings and households covered."),
    (3, "Listed households reconciled with enumerated households."),
    (4, "Listed population reconciled with enumerated population."),
    (5, "Any household or population reduction/spike explained and validated."),
    (6, "All partial and incomplete cases are completed or given an approved final status."),
    (7, "All required household revisits and supervisor follow-ups completed."),
    (8, "All applicable CAPI sections are completed in line with census methodology."),
    (9, "All supervisor corrections and DQMT issues resolved."),
    (10, "Final enumerator-to-supervisor synchronisation completed."),
    (11, "Paradata sync status and backup census data."),
    (12, "Comment on the integrity, conduct and attitude of the enumerator."),
]

ITEMS = [
    ("FINAL_SYNC", "Final supervisor to central server synchronisation completed."),
    ("NO_UNSYNCED", "No unsynchronised or unresolved cases remain on the device."),
    ("TABLET", "Tablet and its accessories"),
    ("POWER_SIM", "Power bank and charger, SIM card"),
    ("ID_LETTER", "ID card, letter of introduction"),
    ("SD_CARD", "SD card"),
    ("PARADATA", "Paradata sync status and backup census data"),
]

APPROVALS = [
    ("DISTRICT_DQM", "District Data Quality Manager (SA)"),
    ("NATIONAL_DQM", "National Data Quality Manager"),
    ("DISTRICT_FC", "District Field Coordinator"),
    ("NATIONAL_FC", "National Field Coordinator"),
]

DECISIONS = {
    "CLEARED_PAYMENT": "Cleared for final payment / contract closure",
    "CLEARED_REDEPLOYMENT": "Cleared for redeployment",
    "CONDITIONAL": "Conditionally cleared, pending minor follow-up",
    "NOT_CLEARED": "Not cleared, pending resolution of outstanding issues",
}


class ChecklistRow(BaseModel):
    n: int = Field(ge=1, le=12)
    answer: str | None = Field(default=None, pattern="^(YES|NO)$")
    remarks: str = ""


class ItemRow(BaseModel):
    item: str = Field(pattern="^(FINAL_SYNC|NO_UNSYNCED|TABLET|POWER_SIM|ID_LETTER|SD_CARD|PARADATA)$")
    returned: bool | None = None
    condition: str = ""
    clearance: str = ""


class ApprovalRow(BaseModel):
    role: str = Field(pattern="^(DISTRICT_DQM|NATIONAL_DQM|DISTRICT_FC|NATIONAL_FC)$")
    name: str = ""
    comment: str = ""
    signed_on: date | None = None


class CheckoutIn(BaseModel):
    district_id: int | None = None
    team_id: int | None = None
    staff_name: str = Field(min_length=1, max_length=160)
    login_id: str | None = None
    role: StaffRole
    sa_ea_codes: str | None = None
    checklist: list[ChecklistRow] = []
    enumerator_conduct: str | None = None
    items: list[ItemRow] = []
    supervisor_conduct: str | None = None
    approvals: list[ApprovalRow] = []


class ClearanceIn(BaseModel):
    decision: ClearanceDecision
    outstanding_issues: str | None = None
    deadline: date | None = None
    decided_name: str | None = None


class SignIn(BaseModel):
    comment: str | None = None


class CheckoutOut(BaseModel):
    id: int
    district_id: int
    district: str = ""
    region_id: int | None = None
    region: str = ""
    team_id: int | None
    team: str | None = None
    status: CheckoutStatus
    staff_name: str
    login_id: str | None
    role: StaffRole
    sa_ea_codes: str | None
    checklist: list[ChecklistRow] = []
    enumerator_conduct: str | None
    items: list[ItemRow] = []
    supervisor_conduct: str | None
    approvals: list[ApprovalRow] = []
    submitted_by: int | None
    submitted_at: datetime | None
    national_signed_by: int | None
    national_signed_name: str | None
    national_signed_at: datetime | None
    national_comment: str | None
    decision: ClearanceDecision | None
    outstanding_issues: str | None
    deadline: date | None
    decided_name: str | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    delete_reason: str | None = None


class CheckoutListRow(BaseModel):
    id: int
    district_id: int
    district: str
    region: str
    team: str | None
    staff_name: str
    login_id: str | None
    role: StaffRole
    status: CheckoutStatus
    checklist_no: int
    items_missing: int
    decision: ClearanceDecision | None
    deadline: date | None
    submitted_at: datetime | None
    updated_at: datetime
    deleted_at: datetime | None = None


class DeleteIn(BaseModel):
    reason: str


class ExitSummaryRow(BaseModel):
    key: int
    label: str
    total: int
    enumerators: int
    supervisors: int
    draft: int
    submitted: int
    national_signed: int
    cleared: int
    cleared_payment: int
    cleared_redeployment: int
    conditional: int
    not_cleared: int
    checklist_no: list[int]  # 12 counts, one per requirement
    items_missing: list[int]  # 7 counts, one per item
    overdue_conditions: int  # NOT_CLEARED/CONDITIONAL with deadline passed


class ExitSummary(BaseModel):
    level: str
    unit_label: str
    title: str
    rows: list[ExitSummaryRow]
    districts: list[ExitSummaryRow]
    totals: ExitSummaryRow
    checklist_labels: list[str]
    item_labels: list[str]
    expected_staff: int | None  # supervisors + enumerators in the reference roster
