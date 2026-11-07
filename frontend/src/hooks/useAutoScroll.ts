import { useCallback, useEffect, useRef, useState } from "react";

const NEAR_BOTTOM_THRESHOLD = 120;

export function useAutoScroll(revision: string, conversationId: string) {
  const ref = useRef<HTMLDivElement>(null);
  const [isNearBottom, setIsNearBottom] = useState(true);

  const scrollToBottom = useCallback(() => {
    const element = ref.current;
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
  }, []);

  useEffect(() => {
    if (isNearBottom) {
      scrollToBottom();
    }
  }, [revision, isNearBottom, scrollToBottom]);

  useEffect(() => {
    setIsNearBottom(true);
    const frame = requestAnimationFrame(scrollToBottom);
    return () => cancelAnimationFrame(frame);
  }, [conversationId, scrollToBottom]);

  const handleScroll = useCallback(() => {
    const element = ref.current;
    if (!element) {
      return;
    }
    const distance =
      element.scrollHeight - element.scrollTop - element.clientHeight;
    setIsNearBottom(distance < NEAR_BOTTOM_THRESHOLD);
  }, []);

  return {
    ref,
    isNearBottom,
    handleScroll,
    scrollToBottom,
  };
}
