import { useRef, useState, type KeyboardEvent } from "react";
import { ArrowUp, Square } from "lucide-react";

import { useChatStore } from "../../store/chatStore";
import { useAutoResize } from "../../hooks/useAutoResize";

export function Composer() {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isStreaming = useChatStore((state) => state.isStreaming);
  const sendMessage = useChatStore((state) => state.sendMessage);
  const stopStreaming = useChatStore((state) => state.stopStreaming);

  useAutoResize(textareaRef, value);

  const submit = () => {
    const question = value.trim();
    if (!question || isStreaming) {
      return;
    }
    setValue("");
    void sendMessage(question);
    textareaRef.current?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }
    if (event.nativeEvent.isComposing || event.keyCode === 229) {
      return;
    }
    event.preventDefault();
    submit();
  };

  return (
    <div className="composer-wrap">
      <div className="composer">
        <label className="visually-hidden" htmlFor="chat-composer">
          Câu hỏi
        </label>
        <textarea
          id="chat-composer"
          ref={textareaRef}
          value={value}
          rows={1}
          placeholder="Hỏi về hồ sơ, điểm số, mục tiêu…"
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={onKeyDown}
          disabled={isStreaming}
        />
        {isStreaming ? (
          <button
            type="button"
            className="send-button"
            onClick={stopStreaming}
            aria-label="Dừng trả lời"
            title="Dừng trả lời"
          >
            <Square size={15} aria-hidden="true" />
          </button>
        ) : (
          <button
            type="button"
            className="send-button"
            onClick={submit}
            disabled={!value.trim()}
            aria-label="Gửi câu hỏi"
            title="Gửi"
          >
            <ArrowUp size={18} aria-hidden="true" />
          </button>
        )}
      </div>
      <p className="composer-hint">
        Enter để gửi · Shift+Enter để xuống dòng
      </p>
    </div>
  );
}
