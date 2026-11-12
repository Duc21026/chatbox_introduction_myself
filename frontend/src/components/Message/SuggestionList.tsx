import type { Suggestion } from "../../lib/chatTypes";

interface SuggestionListProps {
  suggestions: Suggestion[];
  onSelect: (question: string) => void;
  disabled?: boolean;
}

export function SuggestionList({
  suggestions,
  onSelect,
  disabled = false,
}: SuggestionListProps) {
  if (suggestions.length === 0) {
    return null;
  }
  return (
    <ul className="suggestion-list" aria-label="Câu hỏi gợi ý">
      {suggestions.map((suggestion) => (
        <li key={suggestion.id}>
          <button
            type="button"
            className="suggestion-button"
            disabled={disabled}
            onClick={() => onSelect(suggestion.question)}
          >
            <span className="suggestion-question">{suggestion.question}</span>
            <span className="suggestion-score">
              {Math.round(suggestion.score * 100)}%
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
