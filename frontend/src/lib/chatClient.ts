import { getApiBaseUrl } from "./config";
import { parseSseEvent } from "./streamParser";

export type { StreamEvent } from "./streamParser";

export type ChatErrorCode =
  | "invalid-input"
  | "network"
  | "server"
  | "client"
  | "rate-limit"
  | "interrupted"
  | "aborted";

export class ChatApiError extends Error {
  readonly code: ChatErrorCode;
  readonly retryable: boolean;

  constructor(code: ChatErrorCode, message: string, retryable: boolean) {
    super(message);
    this.name = "ChatApiError";
    this.code = code;
    this.retryable = retryable;
  }
}

export interface SendOptions {
  signal?: AbortSignal;
  onChunk?: (text: string) => void;
}

export interface SendResult {
  mode: "stream" | "complete";
  content: string;
  interrupted?: boolean;
}

export function isAbortError(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === "AbortError") ||
    (error instanceof Error && error.name === "AbortError")
  );
}

export function isTimeoutError(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === "TimeoutError") ||
    (error instanceof Error && error.name === "TimeoutError")
  );
}

const DEFAULT_TIMEOUT_MS = 120_000;

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const external = init.signal;
  const forwardAbort = () => controller.abort();
  if (external) {
    if (external.aborted) {
      controller.abort();
    } else {
      external.addEventListener("abort", forwardAbort, { once: true });
    }
  }
  const timer = setTimeout(() => {
    controller.abort(new DOMException("Hết thời gian chờ", "TimeoutError"));
  }, timeoutMs);

  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
    external?.removeEventListener("abort", forwardAbort);
  }
}

export function isChatApiError(error: unknown): error is ChatApiError {
  return error instanceof ChatApiError;
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function responseContent(payload: unknown): string | null {
  if (
    payload !== null &&
    typeof payload === "object" &&
    "response" in payload &&
    typeof (payload as { response: unknown }).response === "string"
  ) {
    return (payload as { response: string }).response;
  }
  return null;
}

async function errorFromResponse(response: Response): Promise<ChatApiError> {
  if (response.status === 429) {
    return new ChatApiError(
      "rate-limit",
      "Hệ thống đang bận. Vui lòng thử lại sau ít phút.",
      true,
    );
  }
  if (response.status >= 500) {
    return new ChatApiError(
      "server",
      "Máy chủ chưa thể trả lời. Vui lòng thử lại.",
      true,
    );
  }
  if (response.status === 400) {
    return new ChatApiError(
      "client",
      "Câu hỏi chưa hợp lệ. Vui lòng nhập lại.",
      false,
    );
  }
  return new ChatApiError(
    "client",
    "Không thể gửi câu hỏi. Vui lòng thử lại.",
    false,
  );
}

async function requestComplete(
  baseUrl: string,
  message: string,
  options: SendOptions,
): Promise<SendResult> {
  let response: Response;
  try {
    response = await fetchWithTimeout(`${baseUrl}/chat`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message }),
      signal: options.signal,
    });
  } catch (error) {
    if (isAbortError(error)) {
      throw new ChatApiError("aborted", "Đã dừng trả lời.", false);
    }
    if (isTimeoutError(error)) {
      throw new ChatApiError(
        "network",
        "Máy chủ phản hồi quá lâu. Vui lòng thử lại.",
        true,
      );
    }
    throw new ChatApiError(
      "network",
      "Không kết nối được máy chủ. Vui lòng kiểm tra kết nối và thử lại.",
      true,
    );
  }

  if (!response.ok) {
    throw await errorFromResponse(response);
  }

  const content = responseContent(await readJson(response));
  if (content === null) {
    throw new ChatApiError(
      "server",
      "Máy chủ trả về dữ liệu không hợp lệ. Vui lòng thử lại.",
      true,
    );
  }
  return { mode: "complete", content };
}

async function consumeStream(
  response: Response,
  options: SendOptions,
): Promise<SendResult> {
  if (!response.body) {
    throw new ChatApiError(
      "interrupted",
      "Kết nối bị ngắt trước khi có câu trả lời. Vui lòng thử lại.",
      true,
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let content = "";
  let finished = false;

  const handleLine = (line: string) => {
    const event = parseSseEvent(line);
    if (!event) {
      return;
    }
    if (event.type === "chunk") {
      content += event.content;
      options.onChunk?.(event.content);
      return;
    }
    if (event.type === "done") {
      finished = true;
      return;
    }
    if (event.type === "error") {
      throw new ChatApiError(
        "server",
        event.message || "Máy chủ gặp lỗi khi trả lời. Vui lòng thử lại.",
        true,
      );
    }
  };

  try {
    while (!finished) {
      const { value, done } = await reader.read();
      if (done) {
        buffer += decoder.decode();
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        handleLine(line);
        if (finished) {
          break;
        }
      }
    }
    if (!finished && buffer.trim()) {
      handleLine(buffer);
    }
  } catch (error) {
    if (isAbortError(error)) {
      throw new ChatApiError("aborted", "Đã dừng trả lời.", false);
    }
    if (error instanceof ChatApiError) {
      throw error;
    }
    throw new ChatApiError(
      "interrupted",
      "Kết nối bị ngắt giữa chừng. Vui lòng thử lại.",
      true,
    );
  } finally {
    try {
      await reader.cancel();
    } catch {
      // The stream may already be closed.
    }
  }

  return { mode: "stream", content, interrupted: !finished };
}

export async function sendMessage(
  message: string,
  options: SendOptions = {},
): Promise<SendResult> {
  const trimmed = message.trim();
  if (!trimmed) {
    throw new ChatApiError(
      "invalid-input",
      "Vui lòng nhập câu hỏi trước khi gửi.",
      false,
    );
  }

  const baseUrl = getApiBaseUrl();

  let response: Response;
  try {
    response = await fetchWithTimeout(`${baseUrl}/chat/stream`, {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message: trimmed }),
      signal: options.signal,
    });
  } catch (error) {
    if (isAbortError(error)) {
      throw new ChatApiError("aborted", "Đã dừng trả lời.", false);
    }
    if (isTimeoutError(error)) {
      throw new ChatApiError(
        "network",
        "Máy chủ phản hồi quá lâu. Vui lòng thử lại.",
        true,
      );
    }
    return requestComplete(baseUrl, trimmed, options);
  }

  if ([404, 405, 501].includes(response.status)) {
    return requestComplete(baseUrl, trimmed, options);
  }

  if (!response.ok) {
    throw await errorFromResponse(response);
  }

  const contentType = response.headers.get("Content-Type") ?? "";
  if (contentType.includes("application/json")) {
    const content = responseContent(await readJson(response));
    if (content === null) {
      throw new ChatApiError(
        "server",
        "Máy chủ trả về dữ liệu không hợp lệ. Vui lòng thử lại.",
        true,
      );
    }
    return { mode: "complete", content };
  }

  return consumeStream(response, options);
}
