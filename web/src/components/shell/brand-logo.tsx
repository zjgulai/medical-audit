"use client";

import Image from "next/image";
import { useState } from "react";

type BrandLogoProps = {
  readonly className?: string;
  readonly height?: number;
  readonly priority?: boolean;
  readonly testId?: string;
  readonly width?: number;
};

export function BrandLogo({
  className,
  height = 28,
  priority = false,
  testId = "auditscope-brand-logo",
  width = 28
}: BrandLogoProps) {
  const [imageFailed, setImageFailed] = useState(false);

  if (imageFailed) {
    return (
      <span
        aria-hidden="true"
        className={`inline-flex items-center justify-center rounded-[var(--audit-radius-sm)] bg-[var(--audit-surface-subtle)] text-[11px] font-semibold text-[var(--audit-primary)] ${className ?? ""}`}
        data-testid={testId}
        style={{ height, width }}
      >
        AI
      </span>
    );
  }

  return (
    <Image
      alt=""
      className={className}
      data-testid={testId}
      height={height}
      onError={() => setImageFailed(true)}
      priority={priority}
      src="/brand/auditscope-logo.png"
      unoptimized
      width={width}
    />
  );
}
