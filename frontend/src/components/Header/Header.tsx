import { PanelLeft, Plus } from "lucide-react";

import { useChatStore } from "../../store/chatStore";
import { ThemeToggle } from "../ThemeToggle/ThemeToggle";

export function Header() {
  const conversations = useChatStore((state) => state.conversations);
  const activeConversationId = useChatStore(
    (state) => state.activeConversationId,
  );
  const toggleSidebar = useChatStore((state) => state.toggleSidebar);
  const newConversation = useChatStore((state) => state.newConversation);

  const active = conversations.find(
    (conversation) => conversation.id === activeConversationId,
  );

  return (
    <header className="header">
      <div className="header-left">
        <button
          type="button"
          className="icon-button"
          onClick={toggleSidebar}
          aria-label="Ẩn hoặc hiện thanh điều hướng"
          title="Thanh điều hướng"
        >
          <PanelLeft size={18} aria-hidden="true" />
        </button>
        <h1 className="header-title">{active?.title ?? "Trợ lý hồ sơ"}</h1>
      </div>
      <div className="header-right">
        <button
          type="button"
          className="icon-button"
          onClick={newConversation}
          aria-label="Cuộc trò chuyện mới"
          title="Cuộc trò chuyện mới"
        >
          <Plus size={18} aria-hidden="true" />
        </button>
        <ThemeToggle />
      </div>
    </header>
  );
}
