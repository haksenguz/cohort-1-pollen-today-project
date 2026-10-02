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
import { allergyChatAdapter } from "./allergyChatAdapter";

const UserMessage = () => (
  <MessagePrimitive.Root className="aui-msg aui-msg-me">
    <MessagePrimitive.Content />
  </MessagePrimitive.Root>
);

const AssistantMessage = () => (
  <MessagePrimitive.Root className="aui-msg aui-msg-bot">
    {/* ErrorPrimitive.Message reads the error off the enclosing message via
        useMessageError(), so it must sit INSIDE MessagePrimitive.Root. At
        thread level it threw "The current scope does not have a 'message'
        property" and unmounted the entire app, blanking /chat, which is the
        default route and where the installed PWA opens. It renders null
        when the message has no error, and takes className, which is why it
        is preferred over MessagePrimitive.Error here. */}
    <ErrorPrimitive.Message className="aui-error-message" />
    <MessagePrimitive.Content />
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
        </div>
      </ThreadPrimitive.Empty>
    </ThreadPrimitive.Viewport>

    <Composer />
    <p className="aui-disclaimer">
      Not a diagnosis. If you have trouble breathing or swelling of the
      tongue or throat, call 119 now.
    </p>
  </ThreadPrimitive.Root>
);

export function ChatScreen() {
  // maxSteps 1: our endpoint answers one prompt per request. The default
  // allows a multi-step agent loop, which this backend does not implement.
  const runtime = useLocalRuntime(allergyChatAdapter, { maxSteps: 1 });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Thread />
    </AssistantRuntimeProvider>
  );
}
