import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChatApiError, sendMessage } from "./chatClient";
import {
  jsonResponse,
  splitStreamResponse,
  streamResponse,
} from "../test/mockChat";

const STREAM_URL = "http://127.0.0.1:5000/chat/stream";
const COMPLETE_URL = "http://127.0.0.1:5000/chat";

describe("sendMessage", () => {
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

  it("falls back to /chat when streaming is unavailable", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response("", { status: 404 }))
      .mockResolvedValueOnce(jsonResponse({ response: "Câu trả lời đầy đủ" }));

    const result = await sendMessage("GPA?");

    expect(result).toEqual({
      mode: "complete",
      content: "Câu trả lời đầy đủ",
    });
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      STREAM_URL,
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      COMPLETE_URL,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("treats a JSON response from /chat/stream as a complete answer", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ response: "Một lần" }));

    const result = await sendMessage("câu hỏi");

    expect(result).toEqual({ mode: "complete", content: "Một lần" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("concatenates streamed chunks and reports completion", async () => {
    fetchMock.mockResolvedValueOnce(
      streamResponse([
        { type: "chunk", content: "Xin " },
        { type: "chunk", content: "chào" },
        { type: "done" },
      ]),
    );
    const onChunk = vi.fn();

    const result = await sendMessage("câu hỏi", { onChunk });

    expect(result).toEqual({ mode: "stream", content: "Xin chào", interrupted: false });
    expect(onChunk).toHaveBeenNthCalledWith(1, "Xin ");
    expect(onChunk).toHaveBeenNthCalledWith(2, "chào");
  });

  it("handles events split across network chunks", async () => {
    const first = 'data: {"type":"chunk","content":"Xin "}\n\n';
    const second =
      'data: {"type":"chunk","content":"chào"}\n\ndata: {"type":"done"}\n\n';
    fetchMock.mockResolvedValueOnce(
      splitStreamResponse([
        first.slice(0, 17),
        first.slice(17) + second.slice(0, 12),
        second.slice(12),
      ]),
    );

    const result = await sendMessage("câu hỏi");

    expect(result.content).toBe("Xin chào");
    expect(result.interrupted).toBe(false);
  });

  it("marks a stream without a terminal event as interrupted", async () => {
    fetchMock.mockResolvedValueOnce(
      splitStreamResponse([
        'data: {"type":"chunk","content":"một phần"}\n\n',
      ]),
    );

    const result = await sendMessage("câu hỏi");

    expect(result.mode).toBe("stream");
    expect(result.content).toBe("một phần");
    expect(result.interrupted).toBe(true);
  });

  it("throws a server error for an error event", async () => {
    fetchMock.mockResolvedValueOnce(
      streamResponse([
        { type: "chunk", content: "bắt đầu" },
        { type: "error", message: "Lỗi máy chủ" },
      ]),
    );

    await expect(sendMessage("câu hỏi")).rejects.toMatchObject({
      code: "server",
      retryable: true,
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
