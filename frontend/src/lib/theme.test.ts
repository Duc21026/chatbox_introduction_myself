import { beforeEach, describe, expect, it } from "vitest";

import {
  applyTheme,
  getStoredTheme,
  isThemeMode,
  persistTheme,
  resolveTheme,
} from "./theme";

describe("theme", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.style.colorScheme = "";
  });

  it("resolves system preference and explicit modes", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("falls back to system for missing or invalid stored values", () => {
    expect(getStoredTheme()).toBe("system");
    window.localStorage.setItem("chatbot.theme.v1", "purple");
    expect(getStoredTheme()).toBe("system");
    window.localStorage.setItem("chatbot.theme.v1", "dark");
    expect(getStoredTheme()).toBe("dark");
  });

  it("persists and applies the chosen mode", () => {
    persistTheme("light");
    expect(window.localStorage.getItem("chatbot.theme.v1")).toBe("light");

    expect(applyTheme("dark", false)).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
  });

  it("recognizes valid theme modes", () => {
    expect(isThemeMode("system")).toBe(true);
    expect(isThemeMode("light")).toBe(true);
    expect(isThemeMode("dark")).toBe(true);
    expect(isThemeMode("sepia")).toBe(false);
  });
});
