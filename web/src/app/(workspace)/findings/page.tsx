"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function FindingsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/medical-audit");
  }, [router]);

  return null;
}
