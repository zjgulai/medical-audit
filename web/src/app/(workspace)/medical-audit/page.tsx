"use client";

import { useEffect, useMemo, useState } from "react";

import {
  addMedicalAuditFindingToReport,
  createMedicalAuditReviewTask,
  fetchAuditFindings,
  fetchDocumentSourceCollections,
  fetchProjectDashboard,
  fetchProjects,
  fetchReportWorkbench,
  recordMedicalAuditImportPreflight,
  registerMedicalAuditSupplement,
  updateMedicalAuditReviewStatus
} from "@/lib/api-client";
import { DEFAULT_AUDIT_PROJECT_KEY } from "@/lib/audit-user";
import type {
  AuditFinding as BackendAuditFinding,
  AuditFindingsResponse,
  DocumentSourceCollectionCatalogItem,
  DocumentSourceCollectionCatalogResponse,
  MedicalAuditWorkflowActionResponse,
  ProjectDashboardResponse,
  ProjectSummaryApiItem,
  ProjectsResponse,
  ReportWorkbenchResponse,
  WorkpaperTemplateRegistryItem
} from "@/lib/api-types";

type AuditView = "audit" | "table1" | "table2" | "table3";
type ToolId = "audit" | "dip" | "code" | "price" | "rule" | "setting";
type RuleFilter = "all" | "policy" | "manage" | "medical" | "dip" | "code" | "price";
type RiskFilter = "全部风险" | "高风险" | "中风险" | "低风险";
type WorkflowKind = "new-task" | "import" | "review" | "report" | "settings";

type LoadState<T> =
  | { readonly status: "loading" }
  | { readonly status: "ready"; readonly data: T }
  | { readonly status: "error"; readonly message: string };

type WorkflowDialog = {
  readonly kind: WorkflowKind;
  readonly finding?: BackendAuditFinding | null;
};

type WorkflowActionState =
  | { readonly status: "idle" }
  | { readonly status: "running"; readonly message: string }
  | { readonly status: "success"; readonly message: string; readonly response?: MedicalAuditWorkflowActionResponse }
  | { readonly status: "error"; readonly message: string };

type TemplateConfig = {
  readonly id: AuditView;
  readonly title: string;
  readonly description: string;
  readonly keywords: readonly string[];
  readonly fallbackColumns: readonly string[];
};

const toolModules: readonly { id: ToolId; label: string; symbol: string }[] = [
  { id: "audit", label: "智能审计", symbol: "审" },
  { id: "dip", label: "DIP/DRG审计", symbol: "分" },
  { id: "code", label: "编码质量", symbol: "码" },
  { id: "price", label: "价格合规", symbol: "费" },
  { id: "rule", label: "两库规则", symbol: "库" },
  { id: "setting", label: "任务配置", symbol: "设" }
];

const viewTabs: readonly { id: AuditView; label: string }[] = [
  { id: "audit", label: "智能审计" },
  { id: "table1", label: "费用汇总表" },
  { id: "table2", label: "分类汇总表" },
  { id: "table3", label: "就诊明细表" }
];

const ruleTabs: readonly { id: RuleFilter; label: string }[] = [
  { id: "all", label: "全部疑点" },
  { id: "policy", label: "政策类" },
  { id: "manage", label: "管理类" },
  { id: "medical", label: "医疗类" },
  { id: "dip", label: "DIP/DRG" },
  { id: "code", label: "编码质量" },
  { id: "price", label: "价格合规" }
];

const toolRuleFilters: Partial<Record<ToolId, RuleFilter>> = {
  audit: "all",
  dip: "dip",
  code: "code",
  price: "price",
  rule: "all"
};

const riskOptions: readonly RiskFilter[] = ["全部风险", "高风险", "中风险", "低风险"];

const statusLabelFallback: Record<string, string> = {
  "pending-review": "待复核",
  "needs-evidence": "需补证",
  "confirmed-violation": "确认违规",
  "not-violation": "排除违规",
  closed: "已关闭"
};

const readinessStatusLabels: Record<string, string> = {
  blocked: "疑点生成链路未就绪",
  "ready-to-run": "规则运行待执行",
  generated: "疑点已生成"
};

const templateConfigs: Record<Exclude<AuditView, "audit">, TemplateConfig> = {
  table1: {
    id: "table1",
    title: "医保费用汇总表",
    description: "用于承接医保费用总量、基金支付和个人支付的批量导入结果。",
    keywords: ["费用汇总", "summary", "table1", "表1"],
    fallbackColumns: ["机构编码", "机构名称", "就诊人次", "总费用", "基金支付", "个人支付", "结算月份"]
  },
  table2: {
    id: "table2",
    title: "医保费用分类汇总表",
    description: "用于按费用类型、项目类别和支付类型归集导入后的分类统计。",
    keywords: ["分类汇总", "category", "table2", "表2"],
    fallbackColumns: ["费用类别", "项目数量", "总费用", "统筹支付", "账户支付", "现金支付", "占比"]
  },
  table3: {
    id: "table3",
    title: "就诊费用明细表",
    description: "用于承接逐人逐次就诊费用明细，后续疑点规则从明细表生成。",
    keywords: ["就诊费用", "明细", "detail", "table3", "表3"],
    fallbackColumns: ["就诊流水号", "姓名", "证件号", "诊断", "项目名称", "医保编码", "数量", "金额"]
  }
};

function formatCurrency(amount: number | null): string {
  if (amount == null || Number.isNaN(amount)) {
    return "-";
  }
  return `¥${amount.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString("zh-CN");
}

function asString(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
}

function stringifyShort(value: unknown): string {
  const text = asString(value);
  if (text) {
    return text;
  }
  if (value == null) {
    return "-";
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function firstRecordValue(record: Record<string, unknown>, keys: readonly string[]): string | null {
  for (const key of keys) {
    const value = asString(record[key]);
    if (value) {
      return value;
    }
  }
  return null;
}

function humanizeKey(value: string | null | undefined): string {
  if (!value) {
    return "未标注";
  }
  return value.replaceAll("_", " ").replaceAll("-", " ");
}

function findingTitle(finding: BackendAuditFinding): string {
  return (
    firstRecordValue(finding.metadata, ["title", "display_name", "rule_name", "description"]) ??
    humanizeKey(finding.rule_key ?? finding.finding_type)
  );
}

function findingSubject(finding: BackendAuditFinding): string {
  return (
    firstRecordValue(finding.metadata, ["subject", "item_name", "patient_name", "hospital_name"]) ??
    firstRecordValue(finding.source_record_locator, ["source_table", "table", "record_no", "visit_id"]) ??
    finding.finding_key
  );
}

function findingDepartment(finding: BackendAuditFinding): string {
  return (
    firstRecordValue(finding.metadata, ["department", "dept_name", "org_name", "institution_name"]) ??
    "待映射"
  );
}

function findingAmount(finding: BackendAuditFinding): number | null {
  const keys = ["amount", "total_amount", "fee_amount", "violation_amount", "claim_amount"];
  for (const key of keys) {
    const raw = finding.calculation_trace[key] ?? finding.metadata[key];
    if (typeof raw === "number" && Number.isFinite(raw)) {
      return raw;
    }
    if (typeof raw === "string") {
      const parsed = Number(raw.replaceAll(",", ""));
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }
  return null;
}

function riskLabelFromSeverity(severity: string): Exclude<RiskFilter, "全部风险"> {
  if (severity === "critical" || severity === "high") {
    return "高风险";
  }
  if (severity === "medium") {
    return "中风险";
  }
  return "低风险";
}

function riskClassFromSeverity(severity: string): string {
  if (severity === "critical" || severity === "high") {
    return "is-high";
  }
  if (severity === "medium") {
    return "is-medium";
  }
  return "is-low";
}

function statusClassFromReviewStatus(status: string): string {
  if (status === "confirmed-violation") {
    return "is-danger";
  }
  if (status === "pending-review" || status === "needs-evidence") {
    return "is-medium";
  }
  if (status === "closed") {
    return "is-low";
  }
  return "is-muted";
}

function statusLabel(options: Record<string, string>, status: string): string {
  return options[status] ?? statusLabelFallback[status] ?? humanizeKey(status);
}

function ruleMatchesFilter(finding: BackendAuditFinding, activeRule: RuleFilter): boolean {
  if (activeRule === "all") {
    return true;
  }
  const haystack = [
    finding.finding_type,
    finding.rule_key,
    finding.rule_version_key,
    stringifyShort(finding.metadata),
    stringifyShort(finding.calculation_trace)
  ]
    .join(" ")
    .toLowerCase();

  if (activeRule === "policy") {
    return /policy|目录|医保|药品|支付|限制/.test(haystack);
  }
  if (activeRule === "manage") {
    return /manage|management|管理|篡改|虚假|分解/.test(haystack);
  }
  if (activeRule === "medical") {
    return /medical|诊疗|耗材|诊断|手术|护理/.test(haystack);
  }
  if (activeRule === "dip") {
    return /dip|drg|分值|病组|入组/.test(haystack);
  }
  if (activeRule === "code") {
    return /code|编码|icd|医保编码/.test(haystack);
  }
  return /price|价格|收费|费用|金额/.test(haystack);
}

function searchMatches(finding: BackendAuditFinding, query: string): boolean {
  if (!query.trim()) {
    return true;
  }
  const text = [
    finding.finding_key,
    finding.finding_type,
    finding.rule_key,
    findingSubject(finding),
    findingTitle(finding),
    stringifyShort(finding.source_record_locator),
    stringifyShort(finding.metadata)
  ]
    .join(" ")
    .toLowerCase();
  return text.includes(query.trim().toLowerCase());
}

function sourceCollectionsForMedical(
  response: DocumentSourceCollectionCatalogResponse | null
): readonly DocumentSourceCollectionCatalogItem[] {
  return (response?.items ?? [])
    .filter((item) => item.queryable || item.product_queryable)
    .filter((item) => /medical|医保|审计|监管|目录|政策/.test(`${item.domain} ${item.label} ${item.description}`));
}

function selectMedicalAuditProject(projects: readonly ProjectSummaryApiItem[]): ProjectSummaryApiItem | null {
  return (
    projects.find((project) => project.id === DEFAULT_AUDIT_PROJECT_KEY) ??
    projects.find((project) => /医保|医疗|基金/.test(`${project.name} ${project.audit_topic}`)) ??
    projects[0] ??
    null
  );
}

function metricValueFromState<T>(state: LoadState<T>, selector: (data: T) => number | string): string {
  if (state.status === "loading") {
    return "...";
  }
  if (state.status === "error") {
    return "异常";
  }
  return String(selector(state.data));
}

function templateForView(
  view: Exclude<AuditView, "audit">,
  templates: readonly WorkpaperTemplateRegistryItem[]
): WorkpaperTemplateRegistryItem | null {
  const config = templateConfigs[view];
  return (
    templates.find((template) => {
      const haystack = [
        template.name,
        template.source_template_id,
        template.source_table,
        template.source_file_name,
        template.sheet_name
      ]
        .join(" ")
        .toLowerCase();
      return config.keywords.some((keyword) => haystack.includes(keyword.toLowerCase()));
    }) ?? null
  );
}

function buildChatHref(finding: BackendAuditFinding | null, sourceCollections: readonly string[]): string {
  const params = new URLSearchParams();
  const question = finding
    ? `请基于医保审计知识库，分析疑点 ${finding.finding_key}：${findingTitle(finding)}，并给出复核建议。`
    : "请基于医保审计知识库，分析当前审计疑点并给出下一步复核建议。";
  params.set("question", question);
  for (const sourceCollection of sourceCollections.slice(0, 5)) {
    params.append("source_collection", sourceCollection);
  }
  return `/chat?${params.toString()}`;
}

function workflowSuccessMessage(
  dialog: WorkflowDialog,
  response: MedicalAuditWorkflowActionResponse | undefined
): string {
  const taskId = response?.task?.task_id;
  if (dialog.kind === "new-task") {
    return taskId ? `复核任务已关联：${taskId}` : "复核任务已提交。";
  }
  if (dialog.kind === "import") {
    return dialog.finding ? "补充材料登记已写入任务 dossier。" : "导入预检已记录，等待正式上传解析。";
  }
  if (dialog.kind === "review") {
    return taskId ? `复核状态已更新：${taskId}` : "复核状态已更新。";
  }
  if (dialog.kind === "report") {
    return taskId ? `疑点已纳入报告草稿：${taskId}` : "疑点已纳入报告草稿。";
  }
  return "配置入口检查已记录。";
}

export default function MedicalAuditPage() {
  const [activeTool, setActiveTool] = useState<ToolId>("audit");
  const [activeView, setActiveView] = useState<AuditView>("audit");
  const [activeRule, setActiveRule] = useState<RuleFilter>("all");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("全部风险");
  const [reviewStatus, setReviewStatus] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedKeys, setSelectedKeys] = useState<ReadonlySet<string>>(new Set());
  const [selectedFindingKey, setSelectedFindingKey] = useState<string | null>(null);
  const [workflowDialog, setWorkflowDialog] = useState<WorkflowDialog | null>(null);
  const [workflowActionState, setWorkflowActionState] = useState<WorkflowActionState>({ status: "idle" });
  const [isAiOpen, setIsAiOpen] = useState(false);

  const [auditState, setAuditState] = useState<LoadState<AuditFindingsResponse>>({
    status: "loading"
  });
  const [sourceState, setSourceState] = useState<LoadState<DocumentSourceCollectionCatalogResponse>>({
    status: "loading"
  });
  const [reportState, setReportState] = useState<LoadState<ReportWorkbenchResponse>>({
    status: "loading"
  });
  const [projectState, setProjectState] = useState<LoadState<ProjectsResponse>>({
    status: "loading"
  });
  const [dashboardState, setDashboardState] = useState<LoadState<ProjectDashboardResponse>>({
    status: "loading"
  });

  useEffect(() => {
    let cancelled = false;
    setAuditState({ status: "loading" });
    fetchAuditFindings(reviewStatus || undefined)
      .then((data) => {
        if (cancelled) {
          return;
        }
        setAuditState({ status: "ready", data });
        setSelectedFindingKey((current) => current ?? data.items[0]?.finding_key ?? null);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setAuditState({
            status: "error",
            message: error instanceof Error ? error.message : "医保审计疑点接口读取异常"
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reviewStatus]);

  useEffect(() => {
    let cancelled = false;
    fetchDocumentSourceCollections()
      .then((data) => {
        if (!cancelled) {
          setSourceState({ status: "ready", data });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setSourceState({
            status: "error",
            message: error instanceof Error ? error.message : "知识库分类接口读取异常"
          });
        }
      });

    fetchReportWorkbench()
      .then((data) => {
        if (!cancelled) {
          setReportState({ status: "ready", data });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setReportState({
            status: "error",
            message: error instanceof Error ? error.message : "报告工作台接口读取异常"
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setProjectState({ status: "loading" });
    setDashboardState({ status: "loading" });
    fetchProjects()
      .then((projects) => {
        if (cancelled) {
          return;
        }
        setProjectState({ status: "ready", data: projects });
        const project = selectMedicalAuditProject(projects.items);
        if (!project) {
          setDashboardState({
            status: "error",
            message: "当前没有可关联的审计专题项目"
          });
          return;
        }
        return fetchProjectDashboard(project.id)
          .then((dashboard) => {
            if (!cancelled) {
              setDashboardState({ status: "ready", data: dashboard });
            }
          })
          .catch((error: unknown) => {
            if (!cancelled) {
              setDashboardState({
                status: "error",
                message: error instanceof Error ? error.message : "专题驾驶舱接口读取异常"
              });
            }
          });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "审计专题项目接口读取异常";
          setProjectState({ status: "error", message });
          setDashboardState({ status: "error", message: "专题驾驶舱等待项目数据恢复" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const auditData = auditState.status === "ready" ? auditState.data : null;
  const sourceData = sourceState.status === "ready" ? sourceState.data : null;
  const statusOptions = auditData?.review_status_options ?? statusLabelFallback;
  const activeProject =
    projectState.status === "ready" ? selectMedicalAuditProject(projectState.data.items) : null;
  const medicalSources = useMemo(() => sourceCollectionsForMedical(sourceData), [sourceData]);
  const sourceKeys = useMemo(
    () => medicalSources.map((source) => source.source_collection),
    [medicalSources]
  );

  const filteredFindings = useMemo(() => {
    const items = auditData?.items ?? [];
    return items.filter((finding) => {
      if (!ruleMatchesFilter(finding, activeRule)) {
        return false;
      }
      if (riskFilter !== "全部风险" && riskLabelFromSeverity(finding.severity) !== riskFilter) {
        return false;
      }
      if (!searchMatches(finding, searchQuery)) {
        return false;
      }
      return true;
    });
  }, [activeRule, auditData, riskFilter, searchQuery]);

  const selectedFinding = useMemo(
    () =>
      filteredFindings.find((finding) => finding.finding_key === selectedFindingKey) ??
      filteredFindings[0] ??
      null,
    [filteredFindings, selectedFindingKey]
  );

  const toolBadges = useMemo(() => {
    const items = auditData?.items ?? [];
    const badges: Record<ToolId, string> = {
      audit: String(auditData?.stats.total ?? 0),
      dip: String(items.filter((finding) => ruleMatchesFilter(finding, "dip")).length),
      code: String(items.filter((finding) => ruleMatchesFilter(finding, "code")).length),
      price: String(items.filter((finding) => ruleMatchesFilter(finding, "price")).length),
      rule: String(medicalSources.length),
      setting: ""
    };
    return badges;
  }, [auditData, medicalSources.length]);

  const selectedCount = selectedKeys.size;

  async function refreshWorkflowData() {
    const [audit, report] = await Promise.all([
      fetchAuditFindings(reviewStatus || undefined),
      fetchReportWorkbench()
    ]);
    setAuditState({ status: "ready", data: audit });
    setReportState({ status: "ready", data: report });
    setSelectedFindingKey((current) => current ?? audit.items[0]?.finding_key ?? null);
  }

  function findingKeysForDialog(dialog: WorkflowDialog): readonly string[] {
    if (dialog.finding) {
      return [dialog.finding.finding_key];
    }
    const selected = Array.from(selectedKeys);
    if (selected.length > 0) {
      return selected;
    }
    return selectedFinding ? [selectedFinding.finding_key] : [];
  }

  async function handleWorkflowConfirm(dialog: WorkflowDialog) {
    setWorkflowActionState({ status: "running", message: "正在提交到后端流程..." });
    try {
      let response: MedicalAuditWorkflowActionResponse | undefined;
      if (dialog.kind === "new-task") {
        const target = dialog.finding ?? selectedFinding;
        if (!target) {
          throw new Error("请先选择一个疑点，再创建复核任务。");
        }
        response = await createMedicalAuditReviewTask(target.finding_key, {
          note: "从医保审计工作台创建复核任务"
        });
      } else if (dialog.kind === "import") {
        if (dialog.finding) {
          response = await registerMedicalAuditSupplement(dialog.finding.finding_key, {
            title: "补充材料登记",
            locator: stringifyShort(dialog.finding.source_record_locator),
            note: "从医保审计详情页登记补充材料入口，等待正式文件上传。"
          });
        } else {
          const template = activeView === "audit" ? templateConfigs.table1 : templateConfigs[activeView];
          response = await recordMedicalAuditImportPreflight({
            template_id: template.id,
            template_name: template.title,
            file_name: null,
            row_count: null,
            note: "医保审计页面触发导入预检，等待上传与字段映射。"
          });
        }
      } else if (dialog.kind === "review") {
        const keys = findingKeysForDialog(dialog);
        if (keys.length === 0) {
          throw new Error("请先选择疑点，再执行复核动作。");
        }
        const responses = await Promise.all(
          keys.map((key) =>
            updateMedicalAuditReviewStatus(key, {
              status: "confirmed-violation",
              reviewer_note: "已通过医保审计工作台完成初步复核，证据链进入报告准备。",
              conclusion: "确认该疑点需纳入后续底稿或报告流程。"
            })
          )
        );
        response = responses[responses.length - 1];
      } else if (dialog.kind === "report") {
        const keys = findingKeysForDialog(dialog);
        if (keys.length === 0) {
          throw new Error("请先选择疑点，再加入报告。");
        }
        const responses = await Promise.all(
          keys.map((key) =>
            addMedicalAuditFindingToReport(key, {
              report_title: `${key} 医保审计复核报告草稿`,
              summary: "由医保审计工作台纳入报告草稿，后续进入正式签发流程。",
              rectification_request: "请责任科室核对收费依据、HIS 明细和补证材料。"
            })
          )
        );
        response = responses[responses.length - 1];
      } else {
        response = await recordMedicalAuditImportPreflight({
          template_id: "medical-audit-settings",
          template_name: "医保审计任务配置",
          note: "配置入口已检查，等待规则集和人员配置写入合同。"
        });
      }
      await refreshWorkflowData();
      setWorkflowActionState({
        status: "success",
        message: workflowSuccessMessage(dialog, response),
        response
      });
      if (dialog.kind === "review" || dialog.kind === "report") {
        setSelectedKeys(new Set());
      }
    } catch (error) {
      setWorkflowActionState({
        status: "error",
        message: error instanceof Error ? error.message : "后端流程提交异常"
      });
    }
  }

  function updateTool(tool: ToolId) {
    setActiveTool(tool);
    const nextRule = toolRuleFilters[tool];
    if (nextRule) {
      setActiveRule(nextRule);
    }
    if (tool === "setting") {
      setWorkflowDialog({ kind: "settings" });
    }
  }

  function toggleFinding(key: string) {
    setSelectedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  return (
    <div className="replica-medical-page">
      <h1 className="replica-medical-sr-title">医保审计</h1>
      <MedicalStatusRail
        activeTool={activeTool}
        badges={toolBadges}
        onToolChange={updateTool}
      />
      <RuleNavigator
        activeRule={activeRule}
        medicalSources={medicalSources}
        searchQuery={searchQuery}
        sourceState={sourceState}
        onRuleChange={setActiveRule}
        onSearchChange={setSearchQuery}
      />
      <section
        className={`replica-medical-content ${selectedFinding && activeView === "audit" ? "has-drawer" : ""} ${isAiOpen ? "has-drawer" : ""}`}
      >
        <main className="replica-medical-main">
          <button
            aria-label={isAiOpen ? "关闭医保审计助手" : "打开医保审计助手"}
            className={`replica-medical-ai-fab ${isAiOpen ? "is-open is-shifted" : selectedFinding ? "is-shifted" : ""}`}
            data-layout-floating-control="medical-ai"
            type="button"
            onClick={() => setIsAiOpen((current) => !current)}
          >
            <span>AI</span>
            <strong>审计助手</strong>
          </button>
          <div className="replica-medical-tabs" role="tablist" aria-label="医保审计视图">
            {viewTabs.map((tab) => (
              <button
                aria-selected={activeView === tab.id}
                className={activeView === tab.id ? "is-active" : ""}
                key={tab.id}
                role="tab"
                type="button"
                onClick={() => setActiveView(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <details className="replica-medical-notice">
            <summary>查看数据与权限说明</summary>
            <p>页面初始加载读取生产数据；复核、报告、任务和补充材料写入仍需经过独立确认门禁。</p>
            <p>
              疑点清单来自 <code>/api/v1/audit-findings</code>，知识库分类来自{" "}
              <code>/api/v1/documents/source-collections</code>，报告模板来自{" "}
              <code>/api/v1/reports/workbench</code>，专题项目来自 <code>/api/v1/projects</code> 与{" "}
              <code>/api/v1/projects/:id/dashboard</code>。
            </p>
          </details>
          {activeView === "audit" ? (
            <SmartAuditView
              activeRule={activeRule}
              auditState={auditState}
              activeProject={activeProject}
              dashboardState={dashboardState}
              filteredFindings={filteredFindings}
              projectState={projectState}
              reportState={reportState}
              riskFilter={riskFilter}
              selectedFindingKey={selectedFinding?.finding_key ?? null}
              selectedKeys={selectedKeys}
              sourceState={sourceState}
              statusOptions={statusOptions}
              reviewStatus={reviewStatus}
              onDialog={setWorkflowDialog}
              onRiskFilterChange={setRiskFilter}
              onReviewStatusChange={setReviewStatus}
              onRuleChange={setActiveRule}
              onSelectFinding={setSelectedFindingKey}
              onToggleFinding={toggleFinding}
            />
          ) : (
            <TemplateWorkbookView
              reportState={reportState}
              view={activeView}
              onDialog={(kind) => setWorkflowDialog({ kind })}
            />
          )}
        </main>
        {activeView === "audit" && selectedFinding && !isAiOpen ? (
          <FindingDrawer
            finding={selectedFinding}
            sourceKeys={sourceKeys}
            statusOptions={statusOptions}
            onDialog={(kind, finding) => setWorkflowDialog({ kind, finding })}
            onClose={() => setSelectedFindingKey(null)}
          />
        ) : null}
        {isAiOpen ? (
          <MedicalAiDrawer
            finding={selectedFinding}
            filteredCount={filteredFindings.length}
            selectedCount={selectedCount}
            sourceKeys={sourceKeys}
            onClose={() => setIsAiOpen(false)}
          />
        ) : null}
      </section>
      <WorkflowGateDialog
        actionState={workflowActionState}
        dialog={workflowDialog}
        onClose={() => {
          setWorkflowDialog(null);
          setWorkflowActionState({ status: "idle" });
        }}
        onConfirm={handleWorkflowConfirm}
      />
    </div>
  );
}

function MedicalStatusRail({
  activeTool,
  badges,
  onToolChange
}: {
  readonly activeTool: ToolId;
  readonly badges: Record<ToolId, string>;
  readonly onToolChange: (tool: ToolId) => void;
}) {
  return (
    <aside className="replica-medical-iconrail" aria-label="医保审计工具">
      {toolModules.map((module) => (
        <button
          aria-label={module.label}
          className={activeTool === module.id ? "is-active" : ""}
          key={module.id}
          title={module.label}
          type="button"
          onClick={() => onToolChange(module.id)}
        >
          <span aria-hidden="true" className="replica-medical-tool-symbol">{module.symbol}</span>
          <span className="replica-medical-tool-label">{module.label}</span>
          {badges[module.id] ? <em>{badges[module.id]}</em> : null}
        </button>
      ))}
    </aside>
  );
}

function RuleNavigator({
  activeRule,
  medicalSources,
  searchQuery,
  sourceState,
  onRuleChange,
  onSearchChange
}: {
  readonly activeRule: RuleFilter;
  readonly medicalSources: readonly DocumentSourceCollectionCatalogItem[];
  readonly searchQuery: string;
  readonly sourceState: LoadState<DocumentSourceCollectionCatalogResponse>;
  readonly onRuleChange: (rule: RuleFilter) => void;
  readonly onSearchChange: (query: string) => void;
}) {
  return (
    <aside className="replica-medical-rules">
      <h2>审计规则与知识范围</h2>
      <label className="replica-medical-search">
        <span>搜</span>
        <input
          aria-label="搜索疑点、规则或源记录"
          placeholder="搜索疑点、规则、源记录"
          value={searchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </label>
      <nav aria-label="规则分类">
        <section>
          <button className="is-active" type="button">
            规则维度
          </button>
          <div>
            {ruleTabs.map((tab) => (
              <button
                className={activeRule === tab.id ? "is-active" : ""}
                key={tab.id}
                type="button"
                onClick={() => onRuleChange(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </section>
        <section>
          <button type="button">一级知识库</button>
          <div>
            {sourceState.status === "loading" ? <button type="button">正在加载知识库</button> : null}
            {sourceState.status === "error" ? <button type="button">知识库分类读取异常</button> : null}
            {medicalSources.slice(0, 9).map((source) => (
              <button key={source.source_collection} title={source.description} type="button">
                {source.label}
              </button>
            ))}
            {medicalSources.length > 9 ? <button type="button">其余 {medicalSources.length - 9} 个</button> : null}
          </div>
        </section>
      </nav>
    </aside>
  );
}

function SmartAuditView({
  activeRule,
  auditState,
  activeProject,
  dashboardState,
  filteredFindings,
  projectState,
  reportState,
  riskFilter,
  selectedFindingKey,
  selectedKeys,
  sourceState,
  statusOptions,
  reviewStatus,
  onDialog,
  onRiskFilterChange,
  onReviewStatusChange,
  onRuleChange,
  onSelectFinding,
  onToggleFinding
}: {
  readonly activeRule: RuleFilter;
  readonly auditState: LoadState<AuditFindingsResponse>;
  readonly activeProject: ProjectSummaryApiItem | null;
  readonly dashboardState: LoadState<ProjectDashboardResponse>;
  readonly filteredFindings: readonly BackendAuditFinding[];
  readonly projectState: LoadState<ProjectsResponse>;
  readonly reportState: LoadState<ReportWorkbenchResponse>;
  readonly riskFilter: RiskFilter;
  readonly selectedFindingKey: string | null;
  readonly selectedKeys: ReadonlySet<string>;
  readonly sourceState: LoadState<DocumentSourceCollectionCatalogResponse>;
  readonly statusOptions: Record<string, string>;
  readonly reviewStatus: string;
  readonly onDialog: (dialog: WorkflowDialog) => void;
  readonly onRiskFilterChange: (risk: RiskFilter) => void;
  readonly onReviewStatusChange: (status: string) => void;
  readonly onRuleChange: (rule: RuleFilter) => void;
  readonly onSelectFinding: (key: string) => void;
  readonly onToggleFinding: (key: string) => void;
}) {
  const auditData = auditState.status === "ready" ? auditState.data : null;
  return (
    <>
      <ProjectFlowPanel
        activeProject={activeProject}
        auditState={auditState}
        dashboardState={dashboardState}
        projectState={projectState}
      />
      <MetricCards auditState={auditState} sourceState={sourceState} reportState={reportState} />
      <div className="replica-medical-rule-tabs" role="tablist" aria-label="规则筛选">
        {ruleTabs.map((tab) => (
          <button
            aria-selected={activeRule === tab.id}
            className={activeRule === tab.id ? "is-active" : ""}
            key={tab.id}
            role="tab"
            type="button"
            onClick={() => onRuleChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="replica-medical-toolbar">
        <div>
          <label className="replica-medical-select">
            <span>风险</span>
            <select value={riskFilter} onChange={(event) => onRiskFilterChange(event.target.value as RiskFilter)}>
              {riskOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="replica-medical-select">
            <span>复核状态</span>
            <select value={reviewStatus} onChange={(event) => onReviewStatusChange(event.target.value)}>
              <option value="">全部状态</option>
              {Object.entries(statusOptions).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <span className="replica-medical-tag is-blue">当前 {filteredFindings.length} 条</span>
        </div>
        <div>
          <button
            className="replica-secondary-button"
            type="button"
            onClick={() => onDialog({ kind: "new-task" })}
          >
            新建审计任务
          </button>
          <button className="replica-primary-button" type="button" onClick={() => onDialog({ kind: "import" })}>
            批量导入
          </button>
          <button className="replica-danger-button" type="button" onClick={() => onDialog({ kind: "review" })}>
            批量复核
          </button>
        </div>
      </div>
      {auditState.status === "loading" ? (
        <section className="replica-medical-evidence is-blue">
          <strong>正在加载审计疑点</strong>
          <p>正在加载审计规则命中记录。</p>
        </section>
      ) : null}
      {auditState.status === "error" ? (
        <section className="replica-medical-evidence is-danger">
          <strong>疑点数据读取异常</strong>
          <p>请检查审计数据服务后重试；当前不会注入本地样例数据。</p>
          <details className="replica-runtime-diagnostics">
            <summary>查看技术诊断</summary>
            <code>{auditState.message}</code>
          </details>
        </section>
      ) : null}
      {auditData && auditData.items.length === 0 ? (
        <EmptyReadinessPanel readiness={auditData.generation_readiness} onDialog={onDialog} />
      ) : null}
      {auditData && auditData.items.length > 0 ? (
        <FindingsTable
          findings={filteredFindings}
          selectedFindingKey={selectedFindingKey}
          selectedKeys={selectedKeys}
          statusOptions={statusOptions}
          onDialog={onDialog}
          onSelectFinding={onSelectFinding}
          onToggleFinding={onToggleFinding}
        />
      ) : null}
    </>
  );
}

function ProjectFlowPanel({
  activeProject,
  auditState,
  dashboardState,
  projectState
}: {
  readonly activeProject: ProjectSummaryApiItem | null;
  readonly auditState: LoadState<AuditFindingsResponse>;
  readonly dashboardState: LoadState<ProjectDashboardResponse>;
  readonly projectState: LoadState<ProjectsResponse>;
}) {
  const auditData = auditState.status === "ready" ? auditState.data : null;
  const dashboardData = dashboardState.status === "ready" ? dashboardState.data : null;
  const projectStatus =
    projectState.status === "loading"
      ? "正在读取专题"
      : projectState.status === "error"
        ? "专题数据暂不可用"
        : activeProject?.status ?? "未选择专题";
  const dashboardStatus =
    dashboardState.status === "loading"
      ? "正在读取驾驶舱"
      : dashboardState.status === "error"
        ? "驾驶舱暂不可用"
        : dashboardState.data.evidence_grade;
  const projectName =
    activeProject?.name ?? (projectState.status === "error" ? "专题项目待恢复" : "医保审计专题");
  const queueItems = dashboardData?.queue.slice(0, 3) ?? [];
  const workloads = dashboardData?.member_workloads.slice(0, 3) ?? [];
  return (
    <section className="replica-medical-project-panel" aria-label="医保审计专题项目流程">
      <div className="replica-medical-project-head">
        <div>
          <span>专题项目</span>
          <h2>{projectName}</h2>
          <p>
            {activeProject?.organization_name ?? "项目数据恢复后显示机构范围"} ·{" "}
            {activeProject?.audit_topic ?? "医保审计"}
          </p>
        </div>
        <div className="replica-medical-project-status">
          <strong>{projectStatus}</strong>
          <span>{dashboardStatus}</span>
        </div>
      </div>
      <div className="replica-medical-project-flow">
        <article>
          <span>1</span>
          <strong>表格导入</strong>
          <p>{auditData?.generation_readiness.table_counts.fee_summary ?? 0} 条汇总表记录</p>
        </article>
        <article>
          <span>2</span>
          <strong>规则命中</strong>
          <p>{auditData?.stats.total ?? 0} 条生产疑点</p>
        </article>
        <article>
          <span>3</span>
          <strong>人工复核</strong>
          <p>{auditData?.stats.pending_review ?? 0} 条待复核</p>
        </article>
        <article>
          <span>4</span>
          <strong>底稿报告</strong>
          <p>{auditData?.stats.linked_review_task ?? 0} 条已关联任务</p>
        </article>
      </div>
      <div className="replica-medical-project-grid">
        <div>
          <h3>待办队列</h3>
          {dashboardState.status === "error" ? <p>{dashboardState.message}</p> : null}
          {queueItems.length > 0 ? (
            <ul>
              {queueItems.map((item) => (
                <li key={item.id}>
                  <span>{item.owner}</span>
                  <strong>{item.title}</strong>
                  <em>{item.dueLabel}</em>
                </li>
              ))}
            </ul>
          ) : (
            <p>{dashboardState.status === "loading" ? "正在同步队列..." : "暂无待办队列"}</p>
          )}
        </div>
        <div>
          <h3>人员承接</h3>
          {workloads.length > 0 ? (
            <ul>
              {workloads.map((item) => (
                <li key={`${item.name}-${item.role}`}>
                  <span>{item.role}</span>
                  <strong>{item.name}</strong>
                  <em>
                    {item.pending} 待处理 / {item.closed} 已闭环
                  </em>
                </li>
              ))}
            </ul>
          ) : (
            <p>{dashboardState.status === "loading" ? "正在同步人员..." : "暂无人员承接数据"}</p>
          )}
        </div>
      </div>
    </section>
  );
}

function MetricCards({
  auditState,
  sourceState,
  reportState
}: {
  readonly auditState: LoadState<AuditFindingsResponse>;
  readonly sourceState: LoadState<DocumentSourceCollectionCatalogResponse>;
  readonly reportState: LoadState<ReportWorkbenchResponse>;
}) {
  const auditData = auditState.status === "ready" ? auditState.data : null;
  const sourceData = sourceState.status === "ready" ? sourceState.data : null;
  const medicalSources = sourceCollectionsForMedical(sourceData);
  const readiness = auditData?.generation_readiness;
  const cards = [
    {
      label: "生产疑点总数",
      value: metricValueFromState(auditState, (data) => data.stats.total),
      tone: "blue",
      change: readinessStatusLabels[readiness?.status ?? ""] ?? readiness?.status ?? "等待同步",
      changeTone: readiness?.ready ? "down" : "up",
      sub:
        auditState.status === "ready"
          ? "疑点数据已同步"
          : auditState.status === "loading"
            ? "正在同步疑点数据"
            : "疑点数据暂未同步"
    },
    {
      label: "待处理疑点",
      value: metricValueFromState(auditState, (data) => data.stats.open),
      tone: "blue",
      change: `${auditData?.stats.pending_review ?? "-"} 待复核`,
      changeTone: "up",
      sub: `${auditData?.stats.linked_review_task ?? "-"} 条已关联任务`
    },
    {
      label: "一级知识库",
      value: metricValueFromState(sourceState, () => medicalSources.length),
      tone: "green",
      change: sourceData?.search_backend.ready ? "知识检索可用" : "知识检索待确认",
      changeTone: sourceData?.search_backend.ready ? "down" : "up",
      sub:
        sourceState.status === "ready"
          ? "知识库分类已同步"
          : sourceState.status === "loading"
            ? "正在同步知识库分类"
            : "知识库分类暂未同步"
    },
    {
      label: "报告工作台",
      value: metricValueFromState(reportState, (data) => data.metrics.report_count),
      tone: "green",
      change: reportState.status === "ready" ? `${reportState.data.metrics.included_finding_count} 条疑点已纳入` : "读取中",
      changeTone: "down",
      sub:
        reportState.status === "ready"
          ? "底稿与报告数据已同步"
          : reportState.status === "loading"
            ? "正在同步底稿与报告"
            : "底稿与报告暂未同步"
    }
  ];
  return (
    <section className="replica-medical-metrics" aria-label="医保审计生产指标">
      {cards.map((card) => (
        <article className={`tone-${card.tone}`} key={card.label}>
          <span>{card.label}</span>
          <strong>{card.value}</strong>
          <em className={card.changeTone === "down" ? "is-down" : "is-up"}>{card.change}</em>
          <p>{card.sub}</p>
        </article>
      ))}
    </section>
  );
}

function FindingsTable({
  findings,
  selectedFindingKey,
  selectedKeys,
  statusOptions,
  onDialog,
  onSelectFinding,
  onToggleFinding
}: {
  readonly findings: readonly BackendAuditFinding[];
  readonly selectedFindingKey: string | null;
  readonly selectedKeys: ReadonlySet<string>;
  readonly statusOptions: Record<string, string>;
  readonly onDialog: (dialog: WorkflowDialog) => void;
  readonly onSelectFinding: (key: string) => void;
  readonly onToggleFinding: (key: string) => void;
}) {
  if (findings.length === 0) {
    return (
      <section className="replica-medical-evidence is-blue">
        <strong>当前筛选无疑点</strong>
        <p>请调整风险、状态或规则分类筛选条件。</p>
      </section>
    );
  }
  return (
    <>
      <div className="replica-medical-data-table">
        <table>
          <thead>
            <tr>
              <th aria-label="选择">选择</th>
              <th>疑点键</th>
              <th>规则/类型</th>
              <th>源记录</th>
              <th>科室/机构</th>
              <th>涉及金额</th>
              <th>风险</th>
              <th>复核状态</th>
              <th>证据</th>
              <th>更新日期</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((finding) => (
              <tr className={selectedFindingKey === finding.finding_key ? "is-active" : ""} key={finding.finding_key}>
                <td>
                  <input
                    aria-label={`选择 ${finding.finding_key}`}
                    checked={selectedKeys.has(finding.finding_key)}
                    type="checkbox"
                    onChange={() => onToggleFinding(finding.finding_key)}
                  />
                </td>
                <td>
                  <button className="is-link-number" type="button" onClick={() => onSelectFinding(finding.finding_key)}>
                    {finding.finding_key}
                  </button>
                </td>
                <td>
                  <span className="replica-medical-dimension">{findingTitle(finding)}</span>
                </td>
                <td>{findingSubject(finding)}</td>
                <td>{findingDepartment(finding)}</td>
                <td className="is-number">{formatCurrency(findingAmount(finding))}</td>
                <td>
                  <span className={`replica-medical-tag ${riskClassFromSeverity(finding.severity)}`}>
                    {riskLabelFromSeverity(finding.severity)}
                  </span>
                </td>
                <td>
                  <span className={`replica-medical-tag ${statusClassFromReviewStatus(finding.review_status)}`}>
                    {statusLabel(statusOptions, finding.review_status)}
                  </span>
                </td>
                <td>{finding.evidence_items.length} 条</td>
                <td>{formatDate(finding.updated_at)}</td>
                <td>
                  <button type="button" onClick={() => onDialog({ kind: "review", finding })}>
                    复核
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="replica-medical-pagination">
        <span>当前展示 {findings.length} 条生产疑点，分页由后端查询合同下一批接入。</span>
        <button className="is-active" type="button">
          1
        </button>
      </div>
    </>
  );
}

function FindingDrawer({
  finding,
  sourceKeys,
  statusOptions,
  onClose,
  onDialog
}: {
  readonly finding: BackendAuditFinding;
  readonly sourceKeys: readonly string[];
  readonly statusOptions: Record<string, string>;
  readonly onClose: () => void;
  readonly onDialog: (kind: WorkflowKind, finding?: BackendAuditFinding | null) => void;
}) {
  const evidence = finding.evidence_items[0];
  return (
    <aside className="replica-medical-drawer" aria-label="疑点详情">
      <div className="replica-medical-drawer-head">
        <button type="button" onClick={onClose}>
          关闭
        </button>
      </div>
      <h2>{finding.finding_key}</h2>
      <dl>
        <div>
          <dt>疑点名称</dt>
          <dd>{findingTitle(finding)}</dd>
        </div>
        <div>
          <dt>源记录</dt>
          <dd>{findingSubject(finding)}</dd>
        </div>
        <div>
          <dt>复核状态</dt>
          <dd>{statusLabel(statusOptions, finding.review_status)}</dd>
        </div>
        <div>
          <dt>任务</dt>
          <dd>{finding.review_task_id ?? "尚未关联复核任务"}</dd>
        </div>
        <div>
          <dt>规则版本</dt>
          <dd>{finding.rule_version_key ?? finding.rule_key ?? "待映射"}</dd>
        </div>
        <div>
          <dt>审计运行</dt>
          <dd>{finding.audit_run_key ?? "待映射"}</dd>
        </div>
      </dl>
      <h3>证据链</h3>
      <div className="replica-medical-evidence is-blue">
        <strong>{evidence?.citation_id ?? evidence?.evidence_type ?? "结构化证据"}</strong>
        <p>{evidence?.snippet ?? "后端已返回疑点，但暂未附带文本证据片段。"}</p>
        <p>
          chunk: <code>{evidence?.chunk_id ?? "未关联"}</code>
        </p>
      </div>
      <h3>源记录定位</h3>
      <div className="replica-medical-evidence">
        <p>{stringifyShort(finding.source_record_locator)}</p>
      </div>
      <h3>计算过程</h3>
      <div className="replica-medical-evidence">
        <p>{stringifyShort(finding.calculation_trace)}</p>
      </div>
      <h3>生产流转</h3>
      <ul className="replica-medical-related">
        <li>
          <span>复核任务</span>
          <strong>{finding.review_task_id ? "已关联" : "待创建"}</strong>
        </li>
        <li>
          <span>证据条目</span>
          <strong>{finding.evidence_items.length}</strong>
        </li>
        <li>
          <span>知识库范围</span>
          <strong>{sourceKeys.length}</strong>
        </li>
      </ul>
      <p className="replica-medical-source">更新时间：{formatDate(finding.updated_at)}</p>
      <div className="replica-medical-drawer-actions">
        <button className="is-primary" type="button" onClick={() => onDialog("review", finding)}>
          进入复核
        </button>
        <a className="replica-secondary-button" href={buildChatHref(finding, sourceKeys)}>
          AI 分析
        </a>
        <button type="button" onClick={() => onDialog("report", finding)}>
          加入报告
        </button>
        <button type="button" onClick={() => onDialog("import", finding)}>
          补充材料
        </button>
      </div>
    </aside>
  );
}

function EmptyReadinessPanel({
  readiness,
  onDialog
}: {
  readonly readiness: AuditFindingsResponse["generation_readiness"];
  readonly onDialog: (dialog: WorkflowDialog) => void;
}) {
  return (
    <section className="replica-medical-evidence is-blue">
      <strong>{readinessStatusLabels[readiness.status] ?? readiness.status}</strong>
      <p>当前没有可展示疑点。请按导入费用表、核验知识库、运行规则、生成复核任务的顺序推进。</p>
      <ul className="replica-medical-related">
        {readiness.prerequisites.map((item) => (
          <li key={item.key}>
            <span>{item.label}</span>
            <strong>{item.ready ? "就绪" : `${item.count} 条`}</strong>
          </li>
        ))}
      </ul>
      <div className="replica-medical-drawer-actions" style={{ position: "static", margin: "14px 0 0" }}>
        <button className="is-primary" type="button" onClick={() => onDialog({ kind: "import" })}>
          导入表格
        </button>
        <button type="button" onClick={() => onDialog({ kind: "new-task" })}>
          创建任务
        </button>
      </div>
    </section>
  );
}

function TemplateWorkbookView({
  reportState,
  view,
  onDialog
}: {
  readonly reportState: LoadState<ReportWorkbenchResponse>;
  readonly view: AuditView;
  readonly onDialog: (kind: WorkflowKind) => void;
}) {
  if (view === "audit") {
    return null;
  }
  const config = templateConfigs[view];
  const templates = reportState.status === "ready" ? reportState.data.workpaper_templates : [];
  const template = templateForView(view, templates);
  const columns = template?.expected_columns.length ? template.expected_columns : config.fallbackColumns;
  return (
    <section className="replica-medical-table-page" aria-label={config.title}>
      <header className="replica-medical-table-head">
        <div>
          <h2>{config.title}</h2>
          <span>{template ? "后端模板已注册" : "等待后端模板映射"}</span>
        </div>
        <div>
          <button className="replica-secondary-button" type="button" onClick={() => onDialog("new-task")}>
            创建审计任务
          </button>
          <button className="replica-primary-button" type="button" onClick={() => onDialog("import")}>
            导入模板文件
          </button>
        </div>
      </header>
      <div className="replica-medical-table-meta">
        <span>
          数据状态：<strong>{reportState.status === "ready" ? reportState.data.store.backend : "读取中"}</strong>
        </span>
        <span>
          模板：<strong>{template?.name ?? config.title}</strong>
        </span>
        <span>
          输出：<strong>{template?.output_type ?? "导入后生成审计底稿"}</strong>
        </span>
      </div>
      <div className="replica-medical-summary-cards">
        <article>
          <span>导入目标</span>
          <strong>{config.title}</strong>
          <p>{config.description}</p>
        </article>
        <article>
          <span>字段数量</span>
          <strong>{columns.length}</strong>
          <p>字段来自后端模板注册表或本地模板合同。</p>
        </article>
        <article>
          <span>生产动作</span>
          <strong>确认后执行</strong>
          <p>本页面先进入导入门禁，不直接写入生产。</p>
        </article>
      </div>
      <div className="replica-medical-data-table is-wide">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {columns.map((column, index) => (
                <td key={column}>{index === 0 ? "导入后由后端解析回填" : "待导入"}</td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MedicalAiDrawer({
  finding,
  filteredCount,
  selectedCount,
  sourceKeys,
  onClose
}: {
  readonly finding: BackendAuditFinding | null;
  readonly filteredCount: number;
  readonly selectedCount: number;
  readonly sourceKeys: readonly string[];
  readonly onClose: () => void;
}) {
  const chatHref = buildChatHref(finding, sourceKeys);
  return (
    <aside className="replica-medical-ai-drawer" aria-label="医保审计 AI 助手">
      <header className="replica-medical-ai-head">
        <div>
          <span>真实问答入口</span>
          <h2>医保审计助手</h2>
        </div>
        <button aria-label="关闭 AI 助手" type="button" onClick={onClose}>
          ×
        </button>
      </header>
      <div className="replica-medical-ai-context">
        <div>
          <span>当前上下文</span>
          <strong>{finding?.finding_key ?? "全局审计"}</strong>
        </div>
        <p>
          本抽屉不再生成本地假回答。点击下方按钮会带上疑点键和知识库范围进入 AI 对话页，由后端知识库问答链路处理。
        </p>
        <dl>
          <div>
            <dt>筛选疑点</dt>
            <dd>{filteredCount}</dd>
          </div>
          <div>
            <dt>已选疑点</dt>
            <dd>{selectedCount}</dd>
          </div>
          <div>
            <dt>知识库</dt>
            <dd>{sourceKeys.length}</dd>
          </div>
        </dl>
      </div>
      <div className="replica-medical-ai-shortcuts">
        <a className="replica-primary-button" href={chatHref}>
          进入 AI 分析
        </a>
        <button className="replica-secondary-button" type="button" onClick={onClose}>
          返回工作台
        </button>
      </div>
      <div className="replica-medical-ai-thread">
        <div className="replica-medical-ai-message">
          <span>AI</span>
          <p>已准备好当前医保审计上下文。后续真实回答将在 AI 对话页通过知识库查询接口产生。</p>
        </div>
      </div>
    </aside>
  );
}

function WorkflowGateDialog({
  actionState,
  dialog,
  onClose,
  onConfirm
}: {
  readonly actionState: WorkflowActionState;
  readonly dialog: WorkflowDialog | null;
  readonly onClose: () => void;
  readonly onConfirm: (dialog: WorkflowDialog) => void;
}) {
  if (!dialog) {
    return null;
  }
  const copy = {
    "new-task": {
      title: "创建审计任务草稿",
      body: "将当前疑点写入复核任务，并与后端疑点记录建立关联。该动作会写入复核任务和审计事件。",
      primary: "创建复核任务"
    },
    import: {
      title: dialog.finding ? "登记补充材料" : "批量导入预检",
      body: dialog.finding
        ? `将为疑点 ${dialog.finding.finding_key} 登记一条补充材料占位记录，后续可接入正式文件上传。`
        : "先登记导入预检，明确模板、文件和映射检查项；正式文件解析和入库仍由下一层导入合同处理。",
      primary: dialog.finding ? "登记补充材料" : "记录导入预检"
    },
    review: {
      title: "疑点复核动作",
      body: dialog.finding
        ? `疑点 ${dialog.finding.finding_key} 已选中。确认后会写入复核状态、意见、结论和审计事件。`
        : "批量复核会对已选疑点写入复核状态、意见、结论和审计事件。",
      primary: "确认违规并写入"
    },
    report: {
      title: "加入报告与底稿",
      body: "将疑点纳入复核任务 dossier，生成底稿占位、负责人确认和报告草稿字段，供报告工作台读取。",
      primary: "加入报告草稿"
    },
    settings: {
      title: "审计任务配置",
      body: "记录配置入口检查，后续接入规则集、知识库范围、费用模板和复核人员的正式配置合同。",
      primary: "记录配置检查"
    }
  }[dialog.kind];
  const isRunning = actionState.status === "running";
  return (
    <div className="replica-modal-backdrop" role="presentation" onClick={onClose}>
      <section
        aria-modal="true"
        className="replica-modal"
        role="dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <h2>{copy.title}</h2>
        <p>{copy.body}</p>
        <div className="replica-medical-evidence is-blue">
          <strong>生产写入边界</strong>
          <p>该动作只写入复核任务、dossier 或审计事件；正式报告签发、文件入库解析和归档仍需单独流程。</p>
        </div>
        {actionState.status !== "idle" ? (
          <div
            className={`replica-medical-evidence ${
              actionState.status === "error" ? "is-danger" : "is-blue"
            }`}
          >
            <strong>
              {actionState.status === "running"
                ? "正在处理"
                : actionState.status === "success"
                  ? "后端已确认"
                  : "提交异常"}
            </strong>
            <p>{actionState.message}</p>
          </div>
        ) : null}
        <div className="replica-modal-actions">
          <button className="replica-secondary-button" disabled={isRunning} type="button" onClick={onClose}>
            关闭
          </button>
          <button className="replica-primary-button" disabled={isRunning} type="button" onClick={() => onConfirm(dialog)}>
            {isRunning ? "提交中..." : copy.primary}
          </button>
        </div>
      </section>
    </div>
  );
}
