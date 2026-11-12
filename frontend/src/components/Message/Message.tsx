import { isValidElement, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import { useChatStore, type Message as ChatMessage } from "../../store/chatStore";
import { CodeBlock } from "./CodeBlock";
import { SuggestionList } from "./SuggestionList";
import { TopicList } from "./TopicList";

function textFromChildren(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }
  if (Array.isArray(node)) {
    return node.map(textFromChildren).join("");
  }
  if (isValidElement<{ children?: ReactNode }>(node)) {
    return textFromChildren(node.props.children);
  }
  return "";
}

const markdownComponents: Components = {
  pre: ({ children }) => <>{children}</>,
  code: ({ node: _node, className, children, ...props }) => {
    const language = /language-([\w-]+)/.exec(className ?? "")?.[1];
    if (language) {
      return (
        <CodeBlock
          code={textFromChildren(children).replace(/\n$/, "")}
          language={language}
        >
          {children}
        </CodeBlock>
      );
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
  a: ({ node: _node, children, ...props }) => (
    <a {...props} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

interface MessageProps {
  message: ChatMessage;
}

function sourceLabel(source: NonNullable<ChatMessage["sources"]>[number]): string {
  if (source.page != null) {
    return `${source.file}, trang ${source.page}`;
  }
  if (source.sheet != null) {
    if (source.row_start != null) {
      const end = source.row_end ?? source.row_start;
      return `${source.file}, sheet ${source.sheet}, dòng ${source.row_start}–${end}`;
    }
    return `${source.file}, sheet ${source.sheet}`;
  }
  if (source.heading) {
    return `${source.file}, ${source.heading}`;
  }
  return source.file;
}

export function Message({ message }: MessageProps) {
  const retryMessage = useChatStore((state) => state.retryMessage);
  const sendMessage = useChatStore((state) => state.sendMessage);
  const sendAction = useChatStore((state) => state.sendAction);
  const isStreaming = useChatStore((state) => state.isStreaming);

  if (message.role === "user") {
    return (
      <article className="message message-user">
        <div className="message-bubble">{message.content}</div>
      </article>
    );
  }

  const isWaiting = message.status === "streaming" && !message.content;

  return (
    <article className="message message-assistant">
      <div className="message-body">
        {isWaiting ? (
          <span className="message-meta" role="status">
            Đang soạn câu trả lời…
          </span>
        ) : (
          <>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={markdownComponents}
            >
              {message.content}
            </ReactMarkdown>
            {message.status === "streaming" && (
              <span className="streaming-cursor" aria-hidden="true" />
            )}
          </>
        )}

        {message.responseType === "suggest" && (
          <SuggestionList
            suggestions={message.suggestions ?? []}
            onSelect={(question) => void sendMessage(question)}
            disabled={isStreaming}
          />
        )}

        {message.responseType === "clarify" && (
          <>
            <TopicList
              topics={message.topics ?? []}
              onSelect={(topic) =>
                void sendAction("topic", { topic, label: topic })
              }
              disabled={isStreaming}
            />
            {(message.examples ?? []).length > 0 && (
              <ul className="example-list" aria-label="Câu hỏi mẫu">
                {(message.examples ?? []).map((example) => (
                  <li key={example}>{example}</li>
                ))}
              </ul>
            )}
          </>
        )}

        {(message.actions ?? []).length > 0 && (
          <div className="message-actions">
            {(message.actions ?? []).map((action) => (
              <button
                key={action.id}
                type="button"
                className="action-button"
                disabled={isStreaming}
                onClick={() =>
                  void sendAction(action.id, {
                    topic: action.topic,
                    label: action.label,
                  })
                }
              >
                {action.label}
              </button>
            ))}
          </div>
        )}

        {message.responseType === "answer" && (message.sources ?? []).length > 0 && (
          <ul className="source-list" aria-label="Nguồn tài liệu">
            {(message.sources ?? []).map((source, index) => (
              <li key={`${source.file}-${index}`}>{sourceLabel(source)}</li>
            ))}
          </ul>
        )}

        {message.responseType === "answer" &&
          (message.sources ?? []).length === 0 &&
          message.source && (
            <p className="source-list">Nguồn: {message.source}</p>
          )}
      </div>

      {message.status === "stopped" && (
        <p className="message-meta">Đã dừng trả lời.</p>
      )}

      {message.status === "interrupted" && (
        <div className="message-meta">
          <span>Phản hồi bị ngắt giữa chừng.</span>
          <button
            type="button"
            className="retry-button"
            onClick={() => void retryMessage(message.id)}
          >
            Thử lại
          </button>
        </div>
      )}

      {message.status === "error" && (
        <div className="message-error" role="alert">
          <span>{message.error ?? "Không thể nhận câu trả lời."}</span>
          <button
            type="button"
            className="retry-button"
            onClick={() => void retryMessage(message.id)}
          >
            Thử lại
          </button>
        </div>
      )}
    </article>
  );
}
