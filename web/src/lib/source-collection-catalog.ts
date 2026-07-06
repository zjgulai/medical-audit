import type {
  DocumentSourceCollectionCatalogItem,
  DocumentSourcePermissionItem,
  SourceCollection
} from "./api-types";
import type { DocumentCategoryStat, KnowledgeBaseCard } from "./portal-data";

export type SourceCollectionOption = {
  readonly value: SourceCollection;
  readonly label: string;
  readonly description: string;
  readonly scope: string;
  readonly queryable: boolean;
};

export type SourceCollectionGroup = {
  readonly title: string;
  readonly options: readonly SourceCollectionOption[];
};

export const DEFAULT_MEDICAL_SOURCE_COLLECTIONS: readonly SourceCollection[] = [
  "medical-insurance-laws",
  "medical-insurance-catalog"
];

export const FALLBACK_SOURCE_COLLECTION_GROUPS: readonly SourceCollectionGroup[] = [
  {
    title: "医保基金",
    options: [
      {
        value: "medical-insurance-laws",
        label: "法规政策",
        description: "医保、医疗、药品、基金监管相关法律政策。",
        scope: "公开知识库",
        queryable: true
      },
      {
        value: "supervision-rules-knowledge",
        label: "监管两库",
        description: "智能监管规则库、知识库和知识点明细。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "medical-insurance-catalog",
        label: "医保目录",
        description: "药品、诊疗项目、编码、支付范围和限制条件。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "risk-negative-list",
        label: "风险清单",
        description: "高风险负面清单、案例和风险线索。",
        scope: "系统知识库",
        queryable: true
      }
    ]
  },
  {
    title: "政策法规",
    options: [
      {
        value: "policy-general-policy",
        label: "综合政策",
        description: "跨部门综合政策、行政规范和通用制度。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "policy-finance-price-procurement",
        label: "财政价格采购",
        description: "财政、价格、收费、采购和招投标政策。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "policy-data-statistics-disclosure",
        label: "数据统计公开",
        description: "数据治理、统计调查、公开披露相关规定。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "policy-reform-pilot",
        label: "改革试点",
        description: "改革方案、试点任务和阶段性实施规则。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "policy-social-security-livelihood",
        label: "社保民生",
        description: "社会保障、民生服务和公共保障政策。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "policy-industry-business-environment",
        label: "产业营商",
        description: "产业监管、市场主体和营商环境政策。",
        scope: "系统知识库",
        queryable: true
      }
    ]
  },
  {
    title: "行业管理",
    options: [
      {
        value: "management-org-personnel-qualification",
        label: "机构人员资质",
        description: "机构设置、人员管理、执业资格和资质审批。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "management-market-quality",
        label: "市场质量监管",
        description: "市场秩序、质量监管、标准认证和消费者保护。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "management-license-enforcement",
        label: "许可执法",
        description: "行政许可、监管执法、处罚程序和监督检查。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "management-safety-emergency",
        label: "安全应急",
        description: "安全生产、应急管理、灾害防控和事故处置。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "management-judicial-audit-procedure",
        label: "司法审计程序",
        description: "司法、审计、监督程序和案件办理规则。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "management-ecology-resources",
        label: "生态资源",
        description: "生态环境、自然资源、能源和资源保护管理。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "management-urban-municipal",
        label: "城市市政",
        description: "城市建设、市政设施、住房城乡建设和基层治理。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "management-general-admin",
        label: "综合行政",
        description: "行政管理、机关运行、公共事务和通用管理规则。",
        scope: "系统知识库",
        queryable: true
      }
    ]
  },
  {
    title: "其他专题",
    options: [
      {
        value: "other-agriculture-water",
        label: "农业水利",
        description: "农业农村、水利治理、乡村建设和涉农管理。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "other-culture-tourism-sports",
        label: "文旅体育",
        description: "文化、旅游、广播电视、体育和公共文化服务。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "other-defense-confidentiality",
        label: "国防保密",
        description: "国防动员、保密管理和涉密监督要求。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "other-education-research",
        label: "教育科研",
        description: "教育、科研、学术管理和科技创新政策。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "other-ethnic-religious-foreign",
        label: "民族宗教外事",
        description: "民族、宗教、外事、侨务和对外交流管理。",
        scope: "系统知识库",
        queryable: true
      },
      {
        value: "other-transport-maritime",
        label: "交通海事",
        description: "交通运输、港航海事、道路水路和运输监管。",
        scope: "系统知识库",
        queryable: true
      }
    ]
  },
  {
    title: "个人材料",
    options: [
      {
        value: "personal-materials",
        label: "个人上传材料",
        description: "仅在显式选择并具备权限时参与检索。",
        scope: "个人知识库",
        queryable: true
      }
    ]
  }
];

const SOURCE_COLLECTION_VALUES = new Set<SourceCollection>(
  FALLBACK_SOURCE_COLLECTION_GROUPS.flatMap((group) => group.options.map((option) => option.value))
);
const GROUP_ORDER = ["medical", "policy", "management", "other", "personal"] as const;
const GROUP_TITLE_BY_DOMAIN: Record<string, string> = {
  medical: "医保基金",
  policy: "政策法规",
  management: "行业管理",
  other: "其他专题",
  personal: "个人材料"
};

export function isSourceCollectionValue(value: string): value is SourceCollection {
  return SOURCE_COLLECTION_VALUES.has(value as SourceCollection);
}

export function sourceCollectionCatalogToGroups(
  items: readonly DocumentSourceCollectionCatalogItem[] | null | undefined
): readonly SourceCollectionGroup[] {
  if (!items || items.length === 0) {
    return FALLBACK_SOURCE_COLLECTION_GROUPS;
  }

  const grouped = new Map<string, SourceCollectionOption[]>();
  for (const item of items) {
    if (!isCatalogItemSelectable(item)) {
      continue;
    }
    const domain = GROUP_TITLE_BY_DOMAIN[item.domain] ? item.domain : "other";
    const options = grouped.get(domain) ?? [];
    options.push({
      value: item.source_collection,
      label: item.label,
      description: item.description,
      scope: item.scope,
      queryable: item.queryable
    });
    grouped.set(domain, options);
  }

  const groups = GROUP_ORDER.flatMap((domain) => {
    const options = grouped.get(domain);
    if (!options || options.length === 0) {
      return [];
    }
    return [{ title: GROUP_TITLE_BY_DOMAIN[domain], options }];
  });
  return groups.length > 0 ? groups : FALLBACK_SOURCE_COLLECTION_GROUPS;
}

export function sourceCollectionCatalogToDocumentCategories(
  items: readonly DocumentSourceCollectionCatalogItem[] | null | undefined,
  fallbackCategories: readonly DocumentCategoryStat[]
): readonly DocumentCategoryStat[] {
  if (!items || items.length === 0) {
    return fallbackCategories;
  }

  const fallbackBySource = new Map(
    fallbackCategories.map((category) => [category.sourceCollection, category])
  );
  const categories = items.filter(isCatalogItemSelectable).map((item) => {
    const fallback = fallbackBySource.get(item.source_collection);
    return {
      id: fallback?.id ?? `doc-cat-${item.source_collection}`,
      name: item.label,
      scope: normalizeKnowledgeBaseScope(item.scope),
      sourceCollection: item.source_collection,
      documentCount:
        item.metrics.document_count ??
        item.metrics.chunk_count ??
        fallback?.documentCount ??
        0,
      description: item.description
    };
  });
  return categories.length > 0 ? categories : fallbackCategories;
}

export function readableSourceCollectionsFromCatalog(
  items: readonly DocumentSourceCollectionCatalogItem[] | null | undefined,
  fallbackPermissions: readonly DocumentSourcePermissionItem[] | null | undefined,
  fallbackSources: readonly SourceCollection[]
): ReadonlySet<SourceCollection> {
  if (items && items.length > 0) {
    return new Set(
      items
        .filter(isCatalogItemSelectable)
        .map((item) => item.source_collection)
    );
  }
  if (fallbackPermissions && fallbackPermissions.length > 0) {
    return new Set(
      fallbackPermissions
        .filter((item) => item.access === "read" || item.access.startsWith("explicit-"))
        .map((item) => item.source_collection)
    );
  }
  return new Set(fallbackSources);
}

export function selectedSourceCollectionLabel(
  selectedCollections: readonly SourceCollection[],
  categories: readonly DocumentCategoryStat[]
): string {
  if (selectedCollections.length === 0) {
    return "全部来源";
  }
  const labels = categories
    .filter((category) => selectedCollections.includes(category.sourceCollection as SourceCollection))
    .map((category) => category.name);
  return labels.length > 0 ? labels.join("、") : selectedCollections.join("、");
}

function isCatalogItemSelectable(item: DocumentSourceCollectionCatalogItem): boolean {
  return item.product_queryable && isReadableAccess(item.access);
}

function isReadableAccess(access: DocumentSourcePermissionItem["access"]): boolean {
  return access === "read" || access === "explicit-owner-read" || access === "explicit-read-all";
}

function normalizeKnowledgeBaseScope(scope: string): KnowledgeBaseCard["scope"] {
  if (scope.includes("个人")) {
    return "个人知识库";
  }
  if (scope.includes("公开")) {
    return "公开知识库";
  }
  return "系统知识库";
}
