import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChatApiError, sendAction, sendMessage } from "./chatClient";
import type { ChatResponse } from "./chatTypes";
import { jsonResponse } from "../test/mockChat";

const CHAT_URL = "http://127.0.0.1:5000/chat";

function answer(): ChatResponse {
  return {
    type: "answer",
    session_id: "s-1",
    score: 0.91,
    response: "GPA hiện tại là 8.30",
    answer_bullets: null,
    source: "kb:gpa",
    sources: [],
    actions: [],
  };
}

describe("chat client", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("rejects blank input without calling the backend", async () => {
    await expect(sendMessage("   ")).rejects.toMatchObject({
      code: "invalid-input",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("uses the canonical /chat endpoint and returns structured data", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(answer()));
    const onChunk = vi.fn();

    const result = await sendMessage("GPA?", { sessionId: "s-1", onChunk });

    expect(result.mode).toBe("complete");
    expect(result.content).toBe("GPA hiện tại là 8.30");
    expect(result.response.type).toBe("answer");
    expect(onChunk).toHaveBeenCalledWith("GPA hiện tại là 8.30");
    expect(fetchMock).toHaveBeenCalledWith(
      CHAT_URL,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("sends session and action payload", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        type: "clarify",
        session_id: "s-1",
        response: "Chọn chủ đề",
        message: "Chọn chủ đề",
        topics: ["Kỹ năng"],
        examples: [],
        actions: [{ id: "rephrase", label: "Hỏi lại cách khác" }],
      }),
    );

    await sendAction("topic", { sessionId: "s-1", topic: "Kỹ năng" });

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body).toMatchObject({
      session_id: "s-1",
      action: "topic",
      topic: "Kỹ năng",
    });
  });

  it("maps HTTP 500 to a retryable server error", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: "boom" }), { status: 500 }),
    );

    const error = await sendMessage("câu hỏi").catch((value) => value);
    expect(error).toBeInstanceOf(ChatApiError);
    expect(error).toMatchObject({ code: "server", retryable: true });
  });

  it("rejects an invalid response body", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ response: "không cấu trúc" }));

    await expect(sendMessage("câu hỏi")).rejects.toMatchObject({
      code: "server",
    });
  });

  it("reports abort as an aborted error", async () => {
    const controller = new AbortController();
    fetchMock.mockImplementationOnce(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        }),
    );

    const pending = sendMessage("câu hỏi", { signal: controller.signal });
    controller.abort();

    await expect(pending).rejects.toMatchObject({ code: "aborted" });
  });
});
