/**
 * Conversation history drawer for the chat screen (TASKS.md B-014).
 *
 * A sheet rather than a fifth tab: on a 375px phone the bottom nav is the
 * primary navigation and history is a detour from Chat, not a destination of
 * its own.
 *
 * Built on the Radix Dialog already vendored through the `radix-ui` package
 * that the shadcn primitives in ./ui depend on, so the focus trap, the
 * Escape-to-dismiss behaviour, the scroll lock and the focus restore back to
 * the trigger come from a tested primitive rather than a hand-rolled overlay.
 *
 * Self-contained on purpose: the chat screen renders this one component and
 * gets the trigger, the list, the loading/empty/error states and the New Chat
 * control without knowing any of it.
 */
import { useEffect, useState } from "react";
import { Dialog } from "radix-ui";
import { History, MessageSquarePlus, X } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { listConversations } from "../api/client";
import type { ConversationSummary } from "../api/types";
import { ChatHistoryList, type ConversationListState } from "./ChatHistoryList";
import { Button } from "./ui/button";

const NEW_CHAT_PATH = "/chat";

export function ChatHistorySheet({ activeId }: { activeId?: number }) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<ConversationListState>({ status: "loading" });
  const navigate = useNavigate();

  // Fetch on open, not on mount: the trigger sits on the chat screen, which is
  // the default route of an installed PWA, so an unreachable backend must not
  // turn the landing screen into a failed load.
  useEffect(() => {
    if (!open) return;

    let cancelled = false;
    // oxlint-disable-next-line react/set-state-in-effect -- reset so a retry never shows the previous failure
    setState({ status: "loading" });

    const load = () => {
      listConversations()
        .then((conversations: ConversationSummary[]) => {
          if (cancelled) return;
          setState({ status: "ready", conversations, activeId });
        })
        .catch((error: unknown) => {
          if (cancelled) return;
          setState({
            status: "error",
            message:
              error instanceof Error && error.message
                ? error.message
                : "Could not reach the server.",
            onRetry: load,
          });
        });
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [open, activeId]);

  return (
    <>
      <div className="flex items-center gap-2 border-b border-border bg-card px-3 py-2">
        <Button
          variant="outline"
          className="min-h-11"
          onClick={() => {
            setOpen(true);
          }}
        >
          <History />
          History
        </Button>
        <Button
          variant="ghost"
          className="min-h-11"
          onClick={() => {
            navigate(NEW_CHAT_PATH);
          }}
        >
          <MessageSquarePlus />
          New chat
        </Button>
      </div>

      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Content
            aria-describedby={undefined}
            className="fixed inset-0 flex flex-col gap-4 bg-background p-4 sm:inset-y-0 sm:right-auto sm:left-1/2 sm:w-full sm:max-w-[412px] sm:-translate-x-1/2"
          >
            <div className="flex items-center gap-2">
              <Dialog.Title className="flex-1 text-base font-semibold text-foreground">
                Conversations
              </Dialog.Title>
              <Dialog.Close asChild>
                <Button variant="ghost" size="icon-lg" className="size-11" aria-label="Close history">
                  <X />
                </Button>
              </Dialog.Close>
            </div>

            <Button
              className="min-h-11"
              onClick={() => {
                setOpen(false);
                navigate(NEW_CHAT_PATH);
              }}
            >
              <MessageSquarePlus />
              New chat
            </Button>

            <div className="-mx-1 flex-1 overflow-y-auto px-1 pb-6">
              <ChatHistoryList state={state} />
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}