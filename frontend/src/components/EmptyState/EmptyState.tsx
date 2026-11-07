import { Sparkles } from "lucide-react";

import { useChatStore } from "../../store/chatStore";

const EXAMPLES = [
  "GPA hiện tại của bạn là bao nhiêu?",
  "Bạn đang học trường nào và chuyên ngành gì?",
  "Mục tiêu nghề nghiệp của bạn là gì?",
];

export function EmptyState() {
  const sendMessage = useChatStore((state) => state.sendMessage);
  const isStreaming = useChatStore((state) => state.isStreaming);

  return (
    <div className="empty-state">
      <div className="empty-card">
        <span className="empty-mark" aria-hidden="true">
          <Sparkles size={26} />
        </span>
        <h2 className="empty-title">Bạn muốn biết điều gì?</h2>
        <p className="empty-subtitle">
          Hỏi về hồ sơ học tập, kinh nghiệm, kỹ năng hoặc mục tiêu của Văn Phú
          Đức. Câu trả lời dựa trên tài liệu đã được cung cấp.
        </p>
        <div className="examples">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              className="example-prompt"
              onClick={() => void sendMessage(example)}
              disabled={isStreaming}
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
