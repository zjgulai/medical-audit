"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

function buildDocumentsAliasTarget(search: string): string {
  const source = new URLSearchParams(search);
  const target = new URLSearchParams();
  const query = source.get("query") ?? source.get("q");

  if (query !== null) {
    target.set("query", query);
  }
  for (const value of source.getAll("source_collection")) {
    target.append("source_collection", value);
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
