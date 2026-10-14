export type KnowledgeType = "memory" | "concept" | "procedure" | "design";
export type Mode = "outline" | "study" | "review";
export type ObjectiveStatus = "new" | "learning" | "mastered";

export interface MapEntry {
  name: string;
  module_id: string;
  module_name: string;
  type: KnowledgeType;
  status: ObjectiveStatus;
  source: string;
  mastery: number;
  threshold: number;
  grounding: string;
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

export interface PathState {
  status: string;
  path_id: string;
  name: string;
  goal: string;
  version: number;
  map: Record<string, MapEntry>;
  next: NextStep;
  gaps: { id: string; kind: string; ref: string; resolution: string | null }[];
  pending_question?: PendingQuestion | null;
  due_reviews: unknown[];
}

export interface TurnEvent {
  type:
    | "text_delta"
    | "tool_call"
    | "tool_result"
    | "question_card"
    | "mode_changed"
    | "usage"
    | "turn_end"
    | "error";
  data: Record<string, unknown>;
}
