/**
 * Starter prompt chips for the empty thread (TASKS.md B-014 C6).
 *
 * The empty thread already explains what to do in prose. These are for the
 * phone case where writing the first sentence is the part that stalls.
 * Tapping one sends it as the user's message through assistant-ui's own
 * suggestion primitive, so it takes the same path as a typed send.
 *
 * Render inside `ThreadPrimitive.Empty`, which only mounts while the thread
 * has no messages.
 */
import { ThreadPrimitive } from "@assistant-ui/react";

import { SUGGESTED_PROMPTS } from "./starterPrompts";

export function SuggestedPrompts() {
  return (
    /* The chips sit in two columns instead of sliding sideways. A row that
       scrolls off the edge hides half of the last chip and tells the user
       there is more, which is a worse way to offer the first sentence. Two
       columns also keep the empty screen short enough that the greeting
       stays on screen on a laptop. */
    <div className="aui-starters">
      {SUGGESTED_PROMPTS.map((prompt) => (
        <ThreadPrimitive.Suggestion
          key={prompt}
          prompt={prompt}
          send
          className="aui-starter"
        >
          {prompt}
        </ThreadPrimitive.Suggestion>
      ))}
    </div>
  );
}
