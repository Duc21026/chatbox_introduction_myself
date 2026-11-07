import { isValidElement, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import { useChatStore, type Message as ChatMessage } from "../../store/chatStore";
import { CodeBlock } from "./CodeBlock";

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

export function Message({ message }: MessageProps) {
  const retryMessage = useChatStore((state) => state.retryMessage);

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
