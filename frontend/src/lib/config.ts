const DEFAULT_API_BASE_URL = "http://127.0.0.1:5000";

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (!configured || !configured.trim()) {
    return DEFAULT_API_BASE_URL;
  }

  try {
    const url = new URL(configured.trim());
    return url.toString().replace(/\/$/, "");
  } catch {
    console.warn("VITE_API_BASE_URL không hợp lệ; dùng địa chỉ mặc định.");
    return DEFAULT_API_BASE_URL;
  }
}
