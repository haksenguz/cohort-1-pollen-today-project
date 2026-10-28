/**
 * The /chat screen (TASKS.md J5).
 *
 * Built from assistant-ui primitives rather than a hand-rolled message
 * list. The library owns the thread state, message ordering, auto-scroll,
 * composer state, send/cancel behaviour and error rendering; this file
 * only decides how it looks and how a message is shaped on screen.
 *
 * The backend talks to us over the SSE contract in docs/API_CONTRACT.md
 * through `allergyChatAdapter`. Nothing here parses a stream.
 */
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  ErrorPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAui,
  useAuiState,
  useLocalRuntime,
} from "@assistant-ui/react";
import { useEffect, useSyncExternalStore } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowDown } from "lucide-react";
import { AgentActivity } from "./agentActivity";
import { getActivity, subscribeActivity } from "./activity";
import { allergyChatAdapter, adoptConversation } from "./allergyChatAdapter";
import { ChatAgentStatus } from "./ChatAgentStatus";
import { ChatOfflineNotice } from "./ChatOfflineNotice";
import { useComposerHistory } from "./composerHistory";
import { Markdown } from "./Markdown";
import { CopyMessageButton, RegenerateButton } from "./MessageActions";
import { MessageTimestamp } from "./MessageTimestamp";
import { ToolResult } from "./ToolResult";
import { AssistantTriage } from "./TriageVerdict";
import { useOnlineStatus } from "./useOnlineStatus";
import { ChatHistorySheet } from "../components/ChatHistorySheet";
import {
  ConversationResumeLoading,
  ConversationResumeNotice,
  SuggestedPrompts,
  conversationRuntimeKey,
  toThreadMessages,
  useConversationResume,
  useConversationRouteId,
} from "./sessions";

const UserMessage = () => (
  /* The root is a column so the time can sit under the bubble. The bubble
     keeps its own right alignment. */
  <MessagePrimitive.Root className="flex w-full flex-col items-end gap-2">
    <div className="aui-msg aui-msg-me">
      <MessagePrimitive.Content />
    </div>
    <div className="aui-msg-meta aui-msg-meta-end">
      <MessageTimestamp />
    </div>
  </MessagePrimitive.Root>
);

/* The model writes markdown, so its text is parsed into HTML. The user's own
   text is left alone: what someone typed is what they should see. */
function MarkdownText({ text }: { text: string }) {
  return <Markdown text={text} />;
}

const AssistantMessage = () => (
  /* The root is a column, not the bubble: the safety verdict sits above the
     reply as its own banner so an EMERGENCY never reads as another paragraph
     of body text inside the bubble. The bubble classes move to the wrapper
     that holds the reply text only. */
  <MessagePrimitive.Root className="flex w-full flex-col items-start gap-2">
    {/* ErrorPrimitive.Message reads the error off the enclosing message via
        useMessageError(), so it must sit INSIDE MessagePrimitive.Root. At
        thread level it threw "The current scope does not have a 'message'
        property" and unmounted the entire app, blanking /chat, which is the
        default route and where the installed PWA opens. It renders null
        when the message has no error, and takes className, which is why it
        is preferred over MessagePrimitive.Error here. */}
    <ErrorPrimitive.Message className="aui-error-message" />
    <AssistantTriage />
    <div className="aui-msg aui-msg-bot">
      {/* The verdict part is rendered above, not here, so the in-bubble
          fallback is suppressed rather than drawing it twice. */}
      <MessagePrimitive.Content
        components={{ Text: MarkdownText, data: { Fallback: () => null } }}
      />
    </div>
    <div className="aui-msg-meta">
      <MessageTimestamp />
      <CopyMessageButton />
      <RegenerateButton />
    </div>
  </MessagePrimitive.Root>
);

function Composer() {
  const aui = useAui();
  const { recall, forget, isWalking } = useComposerHistory();
  const online = useOnlineStatus();

  /* Land the caret at the end after a recall. Deferred by a tick so it runs
     after the controlled textarea has re-rendered with the new value. */
  const placeCaretAtEnd = (element: HTMLTextAreaElement) => {
    setTimeout(() => {
      const end = element.value.length;
      element.setSelectionRange(end, end);
    }, 0);
  };

  const recallBy = (direction: -1 | 1, element: HTMLTextAreaElement) => {
    aui.composer.setText(recall(direction, element.value));
    placeCaretAtEnd(element);
  };

  return (
    <ComposerPrimitive.Root
      className="aui-composer"
      /* Offline means the socket is dead. The send is refused here rather
         than left to fail on the network, because a message that appears in
         the thread and then disappears is a message the user believes was
         sent. */
      onSubmit={(event) => {
        if (!online) event.preventDefault();
      }}
    >
      <ComposerPrimitive.Input
        className="aui-composer-input"
        placeholder="Describe how you feel, in any language"
        aria-label="Message"
        /* Pinned rather than inherited. Enter sends, Shift+Enter inserts a
           newline and Escape stops the turn, and those are assistant-ui's
           defaults today. A triage app should not quietly change its keyboard
           contract because a dependency shipped a minor version, so the
           behaviour is stated here where a change has to be deliberate. */
        submitMode="enter"
        cancelOnEscape={true}
        onChange={forget}
        onKeyDown={(event) => {
          const element = event.currentTarget as HTMLTextAreaElement;
          const plain = !event.shiftKey && !event.altKey;
          /* Once a recall walk is under way the arrows belong to it, whatever
             the caret is doing. A shell behaves the same way, and it is what
             makes holding the key walk backwards through the thread. */
          const walking = isWalking();

          if (event.key === "ArrowUp" && plain) {
            /* Otherwise only from the very start, so a newline above in a
               multi-line draft stays reachable. */
            if (
              !walking &&
              (element.selectionStart !== 0 || element.selectionEnd !== 0)
            ) {
              return;
            }
            event.preventDefault();
            recallBy(-1, element);
            return;
          }
          if (event.key === "ArrowDown" && plain && walking) {
            /* Only claimed while walking. Otherwise the arrow is left alone so
               it keeps moving the caret in a multi-line draft. */
            event.preventDefault();
            recallBy(1, element);
          }
        }}
      />
      {/* Send and Cancel manage their own visibility from composer state, so
          both are rendered and only the relevant one shows. */}
      <ComposerPrimitive.Send
        className="aui-send"
        aria-label="Send message"
        disabled={!online}
      >
        Send
      </ComposerPrimitive.Send>
      <ComposerPrimitive.Cancel className="aui-cancel" aria-label="Stop generating">
        Stop
      </ComposerPrimitive.Cancel>
    </ComposerPrimitive.Root>
  );
}

/**
 * The answer a tool produced, rendered where the user is already looking.
 *
 * While a call is running the activity strip above the composer already says
 * so, so this only mounts once the call has settled. An errored call gets a
 * card too: the strip's row is polite, and this announces the failure
 * assertively, which is the right weight for "the search failed".
 *
 * Only a clinic lookup gets one. A tool this card cannot draw would otherwise
 * leave "Clinic search result could not be read" sitting under a strip that
 * just said something else happened entirely, which is two tools disagreeing
 * about one call. The store answers whether this is a clinic lookup without
 * holding the name that decides it.
 */
function LatestToolResult() {
  const activity = useSyncExternalStore(subscribeActivity, getActivity);
  const navigate = useNavigate();
  const latest = activity?.tools.at(-1);
  if (!latest || !latest.isClinicLookup) return null;
  if (latest.status === "running") return null;
  return (
    <div className="px-3 pb-1">
      <ToolResult
        status={latest.status}
        result={latest.result}
        summary={latest.summary}
        code={latest.code}
        onAction={() => navigate("/settings?screen=location")}
      />
    </div>
  );
}

function Thread() {
  /* F1 and F2 are one mechanism, not two. role="log" with aria-atomic="false"
     tells assistive tech to speak only what was added to the transcript rather
     than re-reading the thread, and aria-busy holds every change while the turn
     is in flight, so the finished message is spoken once when that flag drops.
     Without the busy flag a streaming reply would be read out token by token,
     which is the trap F2 exists to prevent. */
  const busy = useAuiState((s) => s.thread.isRunning);

  return (
    <ThreadPrimitive.Root className="aui-thread">
      <ChatHistorySheet />
      <ThreadPrimitive.Viewport
        className="aui-viewport"
        role="log"
        aria-label="Conversation"
        aria-live="polite"
        aria-atomic="false"
        aria-relevant="additions"
        aria-busy={busy}
      >
      <ThreadPrimitive.Messages
        components={{ UserMessage, AssistantMessage }}
      />
      {/* Empty is a render-condition primitive and takes no className, so
          the styling lives on a wrapper inside it. */}
      <ThreadPrimitive.Empty>
        <div className="aui-empty">
          <p className="aui-empty-title">Tell me how you feel</p>
          <p className="aui-empty-body">
            Describe your symptoms and how long they have been going on. I
            ask a few follow-up questions, then the safety rules decide how
            urgent this is.
          </p>
          <SuggestedPrompts />
        </div>
      </ThreadPrimitive.Empty>
      {/* The library keeps this control mounted and disables it while the
          viewport is already at the bottom, where there is nowhere to jump to.
          The auto-scroll reads the same state, so the two never fight. */}
      <ThreadPrimitive.ScrollToBottom
        className="aui-jump"
        aria-label="Jump to latest message"
      >
        <ArrowDown aria-hidden="true" className="aui-jump-icon" />
      </ThreadPrimitive.ScrollToBottom>
    </ThreadPrimitive.Viewport>

    <ChatAgentStatus />
    <AgentActivity />
    <LatestToolResult />
    <ChatOfflineNotice />
    <Composer />
    <p className="aui-disclaimer">
      Not a diagnosis. If you have trouble breathing or swelling of the
      tongue or throat, call 119 now.
    </p>
  </ThreadPrimitive.Root>
  );
}

export function ChatScreen() {
  const conversationId = useConversationRouteId();
  const { state, retry } = useConversationResume(conversationId);

  /* The adapter holds the active conversation id in module state, so a
     reopened thread has to claim it before the first turn is sent. */
  useEffect(() => {
    adoptConversation(conversationId);
  }, [conversationId]);

  const initialMessages =
    state.status === "ready" ? toThreadMessages(state.conversation) : [];

  // maxSteps 1: our endpoint answers one prompt per request. The default
  // allows a multi-step agent loop, which this backend does not implement.
  const runtime = useLocalRuntime(allergyChatAdapter, { maxSteps: 1, initialMessages });

  /* useLocalRuntime reads initialMessages once at construction, so the
     provider key is what makes switching conversations rebuild the thread
     instead of handing the old runtime a new message list. */
  const key = conversationRuntimeKey(conversationId, state);
  const showThread = state.status === "new" || state.status === "ready";

  return (
    <AssistantRuntimeProvider key={key} runtime={runtime}>
      {showThread ? (
        <Thread />
      ) : state.status === "loading" ? (
        <ConversationResumeLoading />
      ) : (
        <ConversationResumeNotice error={state.error} onRetry={retry} />
      )}
    </AssistantRuntimeProvider>
  );
}
