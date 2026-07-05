import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { backendApiEndpoints } from "./api-endpoints";
import type { QueryRequest, QueryResponse, SourceCollection } from "./api-types";

type KnowledgeQueryContract = {
  readonly source_collections: {
    readonly allowed: readonly SourceCollection[];
  };
  readonly endpoints: {
    readonly post_query: {
      readonly frontend_proxy_path: string;
      readonly request: {
        readonly required: readonly (keyof QueryRequest)[];
        readonly fields: Record<string, unknown>;
      };
      readonly response: {
        readonly required: readonly (keyof QueryResponse)[];
      };
      readonly error_contract: readonly {
        readonly status: number;
        readonly frontend_code: string;
      }[];
    };
    readonly get_query_logs: {
      readonly frontend_proxy_path: string;
      readonly query_parameters: {
        readonly limit: {
          readonly frontend_default: number;
        };
      };
    };
  };
};

function loadContract(): KnowledgeQueryContract {
  const raw = readFileSync(
    resolve(process.cwd(), "../docs/api/knowledge-query-contract-v1.json"),
    "utf8"
  );
  return JSON.parse(raw) as KnowledgeQueryContract;
}

const frontendSourceCollections = [
  "medical-insurance-catalog",
  "medical-insurance-laws",
  "personal-materials",
  "risk-negative-list",
  "supervision-rules-knowledge"
] satisfies readonly SourceCollection[];

const sampleRequest = {
  question: "fund audit evidence",
  top_k: 5,
  source_collections: ["medical-insurance-laws"],
  years: [2024],
  regions: ["national"],
  document_types: ["law"],
  business_topics: ["fund-supervision"],
  topic: "medical-insurance-fund",
  title_only: false,
  agent: null
} satisfies QueryRequest;

const sampleResponse = {
  question: "fund audit evidence",
  answer: "Cited answer [C1].",
  confidence: "high",
  fallback_used: true,
  effective_source_collections: ["medical-insurance-laws"],
  basis_groups: [
    {
      evidence_type: "legal_basis",
      title: "Legal basis",
      items: [
        {
          citation_id: "C1",
          chunk_id: "11111111-1111-4111-8111-111111111111",
          source_collection: "medical-insurance-laws",
          snippet: "Evidence snippet.",
          locator: { source_path: "laws/example.md", line_start: 1, line_end: 2 },
          index_version_key: "index-v1",
          source_package_version_key: "package-v1"
        }
      ]
    }
  ],
  citations: [
    {
      citation_id: "C1",
      marker: "[C1]",
      chunk_id: "11111111-1111-4111-8111-111111111111",
      evidence_type: "legal_basis",
      source_collection: "medical-insurance-laws",
      snippet: "Evidence snippet.",
      locator: { source_path: "laws/example.md", line_start: 1, line_end: 2 },
      index_version_key: "index-v1",
      source_package_version_key: "package-v1"
    }
  ],
  personal_upload_matches: [],
  query_log_index: 0,
  query_log_id: null,
  agent_invocation_id: null
} satisfies QueryResponse;

describe("knowledge query contract freeze", () => {
  it("keeps frontend proxy paths aligned with the frozen contract", () => {
    const contract = loadContract();

    expect(contract.endpoints.post_query.frontend_proxy_path).toBe(backendApiEndpoints.query);
    expect(contract.endpoints.get_query_logs.frontend_proxy_path).toBe("/api/v1/query/logs");
    expect(contract.endpoints.get_query_logs.query_parameters.limit.frontend_default).toBe(8);
    expect(backendApiEndpoints.queryLogs()).toBe("/api/v1/query/logs?limit=8");
  });

  it("keeps source collections and request fields aligned with frontend types", () => {
    const contract = loadContract();

    expect([...contract.source_collections.allowed].sort()).toEqual(
      [...frontendSourceCollections].sort()
    );
    expect(contract.endpoints.post_query.request.required).toEqual(["question"]);
    for (const field of Object.keys(sampleRequest)) {
      expect(field in contract.endpoints.post_query.request.fields).toBe(true);
    }
  });

  it("keeps required response fields and typed query states stable", () => {
    const contract = loadContract();

    for (const field of contract.endpoints.post_query.response.required) {
      expect(field in sampleResponse).toBe(true);
    }
    expect(
      contract.endpoints.post_query.error_contract.map(({ status, frontend_code }) => ({
        status,
        frontend_code
      }))
    ).toEqual([
      { status: 400, frontend_code: "unknown-topic" },
      { status: 403, frontend_code: "source-collection-denied" },
      { status: 404, frontend_code: "no-cited-evidence" },
      { status: 409, frontend_code: "search-engine-not-initialized" }
    ]);
  });
});
