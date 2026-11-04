/**
 * When a message was sent (bugs.md C5).
 *
 * The live stream carries no timestamp, so a message that was just sent has
 * none to show. A message loaded from the server does, and that is the only
 * time this renders. The time is never invented.
 */
import { useAuiState } from "@assistant-ui/react";

/** Key the server timestamp travels under in the message metadata. */
const SENT_AT = "sentAt";

function formatTime(value: string): string | null {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function MessageTimestamp() {
  const sentAt = useAuiState((s) => {
    const custom = s.message.metadata?.custom as
      | Record<string, unknown>
      | undefined;
    const value = custom?.[SENT_AT];
    return typeof value === "string" ? value : null;
  });

  if (!sentAt) return null;
  const label = formatTime(sentAt);
  if (!label) return null;

  return (
    <time className="aui-msg-time" dateTime={sentAt}>
      {label}
    </time>
  );
}
