import { useEffect, useRef } from "react";
import { MessageSquare, Plus } from "lucide-react";

import { useChatStore } from "../../store/chatStore";

export function Sidebar() {
  const conversations = useChatStore((state) => state.conversations);
  const activeConversationId = useChatStore(
    (state) => state.activeConversationId,
  );
  const sidebarOpen = useChatStore((state) => state.sidebarOpen);
  const newConversation = useChatStore((state) => state.newConversation);
  const selectConversation = useChatStore(
    (state) => state.selectConversation,
  );
  const setSidebarOpen = useChatStore((state) => state.setSidebarOpen);
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!sidebarOpen) {
      return;
    }

    const isMobile =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(max-width: 767px)").matches;
    if (!isMobile) {
      return;
    }

    const previousFocus = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    const focusable = panel?.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    focusable?.[0]?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setSidebarOpen(false);
        return;
      }
      if (event.key !== "Tab" || !focusable || focusable.length === 0) {
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previousFocus?.focus();
    };
  }, [sidebarOpen, setSidebarOpen]);

  return (
    <aside
      ref={panelRef}
      className={`sidebar ${sidebarOpen ? "is-open" : "is-collapsed"}`}
      aria-label="Điều hướng cuộc trò chuyện"
    >
      <div className="sidebar-inner">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            V
          </span>
          <span className="brand-copy">
            <span className="brand-title">Trợ lý hồ sơ</span>
            <span className="brand-subtitle">Văn Phú Đức</span>
          </span>
        </div>

        <button
          type="button"
          className="new-chat"
          onClick={newConversation}
          aria-label="Bắt đầu cuộc trò chuyện mới"
        >
          <Plus size={17} aria-hidden="true" />
          <span className="label">Cuộc trò chuyện mới</span>
        </button>

        <section className="conversation-section" aria-label="Lịch sử trò chuyện">
          <h2 className="sidebar-heading">Gần đây</h2>
          {conversations.length === 0 ? (
            <p className="sidebar-footer">Chưa có cuộc trò chuyện</p>
          ) : (
            <ul className="conversation-list">
              {conversations.map((conversation) => (
                <li key={conversation.id}>
                  <button
                    type="button"
                    className="conversation-item"
                    onClick={() => selectConversation(conversation.id)}
                    aria-current={
                      conversation.id === activeConversationId
                        ? "true"
                        : undefined
                    }
                    title={conversation.title}
                  >
                    <MessageSquare size={15} aria-hidden="true" />
                    <span className="conversation-label">
                      {conversation.title}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <p className="sidebar-footer">
          Backend Python đang được giữ tạm thời.
        </p>
      </div>
    </aside>
  );
}
