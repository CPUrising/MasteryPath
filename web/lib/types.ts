export type KnowledgeType = "memory" | "concept" | "procedure" | "design";
export type Mode = "outline" | "study" | "review";
export type ObjectiveStatus = "new" | "learning" | "mastered";

export interface MapEntry {
  name: string;
  module_id: string;
  module_name: string;
  type: KnowledgeType;
  status: ObjectiveStatus;
  source: "system" | "learner" | "";
  mastery: number;
  threshold: number;
  grounding: "grounded" | "ungrounded";
}

export interface NextStep {
  action: string;
  module_id: string;
  module_name: string;
  knowledge_point_id: string;
  knowledge_point_name: string;
  knowledge_point_type: KnowledgeType;
  status: string;
  mastery: number;
  threshold: number;
  reason: string;
  pending_prompt?: string;
}

export interface PendingQuestion {
  question_id: string;
  knowledge_point_id: string;
  prompt: string;
  question_type: "choice" | "short" | "open";
  options: { label: string; body: string }[];
  objective_name?: string;
  attempt?: number;
}

export interface ReviewItem {
  id: string;
  knowledge_point_id: string;
  knowledge_point_name: string;
  knowledge_type: KnowledgeType;
  due_at: number;
  due: boolean;
  forgetting_risk: number;
  reason: string;
  interval_index: number;
  scheduled_after_failure: boolean;
  desired_retention: number;
  provenance: "system" | "learner";
}

export interface Source {
  id: string;
  kind: string;
  source_id: string;
  label: string;
  excerpt: string;
  available: boolean;
}

export interface Gap {
  id: string;
  kind: string;
  ref: string;
  reason: string;
  resolution: string | null;
}

export interface PathState {
  status: string;
  path_id: string;
  name: string;
  goal: string;
  version: number;
  map: Record<string, MapEntry>;
  counts: { mastered: number; learning: number; new: number; total: number };
  next: NextStep;
  sources: Source[];
  knowledge_bases: { id: string; name: string; ready: boolean }[];
  gaps: Gap[];
  reviews: ReviewItem[];
  review_settings: { desired_retention: number; scope: string };
  session_count: number;
  learner_profile: Record<string, string> | null;
  pending_question?: PendingQuestion | null;
}

export interface TopicSession {
  session_id: string;
  path_id: string;
  title: string;
  mode: Mode;
  status: string;
  message_count: number;
  last_message: string;
  has_pending_question: boolean;
  created_at: number;
  updated_at: number;
}

export interface SessionMessage {
  id: number;
  turn_id: string;
  role: "user" | "assistant";
  content: string;
  data: { card?: PendingQuestion };
  created_at: number;
}

export interface TurnEvent {
  type: string;
  data: Record<string, unknown>;
}

export interface LLMSelection {
  provider_id: string;
  model_id: string;
}

export interface Provider {
  id: string;
  name: string;
  base_url: string;
  api_key: string;
  protocol?: ProviderProtocol;
  detection?: ProviderDetection;
}

export type ProviderProtocol = "openai" | "anthropic" | "ollama" | "custom";

export type ModelService = "llm" | "task" | "embedding";

export interface DetectedModel {
  id: string;
  services: ModelService[];
}

export interface ProviderDetection {
  status: string;
  models: DetectedModel[];
  http_status?: number | null;
  warning?: string;
  checked_at?: string;
}

export interface CatalogProvider {
  id: string;
  name: string;
  base_url: string;
  protocol: ProviderProtocol;
  services: ModelService[];
  requires_key: boolean;
  /** Two-letter monogram shown when there is no brand icon. */
  monogram: string;
}

export interface ModelEntry {
  id: string;
  provider_id: string;
  model: string;
  name: string;
  dimension?: number;
  services?: ModelService[];
}

export interface ModelSection {
  models: ModelEntry[];
  active_id: string;
}

export interface EmbeddingModelRef {
  model_id?: string;
  provider_id?: string;
  name?: string;
  model?: string;
  dimension?: number;
}

export interface LinkedFolder {
  id: string;
  path: string;
  file_count: number;
  added_at: number;
  added_at_iso?: string;
  last_sync?: number | null;
}

export interface IndexConfig {
  chunk_size: number;
  chunk_overlap: number;
  tokenizer?: string;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  mode: "import" | "link";
  rag_provider: string;
  search_mode: string;
  embedding_model: EmbeddingModelRef;
  status: string;
  error: string;
  created_at: number;
  updated_at: number;
  last_indexed_at: number | null;
  created_at_iso: string;
  updated_at_iso: string;
  last_indexed_at_iso: string;
  disk_path: string;
  doc_count: number;
  chunk_count: number;
  skipped_count: number;
  linked_folders: LinkedFolder[];
  index_config: Partial<IndexConfig>;
  indexed_config: Partial<IndexConfig>;
  effective_config: IndexConfig;
  index_config_source: "kb" | "global";
  needs_reindex: boolean;
}

export interface KnowledgeFile {
  path: string;
  size: number;
  modified_at: string;
  linked?: boolean;
  folder_id?: string;
}

export interface KnowledgeProgress {
  run_id: string;
  status: string;
  phase: string;
  indexed_files: number;
  total_files: number;
  chunks: number;
  error: string;
  started_at: number;
  updated_at: number;
  percent: number | null;
}

export interface ChatSessionSummary {
  session_id: string;
  title: string;
  model_id: string;
  kb_ids: string[];
  message_count: number;
  last_message: string;
  created_at: number;
  updated_at: number;
}

export interface ChatAttachment {
  name: string;
}

export interface ChatMessage {
  id: number;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  attachments: ChatAttachment[];
  created_at: number;
}

export interface ChatSessionDetail {
  session: ChatSessionSummary;
  messages: ChatMessage[];
}

export interface ChatTurnEvent {
  type: string;
  data: Record<string, unknown>;
}

export interface QuestionEntry {
  entry_id: string;
  path_id: string;
  path_name?: string;
  knowledge_point_name: string;
  question: string;
  question_type: string;
  correct_answer: string;
  user_answer: string;
  explanation: string;
  is_correct: boolean | null;
  result: string;
  tags: string[];
  created_at: number;
}
