import { useEffect } from "react";

import { useChatStore } from "./store/chatStore";
import { applyTheme, watchSystemTheme } from "./lib/theme";
import { Sidebar } from "./components/Sidebar/Sidebar";
import { Header } from "./components/Header/Header";
import { MessageList } from "./components/MessageList/MessageList";
import { EmptyState } from "./components/EmptyState/EmptyState";
import { Composer } from "./components/Composer/Composer";

export default function App() {
  const conversations = useChatStore((state) => state.conversations);
  const activeConversationId = useChatStore(
    (state) => state.activeConversationId,
  );
  const sidebarOpen = useChatStore((state) => state.sidebarOpen);
  const themeMode = useChatStore((state) => state.themeMode);
  const setSidebarOpen = useChatStore((state) => state.setSidebarOpen);
  const refreshSystemTheme = useChatStore(
    (state) => state.refreshSystemTheme,
  );

  const active = conversations.find(
    (conversation) => conversation.id === activeConversationId,
  );
  const hasMessages = Boolean(active && active.messages.length > 0);

  useEffect(() => {
    applyTheme(themeMode);
    return watchSystemTheme((prefersDark) => {
      refreshSystemTheme(prefersDark);
      applyTheme(themeMode, prefersDark);
    });
  }, [themeMode, refreshSystemTheme]);

  return (
    <div className="app-shell">
      <Sidebar />
      <button
        type="button"
        className={`drawer-backdrop ${sidebarOpen ? "is-visible" : ""}`}
        aria-label="Đóng thanh điều hướng"
        onClick={() => setSidebarOpen(false)}
      />
      <div className="workspace">
        <Header />
        <main className="chat-main">
          {hasMessages ? <MessageList /> : <EmptyState />}
        </main>
        <Composer />
      </div>
    </div>
  );
}
