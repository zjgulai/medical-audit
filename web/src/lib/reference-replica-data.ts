import { medicalAuditAgentCatalog } from "./audit-agent-catalog";

export type ReferenceNavigationItem = {
  readonly id: string;
  readonly label: string;
  readonly href: string;
  readonly icon: string;
};

export type ReferenceHistoryItem = {
  readonly id: string;
  readonly title: string;
  readonly topic?: string;
  readonly agentName?: string;
  readonly summary?: string;
  readonly messages?: readonly ReferenceHistoryMessage[];
  readonly taskConvertible?: boolean;
};

export type ReferenceHistoryMessage = {
  readonly id: string;
  readonly role: "user" | "assistant";
  readonly text: string;
};

export type ReferenceAgentCategory = string;

export type ReferenceAgentCard = {
  readonly id: string;
  readonly name: string;
  readonly category: ReferenceAgentCategory;
  readonly summary: string;
  readonly project: string;
  readonly topic: string;
  readonly initial: string;
  readonly tone: "blue" | "cyan" | "rose" | "amber" | "slate";
  readonly prompt?: string;
  readonly sourceFile?: string;
  readonly avatarSeed?: string;
  readonly templateKey?: string;
  readonly catalogScope?: "medical-default" | "extension-validation";
};

export type ReferenceKnowledgeBase = {
  readonly id: string;
  readonly name: string;
  readonly scope: "个人知识库" | "公开知识库" | "系统知识库" | "项目知识库";
  readonly owner: string;
  readonly documentCount: number;
  readonly chunkCount?: number | null;
  readonly appCount: number;
  readonly updatedAt: string;
  readonly description: string;
  readonly tags: readonly string[];
};

export type ReferenceDocumentCategory = {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly count: number;
};

export type ReferenceDocumentResult = {
  readonly id: string;
  readonly title: string;
  readonly category: string;
  readonly excerpt: string;
  readonly source: string;
  readonly updatedAt: string;
};

export type ReferenceAnalysisDataset = {
  readonly id: string;
  readonly name: string;
  readonly rows: number;
  readonly columns: number;
  readonly status: string;
  readonly insight: string;
};

export type ReferenceGraphNode = {
  readonly id: string;
  readonly label: string;
  readonly kind: string;
  readonly metric: string;
  readonly status: string;
  readonly description?: string;
  readonly href?: string;
  readonly sourceCollection?: string;
  readonly domain?: string;
  readonly x?: number;
  readonly y?: number;
};

export type ReferenceGraphRelation = {
  readonly id: string;
  readonly sourceId?: string;
  readonly targetId?: string;
  readonly source: string;
  readonly relation: string;
  readonly target: string;
  readonly evidence: string;
  readonly strength: "强" | "中" | "待补";
};

export type ReferenceReportRecord = {
  readonly id: string;
  readonly title: string;
  readonly project: string;
  readonly status: string;
  readonly generatedAt: string;
  readonly sourceCount: number;
};

export type ReferenceProject = {
  readonly id: string;
  readonly name: string;
  readonly type: string;
  readonly owner: string;
  readonly members: number | null;
  readonly status: string;
  readonly updatedAt: string;
  readonly progress: number;
};

export const referenceNavigation: readonly ReferenceNavigationItem[] = [
  { id: "chat", label: "AI 对话", href: "/chat", icon: "chat" },
  { id: "assistant", label: "我的智能体", href: "/agents", icon: "agent" },
  { id: "agent-market", label: "智能体广场", href: "/agent-market", icon: "grid" },
  { id: "knowledge", label: "知识库", href: "/knowledge-base", icon: "book" },
  { id: "documents", label: "文档检索", href: "/documents", icon: "scan" },
  { id: "analysis", label: "AI数据分析", href: "/analytics", icon: "ai" },
  { id: "graph", label: "知识图谱", href: "/graph", icon: "graph" },
  { id: "workpaper", label: "审计底稿/报告", href: "/reports", icon: "paper" },
  { id: "project", label: "项目管理", href: "/projects", icon: "folder" }
];

export const referenceTopicNavigation: ReferenceNavigationItem = {
  id: "medical-topic",
  label: "医保审计专题",
  href: "/medical-audit",
  icon: "shield"
};

export const referenceHistoryItems: readonly ReferenceHistoryItem[] = [
  {
    id: "history-1",
    title: "中标候选人名单表",
    topic: "招投标流程复核",
    agentName: "政策依据速查助手",
    summary: "已定位候选人排序、定标记录和招标人决策链，下一步核验是否超出推荐范围定标。",
    messages: [
      {
        id: "history-1-user",
        role: "user",
        text: "请核验中标候选人名单表是否支持定标结论。"
      },
      {
        id: "history-1-assistant",
        role: "assistant",
        text: "本地历史记录：已标出候选人排序、定标人和定标时间，建议补充评标报告原件后再形成问题定性。"
      }
    ]
  },
  {
    id: "history-2",
    title: "小金库定性分析",
    topic: "资金合规",
    agentName: "资金线索核验助手",
    summary: "围绕账外收入、私设账户和支出票据完整性形成待补证清单。",
    messages: [
      {
        id: "history-2-user",
        role: "user",
        text: "这些收入没有纳入单位账簿，是否可以定性为小金库？"
      },
      {
        id: "history-2-assistant",
        role: "assistant",
        text: "本地历史记录：需先确认资金来源、保管方式、审批链和支出用途，再引用财经纪律依据。"
      }
    ]
  },
  {
    id: "history-3",
    title: "篡改日期疑问",
    topic: "证据链核验",
    agentName: "底稿证据助手",
    summary: "对比合同、发票、付款和系统日志时间，标记日期倒挂和补录风险。",
    messages: [
      {
        id: "history-3-user",
        role: "user",
        text: "这组单据日期前后不一致，如何判断是否存在篡改？"
      },
      {
        id: "history-3-assistant",
        role: "assistant",
        text: "本地历史记录：优先调取原始系统日志和审批流，避免只凭扫描件日期下结论。"
      }
    ]
  },
  {
    id: "history-4",
    title: "外定中标人",
    topic: "招投标流程复核",
    agentName: "招投标核验助手",
    summary: "聚焦评标委员会推荐名单之外定标的流程风险。",
    messages: [
      {
        id: "history-4-user",
        role: "user",
        text: "招标人是否可以在推荐候选人之外确定中标人？"
      },
      {
        id: "history-4-assistant",
        role: "assistant",
        text: "本地历史记录：需核对招标文件、评标报告、定标会议纪要和异议处理记录。"
      }
    ]
  },
  { id: "history-5", title: "不合格放贷", topic: "金融审计", agentName: "贷款合规助手" },
  { id: "history-6", title: "候选人外定标", topic: "财政审计", agentName: "招投标核验助手" },
  { id: "history-7", title: "银行放贷复核", topic: "金融审计", agentName: "贷款合规助手" },
  { id: "history-8", title: "评委会流程查询", topic: "财政审计", agentName: "招投标核验助手" },
  { id: "history-9", title: "招标违法分析", topic: "财政审计", agentName: "政策依据速查助手" },
  { id: "history-10", title: "会议纪要生成", topic: "办公效率", agentName: "会议纪要助手" }
];

export const referenceAgents: readonly ReferenceAgentCard[] = [
  {
    id: "mock-audit-data",
    name: "模拟数据助手",
    category: "研究类",
    summary: "生成一些模拟数据和文件，帮助审计人员进行案例教学，要求数据真实且存在勾稽关系。",
    project: "未关联项目",
    topic: "乡村振兴审计",
    initial: "生",
    tone: "rose"
  },
  {
    id: "toilet-maintenance",
    name: "厕所管护核验",
    category: "业务类",
    summary: "识别未建立管护机制、厕具损坏无法维修、公厕未定期清扫等常见表现形式。",
    project: "未关联项目",
    topic: "其他",
    initial: "厕",
    tone: "blue"
  },
  {
    id: "bidder-illegal-v2",
    name: "定标合规核验",
    category: "业务类",
    summary: "核验招标人在评标委员会依法推荐的中标候选人以外确定中标人的情形。",
    project: "未关联项目",
    topic: "财政审计",
    initial: "中标",
    tone: "rose"
  },
  {
    id: "black-soil",
    name: "黑土保护核验",
    category: "业务类",
    summary: "检查黑土地保护协调机制、调查档案、保护规划和常态化监测要求。",
    project: "未关联项目",
    topic: "农业农村审计",
    initial: "黑",
    tone: "slate"
  },
  {
    id: "board-extract",
    name: "会议要素提取",
    category: "效率类",
    summary: "从会议纪要中提取会议、人员、议题、结果、合同事项等结构化要素。",
    project: "佳木斯市林业局",
    topic: "乡村振兴审计",
    initial: "董",
    tone: "amber"
  },
  {
    id: "dupont",
    name: "杜邦财务分析",
    category: "业务类",
    summary: "快速对财务报表进行杜邦分析，识别盈利能力、周转效率和杠杆异常。",
    project: "未关联项目",
    topic: "国有企业审计",
    initial: "企",
    tone: "cyan"
  },
  {
    id: "medical-insurance-policy",
    name: "医保政策核验",
    category: "业务类",
    summary: "核验城乡居民医疗保险报销政策执行不到位、大病保险比例不达标等问题。",
    project: "未关联项目",
    topic: "社会保障审计",
    initial: "医",
    tone: "blue"
  },
  {
    id: "meeting-over-standard",
    name: "会议标准核验",
    category: "业务类",
    summary: "核验超标准、超预算、超人数、超天数、超范围举办会议等问题。",
    project: "未关联项目",
    topic: "部门预算执行审计",
    initial: "会",
    tone: "amber"
  }
];

export const referenceMarketAgents: readonly ReferenceAgentCard[] = medicalAuditAgentCatalog;

export const referenceKnowledgeBases: readonly ReferenceKnowledgeBase[] = [
  {
    id: "kb-personal",
    name: "审计员个人知识库",
    scope: "个人知识库",
    owner: "审计员",
    documentCount: 28,
    appCount: 3,
    updatedAt: "2026-07-03",
    description: "沉淀个人上传的审计材料、访谈纪要、问题草稿和常用提示词。",
    tags: ["个人材料", "工作草稿", "仅本人"]
  },
  {
    id: "kb-public-policy",
    name: "法律法规库",
    scope: "公开知识库",
    owner: "系统",
    documentCount: 1362,
    appCount: 18,
    updatedAt: "2026-07-01",
    description: "集中收录法律、行政法规、部门规章和审计定性常用依据。",
    tags: ["法律法规", "政策依据", "可引用"]
  },
  {
    id: "kb-system-medical-fund",
    name: "医保基金合规知识库",
    scope: "系统知识库",
    owner: "系统",
    documentCount: 32449,
    appCount: 9,
    updatedAt: "2026-07-04",
    description: "汇集法规政策、监管两库、医保目录和风险清单，用于医保基金使用合规审计。",
    tags: ["医保目录", "监管两库", "风险清单"]
  },
  {
    id: "kb-system-audit",
    name: "审计案例库",
    scope: "系统知识库",
    owner: "系统",
    documentCount: 842,
    appCount: 12,
    updatedAt: "2026-06-30",
    description: "按审计主题沉淀常见问题表现、定性依据和处理处罚口径。",
    tags: ["案例", "问题定性", "审计经验"]
  },
  {
    id: "kb-project-village",
    name: "乡村振兴项目知识库",
    scope: "项目知识库",
    owner: "项目组",
    documentCount: 156,
    appCount: 7,
    updatedAt: "2026-06-28",
    description: "项目级材料、专项政策、资金拨付台账和现场核查记录。",
    tags: ["项目材料", "乡村振兴", "专项审计"]
  }
];

export const referenceDocumentCategories: readonly ReferenceDocumentCategory[] = [
  { id: "law", name: "法律法规库", description: "法律、法规、规章、司法解释", count: 1362 },
  { id: "policy", name: "政策文件库", description: "政策通知、管理办法、专项方案", count: 945 },
  { id: "case", name: "审计案例库", description: "典型问题、案例摘要、处理口径", count: 842 },
  { id: "faq", name: "常见问题库", description: "常用问答、复核口径、操作提示", count: 286 },
  { id: "research", name: "研究报告库", description: "研究资料、行业报告、专题分析", count: 193 },
  { id: "hot", name: "热点事件库", description: "热点事件、舆情材料、风险线索", count: 75 },
  { id: "book", name: "书本期刊库", description: "教材、期刊、专著和参考资料", count: 214 }
];

export const referenceSearchHistory: readonly string[] = [
  "招标人违法确定中标人的定性依据",
  "厕所建后管护不到位表现形式",
  "医保基金重复收费怎么取证",
  "会议费超标准审计处理"
];

export const referenceDocumentResults: readonly ReferenceDocumentResult[] = [
  {
    id: "doc-law-1",
    title: "中华人民共和国招标投标法实施条例",
    category: "法律法规库",
    excerpt: "检索命中定标、评标委员会推荐候选人、招标人确定中标人的条款。",
    source: "国务院令",
    updatedAt: "2026-06-18"
  },
  {
    id: "doc-case-1",
    title: "某项目招标人违规确定中标人案例",
    category: "审计案例库",
    excerpt: "案例展示招标人绕开候选人排序定标、资料缺失和整改建议。",
    source: "审计案例库",
    updatedAt: "2026-06-22"
  },
  {
    id: "doc-policy-1",
    title: "农村公厕建设和管护专项资金管理提示",
    category: "政策文件库",
    excerpt: "覆盖资金拨付、管护责任、后续使用效果和绩效评价指标。",
    source: "政策文件库",
    updatedAt: "2026-06-25"
  }
];

export const referenceAnalysisDatasets: readonly ReferenceAnalysisDataset[] = [
  {
    id: "dataset-1",
    name: "政府采购合同台账.xlsx",
    rows: 4280,
    columns: 36,
    status: "已解析",
    insight: "识别到 17 条供应商同日多合同、9 条预算金额与中标金额异常接近。"
  },
  {
    id: "dataset-2",
    name: "医保结算明细.csv",
    rows: 18542,
    columns: 42,
    status: "待生成图表",
    insight: "费用、支付、目录限制字段齐备，可进入重复收费和超范围支付核验。"
  }
];

export const referenceGraphNodes: readonly ReferenceGraphNode[] = [
  { id: "graph-project", label: "乡村振兴专项审计", kind: "项目", metric: "4 个主题", status: "运行中" },
  { id: "graph-agent", label: "厕所管护核验智能体", kind: "智能体", metric: "12 次调用", status: "已关联" },
  { id: "graph-kb", label: "乡村振兴项目知识库", kind: "知识库", metric: "156 份文档", status: "可检索" },
  { id: "graph-doc", label: "管护资金拨付台账", kind: "文档", metric: "28 条证据", status: "已入库" },
  { id: "graph-bank", label: "县级财政专户", kind: "银行", metric: "3 条资金链", status: "待核验" },
  { id: "graph-company", label: "建设运维单位", kind: "企业", metric: "5 个合同", status: "已关联" },
  { id: "graph-gov", label: "主管部门", kind: "政府机构", metric: "7 个责任事项", status: "已关联" },
  { id: "graph-policy", label: "专项资金管理办法", kind: "政策文件", metric: "9 条引用", status: "可引用" }
];

export const referenceGraphRelations: readonly ReferenceGraphRelation[] = [
  {
    id: "relation-project-kb",
    sourceId: "graph-project",
    targetId: "graph-kb",
    source: "乡村振兴专项审计",
    relation: "调用知识库",
    target: "乡村振兴项目知识库",
    evidence: "项目问答和文档检索均需先限定知识库范围。",
    strength: "强"
  },
  {
    id: "relation-project-doc",
    sourceId: "graph-project",
    targetId: "graph-doc",
    source: "乡村振兴专项审计",
    relation: "归集材料",
    target: "管护资金拨付台账",
    evidence: "台账提供拨付时间、金额、对象和凭证编号。",
    strength: "强"
  },
  {
    id: "relation-doc-bank",
    sourceId: "graph-doc",
    targetId: "graph-bank",
    source: "管护资金拨付台账",
    relation: "指向账户",
    target: "县级财政专户",
    evidence: "资金链核验需要与银行流水逐笔对齐。",
    strength: "中"
  },
  {
    id: "relation-doc-company",
    sourceId: "graph-doc",
    targetId: "graph-company",
    source: "管护资金拨付台账",
    relation: "关联合同主体",
    target: "建设运维单位",
    evidence: "合同主体、付款对象和验收记录需要一致性核验。",
    strength: "中"
  },
  {
    id: "relation-policy-project",
    sourceId: "graph-policy",
    targetId: "graph-project",
    source: "专项资金管理办法",
    relation: "提供定性依据",
    target: "乡村振兴专项审计",
    evidence: "图谱只展示可追溯依据，不直接生成处理决定。",
    strength: "待补"
  }
];

export const referenceReportRecords: readonly ReferenceReportRecord[] = [
  {
    id: "report-1",
    title: "招标人违法确定中标人审计底稿",
    project: "财政专项审计",
    status: "已生成",
    generatedAt: "2026-07-03 15:42",
    sourceCount: 6
  },
  {
    id: "report-2",
    title: "厕所建后管护不到位问题报告",
    project: "乡村振兴审计",
    status: "草稿",
    generatedAt: "2026-07-02 18:10",
    sourceCount: 9
  },
  {
    id: "report-3",
    title: "医保基金支付异常分析底稿",
    project: "社会保障审计",
    status: "待复核",
    generatedAt: "2026-07-01 11:28",
    sourceCount: 12
  }
];

export const referenceProjects: readonly ReferenceProject[] = [
  {
    id: "project-village",
    name: "乡村振兴资金专项审计",
    type: "专项审计",
    owner: "审计员",
    members: 8,
    status: "进行中",
    updatedAt: "2026-07-03",
    progress: 68
  },
  {
    id: "project-finance",
    name: "财政专项资金绩效审计",
    type: "财政审计",
    owner: "审计一组",
    members: 5,
    status: "资料收集",
    updatedAt: "2026-07-02",
    progress: 42
  },
  {
    id: "project-healthcare",
    name: "医保基金使用合规审计",
    type: "社会保障审计",
    owner: "审计二组",
    members: 11,
    status: "问题复核",
    updatedAt: "2026-07-01",
    progress: 76
  },
  {
    id: "project-company",
    name: "国有企业经营管理审计",
    type: "企业审计",
    owner: "审计三组",
    members: 6,
    status: "底稿编制",
    updatedAt: "2026-06-30",
    progress: 84
  }
];
