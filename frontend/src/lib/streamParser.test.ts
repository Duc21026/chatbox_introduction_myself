import { describe, expect, it } from "vitest";

import { parseSseEvent } from "./streamParser";

describe("parseSseEvent", () => {
  it("parses chunk, done, and error events", () => {
    expect(parseSseEvent('data: {"type":"chunk","content":"Xin"}')).toEqual({
      type: "chunk",
      content: "Xin",
    });
    expect(parseSseEvent('data: {"type":"done"}')).toEqual({ type: "done" });
    expect(
      parseSseEvent('data: {"type":"error","message":"Lỗi"}'),
    ).toEqual({ type: "error", message: "Lỗi" });
  });

  it("ignores comments, empty data, malformed JSON, and unknown types", () => {
    expect(parseSseEvent(": ping")).toBeNull();
    expect(parseSseEvent("data:")).toBeNull();
    expect(parseSseEvent("data: not-json")).toBeNull();
    expect(parseSseEvent('data: {"type":"unknown"}')).toBeNull();
    expect(parseSseEvent("event: message")).toBeNull();
  });

  it("preserves Vietnamese content and whitespace", () => {
    expect(
      parseSseEvent('data: {"type":"chunk","content":"  học phí  "}'),
    ).toEqual({ type: "chunk", content: "  học phí  " });
  });
});
