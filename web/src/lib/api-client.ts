import type {
  BackendHealthResponse,
  QueryRequest,
  QueryResponse,
  SearchBackendStatusResponse
} from "./api-types";

function assertBackendProxyClientRuntime(): void {
  if (typeof window === "undefined") {
    throw new Error(
      "Backend proxy client must be called from browser/client code; server code needs an absolute backend URL."
    );
  }
}

async function getJson<T>(path: string): Promise<T> {
  assertBackendProxyClientRuntime();

  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Backend request failed: GET ${path} returned ${response.status}`);
  }

  return (await response.json()) as T;
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  assertBackendProxyClientRuntime();

  const response = await fetch(path, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Role": "auditor",
      "X-User-Id": "next-knowledge-query"
    },
    body: JSON.stringify(payload),
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Backend request failed: POST ${path} returned ${response.status}`);
  }

  return (await response.json()) as T;
}

export function fetchBackendHealth(): Promise<BackendHealthResponse> {
  return getJson<BackendHealthResponse>("/api/backend/health");
}

export function fetchSearchBackendStatus(): Promise<SearchBackendStatusResponse> {
  return getJson<SearchBackendStatusResponse>("/api/backend/index/search-backend");
}

export function runKnowledgeQuery(payload: QueryRequest): Promise<QueryResponse> {
  return postJson<QueryResponse>("/api/v1/query", payload);
}
