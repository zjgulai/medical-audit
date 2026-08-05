---
title: medical_audit Codex 项目规则
doc_type: agent-instructions
module: repository
status: active
created: 2026-07-06
updated: 2026-07-06
owner: self
source: human+ai
---

# medical_audit Codex 项目规则

## 基本原则

- 默认使用中文；代码、路径、配置名、命令和技术术语保留英文。
- 结论必须区分事实、推断和不确定项，不能把未验证状态说成已完成。
- Do not send optional commentary.
- 不自动写长期记忆；自进化只允许按明确要求追加候选经验到 `~/.codex/evolution/inbox/candidates.jsonl`，不得写入 `global.jsonl` 或 `global.md`。
- 代码修改保持窄 scope，不做未请求的清理、重构、配置补充或生产操作。
- 文件编辑前按需备份关键文件到 `~/.Codex/file-history/`；删除、批量移动、覆盖关键配置前必须确认。

## 项目定位

- 本仓库是面向医院场景的私有化医疗审计产品，不是通用 SaaS 或纯研究仓库。
- 核心闭环是：法规与知识支撑 -> 合规判断与风险识别 -> 审计底稿与报告 -> 整改跟踪。
- 产品基线优先级参考：
  - `docs/product/product-meeting-consensus-20260315-stable.md`
  - `docs/product/product-prd-medical-audit-v1-stable.md`
  - `docs/product/product-development-plan-medical-audit-stable.md`
  - `docs/product/product-scope-baseline-stable.md`
  - `docs/knowledge/knowledge-query-evidence-register-stable.md`

## 目录约定

- `src/medical_audit_kb/`: FastAPI、CLI、检索、PostgreSQL/pgvector 后端代码。
- `web/`: Next.js 前端应用，包名 `medical-audit-web`。
- `scripts/`: 本地验证、生产只读检查、部署和运维脚本。
- `configs/`: 本地与生产配置模板；不要写入 secret。
- `docs/`: 稳定产品、架构、API、workflow 文档。
- `drafts/`: 未定稿分析和报告草稿，新建 Markdown 必须带 frontmatter。
- `tmp/`: 临时输出、截图、调试文件和一次性运行产物。
- `.kiro/plan/`: 长周期计划、进展和发现记录；更新时保持事实边界。

## 常用命令

- Python 后端：
  - `uv run pytest`
  - `uv run ruff check .`
  - `uv run mypy src`
  - `uv run medical-audit-kb --help`
- Web 前端：
  - `pnpm web:dev`
  - `pnpm web:lint`
  - `pnpm web:typecheck`
  - `pnpm web:test`
  - `pnpm web:build`
  - `pnpm web:e2e`
- 本地全栈/只读验证：
  - `pnpm local:fullstack:e2e`
  - `pnpm local:postgres:readonly`
  - `pnpm local:permission:readonly`
- 生产只读检查：
  - `pnpm production:permission-readonly`
  - `pnpm production:frontend-acceptance`

## Docker 与数据库

- 本地开发 Compose 文件是 `docker-compose.dev.yaml`，PostgreSQL/pgvector 容器名是 `medical-audit-kb-postgres`，宿主机端口是 `5433`。
- 生产 PostgreSQL 容器名通常是 `medical_audit_pg`；不要把本地容器、生产容器和历史备份路径混为同一证据层。
- `pg_dump`/`pg_restore` 必须使用与数据库主版本匹配的容器内工具，避免 host 工具版本不兼容。
- 大型 pgvector/embedding 备份很容易受压缩和磁盘 I/O 限制；诊断时先用进程、`pg_stat_activity`、文件增长和容器 I/O 判断瓶颈，避免直接跑完整 `gzip -t` 读取多 GB 文件。
- 生产部署备份脚本优先保持 `.sql.gz` 恢复格式；如使用 `pigz`，必须保留 `gzip` fallback。

## 生产与权限边界

- `merge`、`deploy`、`production`、`provider call`、`live send`、`manual approval` 必须先核验证据层级，再下结论。
- `docs-only`、`draft`、`read-only`、`production unchanged`、`no provider call`、`manual review` 必须按字面边界处理。
- 用户说 `继续下一步` 或 `继续下一个loop` 时，只继续下一个已验证的本地或只读步骤；生产写入、部署、provider 调用、SQL 写入、runtime switch、merge/push 仍需单独明确授权。
- 生产状态必须区分：本地测试、deploy preflight、远端备份、脚本最终退出、生产只读检查、浏览器验收、授权 live side effect。
- 不得把中间备份、健康容器、文件存在或旧记忆当作部署完成证据。

## 验收与汇报

- 完成声明必须带新鲜证据：命令、测试、构建、页面检查、只读生产检查或审批记录。
- 测试失败、用户纠正或返工后，优先按明确要求沉淀一条候选经验；普通成功不复盘。
- 保存报告型 Markdown 时，优先放入 `drafts/analysis/`，用 frontmatter、路径、行数和关键元数据验证，不在回复中粘贴长正文。
