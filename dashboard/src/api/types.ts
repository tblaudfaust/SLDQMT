export type Role = "FIELD_MONITOR" | "DISTRICT_DQM" | "REGIONAL" | "NATIONAL_DQM" | "ADMIN" | "ME";
export type Status = "UNRESOLVED" | "RESOLVED";

export interface User {
  id: number;
  username: string;
  full_name: string;
  phone?: string | null;
  role: Role;
  active: boolean;
  last_login_at?: string | null;
  pin_reset_requested_at?: string | null;
  staff_code?: string | null;
  assigned_sas?: number;
  district_ids?: number[] | null;
  scopes: { region_id: number | null; district_id: number | null }[];
  permissions: string[];
}

export interface UserStats { total: number; active: number; inactive: number; by_role: Record<string, number>; locked: number; never_logged_in: number }
export interface UserActivity { user: User; devices: Device[]; recent: AuditRow[]; counts: Record<string, number> }
export interface UserImportResult { created: number; skipped: number; errors: string[]; created_users: string[] }
export interface PermissionInfo { code: string; group: string; description: string }
export interface RoleMatrix { roles: Record<string, string[]>; defaults: Record<string, string[]>; permissions: PermissionInfo[] }
export interface UserPermissions { user_id: number; role: Role; role_codes: string[]; grant: string[]; revoke: string[]; effective: string[] }

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: User;
  settings: Record<string, string>;
}

export interface Summary {
  total: number;
  resolved: number;
  unresolved: number;
  overdue: number;
  resolution_rate: number;
  median_days_to_resolve: number | null;
  as_of: string;
  last_sync_at: string | null;
}

export interface Bucket {
  key: number | string | null;
  label: string;
  total: number;
  resolved: number;
  unresolved: number;
  overdue: number;
}

export interface TrendPoint {
  period: string;
  received: number;
  resolved: number;
}

export interface AgeingBand {
  band: string;
  count: number;
}

export interface MonitorRow {
  user_id: number;
  full_name: string;
  districts: string;
  total: number;
  unresolved: number;
  overdue: number;
  last_sync_at: string | null;
  last_activity_at: string | null;
  app_version: string | null;
  pending_reported: number;
}

export interface TeamRow {
  team_id: number | null;
  team: string;
  district: string;
  supervisor: string | null;
  total: number;
  resolved: number;
  unresolved: number;
  overdue: number;
}

export interface OverdueRow {
  id: string;
  display_id: string;
  district: string;
  team: string | null;
  category: string;
  supervisor_name: string | null;
  monitor: string;
  next_follow_up_at: string | null;
  hours_overdue: number;
}

export interface ErrorListRow {
  id: string;
  display_id: string;
  district: string;
  team: string | null;
  ea: string | null;
  category: string;
  supervisor_name: string | null;
  enumerator_name: string | null;
  description: string;
  date_received: string;
  support_method: "REMOTE" | "ONSITE";
  status: Status;
  next_follow_up_at: string | null;
  overdue: boolean;
  monitor: string;
  last_action_at: string;
  follow_up_count: number;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface FollowUp {
  id: string;
  at: string;
  method: "REMOTE" | "ONSITE";
  contacted: string | null;
  outcome: string | null;
  comments: string | null;
  lat: number | null;
  lng: number | null;
  accuracy_m: number | null;
}

export interface Activity {
  id: string;
  previous_status: Status | null;
  new_status: Status;
  action_taken: string | null;
  comments: string | null;
  client_at: string;
}

export interface ErrorDetail {
  id: string;
  display_id: string;
  user_id: number;
  district_id: number;
  team_id: number | null;
  supervisor_name: string | null;
  enumerator_name: string | null;
  ea_id: number | null;
  category_id: number;
  source_id: number | null;
  description: string;
  date_received: string;
  support_method: "REMOTE" | "ONSITE";
  action_taken: string | null;
  comments: string | null;
  status: Status;
  resolved_at: string | null;
  last_action_at: string;
  next_follow_up_at: string | null;
  lat: number | null;
  lng: number | null;
  accuracy_m: number | null;
  version: number;
  deleted_at: string | null;
  delete_reason: string | null;
  follow_ups: FollowUp[];
  activity: Activity[];
}

export interface Named {
  id: number;
  code: string;
  name: string;
}

export interface District extends Named {
  region_id: number;
  abbreviation?: string; // district token of its officers' staff codes: FM-Bo-001 -> "Bo"
}

export interface Team extends Named {
  district_id: number;
  chiefdom?: string | null;
  local_council?: string | null;
  ea_count?: number | null;
  monitor_code?: string | null;
  dqm_code?: string | null;
  active: boolean;
}

export interface WorkloadRow {
  team_id: number;
  district_id: number;
  district: string;
  code: string;
  name: string;
  chiefdom: string | null;
  ea_count: number | null;
  monitor_code: string | null;
  monitor_name: string | null;
  dqm_code: string | null;
  dqm_name: string | null;
}

export interface Officer {
  staff_code: string;
  role: "FIELD_MONITOR" | "DISTRICT_DQM";
  district_id: number;
  full_name: string | null;
  user_id: number | null;
  sa_count: number;
}

export interface CreatedAccount { username: string; staff_code: string; role: string; district: string; password: string }
export interface WorkloadAccountsOut { created: CreatedAccount[]; existing: number }
export interface OfficerPairOut { field_monitor: CreatedAccount; dqm: CreatedAccount; sa_count: number }

export interface PickList extends Named {
  active: boolean;
  sort_order: number;
}

export interface Device {
  id: string;
  user_id: number;
  username: string | null;
  full_name: string | null;
  model: string | null;
  android_version: string | null;
  app_version: string | null;
  status: "ACTIVE" | "BLOCKED";
  registered_at: string;
  last_login_at: string | null;
  last_sync_at: string | null;
  pending_reported: number;
}

export interface ImportResult {
  regions: number;
  districts: number;
  teams: number;
  supervisors: number;
  enumerators: number;
  eas: number;
  assigned: number;
  rows: number;
  warnings: string[];
}

export type ReportPeriod = "LISTING" | "ENUMERATION";
export type ReportStatus = "DRAFT" | "SUBMITTED" | "RECEIVED";

export interface ErrorProfileRow { band: "LOW" | "MEDIUM" | "HIGH"; ea_code: string; team: string; likely_cause: string; correction: string; remarks: string }
export interface SystemIssueRow { issue_type: "OUTLIER" | "GPS" | "SYNC"; ea_code: string; finding: string; referred_to: string; action_taken: string; resolution_status: "OPEN" | "IN_PROGRESS" | "RESOLVED" }
export interface LessonRow { quality_area: "GPS" | "REINTERVIEW" | "CAPI"; lesson: string; risk: string; control: string }
export interface SaPerformanceRow { sa: string; assessment: string }

export interface DqmReportIn {
  district_id?: number | null;
  report_date: string;
  period: ReportPeriod;
  day_number: number;
  teams_reviewed: number | null;
  teams_certified: number | null;
  teams_pending: number | null;
  executive_summary: string | null;
  reinterviews_received: number | null;
  reinterviews_received_pending: number | null;
  reinterviews_received_remarks: string | null;
  reinterviews_certified: number | null;
  reinterviews_certified_pending: number | null;
  reinterviews_certified_remarks: string | null;
  error_profile: ErrorProfileRow[];
  system_issues: SystemIssueRow[];
  lessons: LessonRow[];
  sa_performance: SaPerformanceRow[];
  prepared_name: string | null;
}

export interface DqmReport extends DqmReportIn {
  id: number;
  district_id: number;
  district: string;
  region_id: number | null;
  region: string;
  status: ReportStatus;
  prepared_by: number | null;
  created_by: number;
  submitted_at: string | null;
  received_by: number | null;
  received_name: string | null;
  received_at: string | null;
  receiver_comment: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  delete_reason: string | null;
}

export interface DqmReportListRow {
  id: number;
  district_id: number;
  district: string;
  region: string;
  report_date: string;
  period: ReportPeriod;
  day_number: number;
  status: ReportStatus;
  teams_reviewed: number | null;
  teams_certified: number | null;
  teams_pending: number | null;
  reinterviews_received: number | null;
  reinterviews_certified: number | null;
  high_errors: number;
  open_issues: number;
  prepared_name: string | null;
  created_by: number;
  submitted_at: string | null;
  received_at: string | null;
}

export interface DqmOptions {
  error_bands: Record<string, string>;
  issue_types: Record<string, string>;
  quality_areas: Record<string, string>;
  can_create: boolean;
  can_edit: boolean;
  can_submit: boolean;
  can_receive: boolean;
  can_delete: boolean;
}

export interface SummaryRow {
  key: number;
  label: string;
  reports: number;
  submitted: number;
  received: number;
  days_covered: number;
  latest_date: string | null;
  teams_reviewed: number | null;
  teams_certified: number | null;
  teams_pending: number | null;
  reinterviews_received: number;
  reinterviews_received_pending: number;
  reinterviews_certified: number;
  reinterviews_certified_pending: number;
  errors_low: number;
  errors_medium: number;
  errors_high: number;
  issues_outlier: number;
  issues_gps: number;
  issues_sync: number;
  issues_open: number;
  lessons: number;
}

export interface DqmSummary {
  level: "national" | "region";
  region_id: number | null;
  region: string | null;
  date_from: string | null;
  date_to: string | null;
  rows: SummaryRow[];
  totals: SummaryRow;
  expected_units: number;
  reported_today: number;
  missing_today: string[];
  today: string;
}

export type StaffRole = "ENUMERATOR" | "SUPERVISOR";
export type CheckoutStatus = "DRAFT" | "SUBMITTED" | "NATIONAL_SIGNED" | "CLEARED";
export type ClearanceDecision = "CLEARED_PAYMENT" | "CLEARED_REDEPLOYMENT" | "CONDITIONAL" | "NOT_CLEARED";

export interface ChecklistRow { n: number; answer: "YES" | "NO" | null; remarks: string }
export interface ItemRow { item: string; returned: boolean | null; condition: string; clearance: string }
export interface ApprovalRow { role: string; name: string; comment: string; signed_on: string | null }

export interface CheckoutIn {
  district_id?: number | null;
  team_id: number | null;
  staff_name: string;
  login_id: string | null;
  role: StaffRole;
  sa_ea_codes: string | null;
  checklist: ChecklistRow[];
  enumerator_conduct: string | null;
  items: ItemRow[];
  supervisor_conduct: string | null;
  approvals: ApprovalRow[];
}

export interface Checkout extends CheckoutIn {
  id: number;
  district_id: number;
  district: string;
  region_id: number | null;
  region: string;
  team: string | null;
  status: CheckoutStatus;
  submitted_by: number | null;
  submitted_at: string | null;
  national_signed_by: number | null;
  national_signed_name: string | null;
  national_signed_at: string | null;
  national_comment: string | null;
  decision: ClearanceDecision | null;
  outstanding_issues: string | null;
  deadline: string | null;
  decided_name: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  delete_reason: string | null;
}

export interface CheckoutListRow {
  id: number;
  district_id: number;
  district: string;
  region: string;
  team: string | null;
  staff_name: string;
  login_id: string | null;
  role: StaffRole;
  status: CheckoutStatus;
  checklist_no: number;
  items_missing: number;
  decision: ClearanceDecision | null;
  deadline: string | null;
  submitted_at: string | null;
  updated_at: string;
}

export interface ExitOptions {
  checklist: { n: number; text: string }[];
  items: { code: string; text: string }[];
  approvals: { role: string; text: string }[];
  decisions: Record<string, string>;
  can_create: boolean;
  can_edit: boolean;
  can_submit: boolean;
  can_sign: boolean;
  can_clear: boolean;
  can_delete: boolean;
  can_national: boolean;
}

export interface ExitSummaryRow {
  key: number;
  label: string;
  total: number;
  enumerators: number;
  supervisors: number;
  draft: number;
  submitted: number;
  national_signed: number;
  cleared: number;
  cleared_payment: number;
  cleared_redeployment: number;
  conditional: number;
  not_cleared: number;
  checklist_no: number[];
  items_missing: number[];
  overdue_conditions: number;
}

export interface ExitSummary {
  level: string;
  unit_label: string;
  title: string;
  rows: ExitSummaryRow[];
  districts: ExitSummaryRow[];
  totals: ExitSummaryRow;
  checklist_labels: string[];
  item_labels: string[];
  expected_staff: number | null;
}

export interface AuditRow {
  id: number;
  at: string;
  user_id: number | null;
  user_name: string | null;
  username: string | null;
  action: string;
  entity: string | null;
  entity_id: string | null;
  detail: string | null;
  ip: string | null;
}

// ---- Monitoring & Evaluation ------------------------------------------------
export interface MeEvaluation {
  id: number;
  title: string;
  training_mode: "ONLINE" | "IN_PERSON";
  period_start: string | null;
  period_end: string | null;
  description: string | null;
  token: string;
  status: "OPEN" | "CLOSED";
  created_at: string;
  share_url: string | null;
  registered: number;
  submitted: number;
  trainees: number;
  trainers: number;
}
export interface MeRespondent {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  registered_at: string;
  role: "TRAINER" | "TRAINEE" | "NEITHER" | null;
  submitted_at: string | null;
  response_id: number | null;
  district: string | null;
}
export interface MeItem { code: string; text: string; n: number; na: number; mean: number | null; pct_favourable: number | null; flag: boolean }
export interface MeDomain { code: string; label: string; n_respondents: number; mean: number | null; pct_favourable: number | null; flag: boolean; threshold: number; items: MeItem[] }
export interface MeBreakdown { label: string; count: number; pct: number }
export interface MeOpenAnswer { code: string; text: string; role: string; district: string | null }
export interface MeDistrictRow { district: string; trainees: number; trainers: number; completion_pct: number | null; domains: Record<string, number | null>; gain: number | null; ready_pct: number | null; not_ready: number; quality_mean: number | null }
export interface MeResults {
  evaluation: MeEvaluation;
  district: string | null;
  by_district: MeDistrictRow[];
  registered: number;
  submitted: number;
  trainees: number;
  trainers: number;
  neither: number;
  response_rate: number | null;
  profile: Record<string, MeBreakdown[]>;
  completion: Record<string, MeBreakdown[]>;
  domains: MeDomain[];
  knowledge: { before: number | null; after: number | null; gain: number | null; pct_positive: number | null };
  overall: Record<string, MeBreakdown[]>;
  reinforcement: { trainees: MeBreakdown[]; trainers: MeBreakdown[] };
  strengths: MeItem[];
  weaknesses: MeItem[];
  open_feedback: MeOpenAnswer[];
}
