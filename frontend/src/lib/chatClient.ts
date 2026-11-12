import type { ChatResponse } from "./chatTypes";
import { getApiBaseUrl } from "./config";

export type { ChatResponse, ResponseType, Suggestion, Action, SourceRef } from "./chatTypes";

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
  sessionId?: string;
  action?: string;
  topic?: string;
  onChunk?: (text: string) => void;
}

export interface SendResult {
  mode: "complete";
  content: string;
  response: ChatResponse;
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

function parseChatResponse(payload: unknown): ChatResponse | null {
  if (
    payload === null ||
    typeof payload !== "object" ||
    !("type" in payload) ||
    !("session_id" in payload) ||
    !("response" in payload)
  ) {
    return null;
  }
  const type = (payload as { type: unknown }).type;
  if (type !== "answer" && type !== "suggest" && type !== "clarify") {
    return null;
  }
  return payload as ChatResponse;
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
  if (response.status === 400 || response.status === 422) {
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

function requestBody(
  message: string | undefined,
  options: SendOptions,
): Record<string, string> {
  const body: Record<string, string> = {};
  if (message) {
    body.message = message;
  }
  if (options.sessionId) {
    body.session_id = options.sessionId;
  }
  if (options.action) {
    body.action = options.action;
  }
  if (options.topic) {
    body.topic = options.topic;
  }
  return body;
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

  return requestChat(trimmed, options);
}

export async function sendAction(
  action: string,
  options: SendOptions = {},
): Promise<SendResult> {
  const normalized = action.trim().toLowerCase();
  if (!normalized) {
    throw new ChatApiError("invalid-input", "Hành động không hợp lệ.", false);
  }
  if (normalized === "topic" && !options.topic?.trim()) {
    throw new ChatApiError("invalid-input", "Thiếu chủ đề đã chọn.", false);
  }
  return requestChat(undefined, { ...options, action: normalized });
}

async function requestChat(
  message: string | undefined,
  options: SendOptions,
): Promise<SendResult> {
  const baseUrl = getApiBaseUrl();
  let response: Response;
  try {
    response = await fetchWithTimeout(`${baseUrl}/chat`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody(message, options)),
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

  const parsed = parseChatResponse(await readJson(response));
  if (parsed === null) {
    throw new ChatApiError(
      "server",
      "Máy chủ trả về dữ liệu không hợp lệ. Vui lòng thử lại.",
      true,
    );
  }
  const content = parsed.response;
  if (content) {
    options.onChunk?.(content);
  }
  return { mode: "complete", content, response: parsed };
}
