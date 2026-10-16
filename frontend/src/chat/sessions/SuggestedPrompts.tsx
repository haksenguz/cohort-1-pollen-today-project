/**
 * Starter prompt chips for the empty thread (TASKS.md B-014 C6).
 *
 * The empty thread already explains what to do in prose. These are for the
 * phone case where writing the first sentence is the part that stalls.
 * Tapping one fills the composer rather than sending, which keeps the patient
 * in control of what gets described and lets them add detail first.
 *
 * Render inside `ThreadPrimitive.Empty`, which only mounts while the thread
 * has no messages.
 */
import { useAui } from "@assistant-ui/react";

import { SUGGESTED_PROMPTS } from "./starterPrompts";

export interface SuggestedPromptsProps {
  /** Overrides the composer seed. Used by tests; the chat screen passes nothing. */
  onSelect?: (prompt: string) => void;
}

export function SuggestedPrompts({ onSelect }: SuggestedPromptsProps = {}) {
  const aui = useAui();

  const select = onSelect ?? ((prompt: string) => aui.composer.setText(prompt));

  return (
    <div className="-mx-4 mt-6 flex gap-2 overflow-x-auto px-4 pb-1">
      {SUGGESTED_PROMPTS.map((prompt) => (
        <button
          key={prompt}
          type="button"
          onClick={() => {
            select(prompt);
          }}
          className="min-h-11 shrink-0 rounded-full border border-border bg-card px-4 py-2 text-left text-sm text-card-foreground transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}