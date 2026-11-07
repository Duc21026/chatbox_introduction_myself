export type StreamEvent =
  | { type: "chunk"; content: string }
  | { type: "done" }
  | { type: "error"; message?: string };

export function parseSseEvent(line: string): StreamEvent | null {
  if (!line.startsWith("data:")) {
    return null;
  }
  const raw = line.slice(5).trim();
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as StreamEvent;
    if (
      parsed &&
      typeof parsed === "object" &&
      "type" in parsed &&
      (parsed.type === "chunk" ||
        parsed.type === "done" ||
        parsed.type === "error")
    ) {
      return parsed;
    }
  } catch {
    return null;
  }
  return null;
}
