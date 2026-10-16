/**
 * Displays the safety verdict the backend rule engine produced.
 *
 * triage.py decides the level (ADR 0001). Nothing here ranks, softens or
 * second-guesses it: the component reads the level it is handed and picks a
 * presentation. A level it cannot read gets its own state rather than a
 * reassuring default.
 */
import { useAuiState } from "@assistant-ui/react";
import { CircleCheck, Info, MapPin, Phone, TriangleAlert } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import type { TriageLevel } from "../api/types";
import { TRIAGE_PART_NAME } from "./allergyChatAdapter";

/** Korea's emergency medical number. */
const EMERGENCY_NUMBER = "119";

type VerdictKind = "low" | "moderate" | "emergency" | "unknown";

/**
 * Deliberately not formatRisk()/riskClass(): those fall back to the low
 * bucket for a level they do not recognise, which would turn a verdict we
 * failed to read into an all-clear.
 */
const KIND_BY_LEVEL: Record<TriageLevel, VerdictKind> = {
  LOW: "low",
  MODERATE: "moderate",
  EMERGENCY: "emergency",
};

const COPY: Record<VerdictKind, { label: string; title: string; body: string }> = {
  emergency: {
    label: "Emergency",
    title: "Get medical help now",
    body: "What you described matches an emergency rule. Do not wait for the chat to finish.",
  },
  moderate: {
    label: "Moderate",
    title: "Safety check: moderate",
    body: "Look after this today. Contact a clinic or doctor, and get emergency help straight away if it gets worse.",
  },
  low: {
    label: "Low",
    title: "Safety check: low",
    body: "Nothing you described needs emergency care right now. Keep watching how you feel and tell me if that changes.",
  },
  unknown: {
    label: "Unchecked",
    title: "Safety check could not be read",
    body: "This message has no safety level we understand, so treat it as unchecked rather than fine. Contact a clinic if you are worried.",
  },
};

const ICON = {
  emergency: TriangleAlert,
  moderate: TriangleAlert,
  low: CircleCheck,
  unknown: Info,
} as const;

/** Tint and border from the risk tokens; body text stays on ink tokens so it
 *  keeps its contrast against the tint. */
const ALERT_CLASS: Record<VerdictKind, string> = {
  emergency: "border-destructive bg-destructive text-primary-foreground",
  moderate: "border-risk-moderate/50 bg-risk-moderate/10",
  low: "border-risk-low/50 bg-risk-low/10",
  unknown: "border-border bg-muted",
};

const ICON_CLASS: Record<VerdictKind, string> = {
  emergency: "text-primary-foreground",
  moderate: "text-risk-moderate",
  low: "text-risk-low",
  unknown: "text-muted-foreground",
};

const BADGE_CLASS: Record<VerdictKind, string> = {
  emergency: "border-transparent bg-primary-foreground text-destructive",
  moderate: "border-risk-moderate/60 bg-transparent",
  low: "border-risk-low/60 bg-transparent",
  unknown: "border-border bg-transparent",
};

const BODY_CLASS: Record<VerdictKind, string> = {
  emergency: "text-primary-foreground/90",
  moderate: "text-foreground",
  low: "text-muted-foreground",
  unknown: "text-muted-foreground",
};

const REASONS_CLASS: Record<VerdictKind, string> = {
  emergency: "text-primary-foreground/90",
  moderate: "text-muted-foreground",
  low: "text-muted-foreground",
  unknown: "text-muted-foreground",
};

function readVerdict(data: unknown): { level: string | null; reasons: string[] } {
  if (typeof data !== "object" || data === null) return { level: null, reasons: [] };
  const raw = data as { level?: unknown; reasons?: unknown };
  const reasons = Array.isArray(raw.reasons)
    ? raw.reasons.filter((r): r is string => typeof r === "string" && r.length > 0)
    : [];
  return {
    level: typeof raw.level === "string" ? raw.level : null,
    reasons,
  };
}

function verdictKind(level: string | null): VerdictKind {
  if (level === null) return "unknown";
  return level in KIND_BY_LEVEL ? KIND_BY_LEVEL[level as TriageLevel] : "unknown";
}

function ReasonList({ reasons, className }: { reasons: string[]; className: string }) {
  if (reasons.length === 0) return null;
  return (
    <div className={className}>
      <p className="font-medium">Why this level</p>
      <ul className="mt-0.5 list-disc space-y-0.5 pl-4">
        {reasons.map((reason, i) => (
          <li key={`${i}-${reason}`}>{reason}</li>
        ))}
      </ul>
    </div>
  );
}

export function TriageVerdict({ data }: { data: unknown }) {
  const { level, reasons } = readVerdict(data);
  const kind = verdictKind(level);
  const Icon = ICON[kind];
  const copy = COPY[kind];
  const navigate = useNavigate();

  return (
    <Alert
      role="status"
      aria-live="polite"
      data-triage={kind}
      className={cn("grid-cols-[auto_1fr] items-start", ALERT_CLASS[kind])}
    >
      {/* Alert forces `text-current` onto the svg, so the colour has to live
          on a wrapper the svg inherits from. */}
      <span className={ICON_CLASS[kind]}>
        <Icon aria-hidden="true" />
      </span>
      <div className="flex min-w-0 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <AlertTitle className="min-w-0">{copy.title}</AlertTitle>
          <Badge variant="outline" className={BADGE_CLASS[kind]}>
            {copy.label}
          </Badge>
        </div>
        <AlertDescription className={BODY_CLASS[kind]}>{copy.body}</AlertDescription>
        {kind === "emergency" ? (
          <Button
            asChild
            size="lg"
            className="w-full bg-primary-foreground text-destructive hover:bg-primary-foreground/90"
          >
            <a
              href={`tel:${EMERGENCY_NUMBER}`}
              aria-label={`Call the emergency number ${EMERGENCY_NUMBER}`}
            >
              <Phone aria-hidden="true" />
              Call {EMERGENCY_NUMBER}
            </a>
          </Button>
        ) : null}
        {/* A verdict that says "get help" has to lead somewhere. /today already
            renders the ranked nearby-clinic list from the stored location, and
            already tells the user plainly when there is no location yet, so this
            hands off rather than duplicating that list inside a chat bubble. */}
        {kind === "emergency" || kind === "moderate" ? (
          <Button
            type="button"
            variant="outline"
            size="lg"
            className={cn(
              "w-full",
              kind === "emergency" &&
                "border-primary-foreground/60 bg-transparent text-primary-foreground hover:bg-primary-foreground/10 hover:text-primary-foreground",
            )}
            onClick={() => navigate("/today")}
          >
            <MapPin aria-hidden="true" />
            Find a clinic near you
          </Button>
        ) : null}
        <ReasonList reasons={reasons} className={cn("text-xs", REASONS_CLASS[kind])} />
      </div>
    </Alert>
  );
}

type MessagePartLike = {
  readonly type: string;
  readonly name?: string;
  readonly data?: unknown;
};

function triageDataOf(parts: readonly MessagePartLike[]): unknown {
  const part = parts.find((p) => p.type === "data" && p.name === TRIAGE_PART_NAME);
  return part?.data ?? null;
}

/**
 * Reads the verdict off the enclosing assistant message. Must sit inside
 * MessagePrimitive.Root. Renders nothing when the message carries no verdict:
 * a LOW verdict is an explicit statement from the rule engine, so its absence
 * is not a LOW statement.
 */
export function AssistantTriage() {
  const data = useAuiState((s) => triageDataOf(s.message.parts));
  if (data === null) return null;
  return <TriageVerdict data={data} />;
}