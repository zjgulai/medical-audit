---
title: 部署备份等待债务与未完成任务盘点
doc_type: analysis-draft
module: operations
status: draft
created: 2026-07-09
updated: 2026-07-09
owner: codex
source: local-readonly+production-readonly
---

# 部署备份等待债务与未完成任务盘点

## 事实

- 当前生产 `.deploy-sha`：`88459548e18d1fd8c64c6289551fb0fac038ad38`。
- 当前生产容器只读检查：`medical_audit_app=running/healthy`，`medical_audit_pg=running/healthy`，`medical_audit_clamav=running/healthy`。
- 当前根目录 `/Users/pray/project/medical_audit` 仍是脏树，并且本地 `main` 落后 `origin/main`。本批不在该脏根目录开发。
- 根目录脏树按顶层分组：`.kiro=20`、`drafts=298`、`docs=4`、`repo-config=3`、`scripts=5`、`src=9`、`tests=7`、`web=19`、`output=1`、`other=1`，合计 `367` 条。
- GitHub 当前开放 PR：`#186 docs: add medical_audit governance manifests`，状态字段返回 `mergeStateStatus=UNKNOWN`。
- 本批隔离分支：`codex/deploy-backup-timeout-debt-20260709`，基于 `origin/main@88459548e18d1fd8c64c6289551fb0fac038ad38`。

## 本批已执行事项

### 1. 部署脚本远端备份等待债务

问题边界：此前部署中，远端 DB/app/web/nginx/env 备份实际已完成，但长 SSH 会话仍可能等待自然返回，导致人工误判为部署卡住，之后需要手动从备份之后继续。

本批修复：

- `scripts/deploy-tencent-cloud-production.py` 新增 `_ssh_background_with_completion(...)`。
- 远端备份脚本不再依赖单个长 SSH 会话自然返回，而是：
  - 写入 `/tmp/<job>.sh`；
  - `nohup bash` 后台执行；
  - 写入 `/tmp/<job>.pid` 和 `/tmp/<job>.log`；
  - 本地轮询 completion marker 和所有必需备份文件；
  - 若后台进程退出但 marker 或备份文件不存在，则 fail-fast 并回显远端日志尾部。
- `_create_remote_backups(...)` 改为调用该后台完成轮询 helper。

验证：

- 红测先失败：`_ssh_background_with_completion` 不存在。
- 修复后聚焦测试通过：`2 passed`。

## 未完成任务盘点

### P0：部署链路可靠性

1. 将本批部署脚本修复走 PR。
   - 原因：这是生产部署稳定性债务，不属于业务功能，但影响每次发布的判断可靠性。
   - 下一步：跑完整 deploy-script 相关测试、`py_compile`、`git diff --check`，再提交 PR。

2. 生产部署脚本需要一次不发布业务代码的 dry-run/preflight 复核。
   - 原因：本批只修本地脚本和测试，不执行生产写入。
   - 下一步：合并后，在下一次授权部署前先跑 preflight，确认后台备份 job 的启动脚本生成逻辑无语法问题。

### P1：项目治理与脏树收敛

1. 根目录 367 条脏树需要按来源分组，不应继续把本地根目录当作开发基线。
   - `drafts=298`：多数是历史知识库和前端迭代草稿，应按日期归档或转正式文档。
   - `web=19`：需要逐项判断是否已经被 `main@88459548` 吸收，未吸收的再建小 PR。
   - `src=9` 与 `tests=7`：疑似知识库后端和测试迭代，不能和前端治理混提交。
   - `scripts=5`：需要区分部署脚本、P6D 决策 manifest 脚本、一次性工具。

2. PR #186 需要单独 review。
   - 原因：它是治理 manifest 类 PR，可能和当前脏树治理高度相关。
   - 只读 review 结论：不建议直接合并当前版本。
   - 依据：PR #186 是 `OPEN/CLEAN`，但文档基线停留在 `main@edae456790c2abb3d2ee896179a0b67be3e696fa` 与当时的 worktree 状态；当前生产事实已推进到 `88459548e18d1fd8c64c6289551fb0fac038ad38`，根目录脏树也已重新统计为 `367` 条。
   - 下一步：保留 PR #186 的治理结构，但用当前生产 SHA、PR #212、根目录脏树分组和最新 Docker/备份边界重写后再合并。

### P1：后端联通与真实数据闭环

1. `/medical-audit` 业务流程仍是下一条产品主线。
   - 目标：用户能从项目/专题进入医保审计，完成数据导入、规则选择、疑点生成、复核、底稿/报告归档。
   - 下一步：不要先做 UI 微调，先做页面事件流、数据实体、API 合同和写入边界。

2. `/chat` 模型选择已能显示未配置状态，但真实模型 provider 配置仍需环境层决策。
   - 下一步：明确 `kimi-2.7`、`deepseek-v4-pro` 的后端别名映射、不可用提示和 query history 记录规则。

3. 知识库、文档检索、知识图谱已显示生产数据，但还需要从“可看”推进到“可操作闭环”。
   - 下一步：逐页列出 GET、POST、上传、详情、引用、跳转、关闭动作，标记真实后端、后端种子、前端静态和只读壳。

### P2：产品精修与文档债务

1. PPT 反馈后的品牌与导航已经进入生产，但仍需面向院方场景继续压缩后台语言。
   - 下一步：逐页扫描“本地样例、接口已校验、后端+本地、内测中”等用户不可理解文案，分为保留、替换、隐藏三类。

2. 知识库草稿文档数量过大。
   - 下一步：建立 `drafts/analysis` 的索引，按 `obsolete / merged / still-active` 标注，不直接删除。

3. 生产备份保留策略需要工程化。
   - 下一步：先生成远端备份 manifest 和磁盘占用报告，再制定保留窗口；删除仍需单独授权。

## 下一批推荐执行顺序

1. 先完成本批部署脚本修复的测试、PR 和 review。
2. 对 PR #186 做只读 review，决定是否合并治理 manifest。
3. 建立根目录脏树 manifest，把 `drafts`、`web`、`src/tests`、`scripts` 分组。
4. 进入 `/medical-audit` 后端闭环第一批：实体和 API 合同，不先改 UI。
5. 对知识库/文档检索/知识图谱做操作闭环矩阵。

## 边界

- 本批没有执行生产部署。
- 本批没有写生产数据库。
- 本批没有清理 Docker、备份或历史文件。
- 本批没有修改用户可见业务页面。
