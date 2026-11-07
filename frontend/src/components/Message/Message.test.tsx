import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Message } from "./Message";
import type { Message as ChatMessage } from "../../store/chatStore";
import { useChatStore } from "../../store/chatStore";

function assistantMessage(
  content: string,
  status: ChatMessage["status"] = "complete",
  error: string | null = null,
): ChatMessage {
  return {
    id: "assistant-1",
    role: "assistant",
    content,
    status,
    error,
    createdAt: Date.now(),
  };
}

describe("Message", () => {
  const writeText = vi.fn();

  beforeEach(() => {
    writeText.mockReset();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    useChatStore.getState().resetSession();
  });

  it("renders Markdown headings, lists, tables, and links", () => {
    render(
      <Message
        message={assistantMessage(
          "# Tiêu đề\n\n- một\n- hai\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n[liên kết](https://example.com)",
        )}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Tiêu đề" }),
    ).toBeInTheDocument();
    expect(screen.getByText("một")).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("target", "_blank");
  });

  it("renders fenced code and copies exactly the code", async () => {
    writeText.mockResolvedValue(undefined);
    render(
      <Message
        message={assistantMessage("```python\nprint(1)\n```")}
      />,
    );

    expect(screen.getByText("python")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sao chép mã" }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith("print(1)"));
    expect(screen.getByText("Đã sao chép")).toBeInTheDocument();
  });

  it("reports copy failure without breaking the page", async () => {
    writeText.mockRejectedValue(new Error("denied"));
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: vi.fn(() => false),
    });
    render(
      <Message message={assistantMessage("```js\nconst x = 1;\n```")} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Sao chép mã" }));

    await waitFor(() =>
      expect(screen.getByText("Không sao chép được")).toBeInTheDocument(),
    );
  });

  it("shows a streaming cursor and stopped label", () => {
    const { container, rerender } = render(
      <Message message={assistantMessage("Đang trả lời", "streaming")} />,
    );
    expect(container.querySelector(".streaming-cursor")).toBeTruthy();

    rerender(<Message message={assistantMessage("Một phần", "stopped")} />);
    expect(screen.getByText("Đã dừng trả lời.")).toBeInTheDocument();
  });

  it("shows an interrupted retry and an error retry", async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    useChatStore.setState({ retryMessage: retry });

    const { rerender } = render(
      <Message message={assistantMessage("Một phần", "interrupted")} />,
    );
    expect(
      screen.getByText("Phản hồi bị ngắt giữa chừng."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Thử lại" }));
    expect(retry).toHaveBeenCalledWith("assistant-1");

    retry.mockClear();
    rerender(
      <Message message={assistantMessage("", "error", "Lỗi máy chủ")} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Lỗi máy chủ");
    await user.click(screen.getByRole("button", { name: "Thử lại" }));
    expect(retry).toHaveBeenCalledWith("assistant-1");
  });
});
