import { afterEach, describe, expect, it, vi } from "vitest";

import { getApiBaseUrl } from "./config";

describe("getApiBaseUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("uses the local backend by default in tests", () => {
    expect(getApiBaseUrl()).toBe("http://127.0.0.1:5000");
  });

  it("accepts the relative deployed prefix", () => {
    vi.stubEnv("VITE_API_BASE_URL", "/api");
    expect(getApiBaseUrl()).toBe("/api");
  });

  it("strips a trailing slash from absolute URLs", () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://example.com/api/");
    expect(getApiBaseUrl()).toBe("https://example.com/api");
  });

  it("falls back when the configured value is invalid", () => {
    vi.stubEnv("VITE_API_BASE_URL", "not a url");
    expect(getApiBaseUrl()).toBe("http://127.0.0.1:5000");
  });
});
