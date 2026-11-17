import { afterEach, describe, expect, it, vi } from "vitest";

import { checkHealth } from "./health";

const HEALTH = {
  status: "ok",
  vectors_loaded: true,
  vector_count: 12,
  model: "@cf/baai/bge-m3",
  dim: 1024,
  normalizer_version: "2",
  source_hash_matches: true,
  embedding_provider: "cloudflare",
  provider_ready: true,
  message: "Sẵn sàng",
};

describe("checkHealth", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("parses a healthy response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => HEALTH }),
    );

    const result = await checkHealth("/api");
    expect(result?.status).toBe("ok");
    expect(result?.vector_count).toBe(12);
    expect(fetch).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("returns null for an unhealthy HTTP response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }));
    expect(await checkHealth("/api")).toBeNull();
  });

  it("returns null on network errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    expect(await checkHealth("/api")).toBeNull();
  });
});
