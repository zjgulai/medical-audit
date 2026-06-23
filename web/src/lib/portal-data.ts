export type AgentCategory = "效率类" | "业务类" | "研究类";

export type AuditAgent = {
  readonly id: string;
  readonly name: string;
  readonly category: AgentCategory;
  readonly topic: string;
  readonly prompt: string;
  readonly knowledgeBase: string;
  readonly projectName: string;
  readonly updatedAt: string;
  readonly status?: string;
  readonly promptVersion?: number;
  readonly promptVersionKey?: string;
  readonly promptVersions?: readonly AuditAgentPromptVersion[];
  readonly visibilityScope?: "project" | "system";
  readonly allowedRoles?: readonly string[];
};

export type AuditAgentPromptReviewStatus = "pending-review" | "approved" | "changes-requested";

export type AuditAgentPromptVersion = {
  readonly version: number;
  readonly prompt: string;
  readonly changeSummary: string;
  readonly isActive: boolean;
  readonly createdBy: string | null;
  readonly createdAt: string;
  readonly reviewStatus: AuditAgentPromptReviewStatus;
  readonly reviewNote: string;
  readonly requestedBy: string | null;
  readonly reviewedBy: string | null;
  readonly reviewedAt: string | null;
  readonly reviewUpdatedAt: string | null;
};

export type AuditTableTemplate = {
  readonly id: string;
  readonly name: string;
  readonly shortName: string;
  readonly fileName: string;
  readonly sheetName: string;
  readonly auditUse: string;
  readonly expectedColumns: readonly string[];
  readonly keyChecks: readonly string[];
  readonly analysisRequest: string;
};

export type WorkpaperPromptTemplate = {
  readonly id: string;
  readonly name: string;
  readonly sourceTemplateId: AuditTableTemplate["id"];
  readonly sourceTable: string;
  readonly sourceFileName?: string;
  readonly templateStatus?: string;
  readonly outputType: "底稿草稿" | "问题清单" | "复核摘要";
  readonly evidenceBindings: readonly string[];
  readonly prompt: string;
  readonly href: string;
};

export type KnowledgeBaseCard = {
  readonly id: string;
  readonly name: string;
  readonly scope: "个人知识库" | "系统知识库" | "公开知识库";
  readonly documentCount: number;
  readonly characterCount: number;
  readonly linkedAppCount: number;
  readonly description: string;
  readonly owner: string;
  readonly status: "可检索" | "待更新" | "只读";
};

export type PortalProjectMember = {
  readonly id: string;
  readonly name: string;
  readonly role: "项目负责人" | "审计员" | "业务专家" | "信息科" | "只读观察员";
  readonly department: string;
  readonly status: "在项目中" | "待确认";
};

export type HospitalPermissionRole = {
  readonly id: string;
  readonly name: "管理员" | "技术人员" | "主任" | "普通成员";
  readonly mapsToProjectRole: PortalProjectMember["role"];
  readonly departmentHint: string;
  readonly responsibility: string;
  readonly allowedActions: readonly string[];
  readonly boundary: string;
};

export type PortalProjectSummary = {
  readonly id: string;
  readonly name: string;
  readonly auditTopic: string;
  readonly organizationName: string;
  readonly memberCount: number;
  readonly creator: string;
  readonly createdAt: string;
  readonly status: "进行中" | "待启动" | "已归档";
  readonly operationLabel: string;
};

export type GuidedCheckStep = {
  readonly id: string;
  readonly order: string;
  readonly title: string;
  readonly status: "已完成" | "进行中" | "待补证" | "未开始";
  readonly owner: "审计员" | "业务专家" | "信息科" | "项目负责人";
  readonly detail: string;
  readonly href: string;
};

export type GuidedCheckQuestion = {
  readonly id: string;
  readonly domain: "收费明细" | "医保目录" | "身份核验" | "底稿报告";
  readonly question: string;
  readonly agentName: string;
  readonly knowledgeScope: string;
  readonly status: "可提问" | "需补数据" | "待复核";
  readonly chatHref: string;
};

export type GuidedCheckEvidenceItem = {
  readonly id: string;
  readonly title: string;
  readonly source: string;
  readonly status: "已就绪" | "待补证" | "需复核";
  readonly blocker: string;
  readonly href: string;
};

export type GuidedCheckRiskSignal = {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly status: "高风险" | "待确认" | "已收敛";
  readonly detail: string;
  readonly href: string;
};

export type GuidedCheckTimelineItem = {
  readonly id: string;
  readonly time: string;
  readonly title: string;
  readonly detail: string;
  readonly status: "已完成" | "进行中" | "待处理";
};

export type DocumentCategoryStat = {
  readonly id: string;
  readonly name: string;
  readonly scope: KnowledgeBaseCard["scope"];
  readonly sourceCollection: string;
  readonly documentCount: number;
  readonly description: string;
};

export type PortalDocumentItem = {
  readonly id: string;
  readonly title: string;
  readonly kind: "对话文档" | "知识库文档";
  readonly libraryName: string;
  readonly owner: string;
  readonly updatedAt: string;
  readonly status: "可审证" | "待补引用" | "只读";
  readonly summary: string;
  readonly href: string;
  readonly chatHref: string;
};

export type GraphNodeKind = "项目" | "知识库" | "文档" | "规则" | "疑点" | "复核" | "报告" | "整改";

export type GraphNode = {
  readonly id: string;
  readonly label: string;
  readonly kind: GraphNodeKind;
  readonly status: "已归集" | "可引用" | "待复核" | "门禁中" | "跟踪中";
  readonly description: string;
  readonly metric: string;
  readonly href: string;
  readonly x: number;
  readonly y: number;
};

export type GraphRelation = {
  readonly id: string;
  readonly sourceId: string;
  readonly targetId: string;
  readonly source: string;
  readonly relation: string;
  readonly target: string;
  readonly evidence: string;
  readonly strength: "强" | "中" | "待补";
};

export type ReportEntry = {
  readonly id: string;
  readonly title: string;
  readonly status: "草稿" | "门禁阻断" | "已签发";
  readonly reportNo: string;
  readonly owner: string;
  readonly source: string;
  readonly includedFindingCount: number;
  readonly appendixCount: number;
  readonly gateSummary: string;
  readonly updatedAt: string;
  readonly href: string;
  readonly taskDocxHref?: string | null;
  readonly reportDocxHref?: string | null;
  readonly reportMarkdownHref?: string | null;
  readonly reportJsonHref?: string | null;
};

export type ReportGateItem = {
  readonly id: string;
  readonly label: string;
  readonly status: "通过" | "阻断" | "待人工确认";
  readonly detail: string;
  readonly owner: "审计员" | "项目负责人" | "信息科";
};

export type ReportEvidenceSource = {
  readonly id: string;
  readonly title: string;
  readonly kind: "疑点" | "底稿" | "附件" | "负责人确认";
  readonly reference: string;
  readonly status: "已纳入" | "待补证" | "只读";
  readonly href: string;
};

export type RectificationSummary = {
  readonly id: string;
  readonly title: string;
  readonly department: string;
  readonly status: "待整改" | "整改中" | "已整改";
  readonly dueDate: string;
  readonly reportNo: string;
};

export type RemediationCase = {
  readonly id: string;
  readonly title: string;
  readonly department: string;
  readonly owner: "医保办" | "财务科" | "信息科" | "药剂科";
  readonly status: "待整改" | "整改中" | "待验收" | "已关闭";
  readonly dueDate: string;
  readonly reportNo: string;
  readonly sourceFinding: string;
  readonly progress: number;
  readonly evidenceStatus: "待补证" | "已提交" | "需退回" | "已验收";
  readonly nextAction: string;
  readonly href: string;
};

export type RemediationEvidenceRequest = {
  readonly id: string;
  readonly title: string;
  readonly linkedCaseId: string;
  readonly kind: "HIS 凭证" | "附件归档" | "负责人确认" | "退费凭证";
  readonly status: "待上传" | "已提交" | "需退回" | "已验收";
  readonly owner: "医保办" | "财务科" | "信息科" | "项目负责人";
  readonly dueDate: string;
  readonly detail: string;
  readonly href: string;
};

export type RemediationClosureGate = {
  readonly id: string;
  readonly label: string;
  readonly status: "通过" | "阻断" | "待人工确认";
  readonly detail: string;
  readonly owner: "审计员" | "项目负责人" | "信息科";
};

export type RemediationTimelineItem = {
  readonly id: string;
  readonly time: string;
  readonly title: string;
  readonly detail: string;
  readonly status: "已记录" | "待处理" | "已阻断";
};

export type ArchivePackage = {
  readonly id: string;
  readonly projectName: string;
  readonly archiveNo: string;
  readonly status: "已归档" | "归档前检查" | "待归档" | "材料阻断";
  readonly reportNo: string;
  readonly owner: string;
  readonly archiveScope: string;
  readonly evidenceSummary: string;
  readonly signedAt: string;
  readonly retainedUntil: string;
  readonly href: string;
  readonly logHref: string;
};

export type ArchiveAuditRun = {
  readonly id: string;
  readonly title: string;
  readonly status: "通过" | "阻断" | "待人工确认" | "待配置";
  readonly time: string;
  readonly archiveRoot: string;
  readonly manifestCount: number;
  readonly failedCount: number;
  readonly detail: string;
};

export type ArchiveSignatureItem = {
  readonly id: string;
  readonly label: string;
  readonly status: "验签通过" | "已生成" | "待生成";
  readonly sha256: string;
  readonly detail: string;
};

export type ArchivePolicyItem = {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly detail: string;
};

export type ArchiveTimelineItem = {
  readonly id: string;
  readonly time: string;
  readonly title: string;
  readonly detail: string;
  readonly status: "已部署" | "已入档" | "待补证" | "已记录";
};

export type RuleLibraryItem = {
  readonly id: string;
  readonly code: string;
  readonly name: string;
  readonly domain: "收费明细" | "医保目录" | "处方用药" | "参保身份";
  readonly status: "已启用" | "待补字段" | "待复核" | "只读";
  readonly sourceCollection: string;
  readonly evidenceScope: string;
  readonly evidenceCount: number;
  readonly findingCount: number;
  readonly owner: "内审部" | "业务专家" | "信息科";
  readonly updatedAt: string;
  readonly href: string;
  readonly chatHref: string;
};

export type RuleSourceCoverage = {
  readonly id: string;
  readonly name: string;
  readonly sourceCollection: string;
  readonly ruleCount: number;
  readonly indexStatus: "可引用" | "待同步" | "只读";
  readonly health: string;
  readonly href: string;
};

export type RuleRunSnapshot = {
  readonly id: string;
  readonly ruleCode: string;
  readonly inputTable: string;
  readonly lastRunAt: string;
  readonly hitCount: number;
  readonly linkedFinding: string;
  readonly nextAction: string;
};

export type RuleControlGate = {
  readonly id: string;
  readonly label: string;
  readonly status: "通过" | "阻断" | "待人工确认";
  readonly detail: string;
  readonly owner: "审计员" | "业务专家" | "信息科";
};

export const defaultAuditAgents: readonly AuditAgent[] = [
  {
    id: "agent-citation-check",
    name: "引用依据核验助手",
    category: "业务类",
    topic: "医保基金使用合规",
    prompt: "只基于命中的法规、目录、规则和风险清单回答；没有引用时输出待补证据。",
    knowledgeBase: "系统医保审计知识库",
    projectName: "医保基金使用合规专项自查",
    updatedAt: "2026-06-12"
  },
  {
    id: "agent-duplicate-charge",
    name: "重复收费复核助手",
    category: "业务类",
    topic: "收费明细复核",
    prompt: "围绕同就诊、同项目、同日期的重复收费线索，列出应核验的执行记录、数量和例外情形。",
    knowledgeBase: "规则库与风险清单",
    projectName: "医保基金使用合规专项自查",
    updatedAt: "2026-06-11"
  },
  {
    id: "agent-report-draft",
    name: "底稿摘要助手",
    category: "效率类",
    topic: "审计底稿",
    prompt: "把已复核的引用、疑点和附件清单整理为底稿摘要，保留待人工确认标记。",
    knowledgeBase: "项目复核资料",
    projectName: "医保基金使用合规专项自查",
    updatedAt: "2026-06-10"
  }
];

export const auditAgentTemplates: readonly AuditAgent[] = [
  {
    id: "template-catalog-limit",
    name: "医保目录限制审查",
    category: "业务类",
    topic: "目录限制",
    prompt: "核对诊疗项目、药品编码、支付范围和限制条件，输出需要补充的 HIS 字段。",
    knowledgeBase: "医保目录库",
    projectName: "医保目录限制条件核验",
    updatedAt: "模板"
  },
  {
    id: "template-identity-risk",
    name: "参保身份异常核验",
    category: "业务类",
    topic: "身份骗保",
    prompt: "围绕参保身份、就诊记录和结算记录查找不一致线索，只输出可追溯问题清单。",
    knowledgeBase: "风险负面清单",
    projectName: "医保基金使用合规专项自查",
    updatedAt: "模板"
  },
  {
    id: "template-working-paper",
    name: "审计底稿生成模板",
    category: "效率类",
    topic: "底稿生成",
    prompt: "把已确认违规疑点、引用依据、附件清单和负责人确认状态整理为底稿草稿。",
    knowledgeBase: "项目复核资料",
    projectName: "医保基金使用合规专项自查",
    updatedAt: "模板"
  },
  {
    id: "template-policy-compare",
    name: "政策口径对比",
    category: "研究类",
    topic: "政策研究",
    prompt: "对比政策条款、适用边界和版本差异，标记不能直接外推的内容。",
    knowledgeBase: "法规政策库",
    projectName: "公开法规政策库",
    updatedAt: "模板"
  }
];

export const auditTableTemplates: readonly AuditTableTemplate[] = [
  {
    id: "medical-expense-summary",
    name: "医保费用汇总表",
    shortName: "表1",
    fileName: "表1_医保费用汇总表-模版.xlsx",
    sheetName: "汇总表",
    auditUse: "按费用分类汇总人次、人数、医疗总费用、现金支付、账户支付和医保基金支付口径。",
    expectedColumns: [
      "费用分类",
      "人次",
      "人数",
      "平均费",
      "医疗总费用",
      "现金支付",
      "账户支付",
      "统筹支付",
      "记账合计"
    ],
    keyChecks: [
      "医疗总费用与支付分项是否存在口径不一致",
      "统筹支付、账户支付、现金支付是否能回溯到明细",
      "重点费用分类是否存在异常占比或环比突增"
    ],
    analysisRequest: "按费用分类核对医疗总费用、现金支付、账户支付、统筹支付和记账合计，识别基金支付异常占比和需下钻的分类。"
  },
  {
    id: "medical-expense-category-summary",
    name: "医保费用分类汇总表",
    shortName: "表2",
    fileName: "表2_医保费用分类汇总表-模版.xlsx",
    sheetName: "汇总表",
    auditUse: "按医保费用类别比较人次、人数、平均费用和基金支付结构。",
    expectedColumns: [
      "费用分类",
      "人次",
      "人数",
      "平均费用",
      "医疗总费用",
      "现金支付",
      "账户支付",
      "统筹支付",
      "公务员补助"
    ],
    keyChecks: [
      "平均费用是否存在明显偏离",
      "基金支付与现金支付结构是否符合费用类别预期",
      "分类口径是否能与就诊明细表闭环"
    ],
    analysisRequest: "按医保费用分类比较平均费用、医疗总费用、统筹支付和现金支付结构，找出需要结合就诊明细复核的分类。"
  },
  {
    id: "visit-expense-detail",
    name: "就诊费用明细表",
    shortName: "表3",
    fileName: "表3_就诊费用明细表-模版.xlsx",
    sheetName: "明细表",
    auditUse: "逐就诊记录核验姓名、身份证号、入院诊断、医疗费用、自费金额和基金支付分项。",
    expectedColumns: [
      "序号",
      "职工类型",
      "就诊记录号",
      "姓名",
      "身份证号码",
      "入院诊断",
      "医疗费用/总额",
      "自费金额",
      "统筹支付",
      "公务员补助",
      "大额支付",
      "账户支付"
    ],
    keyChecks: [
      "同一就诊记录是否存在重复收费或异常支付",
      "自费金额与统筹支付是否出现不合理组合",
      "身份证号、就诊记录号等直接身份字段需按权限处理"
    ],
    analysisRequest: "按就诊记录号、诊断、医疗费用、自费金额和医保支付分项识别重复收费、支付范围异常和需要人工复核的明细。"
  }
];

export const workpaperPromptTemplates: readonly WorkpaperPromptTemplate[] = [
  {
    id: "workpaper-summary-risk",
    name: "费用汇总风险底稿",
    sourceTemplateId: "medical-expense-summary",
    sourceTable: "表1 医保费用汇总表",
    outputType: "底稿草稿",
    evidenceBindings: ["费用分类汇总", "支付分项合计", "异常占比说明", "人工复核意见"],
    prompt: "基于已上传的医保费用汇总表和已核验引用依据，生成费用分类风险底稿草稿；只写已确认数据事实、待补证项和人工复核意见。",
    href: "/chat?agent=agent-report-draft&question=%E5%9F%BA%E4%BA%8E%E5%8C%BB%E4%BF%9D%E8%B4%B9%E7%94%A8%E6%B1%87%E6%80%BB%E8%A1%A8%E7%94%9F%E6%88%90%E5%BA%95%E7%A8%BF%E8%8D%89%E7%A8%BF"
  },
  {
    id: "workpaper-category-review",
    name: "分类费用复核清单",
    sourceTemplateId: "medical-expense-category-summary",
    sourceTable: "表2 医保费用分类汇总表",
    outputType: "问题清单",
    evidenceBindings: ["平均费用偏离", "基金支付结构", "分类口径说明", "需下钻明细"],
    prompt: "基于医保费用分类汇总表，列出平均费用、基金支付结构和分类口径需要复核的问题清单；不能直接形成结论的内容标为待人工确认。",
    href: "/chat?agent=agent-citation-check&question=%E5%8C%BB%E4%BF%9D%E8%B4%B9%E7%94%A8%E5%88%86%E7%B1%BB%E6%B1%87%E6%80%BB%E8%A1%A8%E5%BA%94%E5%BD%A2%E6%88%90%E5%93%AA%E4%BA%9B%E5%A4%8D%E6%A0%B8%E6%B8%85%E5%8D%95"
  },
  {
    id: "workpaper-visit-detail",
    name: "就诊明细疑点摘要",
    sourceTemplateId: "visit-expense-detail",
    sourceTable: "表3 就诊费用明细表",
    outputType: "复核摘要",
    evidenceBindings: ["就诊记录号", "诊断与费用", "自费和基金支付", "隐私字段处理记录"],
    prompt: "基于就诊费用明细表，按就诊记录输出疑点摘要、证据字段和隐私字段处理提醒；只把已人工确认的疑点纳入底稿草稿。",
    href: "/chat?agent=agent-report-draft&question=%E5%9F%BA%E4%BA%8E%E5%B0%B1%E8%AF%8A%E8%B4%B9%E7%94%A8%E6%98%8E%E7%BB%86%E8%A1%A8%E6%95%B4%E7%90%86%E7%96%91%E7%82%B9%E6%91%98%E8%A6%81"
  }
];

export const knowledgeBases: readonly KnowledgeBaseCard[] = [
  {
    id: "kb-personal",
    name: "个人审计材料库",
    scope: "个人知识库",
    documentCount: 24,
    characterCount: 186000,
    linkedAppCount: 2,
    description: "审计员上传的项目材料、会议纪要和人工复核记录，首期只读展示。",
    owner: "审计员",
    status: "只读"
  },
  {
    id: "kb-system",
    name: "系统医保审计知识库",
    scope: "系统知识库",
    documentCount: 48985,
    characterCount: 14862000,
    linkedAppCount: 6,
    description: "法规政策、医保目录、监管规则和风险负面清单组成的系统检索底座。",
    owner: "内审部",
    status: "可检索"
  },
  {
    id: "kb-public",
    name: "公开法规政策库",
    scope: "公开知识库",
    documentCount: 612,
    characterCount: 2419000,
    linkedAppCount: 3,
    description: "长期保留的公开政策、法律法规和可供审计引用的通用资料。",
    owner: "法规政策",
    status: "可检索"
  }
];

export const defaultProjectMembers: readonly PortalProjectMember[] = [
  {
    id: "member-auditor",
    name: "审计员",
    role: "审计员",
    department: "内审部",
    status: "在项目中"
  },
  {
    id: "member-owner",
    name: "项目负责人",
    role: "项目负责人",
    department: "内审部",
    status: "在项目中"
  },
  {
    id: "member-it",
    name: "信息科接口人",
    role: "信息科",
    department: "信息科",
    status: "待确认"
  }
];

export const hospitalPermissionRoles: readonly HospitalPermissionRole[] = [
  {
    id: "hospital-admin",
    name: "管理员",
    mapsToProjectRole: "项目负责人",
    departmentHint: "信息科",
    responsibility: "开设账号、分配项目角色、查看全局项目和知识库状态。",
    allowedActions: ["账号开设", "角色分配", "索引状态查看", "审计日志查看"],
    boundary: "首期仅展示权限配置视图，真实账号和全站权限仍需后端认证体系生效。"
  },
  {
    id: "hospital-technician",
    name: "技术人员",
    mapsToProjectRole: "信息科",
    departmentHint: "信息科",
    responsibility: "负责数据导入、字段补证、索引协助和接口状态排查。",
    allowedActions: ["数据与索引协助", "字段补证", "接口状态核验", "材料留存协助"],
    boundary: "技术人员可协助数据链路，不代表拥有业务结论签发权限。"
  },
  {
    id: "hospital-director",
    name: "主任",
    mapsToProjectRole: "项目负责人",
    departmentHint: "内审部",
    responsibility: "负责专项审计范围确认、复核意见、底稿和报告签发前把关。",
    allowedActions: ["专题范围确认", "疑点复核", "底稿确认", "整改跟踪"],
    boundary: "主任视图只标识人工把关责任，正式签发仍按后续底稿/报告门禁执行。"
  },
  {
    id: "hospital-member",
    name: "普通成员",
    mapsToProjectRole: "审计员",
    departmentHint: "内审部",
    responsibility: "执行日常检索、AI 对话、表格分析和补证记录整理。",
    allowedActions: ["文档检索", "AI 对话", "数据分析", "补证记录"],
    boundary: "普通成员可形成线索和草稿，不能直接绕过引用和人工复核门禁。"
  }
];

export const portalProjectSummaries: readonly PortalProjectSummary[] = [
  {
    id: "SELF-CHECK-FUND-20260607",
    name: "医保基金使用合规专项自查",
    auditTopic: "医保基金使用合规",
    organizationName: "单院医保内审试运行",
    memberCount: 3,
    creator: "项目负责人",
    createdAt: "2026-06-07",
    status: "进行中",
    operationLabel: "进入项目"
  },
  {
    id: "CATALOG-LIMIT-202606",
    name: "医保目录限制条件核验",
    auditTopic: "目录限制",
    organizationName: "单院医保内审试运行",
    memberCount: 4,
    creator: "业务专家",
    createdAt: "2026-06-09",
    status: "待启动",
    operationLabel: "查看成员"
  },
  {
    id: "OUTPATIENT-DOSE-202606",
    name: "门诊超量开药专项复核",
    auditTopic: "门诊处方合规",
    organizationName: "单院医保内审试运行",
    memberCount: 5,
    creator: "审计员",
    createdAt: "2026-06-10",
    status: "进行中",
    operationLabel: "进入项目"
  },
  {
    id: "KB-GOVERNANCE-202606",
    name: "审计知识库治理项目",
    auditTopic: "知识库治理",
    organizationName: "内审部",
    memberCount: 2,
    creator: "信息科接口人",
    createdAt: "2026-06-11",
    status: "已归档",
    operationLabel: "查看归档"
  }
];

export const guidedCheckSteps: readonly GuidedCheckStep[] = [
  {
    id: "guided-step-scope",
    order: "01",
    title: "锁定自查范围",
    status: "已完成",
    owner: "项目负责人",
    detail: "当前项目已限定医保基金使用合规主题、审计期间和参与成员。",
    href: "/projects"
  },
  {
    id: "guided-step-data",
    order: "02",
    title: "上传并识别数据",
    status: "进行中",
    owner: "审计员",
    detail: "收费明细样本已可分析，目录限制字段仍需补齐 HIS 截图。",
    href: "/analytics"
  },
  {
    id: "guided-step-rules",
    order: "03",
    title: "选择规则与依据",
    status: "待补证",
    owner: "业务专家",
    detail: "重复收费规则可运行；目录限制规则被字段门禁阻断。",
    href: "/rules"
  },
  {
    id: "guided-step-chat",
    order: "04",
    title: "进入 AI 审证对话",
    status: "进行中",
    owner: "审计员",
    detail: "使用提示词型智能体生成审证问题、引用依据和待人工复核清单。",
    href: "/chat"
  },
  {
    id: "guided-step-report",
    order: "05",
    title: "沉淀底稿与整改",
    status: "未开始",
    owner: "项目负责人",
    detail: "仅已确认疑点可进入底稿、报告、整改和项目归档链路。",
    href: "/reports"
  }
];

export const guidedCheckQuestions: readonly GuidedCheckQuestion[] = [
  {
    id: "guided-question-duplicate-charge",
    domain: "收费明细",
    question: "同就诊同项目同日期同金额的重复收费，应核验哪些执行记录和例外情形？",
    agentName: "重复收费复核助手",
    knowledgeScope: "规则库与风险清单",
    status: "可提问",
    chatHref: "/chat?agent=agent-duplicate-charge&question=%E5%90%8C%E5%B0%B1%E8%AF%8A%E5%90%8C%E9%A1%B9%E7%9B%AE%E5%90%8C%E6%97%A5%E6%9C%9F%E5%90%8C%E9%87%91%E9%A2%9D%E7%9A%84%E9%87%8D%E5%A4%8D%E6%94%B6%E8%B4%B9%EF%BC%8C%E5%BA%94%E6%A0%B8%E9%AA%8C%E5%93%AA%E4%BA%9B%E6%89%A7%E8%A1%8C%E8%AE%B0%E5%BD%95%E5%92%8C%E4%BE%8B%E5%A4%96%E6%83%85%E5%BD%A2%EF%BC%9F"
  },
  {
    id: "guided-question-catalog-limit",
    domain: "医保目录",
    question: "目录限制条件核验缺少哪些 HIS 字段，哪些内容不能直接形成结论？",
    agentName: "医保目录限制审查",
    knowledgeScope: "医保目录库",
    status: "需补数据",
    chatHref: "/chat?agent=template-catalog-limit&question=%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6%E6%9D%A1%E4%BB%B6%E6%A0%B8%E9%AA%8C%E7%BC%BA%E5%B0%91%E5%93%AA%E4%BA%9B%20HIS%20%E5%AD%97%E6%AE%B5%EF%BC%9F"
  },
  {
    id: "guided-question-identity-risk",
    domain: "身份核验",
    question: "参保身份、就诊记录和结算记录不一致时，应先做哪三类交叉核验？",
    agentName: "参保身份异常核验",
    knowledgeScope: "风险负面清单",
    status: "待复核",
    chatHref: "/chat?agent=template-identity-risk&question=%E5%8F%82%E4%BF%9D%E8%BA%AB%E4%BB%BD%E4%B8%8E%E5%B0%B1%E8%AF%8A%E7%BB%93%E7%AE%97%E8%AE%B0%E5%BD%95%E4%B8%8D%E4%B8%80%E8%87%B4%E5%BA%94%E5%A6%82%E4%BD%95%E6%A0%B8%E9%AA%8C%EF%BC%9F"
  },
  {
    id: "guided-question-report-gate",
    domain: "底稿报告",
    question: "哪些疑点已满足底稿生成门禁，哪些证据必须人工确认后才能入报告？",
    agentName: "底稿摘要助手",
    knowledgeScope: "项目复核资料",
    status: "可提问",
    chatHref: "/chat?agent=agent-report-draft&question=%E5%93%AA%E4%BA%9B%E7%96%91%E7%82%B9%E5%B7%B2%E6%BB%A1%E8%B6%B3%E5%BA%95%E7%A8%BF%E7%94%9F%E6%88%90%E9%97%A8%E7%A6%81%EF%BC%9F"
  }
];

export const guidedCheckEvidenceItems: readonly GuidedCheckEvidenceItem[] = [
  {
    id: "guided-evidence-charge-detail",
    title: "收费明细 CSV 样本",
    source: "AI 数据分析",
    status: "已就绪",
    blocker: "字段识别已覆盖患者、就诊、项目、日期和金额。",
    href: "/analytics"
  },
  {
    id: "guided-evidence-catalog-field",
    title: "目录限制 HIS 字段截图",
    source: "补证整改",
    status: "待补证",
    blocker: "缺少项目编码、支付范围和限制条件字段截图。",
    href: "/remediation"
  },
  {
    id: "guided-evidence-policy-source",
    title: "医保目录限制条件资料包",
    source: "知识库文档",
    status: "已就绪",
    blocker: "可作为引用依据，仍需结合本院 HIS 字段。",
    href: "/documents"
  },
  {
    id: "guided-evidence-owner-confirm",
    title: "负责人确认记录",
    source: "底稿报告",
    status: "需复核",
    blocker: "报告入档前必须记录人工确认结论。",
    href: "/reports"
  }
];

export const guidedCheckRiskSignals: readonly GuidedCheckRiskSignal[] = [
  {
    id: "guided-risk-duplicate-charge",
    label: "重复收费线索",
    value: "1 条",
    status: "高风险",
    detail: "已由 CHARGE-RULE-001 命中，等待人工核验执行记录。",
    href: "/findings?rule=CHARGE-RULE-001"
  },
  {
    id: "guided-risk-catalog-blocker",
    label: "目录限制阻断",
    value: "2 项",
    status: "待确认",
    detail: "字段证据不足，不能自动进入底稿结论。",
    href: "/rules"
  },
  {
    id: "guided-risk-report-ready",
    label: "可入底稿疑点",
    value: "1 项",
    status: "已收敛",
    detail: "已确认疑点可进入报告草稿，但整改验收仍未关闭。",
    href: "/reports"
  }
];

export const guidedCheckTimeline: readonly GuidedCheckTimelineItem[] = [
  {
    id: "guided-timeline-project",
    time: "2026-06-07 09:00",
    title: "创建医保基金使用合规专项自查",
    detail: "项目范围、成员和知识库绑定已确定。",
    status: "已完成"
  },
  {
    id: "guided-timeline-data",
    time: "2026-06-12 10:20",
    title: "收费明细进入自查分析",
    detail: "CSV 上传入口可生成字段质量和重复收费初步提示。",
    status: "进行中"
  },
  {
    id: "guided-timeline-evidence",
    time: "2026-06-12 14:05",
    title: "目录限制字段待补证",
    detail: "需由财务科补充 HIS 字段截图后再审证。",
    status: "待处理"
  }
];

export const documentSearchHistory: readonly string[] = [
  "门诊超量开药依据",
  "目录限制支付范围",
  "重复收费执行记录",
  "医保基金支付异常"
];

export const documentCategoryStats: readonly DocumentCategoryStat[] = [
  {
    id: "doc-cat-laws",
    name: "法规政策",
    scope: "公开知识库",
    sourceCollection: "medical-insurance-laws",
    documentCount: 612,
    description: "医疗、医保、药品和基金监管相关法律政策。"
  },
  {
    id: "doc-cat-rules",
    name: "监管两库",
    scope: "系统知识库",
    sourceCollection: "supervision-rules-knowledge",
    documentCount: 12840,
    description: "智能监管规则库、知识库和知识点明细。"
  },
  {
    id: "doc-cat-catalog",
    name: "医保目录",
    scope: "系统知识库",
    sourceCollection: "medical-insurance-catalog",
    documentCount: 18266,
    description: "药品、诊疗项目、编码、支付范围和限制条件。"
  },
  {
    id: "doc-cat-risk",
    name: "风险清单",
    scope: "系统知识库",
    sourceCollection: "risk-negative-list",
    documentCount: 731,
    description: "负面清单、风险案例和专项审计线索。"
  }
];

export const ruleLibraryItems: readonly RuleLibraryItem[] = [
  {
    id: "rule-duplicate-charge",
    code: "CHARGE-RULE-001",
    name: "同就诊同项目重复收费",
    domain: "收费明细",
    status: "已启用",
    sourceCollection: "supervision-rules-knowledge",
    evidenceScope: "按患者、就诊、项目、日期和金额聚合，识别同源重复收费。",
    evidenceCount: 4,
    findingCount: 1,
    owner: "内审部",
    updatedAt: "2026-06-11",
    href: "/findings?rule=CHARGE-RULE-001",
    chatHref: "/chat?question=%E5%90%8C%E5%B0%B1%E8%AF%8A%E5%90%8C%E9%A1%B9%E7%9B%AE%E9%87%8D%E5%A4%8D%E6%94%B6%E8%B4%B9%E8%A7%84%E5%88%99%E5%A6%82%E4%BD%95%E6%A0%B8%E9%AA%8C%E8%AF%81%E6%8D%AE%E9%93%BE%EF%BC%9F"
  },
  {
    id: "rule-catalog-limit",
    code: "CATALOG-RULE-014",
    name: "目录限制条件交叉核验",
    domain: "医保目录",
    status: "待补字段",
    sourceCollection: "medical-insurance-catalog",
    evidenceScope: "核对诊疗项目编码、医保支付范围、限制条件和结算口径。",
    evidenceCount: 3,
    findingCount: 2,
    owner: "业务专家",
    updatedAt: "2026-06-10",
    href: "/knowledge-query?q=%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6%E6%9D%A1%E4%BB%B6",
    chatHref: "/chat?question=%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6%E6%9D%A1%E4%BB%B6%E8%A7%84%E5%88%99%E9%9C%80%E8%A6%81%E5%93%AA%E4%BA%9B%20HIS%20%E5%AD%97%E6%AE%B5%EF%BC%9F"
  },
  {
    id: "rule-dose-limit",
    code: "DOSE-RULE-006",
    name: "门诊超量开药提示",
    domain: "处方用药",
    status: "待复核",
    sourceCollection: "risk-negative-list",
    evidenceScope: "结合处方天数、药品用量、就诊频次和特殊病种标识形成提示。",
    evidenceCount: 2,
    findingCount: 0,
    owner: "内审部",
    updatedAt: "2026-06-09",
    href: "/documents",
    chatHref: "/chat?question=%E9%97%A8%E8%AF%8A%E8%B6%85%E9%87%8F%E5%BC%80%E8%8D%AF%E5%BA%94%E6%A0%B8%E5%AF%B9%E5%93%AA%E4%BA%9B%E5%8C%BB%E4%BF%9D%E5%AE%A1%E6%A0%B8%E4%BE%9D%E6%8D%AE%EF%BC%9F"
  },
  {
    id: "rule-identity-risk",
    code: "IDENTITY-RULE-003",
    name: "参保身份异常核验",
    domain: "参保身份",
    status: "只读",
    sourceCollection: "risk-negative-list",
    evidenceScope: "比对参保身份、就诊记录、结算记录和异常高频使用线索。",
    evidenceCount: 2,
    findingCount: 0,
    owner: "信息科",
    updatedAt: "2026-06-08",
    href: "/agent-market",
    chatHref: "/chat?agent=template-identity-risk"
  }
];

export const ruleSourceCoverages: readonly RuleSourceCoverage[] = [
  {
    id: "rule-source-supervision",
    name: "监管两库",
    sourceCollection: "supervision-rules-knowledge",
    ruleCount: 12840,
    indexStatus: "可引用",
    health: "规则库、知识库和知识点明细已同步。",
    href: "/documents"
  },
  {
    id: "rule-source-catalog",
    name: "医保目录",
    sourceCollection: "medical-insurance-catalog",
    ruleCount: 18266,
    indexStatus: "可引用",
    health: "支付范围和限制条件已进入统一检索。",
    href: "/knowledge-query?q=%E5%8C%BB%E4%BF%9D%E7%9B%AE%E5%BD%95"
  },
  {
    id: "rule-source-risk",
    name: "风险清单",
    sourceCollection: "risk-negative-list",
    ruleCount: 731,
    indexStatus: "可引用",
    health: "负面清单和专项风险案例可用于审计提示。",
    href: "/documents"
  },
  {
    id: "rule-source-chat",
    name: "对话审证沉淀",
    sourceCollection: "conversation-documents",
    ruleCount: 2,
    indexStatus: "待同步",
    health: "对话材料只能作为草稿来源，转规则前需人工确认。",
    href: "/chat"
  }
];

export const ruleRunSnapshots: readonly RuleRunSnapshot[] = [
  {
    id: "run-duplicate-charge",
    ruleCode: "CHARGE-RULE-001",
    inputTable: "charge_detail",
    lastRunAt: "2026-06-11 10:24",
    hitCount: 1,
    linkedFinding: "FINDING-F044EBD309B659DC",
    nextAction: "进入疑点工作台复核。"
  },
  {
    id: "run-catalog-limit",
    ruleCode: "CATALOG-RULE-014",
    inputTable: "his_charge_detail",
    lastRunAt: "2026-06-10 16:30",
    hitCount: 2,
    linkedFinding: "待生成复核任务",
    nextAction: "补齐医保目录限制字段。"
  },
  {
    id: "run-dose-limit",
    ruleCode: "DOSE-RULE-006",
    inputTable: "prescription_detail",
    lastRunAt: "2026-06-09 09:10",
    hitCount: 0,
    linkedFinding: "无",
    nextAction: "保留为专项提示规则。"
  }
];

export const ruleControlGates: readonly RuleControlGate[] = [
  {
    id: "rule-gate-source",
    label: "来源可追溯",
    status: "通过",
    detail: "每条规则必须绑定知识库来源、规则编码和适用审计主题。",
    owner: "审计员"
  },
  {
    id: "rule-gate-field",
    label: "字段可运行",
    status: "阻断",
    detail: "目录限制规则缺少部分 HIS 字段，不能直接进入批量运行。",
    owner: "信息科"
  },
  {
    id: "rule-gate-business",
    label: "业务口径确认",
    status: "待人工确认",
    detail: "处方用药和身份异常规则需要业务专家确认阈值口径。",
    owner: "业务专家"
  },
  {
    id: "rule-gate-output",
    label: "输出去向明确",
    status: "通过",
    detail: "规则命中后只能进入疑点、复核或审证对话，不能直接写入报告。",
    owner: "审计员"
  }
];

export const conversationDocuments: readonly PortalDocumentItem[] = [
  {
    id: "conv-duplicate-charge",
    title: "重复收费疑点复核对话",
    kind: "对话文档",
    libraryName: "历史对话",
    owner: "审计员",
    updatedAt: "2026-06-12",
    status: "可审证",
    summary: "围绕同就诊、同项目、同日期和同金额线索整理复核问题。",
    href: "/knowledge-query?q=%E9%87%8D%E5%A4%8D%E6%94%B6%E8%B4%B9",
    chatHref: "/chat?question=%E9%87%8D%E5%A4%8D%E6%94%B6%E8%B4%B9%E7%96%91%E7%82%B9%E5%BA%94%E5%A6%82%E4%BD%95%E6%A0%B8%E9%AA%8C%E8%AF%81%E6%8D%AE%E9%93%BE%EF%BC%9F"
  },
  {
    id: "conv-catalog-limit",
    title: "目录限制交叉审核对话",
    kind: "对话文档",
    libraryName: "历史对话",
    owner: "业务专家",
    updatedAt: "2026-06-11",
    status: "待补引用",
    summary: "整理医保目录限制、诊疗项目编码和支付范围交叉核验问题。",
    href: "/knowledge-query?q=%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6",
    chatHref: "/chat?question=%E8%AF%8A%E7%96%97%E9%A1%B9%E7%9B%AE%E6%94%B6%E8%B4%B9%E4%B8%8E%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6%E5%A6%82%E4%BD%95%E4%BA%A4%E5%8F%89%E5%AE%A1%E6%A0%B8%EF%BC%9F"
  }
];

export const knowledgeDocuments: readonly PortalDocumentItem[] = [
  {
    id: "doc-catalog-limit",
    title: "医保目录限制条件资料包",
    kind: "知识库文档",
    libraryName: "系统医保审计知识库",
    owner: "内审部",
    updatedAt: "2026-06-12",
    status: "只读",
    summary: "包含目录编码、支付范围、限制条件和可预览原文入口。",
    href: "/knowledge-query?q=%E5%8C%BB%E4%BF%9D%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6%E6%9D%A1%E4%BB%B6",
    chatHref: "/chat?question=%E5%8C%BB%E4%BF%9D%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6%E6%9D%A1%E4%BB%B6%E5%BA%94%E5%A6%82%E4%BD%95%E6%A0%B8%E9%AA%8C%EF%BC%9F"
  },
  {
    id: "doc-risk-negative-list",
    title: "医保基金风险负面清单",
    kind: "知识库文档",
    libraryName: "系统医保审计知识库",
    owner: "内审部",
    updatedAt: "2026-06-10",
    status: "只读",
    summary: "沉淀高风险收费、身份异常和基金支付异常线索。",
    href: "/knowledge-query?q=%E9%A3%8E%E9%99%A9%E8%B4%9F%E9%9D%A2%E6%B8%85%E5%8D%95",
    chatHref: "/chat?question=%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E9%A3%8E%E9%99%A9%E8%B4%9F%E9%9D%A2%E6%B8%85%E5%8D%95%E5%A6%82%E4%BD%95%E7%94%A8%E4%BA%8E%E5%AE%A1%E8%AE%A1%E7%96%91%E7%82%B9%EF%BC%9F"
  }
];

export const graphNodes: readonly GraphNode[] = [
  {
    id: "graph-node-project",
    label: "专项自查项目",
    kind: "项目",
    status: "已归集",
    description: "医保基金使用合规专项自查，承载当前审计主题、成员和工作流。",
    metric: "3 名成员",
    href: "/projects",
    x: 100,
    y: 250
  },
  {
    id: "graph-node-kb",
    label: "系统知识库",
    kind: "知识库",
    status: "可引用",
    description: "法规政策、医保目录、监管两库和风险负面清单的统一知识底座。",
    metric: "48,985 篇",
    href: "/knowledge-base",
    x: 260,
    y: 130
  },
  {
    id: "graph-node-document",
    label: "目录限制资料包",
    kind: "文档",
    status: "可引用",
    description: "用于限定诊疗项目、药品编码、支付范围和限制条件的可审证材料。",
    metric: "2 份引用",
    href: "/documents",
    x: 430,
    y: 130
  },
  {
    id: "graph-node-rule",
    label: "重复收费规则",
    kind: "规则",
    status: "已归集",
    description: "围绕同就诊、同项目、同日期和同金额线索形成规则命中条件。",
    metric: "CHARGE-RULE-001",
    href: "/rules",
    x: 600,
    y: 130
  },
  {
    id: "graph-node-finding",
    label: "疑点 F044",
    kind: "疑点",
    status: "待复核",
    description: "由收费明细和规则运行生成的重复收费疑点，等待人工核验。",
    metric: "2 条记录",
    href: "/findings",
    x: 790,
    y: 250
  },
  {
    id: "graph-node-review",
    label: "复核任务 0007",
    kind: "复核",
    status: "门禁中",
    description: "沉淀负责人确认、附件和人工判断，决定是否进入报告。",
    metric: "负责人确认",
    href: "/pages/review-tasks",
    x: 600,
    y: 370
  },
  {
    id: "graph-node-report",
    label: "报告草稿",
    kind: "报告",
    status: "门禁中",
    description: "从已复核疑点和引用材料生成的底稿与报告记录。",
    metric: "1 份草稿",
    href: "/reports",
    x: 430,
    y: 370
  },
  {
    id: "graph-node-remediation",
    label: "整改跟踪",
    kind: "整改",
    status: "跟踪中",
    description: "报告签发后进入整改责任、状态跟踪和后续归档链路。",
    metric: "1 项跟踪",
    href: "/remediation",
    x: 260,
    y: 370
  }
];

export const graphRelations: readonly GraphRelation[] = [
  {
    id: "graph-project-kb",
    sourceId: "graph-node-project",
    targetId: "graph-node-kb",
    source: "医保基金使用合规专项自查",
    relation: "引用",
    target: "系统医保审计知识库",
    evidence: "项目知识库绑定 · system-kb",
    strength: "强"
  },
  {
    id: "graph-kb-document",
    sourceId: "graph-node-kb",
    targetId: "graph-node-document",
    source: "系统医保审计知识库",
    relation: "产出",
    target: "医保目录限制条件资料包",
    evidence: "medical-insurance-catalog · 2 refs",
    strength: "强"
  },
  {
    id: "graph-document-rule",
    sourceId: "graph-node-document",
    targetId: "graph-node-rule",
    source: "医保目录限制条件资料包",
    relation: "约束",
    target: "重复收费规则",
    evidence: "支付范围和限制条件交叉核验",
    strength: "中"
  },
  {
    id: "graph-rule-finding",
    sourceId: "graph-node-rule",
    targetId: "graph-node-finding",
    source: "重复收费规则",
    relation: "命中",
    target: "FINDING-F044EBD309B659DC",
    evidence: "charge_detail · 2 records",
    strength: "强"
  },
  {
    id: "graph-finding-task",
    sourceId: "graph-node-finding",
    targetId: "graph-node-review",
    source: "FINDING-F044EBD309B659DC",
    relation: "生成",
    target: "review-task-0007",
    evidence: "rule_version CHARGE-RULE-001@v1",
    strength: "强"
  },
  {
    id: "graph-task-report",
    sourceId: "graph-node-review",
    targetId: "graph-node-report",
    source: "review-task-0007",
    relation: "进入",
    target: "报告草稿",
    evidence: "负责人确认和附件门禁",
    strength: "中"
  },
  {
    id: "graph-report-remediation",
    sourceId: "graph-node-report",
    targetId: "graph-node-remediation",
    source: "报告草稿",
    relation: "形成",
    target: "整改跟踪",
    evidence: "底稿结论、责任科室和整改期限",
    strength: "待补"
  },
  {
    id: "graph-remediation-project",
    sourceId: "graph-node-remediation",
    targetId: "graph-node-project",
    source: "整改跟踪",
    relation: "回写",
    target: "医保基金使用合规专项自查",
    evidence: "整改状态进入项目归档前检查",
    strength: "待补"
  }
];

export const reportEntries: readonly ReportEntry[] = [
  {
    id: "report-duplicate-charge",
    title: "同就诊同项目重复收费复核报告",
    status: "已签发",
    reportNo: "AUDIT-REPORT-20260611-001",
    owner: "项目负责人",
    source: "review-task-0007",
    includedFindingCount: 1,
    appendixCount: 4,
    gateSummary: "正式报告已签发，正文 sha256 已冻结。",
    updatedAt: "2026-06-11",
    href: "/pages/review-tasks"
  },
  {
    id: "report-policy-evidence",
    title: "医保基金异常收费证据核验底稿",
    status: "门禁阻断",
    reportNo: "WORKPAPER-20260611-002",
    owner: "审计员",
    source: "review-task-0002",
    includedFindingCount: 0,
    appendixCount: 1,
    gateSummary: "缺少负责人确认，不得进入正式报告。",
    updatedAt: "2026-06-11",
    href: "/pages/review-tasks"
  },
  {
    id: "report-catalog-limit",
    title: "目录限制专项复核摘要",
    status: "草稿",
    reportNo: "WORKPAPER-20260610-003",
    owner: "业务专家",
    source: "对话审证",
    includedFindingCount: 2,
    appendixCount: 2,
    gateSummary: "已形成底稿草稿，待补附件清单和负责人确认。",
    updatedAt: "2026-06-10",
    href: "/pages/review-tasks"
  }
];

export const reportGateItems: readonly ReportGateItem[] = [
  {
    id: "gate-confirmed-findings",
    label: "确认违规明细",
    status: "通过",
    detail: "仅纳入已人工确认的疑点，不把 AI 草稿写入正式正文。",
    owner: "审计员"
  },
  {
    id: "gate-review-closed",
    label: "复核任务闭合",
    status: "通过",
    detail: "review-task-0007 已完成复核结论和承办人记录。",
    owner: "审计员"
  },
  {
    id: "gate-workpaper",
    label: "底稿与负责人确认",
    status: "待人工确认",
    detail: "底稿编号已生成，正式签发前仍需负责人复核确认。",
    owner: "项目负责人"
  },
  {
    id: "gate-attachments",
    label: "附件登记与报告草稿",
    status: "阻断",
    detail: "部分附件只登记名称，缺少归档文件校验。",
    owner: "信息科"
  },
  {
    id: "gate-rectification",
    label: "整改事项",
    status: "待人工确认",
    detail: "已生成整改请求，验收完成前不得结案。",
    owner: "项目负责人"
  }
];

export const reportEvidenceSources: readonly ReportEvidenceSource[] = [
  {
    id: "report-source-finding",
    title: "FINDING-F044EBD309B659DC",
    kind: "疑点",
    reference: "charge_detail · 2 records",
    status: "已纳入",
    href: "/findings"
  },
  {
    id: "report-source-workpaper",
    title: "workpaper-20260604-001",
    kind: "底稿",
    reference: "底稿已核对引用、原文和 HIS 凭证位置。",
    status: "已纳入",
    href: "/pages/review-tasks"
  },
  {
    id: "report-source-attachment",
    title: "收费明细复核附件",
    kind: "附件",
    reference: "附件清单已登记，归档文件仍需校验。",
    status: "待补证",
    href: "/pages/review-tasks"
  },
  {
    id: "report-source-owner",
    title: "负责人确认记录",
    kind: "负责人确认",
    reference: "报告正文、附件和负责人确认需一起核验。",
    status: "只读",
    href: "/pages/review-tasks"
  }
];

export const rectificationSummaries: readonly RectificationSummary[] = [
  {
    id: "rect-duplicate-charge",
    title: "重复收费退费与流程复核",
    department: "医保办",
    status: "整改中",
    dueDate: "2026-06-20",
    reportNo: "AUDIT-REPORT-20260611-001"
  },
  {
    id: "rect-catalog-limit",
    title: "目录限制项目收费口径复查",
    department: "财务科",
    status: "待整改",
    dueDate: "2026-06-25",
    reportNo: "WORKPAPER-20260610-003"
  }
];

export const remediationCases: readonly RemediationCase[] = [
  {
    id: "remediation-duplicate-charge",
    title: "重复收费退费与流程复核",
    department: "医保办",
    owner: "医保办",
    status: "整改中",
    dueDate: "2026-06-20",
    reportNo: "AUDIT-REPORT-20260611-001",
    sourceFinding: "FINDING-F044EBD309B659DC",
    progress: 62,
    evidenceStatus: "已提交",
    nextAction: "核验退费凭证和流程复核记录。",
    href: "/pages/review-tasks"
  },
  {
    id: "remediation-catalog-limit",
    title: "目录限制项目收费口径复查",
    department: "财务科",
    owner: "财务科",
    status: "待整改",
    dueDate: "2026-06-25",
    reportNo: "WORKPAPER-20260610-003",
    sourceFinding: "CATALOG-RULE-014",
    progress: 18,
    evidenceStatus: "待补证",
    nextAction: "补齐收费口径说明和 HIS 字段截图。",
    href: "/knowledge-query?q=%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6"
  },
  {
    id: "remediation-attachment-archive",
    title: "复核附件归档校验",
    department: "信息科",
    owner: "信息科",
    status: "待验收",
    dueDate: "2026-06-18",
    reportNo: "WORKPAPER-20260611-002",
    sourceFinding: "review-task-0002",
    progress: 82,
    evidenceStatus: "需退回",
    nextAction: "重新上传带校验值的归档文件。",
    href: "/pages/review-tasks"
  },
  {
    id: "remediation-dose-review",
    title: "门诊超量开药口径确认",
    department: "药剂科",
    owner: "药剂科",
    status: "已关闭",
    dueDate: "2026-06-15",
    reportNo: "INTERNAL-MEMO-20260609-001",
    sourceFinding: "DOSE-RULE-006",
    progress: 100,
    evidenceStatus: "已验收",
    nextAction: "已进入项目归档检查。",
    href: "/documents"
  }
];

export const remediationEvidenceRequests: readonly RemediationEvidenceRequest[] = [
  {
    id: "evidence-refund",
    title: "重复收费退费凭证",
    linkedCaseId: "remediation-duplicate-charge",
    kind: "退费凭证",
    status: "已提交",
    owner: "医保办",
    dueDate: "2026-06-18",
    detail: "退费流水、患者确认和财务复核记录已提交，等待审计验收。",
    href: "/pages/review-tasks"
  },
  {
    id: "evidence-catalog-field",
    title: "目录限制 HIS 字段截图",
    linkedCaseId: "remediation-catalog-limit",
    kind: "HIS 凭证",
    status: "待上传",
    owner: "财务科",
    dueDate: "2026-06-21",
    detail: "需补充项目编码、支付范围、限制条件和结算口径字段截图。",
    href: "/knowledge-query?q=%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6"
  },
  {
    id: "evidence-archive-hash",
    title: "附件归档文件校验值",
    linkedCaseId: "remediation-attachment-archive",
    kind: "附件归档",
    status: "需退回",
    owner: "信息科",
    dueDate: "2026-06-18",
    detail: "附件名称已登记，但缺少文件 hash 和归档位置校验。",
    href: "/pages/review-tasks"
  },
  {
    id: "evidence-owner-confirm",
    title: "整改负责人确认记录",
    linkedCaseId: "remediation-duplicate-charge",
    kind: "负责人确认",
    status: "待上传",
    owner: "项目负责人",
    dueDate: "2026-06-20",
    detail: "报告签发后的整改责任确认需与验收意见一起留痕。",
    href: "/reports"
  }
];

export const remediationClosureGates: readonly RemediationClosureGate[] = [
  {
    id: "remediation-gate-evidence",
    label: "补证材料完整",
    status: "阻断",
    detail: "附件归档缺少文件 hash，目录限制字段仍未上传。",
    owner: "信息科"
  },
  {
    id: "remediation-gate-owner",
    label: "责任科室确认",
    status: "待人工确认",
    detail: "医保办已提交退费凭证，仍需项目负责人确认闭环意见。",
    owner: "项目负责人"
  },
  {
    id: "remediation-gate-review",
    label: "审计验收结论",
    status: "待人工确认",
    detail: "整改说明不能自动关闭，必须由审计员记录验收结论。",
    owner: "审计员"
  },
  {
    id: "remediation-gate-archive",
    label: "归档前检查",
    status: "通过",
    detail: "已关闭事项可进入项目档案，未关闭事项继续留在整改台账。",
    owner: "信息科"
  }
];

export const remediationTimeline: readonly RemediationTimelineItem[] = [
  {
    id: "timeline-report-issued",
    time: "2026-06-11 15:40",
    title: "报告签发后生成整改事项",
    detail: "AUDIT-REPORT-20260611-001 形成重复收费退费与流程复核整改事项。",
    status: "已记录"
  },
  {
    id: "timeline-refund-evidence",
    time: "2026-06-12 09:15",
    title: "医保办提交退费凭证",
    detail: "退费流水和财务复核记录已进入验收队列。",
    status: "已记录"
  },
  {
    id: "timeline-attachment-blocked",
    time: "2026-06-12 11:20",
    title: "附件归档校验阻断",
    detail: "系统发现附件只有登记名称，缺少文件 hash 和归档位置。",
    status: "已阻断"
  },
  {
    id: "timeline-catalog-pending",
    time: "2026-06-12 14:05",
    title: "目录限制字段待补",
    detail: "财务科需补充 HIS 字段截图和收费口径说明。",
    status: "待处理"
  }
];

export const archivePackages: readonly ArchivePackage[] = [
  {
    id: "archive-package-fund-self-check",
    projectName: "医保基金使用合规专项自查",
    archiveNo: "ARCHIVE-SELF-CHECK-FUND-202606",
    status: "归档前检查",
    reportNo: "AUDIT-REPORT-20260611-001",
    owner: "项目负责人",
    archiveScope: "报告正文、整改事项、复核附件和审计日志索引。",
    evidenceSummary: "1 项整改门禁仍阻断，等待附件 hash 和目录限制字段。",
    signedAt: "2026-06-11",
    retainedUntil: "2026-12-09",
    href: "/reports",
    logHref: "/pages/audit-logs?entity_type=review-task&entity_id=review-task-0001"
  },
  {
    id: "archive-package-kb-governance",
    projectName: "审计知识库治理项目",
    archiveNo: "ARCHIVE-KB-GOV-202606",
    status: "已归档",
    reportNo: "INTERNAL-MEMO-20260609-001",
    owner: "信息科接口人",
    archiveScope: "知识库索引、文档入库、规则发布和巡检记录。",
    evidenceSummary: "签名 manifest 可验，archive root 巡检通过。",
    signedAt: "2026-06-10",
    retainedUntil: "2026-12-07",
    href: "/projects",
    logHref: "/pages/audit-logs?entity_type=project&entity_id=KB-GOVERNANCE-202606"
  },
  {
    id: "archive-package-dose-review",
    projectName: "门诊超量开药专项复核",
    archiveNo: "ARCHIVE-DOSE-202606",
    status: "待归档",
    reportNo: "WORKPAPER-20260610-003",
    owner: "审计员",
    archiveScope: "复核底稿、处方分析、人工确认记录。",
    evidenceSummary: "底稿草稿可导出，负责人确认仍待补。",
    signedAt: "未签发",
    retainedUntil: "待签发后计算",
    href: "/reports",
    logHref: "/pages/audit-logs?entity_type=review-task&entity_id=review-task-0007"
  },
  {
    id: "archive-package-catalog-limit",
    projectName: "医保目录限制条件核验",
    archiveNo: "ARCHIVE-CATALOG-LIMIT-202606",
    status: "材料阻断",
    reportNo: "WORKPAPER-20260611-002",
    owner: "业务专家",
    archiveScope: "规则命中、HIS 字段截图、整改验收和引用来源。",
    evidenceSummary: "目录限制 HIS 字段截图缺失，不能进入长期归档。",
    signedAt: "未签发",
    retainedUntil: "待补证后计算",
    href: "/remediation",
    logHref: "/pages/audit-logs?entity_type=rule&entity_id=CATALOG-RULE-014"
  }
];

export const archiveAuditRuns: readonly ArchiveAuditRun[] = [
  {
    id: "archive-run-root-audit",
    title: "archive root 巡检",
    status: "通过",
    time: "2026-06-12 03:17",
    archiveRoot: "/opt/medical-audit/audit-log-archive",
    manifestCount: 0,
    failedCount: 0,
    detail: "latest JSON 报告 status=pass，当前没有失败 manifest。"
  },
  {
    id: "archive-run-retention-plan",
    title: "保留期归档计划",
    status: "待人工确认",
    time: "2026-06-12 02:40",
    archiveRoot: "audit_log_events",
    manifestCount: 1,
    failedCount: 0,
    detail: "180 天外事件必须先 dry-run，再显式执行归档清理。"
  },
  {
    id: "archive-run-alert-webhook",
    title: "外部告警端点",
    status: "待配置",
    time: "配置后启用",
    archiveRoot: "MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL",
    manifestCount: 0,
    failedCount: 0,
    detail: "未配置 webhook 时只能依赖 cron 退出码和 latest 报告排查。"
  }
];

export const archiveSignatureItems: readonly ArchiveSignatureItem[] = [
  {
    id: "archive-signature-retention-batch",
    label: "retention-batch-0001.jsonl",
    status: "验签通过",
    sha256: "e7c4a6b2c41f0b1a9f7d2e3a6b8c9d01",
    detail: "归档文件、archive_sha256 和 detached HMAC-SHA256 manifest 一致。"
  },
  {
    id: "archive-signature-latest-report",
    label: "audit-log-archive-audit-latest.json",
    status: "已生成",
    sha256: "latest-report-managed-by-cron",
    detail: "巡检脚本维护 latest 报告，用于生产只读排查。"
  },
  {
    id: "archive-signature-case-file",
    label: "case-level-remediation-archive",
    status: "待生成",
    sha256: "等待整改验收后生成",
    detail: "案件级整改归档流仍是后续范围，首期只读展示阻断原因。"
  }
];

export const archivePolicyItems: readonly ArchivePolicyItem[] = [
  {
    id: "archive-policy-roles",
    label: "允许角色",
    value: "it-admin / department-head",
    detail: "审计日志查询和导出必须通过角色校验。"
  },
  {
    id: "archive-policy-retention",
    label: "保留周期",
    value: "180 days",
    detail: "保留期外事件归档后再清理数据库记录。"
  },
  {
    id: "archive-policy-redaction",
    label: "脱敏模式",
    value: "response-only",
    detail: "API 响应和导出结果对敏感字段脱敏，原始归档受控保存。"
  },
  {
    id: "archive-policy-layout",
    label: "受控目录",
    value: "audit-log-events/YYYY/MM/DD/<batch-key>.jsonl",
    detail: "归档输出和签名 manifest 不得逃出 archive root。"
  }
];

export const archiveTimeline: readonly ArchiveTimelineItem[] = [
  {
    id: "archive-timeline-cron",
    time: "2026-06-05 03:17",
    title: "归档巡检 cron 生效",
    detail: "腾讯云生产环境每天执行只读 archive root 巡检。",
    status: "已部署"
  },
  {
    id: "archive-timeline-kb",
    time: "2026-06-10 16:30",
    title: "知识库治理项目入档",
    detail: "索引治理、规则发布和巡检证据已进入项目档案。",
    status: "已入档"
  },
  {
    id: "archive-timeline-report",
    time: "2026-06-11 15:40",
    title: "报告签发生成档案包",
    detail: "AUDIT-REPORT-20260611-001 进入归档前检查。",
    status: "已记录"
  },
  {
    id: "archive-timeline-blocked",
    time: "2026-06-12 11:20",
    title: "附件 hash 阻断归档",
    detail: "缺少附件 hash 和归档位置，不能进入长期保存。",
    status: "待补证"
  }
];
