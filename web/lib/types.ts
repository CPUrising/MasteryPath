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

export interface Provider {
  id: string;
  name: string;
  base_url: string;
  api_key: string;
}

export interface ModelEntry {
  id: string;
  provider_id: string;
  model: string;
  name: string;
  dimension?: number;
}

export interface ModelSection {
  models: ModelEntry[];
  active_id: string;
}
