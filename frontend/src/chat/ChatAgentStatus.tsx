/**
 * Status strip for the chat agent's credential.
 *
 * Why this exists
 * ---------------
 * Without a key the chat endpoint still answers 200/SSE — it emits the
 * assistant's follow-up question and then an `error` event with
 * `kind: "unavailable"`. That is correct server behaviour (ADR 0001: the
 * deterministic engine still gets to ask its screening questions even when
 * the model is down), but from the user's side it looks like the bot thought
 * about it and then gave up, with no hint that the fix is a missing API key
 * buried at the bottom of the Profile screen.
 *
 * So: one strip at the top of /chat that says either "agent ready" or "no key
 * yet — add one", with a link to the one place it can be saved. That makes
 * Profile the single save location and removes the hunt.
 *
 * Renders nothing at all when the backend has DEV_SETTINGS_ENABLED off, which
 * is every build except a local dev box.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CircleCheck, TriangleAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

import { readDevLlmSettings } from "../api/client";

type State = "hidden" | "ready" | "missing";

export function ChatAgentStatus() {
  const [state, setState] = useState<State>("hidden");
  const [model, setModel] = useState("");

  useEffect(() => {
    let cancelled = false;
    readDevLlmSettings()
      .then((s) => {
        if (cancelled) return;
        setModel(s.model);
        setState(s.configured ? "ready" : "missing");
      })
      .catch(() => {
        // Endpoint absent -> DEV_SETTINGS_ENABLED is off. Not a problem the
        // user can act on, so say nothing.
        if (!cancelled) setState("hidden");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "hidden") return null;

  // Built on shadcn primitives, not hand-rolled divs and hand-picked CSS.
  // The earlier version of this used `.agentbar*` classes that were never
  // actually defined in theme.css — dead hooks that looked like styling and
  // were not, which is how colours "chosen by eye" survived a rebuild. See
  // bugs.md B-006. Spacing and colour now come from Tailwind utilities and
  // the theme tokens Alert already binds to, so contrast is guaranteed in
  // both themes rather than eyeballed once.
  // `variant="warning"` does not exist on Alert, so the missing-key case uses
  // the default variant plus an explicit icon, which keeps the colour token
  // (and therefore its contrast) coming from the theme.
  if (state === "missing") {
    return (
      <div className="mb-1.5">
        <Alert role="status">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>No chat agent key is set</AlertTitle>
          <AlertDescription>
            Replies will fail until one is saved.{" "}
            <Link className="font-medium underline underline-offset-4" to="/settings">
              Add your API key
            </Link>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="mb-1.5">
      <Alert role="status">
        <CircleCheck aria-hidden="true" />
        <AlertDescription>
          Chat agent ready
          <span className="text-muted-foreground"> · {model}</span>
        </AlertDescription>
      </Alert>
    </div>
  );
}