/**
 * Renders a `find_nearby_care` tool result inside a chat bubble.
 *
 * The failure modes this component exists to keep apart
 * ------------------------------------------------------
 * A clinic search has four outcomes that a naive renderer collapses into one
 * grey line, and three of those collapses are lies:
 *
 *   - the provider answered with clinics  -> render them
 *   - the provider answered with nothing -> "no clinics found"
 *   - the provider is not connected      -> we do not know either way
 *   - the tool failed                    -> the search did not happen
 *
 * The last three all have "no list appeared" in common, so the list alone
 * cannot tell the user which happened. Each gets its own `data-state`, its own
 * icon and its own sentence, and the unavailable and failed states are tinted
 * so they never sit next to a zero-result line without looking different.
 * This is the same rule the safety banner follows: a value we did not get must
 * never render as a value we did.
 *
 * Nothing clinical is inferred here. No hours, no "open now", no availability:
 * if the tool did not return a field, it is not shown.
 */
import {
  Info,
  LoaderCircle,
  MapPin,
  MapPinOff,
  Phone,
  SearchX,
  TriangleAlert,
  WifiOff,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import { formatDistance } from "../utils/format";

/**
 * One clinic, as `find_nearby_care` returns it. Matches `HospitalResult` in
 * `api/types.ts` field for field, minus the fields the chat bubble has no room
 * for, so a `HospitalResult[]` can be passed straight in.
 */
export interface ToolResultClinic {
  name: string;
  address?: string | null;
  distance_m?: number | null;
  phone?: string | null;
  rank?: number | null;
}

/**
 * The payload half of a finished tool call.
 *
 * `provider_available` is the field that separates "searched and found none"
 * from "never searched". It is required rather than optional because a result
 * without it cannot honestly claim either: see the `unreadable` state.
 */
export interface ToolResultValue {
  clinics?: readonly ToolResultClinic[] | null;
  /**
   * The server saying outright that it did not search. This is the only field
   * that separates "searched, found none" from "never searched", so a payload
   * carrying it alone is still readable.
   *
   * There is deliberately no `count` here. The wire sends `clinics` and
   * `provider_available` only, and a declared field nothing populates and
   * nothing reads is only a future lie. The badge counts the rendered rows.
   */
  provider_available?: boolean | null;
}

export interface ToolResultProps {
  status: "running" | "done" | "error";
  result?: ToolResultValue | null;
  /** One plain-English line from the backend. Never a raw exception. */
  summary?: string | null;
  /**
   * The backend's agreed reason a call produced nothing.
   *
   * `no_location` is the one that changes what the user should do next, so it
   * gets its own state and its own action rather than being folded into a
   * generic failure. An unrecognised code is a plain failure.
   */
  code?: string | null;
  /**
   * Offered only for a state the user can fix. Left out of the component's
   * knowledge on purpose: it says "there is something to do", not what or where.
   */
  onAction?: (() => void) | null;
  className?: string;
}

type State =
  | "running"
  | "results"
  | "empty"
  | "unavailable"
  | "no_location"
  | "error"
  | "unreadable";

const ICON = {
  running: LoaderCircle,
  results: MapPin,
  empty: SearchX,
  unavailable: WifiOff,
  no_location: MapPinOff,
  error: TriangleAlert,
  unreadable: Info,
} as const;

const FRAME: Record<State, string> = {
  running: "border-border",
  results: "border-border",
  empty: "border-border",
  unavailable: "border-border bg-muted",
  // Not destructive: nothing failed, the user simply has not set a location,
  // and tinting it red would say something untrue about their health.
  no_location: "border-border bg-muted",
  error: "border-destructive/50 bg-destructive/10",
  unreadable: "border-border bg-muted",
};

const ICON_TINT: Record<State, string> = {
  running: "text-muted-foreground",
  results: "text-primary",
  empty: "text-muted-foreground",
  unavailable: "text-muted-foreground",
  no_location: "text-muted-foreground",
  error: "text-destructive",
  unreadable: "text-muted-foreground",
};

const COPY: Record<Exclude<State, "results">, { title: string; body: string }> = {
  running: {
    title: "Looking for nearby clinics",
    body: "Searching now. This usually takes a moment.",
  },
  empty: {
    title: "No clinics found",
    body: "The search finished and returned no clinics in this area. That is an answer, not a failure.",
  },
  unavailable: {
    title: "Clinic search is offline",
    body: "The clinic provider is not connected, so we cannot tell you whether there are clinics nearby. We did not search.",
  },
  no_location: {
    title: "We need your location first",
    body: "Your profile has no location saved, so we cannot search nearby. This does not mean there are no clinics around you.",
  },
  error: {
    title: "Clinic search failed",
    body: "The search did not finish, so there is no answer either way. Try again in a moment.",
  },
  unreadable: {
    title: "Clinic search result could not be read",
    body: "The tool finished but its result did not say whether the search ran. Treat this as unknown, not as zero clinics.",
  },
};

/**
 * Order matters: a failed tool must never fall through to the empty state, and
 * an offline provider must never fall through either. Both are checked before
 * the clinic list, so "no list" can only ever mean one of the two.
 *
 * The state is decided from the clinics we can actually render, not from how
 * many arrived. A payload of two unrenderable rows would otherwise take the
 * results branch and then draw a header reading "0 found", which claims a
 * search came back empty when no clinic was ever readable.
 */
function resolveState(
  status: ToolResultProps["status"],
  result: ToolResultValue | null,
  raw: readonly ToolResultClinic[] | null,
  clinics: readonly NormalizedClinic[],
  code?: string | null,
): State {
  if (status === "running") return "running";
  /* The code is read before the status, because a named reason is more specific
     than the status it arrives with. `no_location` ships as `error`, but "no
     location saved" is not a failure and must not render as one. */
  if (code === "no_location") return "no_location";
  /* `provider_unavailable` arrives as status `error` with no result at all, so
     without this the whole "we did not search" state would be unreachable and an
     outage would read as a failed search. */
  if (code === "provider_unavailable") return "unavailable";
  if (status === "error") return "error";
  if (result === null) return "unreadable";
  if (result.provider_available === false) return "unavailable";
  if (clinics.length > 0) return "results";
  // No list at all, or a list whose every row we could not read. Both are
  // unknown, and unknown is not "none".
  if (raw === null || raw.length > 0) return "unreadable";
  return "empty";
}

/** Every optional field is resolved to a concrete value, so rendering never
 *  has to ask whether a field exists. */
interface NormalizedClinic {
  name: string;
  address: string | null;
  phone: string | null;
  distance_m: number | null;
}

/**
 * The payload arrives from an SSE stream, so it is read defensively: anything
 * that is not a string or a number is treated as absent. That is what keeps a
 * malformed row rendering as a blank field rather than the word "undefined".
 */
function readClinics(raw: readonly ToolResultClinic[] | null | undefined): NormalizedClinic[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((c): c is ToolResultClinic => typeof c?.name === "string" && c.name.trim() !== "")
    .map((c) => ({
      name: c.name,
      address: typeof c.address === "string" && c.address.trim() !== "" ? c.address : null,
      phone: typeof c.phone === "string" && c.phone.trim() !== "" ? c.phone : null,
      distance_m:
        typeof c.distance_m === "number" && Number.isFinite(c.distance_m) ? c.distance_m : null,
    }));
}

function ClinicRow({ clinic }: { clinic: NormalizedClinic }) {
  return (
    <li className="flex flex-col gap-0.5 border-t border-border/70 py-2 first:border-t-0 first:pt-0 last:pb-0">
      <div className="flex items-baseline justify-between gap-2">
        <span className="min-w-0 text-sm leading-snug font-medium break-words">{clinic.name}</span>
        <span className="shrink-0 text-xs whitespace-nowrap text-muted-foreground tabular-nums">
          {formatDistance(clinic.distance_m)}
        </span>
      </div>
      {clinic.address ? (
        <span className="text-xs leading-snug break-words text-muted-foreground">{clinic.address}</span>
      ) : null}
      {clinic.phone ? (
        /* min-h-11 is the 44px target the rest of the app uses, not a size
           this link happens to render at: a 12px line of phone number is not a
           tap target on a phone. */
        <a
          href={`tel:${clinic.phone.replace(/\s+/g, "")}`}
          className="inline-flex min-h-11 w-fit items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          <Phone className="size-3" aria-hidden="true" />
          {clinic.phone}
        </a>
      ) : null}
    </li>
  );
}

export function ToolResult({
  status,
  result,
  summary,
  code,
  onAction,
  className,
}: ToolResultProps) {
  const value = result ?? null;
  const raw = Array.isArray(value?.clinics) ? value.clinics : null;
  const clinics = raw === null ? [] : readClinics(raw);
  const state = resolveState(status, value, raw, clinics, code);
  const Icon = ICON[state];

  // A failed call is the one state announced assertively: the user asked for a
  // clinic and did not get one, so a screen reader should say so rather than
  // wait for them to go looking.
  const live = state === "error" ? "assertive" : "polite";

  return (
    <Card
      size="sm"
      role={state === "error" ? "alert" : "status"}
      aria-live={live}
      data-state={state}
      data-slot="tool-result"
      className={cn("w-full border", FRAME[state], className)}
    >
      <div className="flex items-start gap-2">
        <span className={cn("mt-0.5 shrink-0", ICON_TINT[state])}>
          <Icon
            className={cn("size-4", state === "running" && "animate-spin motion-reduce:animate-none")}
            aria-hidden="true"
          />
        </span>

        {state === "results" ? (
          <div className="flex min-w-0 flex-1 flex-col gap-1.5">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium">Nearby clinics</p>
              <Badge variant="outline" className="shrink-0 text-xs">
                {clinics.length} found
              </Badge>
            </div>
            {/* Long lists scroll inside the bubble rather than pushing the
                composer off a 375px screen. */}
            <ul className="max-h-56 overflow-y-auto overscroll-contain pr-1">
              {clinics.map((clinic, i) => (
                <ClinicRow key={`${i}-${clinic.name}`} clinic={clinic} />
              ))}
            </ul>
          </div>
        ) : (
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">{COPY[state].title}</p>
            <p className="mt-0.5 text-xs leading-snug text-muted-foreground">
              {state === "error" && summary ? summary : COPY[state].body}
            </p>
            {/* The one state with something the user can do about it. Without this
                the card is a dead end on the exact path where someone was told to
                get help and then cannot. */}
            {state === "no_location" && onAction ? (
              <Button type="button" variant="outline" size="sm" className="mt-2 min-h-11" onClick={onAction}>
                Set your location
              </Button>
            ) : null}
          </div>
        )}
      </div>
    </Card>
  );
}