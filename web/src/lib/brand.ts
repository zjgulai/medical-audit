export const AUDIT_PLATFORM_NAME = "AI审计一体化协作平台";
export const AUDIT_PLATFORM_SUBTITLE = "医保基金合规审计";
export const AUDIT_PLATFORM_DESCRIPTION = "面向医院内审人员的医保基金审计、依据检索、表格分析和底稿工作区";

const DEFAULT_ORG_NAME = "医院名称待配置";

export const AUDIT_ORGANIZATION_NAME =
  process.env.NEXT_PUBLIC_AUDIT_ORG_NAME?.trim() || DEFAULT_ORG_NAME;

export const AUDIT_ORGANIZATION_LOGO =
  process.env.NEXT_PUBLIC_AUDIT_ORG_LOGO?.trim() || "";

export const HAS_CONFIGURED_ORGANIZATION =
  AUDIT_ORGANIZATION_NAME !== DEFAULT_ORG_NAME || AUDIT_ORGANIZATION_LOGO.length > 0;
