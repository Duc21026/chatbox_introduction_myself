import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Sidebar } from "./Sidebar";
import { useChatStore, type Conversation } from "../../store/chatStore";

function conversation(id: string, title: string): Conversation {
  return {
    id,
    title,
    messages: [],
    createdAt: Date.now(),
  };
}

const originalMatchMedia = window.matchMedia;

describe("Sidebar", () => {
  beforeEach(() => {
    useChatStore.getState().resetSession();
    useChatStore.setState({
      conversations: [
        conversation("one", "Câu hỏi một"),
        conversation("two", "Câu hỏi hai"),
      ],
      activeConversationId: "one",
      sidebarOpen: true,
    });
  });

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
  });

  it("marks the active conversation and selects another", async () => {
    const user = userEvent.setup();
    render(<Sidebar />);

    expect(screen.getByRole("button", { name: "Câu hỏi một" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(
      screen.getByRole("button", { name: "Câu hỏi hai" }),
    ).not.toHaveAttribute("aria-current");

    await user.click(screen.getByRole("button", { name: "Câu hỏi hai" }));

    expect(useChatStore.getState().activeConversationId).toBe("two");
    expect(useChatStore.getState().sidebarOpen).toBe(false);
  });

  it("closes the mobile drawer on Escape", () => {
    window.matchMedia = ((query: string) => ({
      matches: query.includes("max-width: 767px"),
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    })) as unknown as typeof window.matchMedia;

    render(<Sidebar />);
    fireEvent.keyDown(document, { key: "Escape" });

    expect(useChatStore.getState().sidebarOpen).toBe(false);
  });

  it("renders the collapsed rail state", () => {
    useChatStore.setState({ sidebarOpen: false });
    const { container } = render(<Sidebar />);

    expect(container.querySelector(".sidebar")).toHaveClass("is-collapsed");
  });
});
