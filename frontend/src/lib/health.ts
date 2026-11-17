import { getApiBaseUrl } from "./config";

export interface HealthStatus {
  status: "ok" | "degraded";
  vectors_loaded: boolean;
  vector_count: number;
  model: string | null;
  dim: number;
  normalizer_version: string | null;
  source_hash_matches: boolean;
  embedding_provider: string;
  provider_ready: boolean;
  message: string;
}

function parseHealth(payload: unknown): HealthStatus | null {
  if (payload === null || typeof payload !== "object") return null;
  const value = payload as Record<string, unknown>;
  if (value.status !== "ok" && value.status !== "degraded") return null;
  return {
    status: value.status,
    vectors_loaded: Boolean(value.vectors_loaded),
    vector_count: Number(value.vector_count) || 0,
    model: typeof value.model === "string" ? value.model : null,
    dim: Number(value.dim) || 0,
    normalizer_version:
      typeof value.normalizer_version === "string"
        ? value.normalizer_version
        : null,
    source_hash_matches: Boolean(value.source_hash_matches),
    embedding_provider:
      typeof value.embedding_provider === "string"
        ? value.embedding_provider
        : "none",
    provider_ready: Boolean(value.provider_ready),
    message: typeof value.message === "string" ? value.message : "",
  };
}

export async function checkHealth(
  baseUrl = getApiBaseUrl(),
  timeoutMs = 5000,
): Promise<HealthStatus | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${baseUrl}/health`, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) return null;
    return parseHealth(await response.json());
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
