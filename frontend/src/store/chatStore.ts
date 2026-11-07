import { create } from "zustand";

import {
  ChatApiError,
  isChatApiError,
  sendMessage as sendChatMessage,
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
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
}

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  sidebarOpen: boolean;
  isStreaming: boolean;
  themeMode: ThemeMode;
  resolvedTheme: ResolvedTheme;
  sendMessage: (text: string) => Promise<void>;
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

  const runAnswer = async (
    conversationId: string,
    assistantId: string,
    question: string,
  ) => {
    const controller = new AbortController();
    activeController = controller;
    set({ isStreaming: true });

    try {
      const result = await sendChatMessage(question, {
        signal: controller.signal,
        onChunk: (chunk) => {
          set((state) => ({
            conversations: state.conversations.map((conversation) =>
              conversation.id === conversationId
                ? {
                    ...conversation,
                    messages: conversation.messages.map((message) =>
                      message.id === assistantId
                        ? { ...message, content: message.content + chunk }
                        : message,
                    ),
                  }
                : conversation,
            ),
          }));
        },
      });

      if (result.mode === "complete") {
        updateMessage(conversationId, assistantId, {
          content: result.content,
          status: result.interrupted ? "interrupted" : "complete",
          error: null,
        });
      } else {
        updateMessage(conversationId, assistantId, {
          status: result.interrupted ? "interrupted" : "complete",
          error: null,
        });
      }
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

      await runAnswer(targetId, assistantMessage.id, question);
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
        });
        await runAnswer(conversation.id, messageId, userMessage.content);
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
