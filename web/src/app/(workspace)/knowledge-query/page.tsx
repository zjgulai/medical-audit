"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

const ALLOWED_ALIAS_SEARCH_PARAMS = ["query", "source_collection"] as const;

function buildDocumentsAliasTarget(search: string): string {
  const source = new URLSearchParams(search);
  const target = new URLSearchParams();

  for (const name of ALLOWED_ALIAS_SEARCH_PARAMS) {
    for (const value of source.getAll(name)) {
      target.append(name, value);
    }
  }

  const serialized = target.toString();
  return serialized ? `/documents?${serialized}` : "/documents";
}

export default function KnowledgeQueryPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(buildDocumentsAliasTarget(window.location.search));
  }, [router]);

  return null;
}
