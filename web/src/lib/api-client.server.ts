const DEFAULT_SERVER_BACKEND_BASE_URL = "http://127.0.0.1:8021";

export function resolveServerBackendBaseUrl(
  value = process.env.MEDICAL_AUDIT_API_BASE_URL
): string {
  const candidate = (value?.trim() || DEFAULT_SERVER_BACKEND_BASE_URL).replace(/\/+$/, "");
  let parsed: URL;

  try {
    parsed = new URL(candidate);
  } catch (error) {
    throw new Error("MEDICAL_AUDIT_API_BASE_URL must be a valid URL.", { cause: error });
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("MEDICAL_AUDIT_API_BASE_URL must use http or https.");
  }

  return candidate;
}

export function toServerBackendUrl(
  path: string,
  backendBaseUrl = resolveServerBackendBaseUrl()
): string {
  if (!path.startsWith("/")) {
    throw new Error("Backend API path must start with '/'.");
  }
  return `${backendBaseUrl}${path}`;
}

export async function serverGetJson<T>(
  path: string,
  init: RequestInit = {},
  backendBaseUrl = resolveServerBackendBaseUrl()
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  const response = await fetch(toServerBackendUrl(path, backendBaseUrl), {
    ...init,
    headers,
    cache: init.cache ?? "no-store"
  });

  if (!response.ok) {
    throw new Error(`Backend request failed: GET ${path} returned ${response.status}`);
  }

  return (await response.json()) as T;
}
