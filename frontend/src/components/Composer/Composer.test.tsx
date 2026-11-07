import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../../lib/chatClient", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/chatClient")>();
  return { ...actual, sendMessage: vi.fn() };
});

import { sendMessage } from "../../lib/chatClient";
import { Composer } from "./Composer";
import { useChatStore } from "../../store/chatStore";

const sendMock = vi.mocked(sendMessage);

describe("Composer", () => {
  beforeEach(() => {
    sendMock.mockReset();
    sendMock.mockResolvedValue({ mode: "complete", content: "Trả lời" });
    useChatStore.getState().resetSession();
  });

  it("sends on Enter and clears the textarea", async () => {
    const user = userEvent.setup();
    render(<Composer />);
    const textarea = screen.getByLabelText("Câu hỏi");

    await user.type(textarea, "GPA hiện tại?");
    fireEvent.keyDown(textarea, { key: "Enter", code: "Enter" });

    await waitFor(() =>
      expect(sendMock).toHaveBeenCalledWith(
        "GPA hiện tại?",
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
    expect(textarea).toHaveValue("");
  });

  it("inserts a newline on Shift+Enter without sending", async () => {
    const user = userEvent.setup();
    render(<Composer />);
    const textarea = screen.getByLabelText("Câu hỏi");

    await user.type(textarea, "dòng một");
    fireEvent.keyDown(textarea, {
      key: "Enter",
      code: "Enter",
      shiftKey: true,
    });

    expect(sendMock).not.toHaveBeenCalled();
  });

  it("does not send while the Vietnamese input method is composing", async () => {
    const user = userEvent.setup();
    render(<Composer />);
    const textarea = screen.getByLabelText("Câu hỏi");

    await user.type(textarea, "xin chào");
    fireEvent.keyDown(textarea, {
      key: "Enter",
      code: "Enter",
      isComposing: true,
    });

    expect(sendMock).not.toHaveBeenCalled();
    expect(textarea).toHaveValue("xin chào");
  });

  it("disables send for blank input and shows stop while streaming", async () => {
    const user = userEvent.setup();
    const stop = vi.fn();
    useChatStore.setState({ stopStreaming: stop });
    const { rerender } = render(<Composer />);

    expect(screen.getByRole("button", { name: "Gửi câu hỏi" })).toBeDisabled();

    act(() => {
      useChatStore.setState({ isStreaming: true });
    });
    rerender(<Composer />);
    await user.click(screen.getByRole("button", { name: "Dừng trả lời" }));
    expect(stop).toHaveBeenCalled();
  });
});
