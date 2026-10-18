/**
 * The activity strip above the composer.
 *
 * One live region, one job: say what the agent is doing right now and what it
 * just finished doing. Before this existed a turn was several seconds of a
 * silent composer, and a tool call the user cannot see is indistinguishable
 * from a slow chatbot.
 *
 * Two rules shape what is rendered here.
 *
 * The user never reads an identifier. The wording comes from `activity.ts`,
 * which maps tool names to sentences, so a name or an argument payload has no
 * route to the screen at all.
 *
 * A failed call never reads as a clean one. An errored row is tinted, carries
 * a warning icon and says it could not finish. A clinic failure is stated
 * twice on purpose: this strip is one polite region, and the tool card that
 * renders alongside it announces the same failure assertively. They are
 * siblings rather than nested regions, so neither swallows the other. A tool
 * with no clinic card has only this one, which is why the row is never muted.
 */
import { CircleCheck, TriangleAlert } from "lucide-react";
import { useSyncExternalStore } from "react";

import { getActivity, subscribeActivity, type ToolActivity } from "./activity";

function ToolRow({ tool }: { tool: ToolActivity }) {
  if (tool.status === "running") {
    return (
      /* No attempt to mute this row. `aria-live="off"` on a descendant does
         not take it out of an ancestor's live region, so an attribute here
         would claim a silence the markup does not produce. The running line is
         worth announcing anyway: it is the answer to "is anything happening". */
      <li className="aui-activity" data-state="running">
        {/* Keyed on the event sequence so the pulse restarts on each new call
            instead of continuing from the previous one. */}
        <span className="aui-activity-dot" key={tool.seq} aria-hidden="true" />
        {tool.label}
      </li>
    );
  }

  if (tool.status === "error") {
    return (
      <li
        className="flex items-start gap-1.5 px-1 py-0.5 text-sm text-destructive"
        data-state="error"
      >
        <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        <span className="min-w-0 break-words">
          <span className="font-medium">{tool.failure}.</span> {tool.summary}
        </span>
      </li>
    );
  }

  return (
    <li className="flex items-start gap-1.5 px-1 py-0.5 text-sm" data-state="done">
      <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden="true" />
      <span className="min-w-0 break-words">{tool.summary}</span>
    </li>
  );
}

export function AgentActivity() {
  const activity = useSyncExternalStore(subscribeActivity, getActivity);
  if (!activity) return null;

  return (
    /* One region for the whole strip, so the stage line and the tool rows are
       announced in order rather than as two competing live regions.
       `aria-atomic` stays off: a finished tool row announces once, on arrival,
       instead of the whole strip being re-read on every stage change. */
    <div role="status" aria-live="polite" data-slot="agent-activity">
      {activity.stage !== null ? (
        <p className="aui-activity">
          <span className="aui-activity-dot" key={activity.seq} aria-hidden="true" />
          {activity.label}
        </p>
      ) : null}

      {activity.tools.length > 0 ? (
        <ul className="mb-1.5 list-none">
          {activity.tools.map((tool) => (
            <ToolRow key={tool.id} tool={tool} />
          ))}
        </ul>
      ) : null}
    </div>
  );
}