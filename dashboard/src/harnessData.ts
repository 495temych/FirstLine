import type { Path } from "./api";

/** What the model reads, in order, and where it comes from. */
export interface Read {
  name: string;
  role: "system" | "user";
  what: string;
  code: string;
}

export interface FormField {
  name: string;
  means: string;
  required: boolean;
  choices: string[] | null;
}

export interface Check {
  when: string;
  then: string;
  code: string;
}

/** What `GET /api/harness` returns: the harness around the model, from the code. */
export interface Harness {
  answer: string;
  instructions: {
    file: string;
    words: number;
    sections: string[];
    text: string;
  };
  search: {
    embedding_model: string;
    sure: number;
    threshold: number;
    margin: number;
    support: number;
    top_k: number;
  };
  reads: Read[];
  fixes: number;
  model: {
    name: string;
    label: string;
    lab: string;
    provider: string | null;
    region: string;
    effort: string | null;
    max_tokens: number;
    attempts: number;
    forced: boolean;
  };
  tool: { name: string; description: string; fields: FormField[] };
  checks: Check[];
  loop: { built: boolean; calls: number; text: string };
  gates: string[];
  examples: { id: string; title: string; family: string }[];
}

/** One development ticket: what the model read, and what it answered. */
export interface HarnessTicket {
  id: string;
  run: string;
  found: {
    doc: string;
    kind: string;
    section: string | null;
    score: number;
  }[];
  message: string;
  answer: {
    path: Path;
    cause: string | null;
    tool: string | null;
    queue: string | null;
    invalid: boolean;
    right: boolean;
    expected: Path[];
  };
}
