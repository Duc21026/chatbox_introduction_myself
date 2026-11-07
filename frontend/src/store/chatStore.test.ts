import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/chatClient", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/chatClient")>();
  return { ...actual, sendMessage: vi.fn() };
});

import { ChatApiError, sendMessage } from "../lib/chatClient";
import {
  titleFromQuestion,
  useChatStore,
} from "./chatStore";

const sendMock = vi.mocked(sendMessage);

describe("chat store", () => {
  beforeEach(() => {
    sendMock.mockReset();
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

  it("creates a conversation and completes a non-streaming answer", async () => {
    sendMock.mockResolvedValueOnce({ mode: "complete", content: "Trả lời" });

    await useChatStore.getState().sendMessage("GPA hiện tại?");

    const state = useChatStore.getState();
    expect(state.conversations).toHaveLength(1);
    const conversation = state.conversations[0];
    expect(conversation.title).toBe("GPA hiện tại?");
    expect(conversation.messages.map((message) => message.role)).toEqual([
      "user",
      "assistant",
    ]);
    expect(conversation.messages[1].content).toBe("Trả lời");
    expect(conversation.messages[1].status).toBe("complete");
    expect(state.isStreaming).toBe(false);
  });

  it("appends streamed chunks to the assistant message", async () => {
    sendMock.mockImplementationOnce(async (_message, options) => {
      options?.onChunk?.("Xin ");
      options?.onChunk?.("chào");
      return { mode: "stream", content: "Xin chào" };
    });

    await useChatStore.getState().sendMessage("Chào bạn");

    const conversation = useChatStore.getState().conversations[0];
    expect(conversation.messages[1].content).toBe("Xin chào");
    expect(conversation.messages[1].status).toBe("complete");
  });

  it("keeps two conversations isolated and selects the correct one", async () => {
    sendMock
      .mockResolvedValueOnce({ mode: "complete", content: "Đáp án một" })
      .mockResolvedValueOnce({ mode: "complete", content: "Đáp án hai" });

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

    useChatStore.getState().selectConversation(first!.id);
    state = useChatStore.getState();
    expect(state.activeConversationId).toBe(first!.id);
  });

  it("retries without duplicating the user message", async () => {
    sendMock
      .mockRejectedValueOnce(new ChatApiError("server", "Lỗi", true))
      .mockResolvedValueOnce({ mode: "complete", content: "Thành công" });

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
    sendMock.mockResolvedValueOnce({ mode: "complete", content: "Trả lời" });
    await useChatStore.getState().sendMessage("Câu hỏi");

    useChatStore.getState().resetSession();

    const state = useChatStore.getState();
    expect(state.conversations).toEqual([]);
    expect(state.activeConversationId).toBeNull();
    expect(state.isStreaming).toBe(false);
    expect(state.themeMode).toBe("dark");
  });
});
