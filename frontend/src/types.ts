export const STAGES = ["TA", "RS", "SC", "AS", "SP"] as const;
export type Stage = (typeof STAGES)[number];

export const STAGE_NAMES: Record<Stage, string> = {
  TA: "Total applications",
  RS: "Resume shortlisted",
  SC: "Screening shortlisted",
  AS: "Assignment shortlisted",
  SP: "Profiles shared",
};

export const STAGE_LABELS: Partial<Record<Stage, string[]>> = {
  RS: ["P1", "P2", "P3", "Reject"],
  SC: ["Select", "Reject", "Hold", "NA"],
  AS: ["P1", "P2", "P3"],
  SP: ["P1", "P2", "P3"],
};

export type Role = "viewer" | "editor" | "admin";
export type Category = "Academy" | "Intensive" | "External";

export interface User {
  email: string;
  name?: string;
  role: Role;
  active?: boolean;
  created_at?: string;
  last_login?: string;
}

export interface BucketStat { candidates: number; tr_cleared: number }

export interface StageStats {
  present: boolean;
  rows: number;
  unique: number;
  academy: number;
  intensive: number;
  external: number;
  academy_in_bucket: number;
  tr_cleared: number;
  academy_tr_cleared: number;
  pct_of_ta: number;
  pct_of_prev: number;
  buckets: Record<string, BucketStat>;
  priority: Record<string, number>;
}

export type StageCounts = Record<Stage, number>;

export interface RunStats {
  run_id: string;
  job_id: string;
  company?: string | null;
  role?: string | null;
  run_at: string;
  saved_at?: string;
  is_latest: boolean;
  sheet_url?: string;
  sheet_title?: string;
  tr_rule?: string;
  stages: Record<Stage, StageStats>;
  save_summary?: SaveResult;
}

export interface Job {
  job_id: string;
  job_key: string;
  company?: string | null;
  role?: string | null;
  sheet_title?: string | null;
  sheet_url?: string | null;
  sheet_urls: string[];
  run_count: number;
  latest_run_at?: string;
  updated_at?: string;
  stage_counts?: StageCounts;
  latest_stats?: RunStats | null;
}

export interface SaveResult {
  status: "saved" | "already_saved";
  run_id: string;
  job_id: string;
  is_latest: boolean;
  rows_received?: number;
  rows_skipped?: number;
  people_in_run?: number;
  students_created?: number;
  students_updated?: number;
  students_merged?: number;
  applications?: number;
  applications_removed?: number;
  identity_conflicts?: number;
  master_sheet?: string;
  warnings?: string[];
}

export interface PriorityRow { label: string; candidates: number; academy: number; intensive: number; external: number }
export interface ProductRow { category: string; candidates: number; tr_cleared: number; tr_cleared_pct: number }

export interface Preview {
  sheet_title: string;
  stages: Record<Stage, StageStats>;
  priority_tables: Partial<Record<Stage, PriorityRow[]>>;
  product_tables: Record<Stage, ProductRow[]>;
  checks: {
    tabs_used: Record<Stage, string[]>;
    product_tabs: string[];
    skipped: string[];
    priority_columns: Record<Stage, string[]>;
    name_columns?: Record<Stage, string[]>;
    name_tabs?: string[];
    row_counts: Record<Stage, { rows: number; unique: number }>;
  };
  warnings: string[];
}

export interface Analysis {
  id: string;
  job_id: string;
  sheet_url: string;
  company?: string | null;
  role?: string | null;
  status: "queued" | "running" | "done" | "failed" | "saved";
  message?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
  preview?: Preview | null;
  save_result?: SaveResult | null;
}

export type StageValues = Record<Stage, string | null>;

export interface Candidate {
  student_id: string;
  name?: string | null;
  mobile?: string | null;
  emails: string[];
  user_ids: string[];
  stages: StageValues;
  furthest_stage?: Stage | null;
  category?: Category | null;
  product?: string | null;
  bucket?: string | null;
  tr_cleared?: boolean | null;
}

export interface StudentRow {
  student_id: string;
  name?: string | null;
  mobile?: string | null;
  emails: string[];
  user_ids: string[];
  product?: string | null;
  category?: Category | null;
  bucket?: string | null;
  tr_cleared?: boolean | null;
  locked_fields: string[];
  jobs: number;
  reached_sp: number;
}

export interface StudentApplication {
  job_id: string;
  company?: string | null;
  role?: string | null;
  stages: StageValues;
  furthest_stage?: Stage | null;
  category?: Category | null;
  bucket?: string | null;
  tr_cleared?: boolean | null;
  run_at?: string;
}

export interface StudentEdit {
  id: string;
  by: string;
  at: string;
  note?: string | null;
  changes: Record<string, { from: unknown; to: unknown }>;
}

export interface Student {
  student_id: string;
  name?: string | null;
  mobile?: string | null;
  emails: string[];
  user_ids: string[];
  product?: string | null;
  category?: Category | null;
  bucket?: string | null;
  tr_cleared?: boolean | null;
  profile_as_of?: string;
  merged_from: string[];
  locked_fields: string[];
  created_at?: string;
  updated_at?: string;
  applications: StudentApplication[];
  edits?: StudentEdit[];
}

export interface CategorySplit { academy: number; intensive: number; external: number }

export interface CompanySummary {
  company: string;
  jobs: number;
  stages: StageCounts;
  category_ta: CategorySplit;
  category_sp: CategorySplit;
  buckets: Record<string, StageCounts>;
  last_run_at?: string;
  rs_pct_of_ta: number;
  sp_pct_of_ta: number;
  sp_pct_of_rs: number;
  job_list?: { job_id: string; role?: string | null; run_at: string; stages: StageCounts; sp_pct_of_ta: number }[];
}

export interface Dashboard {
  jobs: number;
  companies: number;
  students: number;
  open_conflicts: number;
  funnel: StageCounts;
  sp_pct_of_ta: number;
  category_ta: CategorySplit;
  category_sp: CategorySplit;
  top_companies: CompanySummary[];
  bottom_companies: CompanySummary[];
  by_month: ({ month: string; jobs: number } & StageCounts)[];
  recent_saves: { job_id: string; company?: string | null; role?: string | null; run_at: string; TA: number; SP: number }[];
}

export interface Conflict {
  id: string;
  key_type: "email" | "user_id" | "mobile";
  key: string;
  mobiles: string[];
  job_ids: string[];
  seen_count: number;
  first_seen: string;
  last_seen: string;
  resolved: boolean;
  students: { student_id: string; name?: string | null; mobile?: string | null }[];
}

export interface PoolInfo {
  title: string;
  source: "uploaded" | "file" | "missing";
  filename: string;
  rows?: number;
  uploaded_at?: string;
  uploaded_by?: string;
}

export interface Paged<T> { total: number; items: T[] }