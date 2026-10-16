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
  useLocalRuntime,
} from "@assistant-ui/react";
import { useEffect, useSyncExternalStore } from "react";
import { allergyChatAdapter, adoptConversation } from "./allergyChatAdapter";
import { getActivity, subscribeActivity } from "./activity";
import { ChatAgentStatus } from "./ChatAgentStatus";
import { AssistantTriage } from "./TriageVerdict";
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

/**
 * Live stage indicator.
 *
 * A turn is two model calls plus the rule engine — several seconds. Without
 * this the composer sits there doing nothing and the whole screen reads as
 * broken. The text is the pipeline stage the backend reported; it never says
 * "using tool", because this agent has no tools and does no function-calling
 * (ADR 0001). `assessing` deliberately reads "applying the safety rules",
 * since that verdict comes from the deterministic engine and not the model.
 */
function AgentActivity() {
  const activity = useSyncExternalStore(subscribeActivity, getActivity);
  if (!activity) return null;
  return (
    <p className="aui-activity" role="status" aria-live="polite">
      {/* Keyed on the sequence so the pulse animation restarts on every
          stage change instead of continuing from the previous stage. */}
      <span className="aui-activity-dot" key={activity.seq} aria-hidden="true" />
      {activity.label}
    </p>
  );
}

const UserMessage = () => (
  <MessagePrimitive.Root className="aui-msg aui-msg-me">
    <MessagePrimitive.Content />
  </MessagePrimitive.Root>
);

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
      <MessagePrimitive.Content components={{ data: { Fallback: () => null } }} />
    </div>
  </MessagePrimitive.Root>
);

const Composer = () => (
  <ComposerPrimitive.Root className="aui-composer">
    <ComposerPrimitive.Input
      className="aui-composer-input"
      placeholder="Describe how you feel, in any language"
      aria-label="Message"
    />
    {/* Send and Cancel manage their own visibility from composer state, so
        both are rendered and only the relevant one shows. */}
    <ComposerPrimitive.Send className="aui-send" aria-label="Send message">
      Send
    </ComposerPrimitive.Send>
    <ComposerPrimitive.Cancel className="aui-cancel" aria-label="Stop generating">
      Stop
    </ComposerPrimitive.Cancel>
  </ComposerPrimitive.Root>
);

const Thread = () => (
  <ThreadPrimitive.Root className="aui-thread">
    <ChatHistorySheet />
    <ThreadPrimitive.Viewport className="aui-viewport">
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
    </ThreadPrimitive.Viewport>

    <ChatAgentStatus />
    <AgentActivity />
    <Composer />
    <p className="aui-disclaimer">
      Not a diagnosis. If you have trouble breathing or swelling of the
      tongue or throat, call 119 now.
    </p>
  </ThreadPrimitive.Root>
);

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
