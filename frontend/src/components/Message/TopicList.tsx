interface TopicListProps {
  topics: string[];
  onSelect: (topic: string) => void;
  disabled?: boolean;
}

export function TopicList({ topics, onSelect, disabled = false }: TopicListProps) {
  if (topics.length === 0) {
    return null;
  }
  return (
    <ul className="topic-list" aria-label="Chọn chủ đề">
      {topics.map((topic) => (
        <li key={topic}>
          <button
            type="button"
            className="topic-chip"
            disabled={disabled}
            onClick={() => onSelect(topic)}
          >
            {topic}
          </button>
        </li>
      ))}
    </ul>
  );
}
