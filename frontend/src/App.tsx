import { useEffect, useState } from "react";

import { useChatStore } from "./store/chatStore";
import { applyTheme, watchSystemTheme } from "./lib/theme";
import { checkHealth, type HealthStatus } from "./lib/health";
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
  const [starting, setStarting] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);

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

  useEffect(() => {
    let mounted = true;
    const timer = window.setTimeout(() => {
      if (mounted) setStarting(true);
    }, 2000);
    checkHealth().then((result) => {
      if (!mounted) return;
      window.clearTimeout(timer);
      setStarting(false);
      setHealth(result);
    });
    return () => {
      mounted = false;
      window.clearTimeout(timer);
    };
  }, []);

  const degraded = health?.status === "degraded";

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
        {starting ? (
          <div className="deployment-banner" role="status">
            Hệ thống đang khởi động, vui lòng chờ trong giây lát…
          </div>
        ) : null}
        {!starting && degraded ? (
          <div className="deployment-banner deployment-banner--degraded" role="status">
            {health?.message || "Hệ thống đang chạy ở chế độ dự phòng."}
          </div>
        ) : null}
        <main className="chat-main">
          {hasMessages ? <MessageList /> : <EmptyState />}
        </main>
        <p className="deployment-notice">
          Câu hỏi được gửi tới Cloudflare Workers AI để tạo vector tìm kiếm.
        </p>
        <Composer />
      </div>
    </div>
  );
}
