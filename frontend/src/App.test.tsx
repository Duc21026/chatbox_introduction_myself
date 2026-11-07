import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("./lib/chatClient", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./lib/chatClient")>();
  return { ...actual, sendMessage: vi.fn() };
});

import App from "./App";
import { ChatApiError, sendMessage } from "./lib/chatClient";
import { useChatStore } from "./store/chatStore";

const sendMock = vi.mocked(sendMessage);

async function sendQuestion(user: ReturnType<typeof userEvent.setup>, text: string) {
  await user.type(screen.getByLabelText("Câu hỏi"), text);
  await user.click(screen.getByRole("button", { name: "Gửi câu hỏi" }));
}

describe("App", () => {
  beforeEach(() => {
    sendMock.mockReset();
    useChatStore.getState().resetSession();
    useChatStore.getState().setSidebarOpen(true);
    useChatStore.getState().setThemeMode("system");
  });

  it("sends a question and shows the answer without reloading", async () => {
    const user = userEvent.setup();
    sendMock.mockResolvedValueOnce({
      mode: "complete",
      content: "GPA hiện tại là 8.30",
    });
    render(<App />);

    expect(screen.getByText("Bạn muốn biết điều gì?")).toBeInTheDocument();
    await sendQuestion(user, "GPA hiện tại?");

    expect(await screen.findByText("GPA hiện tại là 8.30")).toBeInTheDocument();
    const log = screen.getByRole("log");
    expect(within(log).getByText("GPA hiện tại?")).toBeInTheDocument();
  });

  it("shows an error and retries without duplicating the question", async () => {
    const user = userEvent.setup();
    sendMock
      .mockRejectedValueOnce(new ChatApiError("server", "Máy chủ gặp lỗi.", true))
      .mockResolvedValueOnce({ mode: "complete", content: "Đã trả lời lại" });

    render(<App />);
    await sendQuestion(user, "Câu hỏi lỗi");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Máy chủ gặp lỗi.");
    await user.click(within(alert).getByRole("button", { name: "Thử lại" }));

    expect(await screen.findByText("Đã trả lời lại")).toBeInTheDocument();
    const log = screen.getByRole("log");
    expect(within(log).getAllByText("Câu hỏi lỗi")).toHaveLength(1);
  });

  it("keeps two conversations isolated when switching", async () => {
    const user = userEvent.setup();
    sendMock
      .mockResolvedValueOnce({ mode: "complete", content: "Đáp án một" })
      .mockResolvedValueOnce({ mode: "complete", content: "Đáp án hai" });

    render(<App />);
    await sendQuestion(user, "Câu hỏi một");
    await screen.findByText("Đáp án một");

    await user.click(
      screen.getByRole("button", { name: "Cuộc trò chuyện mới" }),
    );
    await sendQuestion(user, "Câu hỏi hai");
    await screen.findByText("Đáp án hai");

    await user.click(screen.getByTitle("Câu hỏi một"));

    const log = screen.getByRole("log");
    expect(within(log).getByText("Đáp án một")).toBeInTheDocument();
    expect(within(log).queryByText("Đáp án hai")).not.toBeInTheDocument();
  });

  it("returns to an empty workspace when the session resets", async () => {
    const user = userEvent.setup();
    sendMock.mockResolvedValueOnce({ mode: "complete", content: "Đáp án" });
    render(<App />);
    await sendQuestion(user, "Câu hỏi");
    await screen.findByText("Đáp án");

    act(() => {
      useChatStore.getState().resetSession();
    });

    await waitFor(() =>
      expect(screen.getByText("Bạn muốn biết điều gì?")).toBeInTheDocument(),
    );
    expect(screen.queryByRole("log")).not.toBeInTheDocument();
  });


  it("keeps streamed content when the theme changes mid-stream", async () => {
    const user = userEvent.setup();
    let finish: () => void = () => undefined;
    const pending = new Promise<{ mode: "stream"; content: string }>(
      (resolve) => {
        finish = () => resolve({ mode: "stream", content: "Một phần" });
      },
    );
    sendMock.mockImplementationOnce(async (_message, options) => {
      options?.onChunk?.("Một phần");
      return pending;
    });

    render(<App />);
    await sendQuestion(user, "Câu hỏi dài");

    expect(await screen.findByText("Một phần")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Giao diện:/ }));

    expect(screen.getByText("Một phần")).toBeInTheDocument();
    expect(useChatStore.getState().themeMode).toBe("light");

    await act(async () => {
      finish();
      await pending;
    });
  });

  it("changes the theme and exposes the current mode", async () => {
    const user = userEvent.setup();
    render(<App />);

    const toggle = screen.getByRole("button", { name: /Giao diện:/ });
    expect(toggle).toHaveAttribute("aria-label", expect.stringContaining("Theo hệ thống"));
    await user.click(toggle);

    expect(useChatStore.getState().themeMode).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
