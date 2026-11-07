import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check, Copy } from "lucide-react";

interface CodeBlockProps {
  code: string;
  language?: string;
  children?: ReactNode;
}

type CopyState = "idle" | "copied" | "error";

function fallbackCopy(text: string): boolean {
  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(textarea);
    return copied;
  } catch {
    return false;
  }
}

export function CodeBlock({ code, language, children }: CodeBlockProps) {
  const [state, setState] = useState<CopyState>("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timer.current) {
        clearTimeout(timer.current);
      }
    };
  }, []);

  const scheduleReset = () => {
    if (timer.current) {
      clearTimeout(timer.current);
    }
    timer.current = setTimeout(() => setState("idle"), 1800);
  };

  const copy = async () => {
    let copied = false;
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(code);
        copied = true;
      } catch {
        copied = fallbackCopy(code);
      }
    } else {
      copied = fallbackCopy(code);
    }
    setState(copied ? "copied" : "error");
    scheduleReset();
  };

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span>{language ?? "code"}</span>
        <button
          type="button"
          className="copy-button"
          onClick={copy}
          aria-label="Sao chép mã"
        >
          {state === "copied" ? (
            <>
              <Check size={13} aria-hidden="true" /> Đã sao chép
            </>
          ) : state === "error" ? (
            "Không sao chép được"
          ) : (
            <>
              <Copy size={13} aria-hidden="true" /> Sao chép
            </>
          )}
        </button>
      </div>
      <pre>
        <code className={language ? `language-${language}` : undefined}>
          {children ?? code}
        </code>
      </pre>
    </div>
  );
}
