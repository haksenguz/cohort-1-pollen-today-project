/**
 * Live activity for the chat turn.
 *
 * Why this exists
 * ---------------
 * A turn is two sequential model calls plus the rule engine. That is several
 * seconds with nothing on screen, and a chat box that goes quiet for that long
 * reads as "broken" rather than "working" — so the user resends, or concludes
 * the agent is dead.
 *
 * The backend emits a `status` SSE event at each stage (see `run_turn`'s
 * `progress` callback in `symptom_agent.py`). This module is the tiny store
 * between that stream and React.
 *
 * What the stage names mean — and do not mean
 * ------------------------------------------
 * These are internal steps of a fixed pipeline. **The agent has no tools and
 * performs no function-calling.** Nothing here may ever be phrased as
 * "using tool X", because there is no tool call to report. See `AGENTS.md`
 * and ADR 0001: the model converses and extracts, the deterministic rule
 * engine decides.
 */

export type ChatStage = "starting" | "extracting" | "asking" | "assessing" | "saving";

const STAGE_LABEL: Record<ChatStage, string> = {
  starting: "Getting your message…",
  extracting: "Reading what you're describing…",
  asking: "Working out what to ask next…",
  // Deliberately says "safety rules", not "thinking". The verdict comes from
  // the deterministic engine in `triage.py`, never from the model, and this is
  // the moment the user most deserves to see that distinction.
  assessing: "Applying the safety rules…",
  saving: "Saving this turn…",
};

const FALLBACK_LABEL = "Working on it…";

export function stageLabel(stage: string): string {
  return STAGE_LABEL[stage as ChatStage] ?? FALLBACK_LABEL;
}

export interface ChatActivity {
  stage: string;
  label: string;
  /** Bumped on every stage change so React sees a new object identity. */
  seq: number;
}

let current: ChatActivity | null = null;
let seq = 0;
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

export function setActivity(stage: string): void {
  current = { stage, label: stageLabel(stage), seq: (seq += 1) };
  emit();
}

export function clearActivity(): void {
  if (current === null) return;
  current = null;
  emit();
}

export function getActivity(): ChatActivity | null {
  return current;
}

export function subscribeActivity(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}