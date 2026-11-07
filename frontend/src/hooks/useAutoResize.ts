import { useEffect, type RefObject } from "react";

export function useAutoResize(
  ref: RefObject<HTMLTextAreaElement | null>,
  value: string,
  maxHeight = 200,
): void {
  useEffect(() => {
    const element = ref.current;
    if (!element) {
      return;
    }
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, maxHeight)}px`;
  }, [ref, value, maxHeight]);
}
