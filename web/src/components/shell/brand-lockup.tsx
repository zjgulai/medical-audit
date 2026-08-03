import { AUDIT_PLATFORM_NAME } from "@/lib/brand";

import { BrandLogo } from "./brand-logo";

type BrandLockupProps = {
  readonly className?: string;
  readonly compact?: boolean;
  readonly priority?: boolean;
  readonly subtitle?: string;
};

export function BrandLockup({
  className,
  compact = false,
  priority = false,
  subtitle
}: BrandLockupProps) {
  const logoSize = compact ? 28 : 30;

  return (
    <span
      className={`audit-brand-lockup ${compact ? "is-compact" : ""} ${className ?? ""}`}
      data-testid="audit-brand-lockup"
    >
      <span className="audit-brand-lockup-logo" aria-hidden="true">
        <BrandLogo priority={priority} height={logoSize} width={logoSize} />
      </span>
      <span className="audit-brand-lockup-copy">
        <span className="audit-brand-lockup-name">{AUDIT_PLATFORM_NAME}</span>
        {subtitle ? <span className="audit-brand-lockup-subtitle">{subtitle}</span> : null}
      </span>
    </span>
  );
}
