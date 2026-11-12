export type ResponseType = "answer" | "suggest" | "clarify";

export interface Suggestion {
  id: string;
  question: string;
  score: number;
}

export interface Action {
  id: "other" | "rephrase" | "topic" | "retry" | string;
  label: string;
  topic?: string;
}

export interface SourceRef {
  file: string;
  page?: number | null;
  sheet?: string | null;
  row_start?: number | null;
  row_end?: number | null;
  heading?: string | null;
}

interface ResponseBase {
  type: ResponseType;
  session_id: string;
  response: string;
  score?: number | null;
  answer_bullets?: string[] | null;
  source?: string | null;
  sources?: SourceRef[];
  message?: string | null;
  suggestions?: Suggestion[];
  topics?: string[];
  examples?: string[];
  actions?: Action[];
}

export interface AnswerResponse extends ResponseBase {
  type: "answer";
}

export interface SuggestResponse extends ResponseBase {
  type: "suggest";
  message: string;
  suggestions: Suggestion[];
  actions: Action[];
}

export interface ClarifyResponse extends ResponseBase {
  type: "clarify";
  message: string;
  topics: string[];
  examples: string[];
  actions: Action[];
}

export type ChatResponse = AnswerResponse | SuggestResponse | ClarifyResponse;
