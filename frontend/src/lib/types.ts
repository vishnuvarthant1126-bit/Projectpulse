// Mirrors backend/app/models.py

export type DocType = "original_plan" | "progress_update" | "meeting_notes" | "other";
export type DocStatus = "uploaded" | "extracting" | "needs_review" | "indexing" | "ready" | "failed";
export type RetrievalMode = "hybrid" | "keyword" | "semantic";
export type AnswerMode = "live" | "precomputed_demo" | "retrieval_only" | "no_evidence";

export const DOC_TYPE_LABELS: Record<DocType, string> = {
  original_plan: "Original plan",
  progress_update: "Progress update",
  meeting_notes: "Meeting notes",
  other: "Other",
};

export interface AppConfig {
  llm_enabled: boolean;
  llm_provider: string | null;
  llm_model: string | null;
  embedding_model: string;
  demo_mode: boolean;
  public_demo: boolean;
  max_upload_mb: number;
  allowed_extensions: string[];
  retrieval: {
    candidates_per_retriever: number;
    answer_max_passages: number;
    rrf_k: number;
    chunk_size: number;
    chunk_overlap: number;
  };
}

export interface Project {
  id: string;
  name: string;
  description: string;
  is_sample: boolean;
  created_at: string;
  document_count: number;
}

export interface ProjectDocument {
  id: string;
  project_id: string;
  filename: string;
  title: string | null;
  doc_type: DocType;
  reporting_date: string | null;
  detected_date: string | null;
  detected_date_source: string | null;
  status: DocStatus;
  error: string | null;
  page_count: number | null;
  chunk_count: number;
  size_bytes: number;
  created_at: string;
  updated_at: string;
}

export interface Section {
  id: string;
  ordinal: number;
  heading: string | null;
  page: number | null;
  text: string;
}

export interface ChunkRef {
  id: string;
  section_id: string;
  char_start: number;
  char_end: number;
  page: number | null;
}

export interface DocumentContent {
  document: ProjectDocument;
  sections: Section[];
  chunks: ChunkRef[];
}

export interface Passage {
  source_id: string | null;
  chunk_id: string;
  document_id: string;
  document_name: string;
  doc_type: DocType;
  reporting_date: string | null;
  heading: string | null;
  page: number | null;
  section_id: string;
  char_start: number;
  char_end: number;
  text: string;
  rank: number;
  fused_rank: number | null;
  keyword_rank: number | null;
  semantic_rank: number | null;
  keyword_score: number | null;
  semantic_score: number | null;
  rrf_score: number | null;
  included_for: string | null;
}

export interface Finding {
  statement: string;
  citations: string[];
}

export interface ComparisonRow {
  milestone: string;
  original_commitment: string;
  latest_status: string;
  reason_for_change: string;
  owner: string;
  citations: string[];
}

export interface Conflict {
  topic: string;
  positions: { claim: string; source_date: string; citations: string[] }[];
}

export interface Blocker {
  blocker: string;
  status: "unresolved_in_latest" | "resolved" | "status_unknown";
  detail: string;
  citations: string[];
}

export interface SuggestedAction {
  action: string;
  rationale: string;
  citations: string[];
}

export interface Answer {
  answer_type: "answer" | "insufficient_evidence";
  summary: string;
  findings: Finding[];
  comparison: ComparisonRow[];
  conflicts: Conflict[];
  blockers: Blocker[];
  suggested_actions: SuggestedAction[];
  missing_information: string[];
}

export interface Validation {
  invalid_citations: string[];
  removed_items: string[];
  unverified_dates: string[];
  passed: boolean;
}

export interface AskResponse {
  question: string;
  mode: RetrievalMode;
  answer_mode: AnswerMode;
  notice: string | null;
  model: string | null;
  answer: Answer | null;
  passages: Passage[];
  validation: Validation;
  intents: string[];
  latency_ms: number;
}
