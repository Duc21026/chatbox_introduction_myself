import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/chatClient", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/chatClient")>();
  return {
    ...actual,
    sendMessage: vi.fn(),
    sendAction: vi.fn(),
  };
});

import {
  ChatApiError,
  sendAction as sendChatAction,
  sendMessage as sendChatMessage,
  type ChatResponse,
} from "../lib/chatClient";
import { titleFromQuestion, useChatStore } from "./chatStore";

const sendMock = vi.mocked(sendChatMessage);
const actionMock = vi.mocked(sendChatAction);

function response(
  type: ChatResponse["type"],
  content = "Trả lời",
  session = "s-1",
): ChatResponse {
  if (type === "suggest") {
    return {
      type,
      session_id: session,
      response: content,
      message: content,
      suggestions: [
        { id: "a", question: "Câu A?", score: 0.8 },
        { id: "b", question: "Câu B?", score: 0.7 },
      ],
      actions: [{ id: "other", label: "Câu hỏi khác" }],
    };
  }
  if (type === "clarify") {
    return {
      type,
      session_id: session,
      response: content,
      message: content,
      topics: ["Kỹ năng"],
      examples: ["Bạn giỏi gì?"],
      actions: [{ id: "rephrase", label: "Hỏi lại cách khác" }],
    };
  }
  return {
    type,
    session_id: session,
    response: content,
    score: 0.9,
    source: "kb:test",
    sources: [],
    actions: [],
  };
}

describe("chat store", () => {
  beforeEach(() => {
    sendMock.mockReset();
    actionMock.mockReset();
    useChatStore.getState().resetSession();
    useChatStore.getState().setThemeMode("system");
    window.localStorage.clear();
  });

  it("derives a title from the first question and truncates long text", () => {
    expect(titleFromQuestion("  GPA   hiện tại? ")).toBe("GPA hiện tại?");
    const long = "a".repeat(80);
    const title = titleFromQuestion(long);
    expect(title.length).toBeLessThanOrEqual(40);
    expect(title.endsWith("…")).toBe(true);
  });

  it("creates a conversation, sends a session id, and shows an answer", async () => {
    sendMock.mockResolvedValueOnce({
      mode: "complete",
      content: "Trả lời",
      response: response("answer"),
    });

    await useChatStore.getState().sendMessage("GPA hiện tại?");

    const state = useChatStore.getState();
    expect(state.conversations).toHaveLength(1);
    const conversation = state.conversations[0];
    expect(conversation.title).toBe("GPA hiện tại?");
    expect(conversation.sessionId).toBe("s-1");
    expect(sendMock.mock.calls[0][1]?.sessionId).toMatch(/^s-/);
    expect(conversation.messages.map((message) => message.role)).toEqual([
      "user",
      "assistant",
    ]);
    expect(conversation.messages[1].content).toBe("Trả lời");
    expect(conversation.messages[1].responseType).toBe("answer");
    expect(conversation.messages[1].status).toBe("complete");
    expect(state.isStreaming).toBe(false);
  });

  it("stores suggestions and topics from structured responses", async () => {
    sendMock
      .mockResolvedValueOnce({
        mode: "complete",
        content: "Chọn câu hỏi",
        response: response("suggest", "Chọn câu hỏi"),
      })
      .mockResolvedValueOnce({
        mode: "complete",
        content: "Chọn chủ đề",
        response: response("clarify", "Chọn chủ đề"),
      });

    await useChatStore.getState().sendMessage("mục tiêu");
    await useChatStore.getState().sendMessage("asdf");

    const messages = useChatStore.getState().conversations[0].messages;
    expect(messages[1].suggestions).toHaveLength(2);
    expect(messages[1].responseType).toBe("suggest");
    expect(messages[3].topics).toEqual(["Kỹ năng"]);
    expect(messages[3].responseType).toBe("clarify");
  });

  it("sends actions with the conversation session", async () => {
    sendMock.mockResolvedValueOnce({
      mode: "complete",
      content: "Trả lời",
      response: response("answer"),
    });
    actionMock.mockResolvedValueOnce({
      mode: "complete",
      content: "Chọn chủ đề",
      response: response("clarify", "Chọn chủ đề"),
    });

    await useChatStore.getState().sendMessage("Câu hỏi");
    const conversation = useChatStore.getState().conversations[0];
    await useChatStore
      .getState()
      .sendAction("topic", { topic: "Kỹ năng", label: "Kỹ năng" });

    expect(actionMock).toHaveBeenCalledWith(
      "topic",
      expect.objectContaining({
        sessionId: conversation.sessionId,
        topic: "Kỹ năng",
      }),
    );
    expect(useChatStore.getState().conversations[0].messages).toHaveLength(4);
  });

  it("keeps two conversations isolated and selects the correct one", async () => {
    sendMock
      .mockResolvedValueOnce({
        mode: "complete",
        content: "Đáp án một",
        response: response("answer", "Đáp án một", "s-1"),
      })
      .mockResolvedValueOnce({
        mode: "complete",
        content: "Đáp án hai",
        response: response("answer", "Đáp án hai", "s-2"),
      });

    await useChatStore.getState().sendMessage("Câu hỏi một");
    useChatStore.getState().newConversation();
    await useChatStore.getState().sendMessage("Câu hỏi hai");

    let state = useChatStore.getState();
    expect(state.conversations).toHaveLength(2);

    const first = state.conversations.find(
      (conversation) => conversation.title === "Câu hỏi một",
    );
    expect(first).toBeTruthy();
    const second = state.conversations.find(
      (conversation) => conversation.title === "Câu hỏi hai",
    );
    expect(second).toBeTruthy();
    expect(first?.messages[1].content).toBe("Đáp án một");
    expect(second?.messages[1].content).toBe("Đáp án hai");
    expect(first?.sessionId).not.toBe(second?.sessionId);

    useChatStore.getState().selectConversation(first!.id);
    state = useChatStore.getState();
    expect(state.activeConversationId).toBe(first!.id);
  });

  it("retries without duplicating the user message", async () => {
    sendMock
      .mockRejectedValueOnce(new ChatApiError("server", "Lỗi", true))
      .mockResolvedValueOnce({
        mode: "complete",
        content: "Thành công",
        response: response("answer", "Thành công"),
      });

    await useChatStore.getState().sendMessage("Câu hỏi");
    let conversation = useChatStore.getState().conversations[0];
    expect(conversation.messages).toHaveLength(2);
    expect(conversation.messages[1].status).toBe("error");

    await useChatStore.getState().retryMessage(conversation.messages[1].id);

    conversation = useChatStore.getState().conversations[0];
    expect(conversation.messages).toHaveLength(2);
    expect(conversation.messages[1].content).toBe("Thành công");
    expect(conversation.messages[1].status).toBe("complete");
  });

  it("resets the session but retains the theme", async () => {
    useChatStore.getState().setThemeMode("dark");
    sendMock.mockResolvedValueOnce({
      mode: "complete",
      content: "Trả lời",
      response: response("answer"),
    });
    await useChatStore.getState().sendMessage("Câu hỏi");

    useChatStore.getState().resetSession();

    const state = useChatStore.getState();
    expect(state.conversations).toEqual([]);
    expect(state.activeConversationId).toBeNull();
    expect(state.isStreaming).toBe(false);
    expect(state.themeMode).toBe("dark");
  });
});
