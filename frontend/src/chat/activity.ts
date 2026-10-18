/**
 * Live activity for the chat turn.
 *
 * Why this exists
 * ---------------
 * A turn is two model calls, the rule engine and any tool the model chose to
 * call. That is several seconds with nothing on screen, and a chat box that
 * goes quiet for that long reads as "broken" rather than "working" — so the
 * user resends, or concludes the agent is dead.
 *
 * Two things report themselves into this store: the backend's `status` SSE
 * events (pipeline stages) and its `tool` SSE events (what the model actually
 * called, see docs/GOAL.md). Both arrive over the same stream and both are
 * transient, so they belong in one place the chat screen can render as one
 * activity strip.
 *
 * What the user is allowed to see
 * -------------------------------
 * Stage names are internal steps. Tool names are internal identifiers. The
 * tool identifier in particular must never reach the screen: the user reads
 * "Looking for clinics near you…", never `find_nearby_care` and never the raw
 * arguments. This module is where that decision is made, so the renderer has
 * no way to get it wrong.
 *
 * Tools remain read-only lookups. Nothing here may imply that a tool can
 * assess urgency: ADR 0001 gives every safety decision to the deterministic
 * engine in `triage.py`, not to the model and not to its tools.
 */
import type { NearbyCareResult, ToolCallEvent } from "../api/types";

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

// ---- Tool calls -------------------------------------------------------

export type ToolStatus = "running" | "done" | "error";

/**
 * One tool call, already translated into something a user can read.
 *
 * The backend's own `name` is deliberately absent: keeping it out of the
 * rendered row is what makes "never show the raw tool name" structural rather
 * than a rule the component has to remember.
 */
export interface ToolActivity {
  /** Pairs the running event with the done or error event for the same call. */
  id: string;
  status: ToolStatus;
  /** Running rows only. */
  label: string;
  /** Error rows only. */
  failure: string;
  /** The backend's one plain-English line, or null when it sent none. */
  summary: string | null;
  /**
   * What the tool returned, for rendering the actual answer.
   *
   * The tool's `name` and `args` are deliberately still absent — only the
   * output travels, so the screen still has no way to render an identifier.
   * Null on running and error rows, which carry no payload by contract.
   */
  result: NearbyCareResult | null;
  /**
   * Whether this call is the clinic lookup the result card knows how to draw.
   *
   * A boolean, not the name: `LatestToolResult` needs to know that a settled
   * row deserves a clinic card, and it must be able to ask without holding the
   * identifier that decides the answer.
   */
  isClinicLookup: boolean;
  /**
   * Why the call produced no result, in the backend's agreed vocabulary.
   *
   * `no_location` is the one a user can act on, so it is kept rather than
   * flattened into the generic failure the strip already renders. An
   * unrecognised code is kept verbatim and treated as a plain failure, never
   * as success.
   */
  code: string | null;
  /** Bumped per event so the pulse restarts instead of continuing. */
  seq: number;
}

const CLINIC_LOOKUP_COPY = {
  running: "Looking for clinics near you…",
  failure: "Could not look up clinics near you",
} as const;

/**
 * docs/GOAL.md names the clinic lookup `find_nearby_care`; the registry that
 * ships today calls the same lookup `find_nearby_hospitals`. Both mean one
 * thing to the user, so both get one sentence rather than one of them leaking.
 */
const TOOL_COPY: Record<string, typeof CLINIC_LOOKUP_COPY> = {
  find_nearby_care: CLINIC_LOOKUP_COPY,
  find_nearby_hospitals: CLINIC_LOOKUP_COPY,
};

/**
 * A tool we have no sentence for is still a call the user waited on, so it
 * says something true. It does not guess what was being looked up, because a
 * wrong guess here is a claim about the user's health data that nothing backs.
 */
const UNKNOWN_TOOL_COPY = {
  running: "Checking something…",
  failure: "A check did not finish",
} as const;

const DONE_WITHOUT_SUMMARY = "Finished.";

function toolStatus(raw: string): ToolStatus | null {
  if (raw === "running" || raw === "done" || raw === "error") return raw;
  return null;
}

function readSummary(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return trimmed === "" ? null : trimmed;
}

/**
 * The backend's agreed reason for a call that produced nothing. Kept verbatim
 * rather than mapped here, so a code this client has never seen still renders as
 * a plain failure instead of silently becoming something more comfortable.
 */
function readCode(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return trimmed === "" ? null : trimmed;
}

/**
 * The client has already normalised this payload, so a null here means the
 * backend sent no result at all. The object is passed through rather than
 * rebuilt, because rebuilding it field by field is how `provider_available`
 * disappeared once already: without it there is no difference between "we
 * searched and found none" and "we never searched".
 */
function readResult(raw: unknown): NearbyCareResult | null {
  if (typeof raw !== "object" || raw === null) return null;
  const result = raw as NearbyCareResult;
  return Array.isArray(result.clinics) ? result : null;
}

// ---- Store ------------------------------------------------------------

export interface ChatActivity {
  /** Null once the turn has ended and only finished tool rows remain. */
  stage: string | null;
  label: string;
  /** Bumped on every change so React sees a new object identity. */
  seq: number;
  tools: ToolActivity[];
}

let current: ChatActivity | null = null;
let seq = 0;
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

export function setActivity(stage: string): void {
  // The adapter calls `setActivity("starting")` once at the top of every turn,
  // so that is where the previous turn's tool rows go. The `anyRunning` guard
  // keeps a repeated "starting" from mid-turn from erasing a call in flight.
  const anyRunning = current?.tools.some((tool) => tool.status === "running") ?? false;
  current = {
    stage,
    label: stageLabel(stage),
    seq: (seq += 1),
    tools: stage === "starting" && !anyRunning ? [] : (current?.tools ?? []),
  };
  emit();
}

/**
 * Report one tool call, from the `tool` SSE event the client hands over.
 *
 * Events for the same call replace each other in place, so a running row
 * becomes its done or error row rather than stacking a second line under it.
 *
 * `name` and `args` are read here and then dropped. That is the whole point of
 * this function being the seam: after it returns, nothing downstream holds the
 * tool identifier or its arguments, so the screen has no way to render either.
 */
export function setToolActivity(event: ToolCallEvent): void {
  const status = toolStatus(event.status);
  if (status === null) return;

  const copy = TOOL_COPY[event.name] ?? UNKNOWN_TOOL_COPY;
  // The client leaves `id` empty when the backend sent none, so fall back to
  // the name: that still pairs a running event with the event that finishes it.
  const id = event.id !== "" ? event.id : event.name;
  const entry: ToolActivity = {
    id,
    status,
    label: copy.running,
    failure: copy.failure,
    // A call that finished with no summary did finish. Saying so is true;
    // leaving the row blank would read as a call that never came back.
    summary: readSummary(event.summary) ?? (status === "done" ? DONE_WITHOUT_SUMMARY : null),
    result: status === "done" ? readResult(event.result) : null,
    isClinicLookup: event.name in TOOL_COPY,
    code: readCode(event.code),
    seq: (seq += 1),
  };

  const tools = [...(current?.tools ?? [])];
  const at = tools.findIndex((tool) => tool.id === id);
  if (at === -1) tools.push(entry);
  else tools[at] = entry;

  current = {
    stage: current?.stage ?? null,
    label: current?.label ?? "",
    seq: entry.seq,
    tools,
  };
  emit();
}

export function clearActivity(): void {
  if (current === null) return;
  const tools = current.tools.filter((tool) => tool.status !== "running");
  // What a tool found has to outlive the turn that found it: the answer is
  // the whole point of the call. A call still running when the turn ended did
  // not finish, so its row goes rather than sitting there spinning forever.
  // With nothing left to report the strip leaves the DOM entirely rather than
  // lingering as an empty live region.
  current = tools.length === 0 ? null : { stage: null, label: "", seq: (seq += 1), tools };
  emit();
}

/** Drops everything, finished tool rows included. For tests. */
export function resetActivity(): void {
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