/**
 * Chat conversation history: list, resume, and new-conversation starters.
 *
 * One import surface so ChatScreen has a single place to look, and so the
 * conversation id handling stays in one module instead of spreading across
 * the screen.
 */
export {
  UNTITLED_CONVERSATION,
  conversationPreview,
  conversationTitle,
  parseConversationId,
  toThreadMessages,
} from "./conversationSession";
export {
  conversationRuntimeKey,
  useConversationResume,
  useConversationRouteId,
  type ConversationResumeError,
  type ConversationResumeErrorKind,
  type ConversationResumeState,
} from "./useConversationResume";
export {
  ConversationResumeLoading,
  ConversationResumeNotice,
} from "./ConversationResumeNotice";
export { SUGGESTED_PROMPTS } from "./starterPrompts";
export { SuggestedPrompts } from "./SuggestedPrompts";