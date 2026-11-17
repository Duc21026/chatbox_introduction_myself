const DEFAULT_LOCAL_API_BASE_URL = "http://127.0.0.1:5000";
const DEFAULT_DEPLOYED_API_BASE_URL = "/api";

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (!configured || !configured.trim()) {
    return import.meta.env.PROD
      ? DEFAULT_DEPLOYED_API_BASE_URL
      : DEFAULT_LOCAL_API_BASE_URL;
  }

  const value = configured.trim();
  if (value.startsWith("/")) {
    const trimmed = value.replace(/\/+$/, "");
    return trimmed;
  }

  try {
    const url = new URL(value);
    return url.toString().replace(/\/$/, "");
  } catch {
    console.warn("VITE_API_BASE_URL không hợp lệ; dùng địa chỉ mặc định.");
    return import.meta.env.PROD
      ? DEFAULT_DEPLOYED_API_BASE_URL
      : DEFAULT_LOCAL_API_BASE_URL;
  }
}
