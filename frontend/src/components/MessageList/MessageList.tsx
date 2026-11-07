import { ArrowDown } from "lucide-react";

import { useChatStore } from "../../store/chatStore";
import { useAutoScroll } from "../../hooks/useAutoScroll";
import { Message } from "../Message/Message";

export function MessageList() {
  const conversations = useChatStore((state) => state.conversations);
  const activeConversationId = useChatStore(
    (state) => state.activeConversationId,
  );

  const active = conversations.find(
    (conversation) => conversation.id === activeConversationId,
  );
  const messages = active?.messages ?? [];
  const revision = messages
    .map((message) => `${message.id}:${message.content.length}:${message.status}`)
    .join("|");
  const { ref, isNearBottom, handleScroll, scrollToBottom } = useAutoScroll(
    revision,
    activeConversationId ?? "",
  );

  return (
    <>
      <div
        ref={ref}
        className="message-list"
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        aria-label="Nội dung cuộc trò chuyện"
        onScroll={handleScroll}
      >
        <div className="message-column">
          {messages.map((message) => (
            <Message key={message.id} message={message} />
          ))}
        </div>
      </div>
      {!isNearBottom && (
        <button
          type="button"
          className="text-button scroll-latest"
          onClick={scrollToBottom}
        >
          <ArrowDown size={14} aria-hidden="true" />
          Xuống mới nhất
        </button>
      )}
    </>
  );
}
