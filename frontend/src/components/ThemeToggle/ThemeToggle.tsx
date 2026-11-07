import { Monitor, Moon, Sun } from "lucide-react";

import { useChatStore } from "../../store/chatStore";
import type { ThemeMode } from "../../lib/theme";

const MODES: ThemeMode[] = ["system", "light", "dark"];
const LABELS: Record<ThemeMode, string> = {
  system: "Theo hệ thống",
  light: "Sáng",
  dark: "Tối",
};

export function ThemeToggle() {
  const themeMode = useChatStore((state) => state.themeMode);
  const setThemeMode = useChatStore((state) => state.setThemeMode);

  const nextMode = MODES[(MODES.indexOf(themeMode) + 1) % MODES.length];
  const Icon =
    themeMode === "light" ? Sun : themeMode === "dark" ? Moon : Monitor;

  return (
    <button
      type="button"
      className="icon-button"
      onClick={() => setThemeMode(nextMode)}
      aria-label={`Giao diện: ${LABELS[themeMode]}. Nhấn để chuyển sang ${LABELS[nextMode]}.`}
      title={`Giao diện: ${LABELS[themeMode]}`}
    >
      <Icon size={18} aria-hidden="true" />
    </button>
  );
}
