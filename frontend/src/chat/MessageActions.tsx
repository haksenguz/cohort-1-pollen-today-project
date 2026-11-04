/**
 * The controls under an assistant reply (bugs.md C3 and C4).
 *
 * Both live inside `MessagePrimitive.Root`, so the message scope gives them the
 * text of the reply they belong to.
 */
import { useAui, useAuiState } from "@assistant-ui/react";
import { Copy, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { markNextRunAsRegeneration } from "./allergyChatAdapter";

/**
 * Writes to the clipboard and says so out loud.
 *
 * A browser can refuse the async clipboard API: it is missing on insecure
 * origins and blocked by permissions. When that happens the user is told the
 * copy failed, because a toast that claims success on a failed copy is worse
 * than no toast.
 */
async function writeToClipboard(text: string): Promise<void> {
  if (!navigator.clipboard?.writeText) {
    throw new Error("clipboard unavailable");
  }
  await navigator.clipboard.writeText(text);
}

/** Copies the plain text of the reply. */
export function CopyMessageButton() {
  const aui = useAui();

  const copy = async () => {
    const text = aui.message.getCopyText();
    if (!text) return;
    try {
      await writeToClipboard(text);
      toast.success("Reply copied.");
    } catch {
      toast.error("Copy failed.", {
        description: "Your browser blocked the clipboard. Select the text and copy it by hand.",
      });
    }
  };

  return (
    <button type="button" className="aui-msg-action" aria-label="Copy reply" onClick={copy}>
      <Copy aria-hidden="true" className="aui-msg-action-icon" />
      Copy
    </button>
  );
}

/**
 * Re-runs the last assistant turn.
 *
 * The button only exists on the last reply, because that is the only one a
 * regeneration replaces. It is disabled while a turn is in flight: two turns
 * writing into the same thread is not a thing the user asked for.
 */
export function RegenerateButton() {
  const aui = useAui();
  const isRunning = useAuiState((s) => s.thread.isRunning);
  const messageId = useAuiState((s) => s.message.id);
  const lastMessageId = useAuiState((s) => {
    const messages = s.thread.messages;
    return messages.length > 0 ? messages[messages.length - 1].id : null;
  });

  if (lastMessageId !== messageId) return null;

  return (
    <button
      type="button"
      className="aui-msg-action"
      aria-label="Regenerate the last reply"
      disabled={isRunning}
      onClick={() => {
        // The adapter cannot tell a regeneration from a normal turn on its
        // own: both end in a user message. The flag says which one this is.
        markNextRunAsRegeneration();
        aui.message.reload();
      }}
    >
      <RotateCcw aria-hidden="true" className="aui-msg-action-icon" />
      Try again
    </button>
  );
}
