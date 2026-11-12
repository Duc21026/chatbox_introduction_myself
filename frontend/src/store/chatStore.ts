import { create } from "zustand";

import {
  ChatApiError,
  isChatApiError,
  sendAction as sendChatAction,
  sendMessage as sendChatMessage,
  type Action,
  type ChatResponse,
  type SourceRef,
  type Suggestion,
} from "../lib/chatClient";
import {
  applyTheme,
  getStoredTheme,
  persistTheme,
  resolveTheme,
  type ResolvedTheme,
  type ThemeMode,
} from "../lib/theme";

export type MessageRole = "user" | "assistant";
export type MessageStatus =
  | "complete"
  | "streaming"
  | "stopped"
  | "interrupted"
  | "error";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  status: MessageStatus;
  error: string | null;
  createdAt: number;
  sessionId?: string;
  responseType?: ChatResponse["type"];
  suggestions?: Suggestion[];
  topics?: string[];
  examples?: string[];
  actions?: Action[];
  sources?: SourceRef[];
  source?: string | null;
  score?: number | null;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  sessionId: string;
}

export interface ActionPayload {
  topic?: string;
  label?: string;
}

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  sidebarOpen: boolean;
  isStreaming: boolean;
  themeMode: ThemeMode;
  resolvedTheme: ResolvedTheme;
  sendMessage: (text: string) => Promise<void>;
  sendAction: (action: string, payload?: ActionPayload) => Promise<void>;
  retryMessage: (messageId: string) => Promise<void>;
  stopStreaming: () => void;
  newConversation: () => void;
  selectConversation: (id: string) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setThemeMode: (mode: ThemeMode) => void;
  refreshSystemTheme: (systemPrefersDark: boolean) => void;
  resetSession: () => void;
}

const MAX_TITLE_LENGTH = 40;
let activeController: AbortController | null = null;

export function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function createSessionId(): string {
  return `s-${createId().replace(/[^a-zA-Z0-9]/g, "").slice(0, 24)}`;
}

export function titleFromQuestion(question: string): string {
  const compact = question.replace(/\s+/g, " ").trim();
  if (compact.length <= MAX_TITLE_LENGTH) {
    return compact;
  }
  return `${compact.slice(0, MAX_TITLE_LENGTH - 1).trimEnd()}…`;
}

function newMessage(
  role: MessageRole,
  content: string,
  status: MessageStatus,
): Message {
  return {
    id: createId(),
    role,
    content,
    status,
    error: null,
    createdAt: Date.now(),
  };
}

function responsePatch(response: ChatResponse): Partial<Message> {
  return {
    content: response.response,
    sessionId: response.session_id,
    responseType: response.type,
    suggestions: response.type === "suggest" ? response.suggestions : [],
    topics: response.type === "clarify" ? response.topics : [],
    examples:
      response.type === "clarify" || response.type === "suggest"
        ? response.examples ?? []
        : [],
    actions: response.actions ?? [],
    sources: response.sources ?? [],
    source: response.source ?? null,
    score: response.score ?? null,
  };
}

const initialMode = getStoredTheme();
const initialResolved = applyTheme(initialMode);
const initialSidebarOpen =
  typeof window === "undefined" ||
  typeof window.matchMedia !== "function" ||
  window.matchMedia("(min-width: 768px)").matches;

export const useChatStore = create<ChatState>((set, get) => {
  const updateMessage = (
    conversationId: string,
    messageId: string,
    patch: Partial<Message>,
  ) => {
    set((state) => ({
      conversations: state.conversations.map((conversation) =>
        conversation.id === conversationId
          ? {
              ...conversation,
              messages: conversation.messages.map((message) =>
                message.id === messageId ? { ...message, ...patch } : message,
              ),
            }
          : conversation,
      ),
    }));
  };

  const updateConversationSession = (
    conversationId: string,
    sessionId: string,
  ) => {
    set((state) => ({
      conversations: state.conversations.map((conversation) =>
        conversation.id === conversationId
          ? { ...conversation, sessionId }
          : conversation,
      ),
    }));
  };

  const runRequest = async (
    conversationId: string,
    assistantId: string,
    request: { question?: string; action?: string; topic?: string; label?: string },
  ) => {
    const controller = new AbortController();
    activeController = controller;
    set({ isStreaming: true });

    const conversation =
      get().conversations.find((item) => item.id === conversationId) ?? null;
    const sessionId = conversation?.sessionId;

    try {
      const result = request.action
        ? await sendChatAction(request.action, {
            signal: controller.signal,
            sessionId,
            topic: request.topic,
          })
        : await sendChatMessage(request.question ?? "", {
            signal: controller.signal,
            sessionId,
          });

      updateMessage(conversationId, assistantId, {
        ...responsePatch(result.response),
        status: "complete",
        error: null,
      });
      updateConversationSession(conversationId, result.response.session_id);
    } catch (error) {
      if (isChatApiError(error) && error.code === "aborted") {
        updateMessage(conversationId, assistantId, {
          status: "stopped",
          error: null,
        });
      } else {
        const message =
          error instanceof ChatApiError
            ? error.message
            : "Không thể nhận câu trả lời. Vui lòng thử lại.";
        updateMessage(conversationId, assistantId, {
          status: "error",
          error: message,
        });
      }
    } finally {
      if (activeController === controller) {
        activeController = null;
      }
      set({ isStreaming: false });
    }
  };

  return {
    conversations: [],
    activeConversationId: null,
    sidebarOpen: initialSidebarOpen,
    isStreaming: false,
    themeMode: initialMode,
    resolvedTheme: initialResolved,

    sendMessage: async (text) => {
      const question = text.trim();
      if (!question || get().isStreaming) {
        return;
      }

      const conversationId = get().activeConversationId;
      let conversation = conversationId
        ? get().conversations.find((item) => item.id === conversationId) ??
          null
        : null;

      if (!conversation) {
        conversation = {
          id: createId(),
          title: titleFromQuestion(question),
          messages: [],
          createdAt: Date.now(),
          sessionId: createSessionId(),
        };
        const created = conversation;
        set((current) => ({
          conversations: [created, ...current.conversations],
          activeConversationId: created.id,
        }));
        conversation = created;
      }

      const userMessage = newMessage("user", question, "complete");
      const assistantMessage = newMessage("assistant", "", "streaming");
      const targetId = conversation.id;

      set((current) => ({
        conversations: current.conversations.map((item) =>
          item.id === targetId
            ? {
                ...item,
                title:
                  item.messages.length === 0
                    ? titleFromQuestion(question)
                    : item.title,
                messages: [
                  ...item.messages,
                  userMessage,
                  assistantMessage,
                ],
              }
            : item,
        ),
        activeConversationId: targetId,
      }));

      await runRequest(targetId, assistantMessage.id, { question });
    },

    sendAction: async (action, payload = {}) => {
      if (get().isStreaming) {
        return;
      }
      const conversationId = get().activeConversationId;
      const conversation = conversationId
        ? get().conversations.find((item) => item.id === conversationId)
        : null;
      if (!conversation) {
        return;
      }

      const label =
        payload.label ??
        (action === "topic"
          ? payload.topic ?? "Chủ đề"
          : action === "rephrase"
            ? "Hỏi lại cách khác"
            : "Câu hỏi khác");
      const userMessage = newMessage("user", label, "complete");
      const assistantMessage = newMessage("assistant", "", "streaming");

      set((current) => ({
        conversations: current.conversations.map((item) =>
          item.id === conversation.id
            ? { ...item, messages: [...item.messages, userMessage, assistantMessage] }
            : item,
        ),
      }));
      await runRequest(conversation.id, assistantMessage.id, {
        action,
        topic: payload.topic,
        label,
      });
    },

    retryMessage: async (messageId) => {
      if (get().isStreaming) {
        return;
      }

      for (const conversation of get().conversations) {
        const index = conversation.messages.findIndex(
          (message) => message.id === messageId,
        );
        if (index < 0 || conversation.messages[index].role !== "assistant") {
          continue;
        }
        const userMessage = [...conversation.messages]
          .slice(0, index)
          .reverse()
          .find((message) => message.role === "user");
        if (!userMessage) {
          return;
        }

        updateMessage(conversation.id, messageId, {
          content: "",
          status: "streaming",
          error: null,
          suggestions: [],
          topics: [],
          examples: [],
          actions: [],
          sources: [],
        });
        await runRequest(conversation.id, messageId, {
          question: userMessage.content,
        });
        return;
      }
    },

    stopStreaming: () => {
      activeController?.abort();
    },

    newConversation: () => {
      if (get().isStreaming) {
        activeController?.abort();
      }
      set({ activeConversationId: null, sidebarOpen: false });
    },

    selectConversation: (id) => {
      if (get().conversations.some((item) => item.id === id)) {
        set({ activeConversationId: id, sidebarOpen: false });
      }
    },

    toggleSidebar: () => {
      set((state) => ({ sidebarOpen: !state.sidebarOpen }));
    },

    setSidebarOpen: (open) => {
      set({ sidebarOpen: open });
    },

    setThemeMode: (mode) => {
      persistTheme(mode);
      set({ themeMode: mode, resolvedTheme: applyTheme(mode) });
    },

    refreshSystemTheme: (systemPrefersDark) => {
      set((state) => ({
        resolvedTheme:
          state.themeMode === "system"
            ? resolveTheme("system", systemPrefersDark)
            : state.resolvedTheme,
      }));
    },

    resetSession: () => {
      activeController?.abort();
      activeController = null;
      set({
        conversations: [],
        activeConversationId: null,
        isStreaming: false,
        sidebarOpen: initialSidebarOpen,
      });
    },
  };
});
