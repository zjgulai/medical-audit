---
title: medical_audit 全量复盘、差异与清理审计
doc_type: analysis-report
module: repository
status: active
created: 2026-08-13
updated: 2026-08-22
owner: self
source: human+ai
repository_observed_at: 2026-08-14T13:23:41+08:00
repository_observed_sha: cc711fdb4dc2b36d2b5de705939a7726917960f1
repository_observed_sha_role: precommit-base
delivery_observed_at: 2026-08-22T00:59:15+08:00
delivery_observed_pr_head: d1973206d4f9b01ad0b287fb252fccf760fdab5c
delivery_observed_ci_run: 32499803192
delivery_observed_ci_conclusion: success
delivery_status_model: dated-external-observations
pull_request: https://github.com/zjgulai/medical-audit/pull/275
production_observed_at: 2026-08-12
production_git_sha: 25e1654e0c44ca5cbb2bb42e82debdb40fa6f224
evidence_grade: L2-local-and-ci+prior-L3-production-read-only
production_side_effect: none
provider_call: false
---

# medical_audit 全量复盘、差异与清理审计

本报告记录候选分支 `codex/medical-audit-reanalysis-playbook-20260813` 的代码、文档、本地测试、外部交付观察、生产历史证据和清理边界。状态采用带时间的外部观察，不把 tracked 文档自身 SHA 或瞬时 push 状态写成长期事实。

## 2026 年 8 月 22 日 PR 身份同步门禁

- 外部观察确认本地、远端候选分支和 Draft PR #275 均指向 `d1973206d4f9b01ad0b287fb252fccf760fdab5c`，`main == origin/main == ccc73e95820e39559430e96c01d52c8dfb77a246`；分支相对 main 为 `0 behind / 13 ahead`。
- exact-head CI run `32499803192` 为 `success`：Python `1018 passed`，Web `419 passed`，Ruff、Mypy、typecheck、lint、普通构建、公开壳层构建和文档门禁通过，Web 原始日志中的 React `act()` warning 为 0。
- PR 相对 base 为 13 个提交、103 个文件；实际路由合同为 21 个独立页面和 2 个兼容跳转。PR 正文仍写旧 head、6 个提交、92 个文件和 `20+3` 路由分类，因此只读 Ready 审计判定为 `NO-GO`。
- GitHub review、review request 和 review thread 均为 0；CodeRabbit status 明确写明因 Draft 跳过 review。GitNexus 把共享前端访问门禁的影响面评为 `critical`，必须取得独立评审证据。
- 当前工作树中 `AGENTS.md`、`.claude/` 和 `CLAUDE.md` 属于用户既有变更，不纳入候选状态同步提交。
- 本节是带时间的提交前外部观察，不声明 tracked 文档自身 SHA。状态同步后的最终 exact head、push、CI 和 review 终态由 GitHub 与仓库外收据另行绑定。
- 本门禁不包含 merge、deploy、生产访问、Provider 调用或本地 Docker 操作。

## 2026 年 8 月 21 日本地部署合同修复（历史：提交前）

- 当时本地和远端候选分支均指向 `4b42b3eab6972d8ce7d870346f13d16f8ef04f79`，`main == origin/main == ccc73e95820e39559430e96c01d52c8dfb77a246`；当时 46 文件工作树未提交。
- 只读候选复核确认三个 P0 发布合同缺陷：预同步检查读取旧生产 Compose 形成启动死锁；部署后检查把受保护知识库目录 `2xx` 当成成功；默认生产 smoke 无条件读取该目录。
- 修复后，生产访问模式在应用同步之后、发布准备之前并持远端部署锁检查；部署后检查只访问公开健康、部署元数据、公开页面，并要求受保护目录返回 `503`。默认 smoke 进一步校验 `runtime_access`、`trusted_identity_required`、`public-shell-readonly` 和 `Cache-Control: no-store`。
- 8 条定向回归完成先红后绿，脚本测试全集通过。完整本地结果为 Python `1016 passed, 1 skipped, 5 warnings`、Web 41 个文件和 418 项测试、Playwright `17/17`；Ruff、Mypy、lint、typecheck、26/26 build 和 docs lint 通过。
- 最新本地全栈收据为 `L2-local-live`，覆盖 21 个独立路由、2 个兼容别名、4 个业务工作流和 27 个功能，`provider_call=false`。
- GitNexus `detect_changes(scope=all)` 报告 38 个 tracked 变更文件、109 个变更符号和 300 条受影响流程，整体风险为 `critical`；该评级要求下一门禁逐项审阅完整候选，不能由全绿测试替代影响分析。
- `web/out/release-manifest.json` 未生成。当前脏工作树没有精确 Git SHA，不能把 HEAD 或合成摘要写成 `source_sha`；可部署 manifest-bound package 继续阻塞到单独的 staging/commit 授权。
- 本门禁没有生产访问或写入、Provider 调用、本地 Docker 操作、stage、commit、push、PR 修改、merge 或 deploy。

## 最新交付观察（外部、只读）

- 观察时间：2026-08-22 00:59（Asia/Shanghai）。
- Draft PR #275 的 base 为 `ccc73e95820e39559430e96c01d52c8dfb77a246`，观测 head 为 `d1973206d4f9b01ad0b287fb252fccf760fdab5c`；PR 为 `OPEN/DRAFT`、`MERGEABLE/CLEAN`，review、review request 和 review thread 均为 0。
- GitHub Actions run `32499803192` 在观测 head 成功：Python `1018 passed`，Web `419 passed`，Ruff、Mypy、typecheck、lint、普通构建、公开壳层构建和文档检查通过；Web 原始日志中的 React `act()` warning 为 0。
- PR diff 为 13 个线性提交、103 个文件；本地、远端候选分支和 PR head 在观察时一致，分支相对 main 为 `0 behind / 13 ahead`。
- GitHub CodeRabbit 因 Draft 跳过 review；独立 CLI review 尚未形成可引用终态。CI 成功不等于代码评审、Ready、merge、部署或生产验收通过。
- 本次观察没有访问生产、调用 Provider 或修改本地 Docker。生产状态仍只引用 2026 年 8 月 12 日 L3 历史证据。

## 提交前与生产历史事实

### 候选建立与生产历史基线

- 开始执行时，`main == origin/main == ccc73e95820e39559430e96c01d52c8dfb77a246`，工作树干净。
- 2026-08-14 13:23 的提交前观察中，Draft PR #275 的 base 为 `ccc73e95820e39559430e96c01d52c8dfb77a246`，远端 head 为 `cc711fdb4dc2b36d2b5de705939a7726917960f1`；PR 为 `OPEN/DRAFT`、`MERGEABLE/CLEAN`，尚无代码评审。
- 该提交前观察对应 GitHub Actions run `31768924010`：Python `1001` 项、Web `417` 项测试和全部 CI job 通过。它是历史证据，不覆盖后续 head。
- 2026 年 8 月 12 日 L3 只读证据显示，生产部署 SHA 为 `25e1654e0c44ca5cbb2bb42e82debdb40fa6f224`。
- `25e1654e..ccc73e95` 没有 `src/` 或 `web/` 业务源码差异，仅含验收脚本和 Sprint 5 文档。
- 提交前本地在 `cc711fdb` 之上形成了本门禁授权的代码和文档差异；其后续提交与交付状态以上方带时间的外部观察为准。

### 已修复问题

1. 生产 API 增加 `public-shell-readonly`，在认证和审计业务处理前阻断受保护请求。
2. 前端生产构建不再发起受保护 API 请求，隐藏角色切换和写操作。
3. `/workspace?finding=<id>` 改为在疑点加载后定位，并统一不可见提示。
4. 整改使用真实 UUID、真实空状态、只读 Sample、父项目鉴权和后端状态机。
5. 报告签发复用项目可见性、关闭态、构建门禁和 `SIGN_REPORTS`。
6. 知识库统计按 package 和文档预聚合，修复等长文本与多 index 放大。
7. 更新旧 E2E 断言，修复 React lint 警告和 Next.js 根目录警告。
8. 生产导航验收把公开壳层主动发起受保护 API 请求列为 P1，并在出现任一请求时失败。
9. 整改列表把项目可见性下推到 SQL 查询，在排序和 `LIMIT` 前过滤不可见项目。
10. API 文档补齐 112 个规范路径、123 个方法/路径操作；`docs:lint` 从 FastAPI OpenAPI 逐项对账。

### 本地验证

- `pnpm local:fullstack:e2e`：17/17 通过。
- 临时 Store：SQLite。
- Provider：确定性 Fake，`provider_call=false`。
- 当前路由合同：21 个独立页面、2 个兼容跳转和 4 条真实 HTTP/SQLite 业务工作流，共 27 条功能记录。旧收据的 `20+3` 分类已确认将独立的 `/workspace` 误列为别名。
- 业务工作流覆盖整改 UUID 附件和完整状态机、报告签发角色/可见性/重复签发，以及项目、成员和文件持久化；数据库快照记录 `audit_projects 0→1`、`audit_project_members 1→3`、`remediation_items 0→1`、`review_actions 0→1`、`document_upload_records 0→2`、`audit_log_events 227→245`。
- 新增整改状态机、项目可见性、报告签发和知识统计定向测试通过。

最终全量质量门禁结果见本报告「完成证据」一节。

### 工程警告归因

- 仓库自有 Ruff、Mypy、ESLint、TypeScript 和 Next.js 构建警告已经修复。
- pytest 剩余 5 条摘要警告均由固定依赖 `pymupdf==1.27.2.2` 在 Python 3.12.13 导入 SWIG 类型时产生，消息为 `SwigPyPacked`、`SwigPyObject` 和 `swigvarlink` 缺少 `__module__`。这不是仓库业务代码触发的弃用 API。
- 升级条件：PyMuPDF 发布兼容当前 Python/SWIG 的版本后，先在候选分支验证 PDF/OCR、合同审计和下载回归，再更新固定版本；本轮不使用全局 warning filter 掩盖它。

## 推断

- OpenCode 优化扩大了产品功能面，但权限、业务动作测试和文档同步落后于实现。
- 生产与原本地基线的用户态源码基本一致；主要差异来自运行访问模式、验收脚本和候选修复。
- 生产源码相近不代表配置、数据、Provider 和业务行为一致。

## 不确定项

- 候选 `public-shell-readonly` 尚未部署，生产负向 `503` 合同未实测。
- 真实 HIS、DLP、OCR/LLM Provider 和医院现场 UAT 未执行。
- 生产备份没有新鲜完整批次和隔离恢复证明，因此删除状态为 `blocked`。
- 可信 SSO/OIDC、性能基线、告警/Webhook 和灾备演练仍待后续门禁。

## 文档差异

执行前存在以下确定问题：

- README、开发计划和状态台账仍声称生产停在 Sprint 4。
- Sprint 5 交付文档同时包含部署后正文和重复的部署前正文。
- 旧 Jinja/Next 边界文档低估 Next.js 路由和写操作。
- 没有完整用户 Playbook、管理员 Playbook或生产功能验收矩阵。
- tracked Markdown 有 3 个无效 frontmatter 和 11 个字段不完整文件。
- `drafts/analysis/backlog-20260807.md` 有一条确定断链。

候选新增权威文档入口、架构、API、用户和管理员 Playbook、验收矩阵、写作规则和 `docs:lint`。2026 年 8 月 14 日收口门禁进一步修正 PR、Git、CI 和本地提交的状态口径，并把 OpenAPI 方法/路径覆盖、带时间观察字段和证据角色纳入机器检查。tracked 文档不自引用最终 `HEAD`，也不保存瞬时 push 状态；最终提交身份由 Git 对象、GitHub 和仓库外收据绑定。

## 本地清理边界

阈值是执行时刻减 72 小时，不使用目录名或目录 mtime 作为唯一依据。批量移动必须先提供 exact-path 清单并取得确认。

### 明确保留

- `tmp/knowledge-query-indexes`，约 43.1 GiB，属于唯一索引证据。
- P6C 唯一数据库 dump，逻辑大小约 5.84 GB。
- 私有 `data/`、被引用截图、生产 L3/L4 收据和恢复证明。
- `.git`、tracked 归档、活动 `.venv`、`node_modules`。
- 本地 Docker 容器、镜像、卷和缓存。

### 低风险候选类别

- `.mypy_cache`、`.pytest_cache`、`.ruff_cache` 和 `.codegraph`。
- 完成最终构建后可再生成的 `web/.next`、`web/out`。
- `.DS_Store`。
- 已被新收据替代且无文档引用的临时输出。

这些类别仍需形成精确文件清单，不能直接按目录通配符移动。

### 历史工作树和 clone

需要逐项证明：

- `_h1_fix_20260721`：先归并 4 份独有文档；`.kiro` 差异保存为外部 patch。
- `_loop128_ocr_failclosed_20260804`：保留注册关系，先把父子关联转换为相对 worktree 路径，再按同级布局成对隔离；不使用会直接删除目录的 `git worktree remove`。
- `_deploy_dda167f9_20260804_ref`：隔离后继续保留指向当前候选仓库的 objects alternates，并在收据中明确非自包含边界。
- `_loop126_acceptance_contract_20260803`：损坏 gitfile 先做文件级哈希和差异证明。
- 其他 clone：只有 clean、HEAD 是当前历史祖先且无独有证据时，才可进入候选。

本轮不会在未确认 exact-path manifest 前移动这些对象。

### 2026-08-13 本地清理候选清单

执行阈值为 `2026-08-10T12:54:09+08:00`。以下对象均超过阈值；大小为执行时只读盘点的近似值。

| 绝对路径 | 大小 | HEAD / 关系 | 独有证据与依赖 | 当前处置 |
| --- | ---: | --- | --- | --- |
| `/Users/pray/project/medical_audit_h1_fix_20260721` | 264 MiB | `13b0fb1c`，当前基线祖先 | 4 份独有草稿、`.kiro` patch 和选定运行证据已归并；匹配强凭据特征的源文件未复制 | 已移动到受管隔离；永久删除保持 `blocked` |
| `/Users/pray/project/medical_audit_loop128_ocr_failclosed_20260804` | 924 MiB | `b96ba72d`，当前基线祖先 | 父仓库保持注册 worktree；2 个运行输出与当前仓库相同 | 已按相对关联成对移动到受管隔离 |
| `/Users/pray/project/medical_audit_deploy_dda167f9_20260804_ref` | 324 MiB | `dda167f9`，当前基线祖先 | 是 Loop 128 父仓库；objects alternates 指向当前仓库；32 个运行文件均有覆盖 | 已按相对关联成对移动到受管隔离 |
| `/Users/pray/project/medical_audit_loop126_acceptance_contract_20260803` | 804 MiB | 损坏 gitfile；文件树与 `6444f540` 的 553 个 tracked blob 全部一致 | 独有收据已归并；额外文件为忽略或生成物 | 已移动到受管隔离 |
| `/Users/pray/project/medical_audit_deploy_84c2420_20260804` | 335 MiB | `84c24207`，当前基线祖先 | 独有收据已归并 | 已移动到受管隔离 |
| `/Users/pray/project/medical_audit_deploy_b8e4737c_20260803` | 816 MiB | `b8e4737c`，当前基线祖先 | 独有收据已归并 | 已移动到受管隔离 |
| `/Users/pray/project/medical_audit_loop129_deploy_2e9495d7` | 341 MiB | `bcb918f6`，当前基线祖先 | 独有收据已归并 | 已移动到受管隔离 |

已完成的证据归并：

- 4 份历史草稿已放入 `drafts/analysis/`，状态统一为 `superseded`，文件内容仍可审阅。
- `.kiro` 外部 patch 位于 `/Users/pray/.Codex/file-history/medical_audit-20260813T114016+0800/h1-fix-kiro-ledgers.patch`，大小为 400,111 字节，SHA-256 为 `6cb5b998d67d7b1a7c528ba957446d855330ff15fb476f0c38a960d93153469e`。
- Loop 126 的损坏 gitfile 指向已不存在的父仓库；文件级对比确认其 553 个 tracked blob 与 `6444f540` 完全一致。该结论不覆盖生成物和独有收据。
- 选定的历史 L3/L4、部署、恢复和运行证据已归并为 416 个文件的 `legacy-workspaces-evidence-pack.tar.gz`。归档 SHA-256 为 `80f730232fd54c385350dd87302a7f3b01ae4e7d82715581ec9f09a2e4fc5836`，`gzip -t` 和隔离解包后的逐文件源哈希校验均通过。
- 证据包收据位于 `/Users/pray/.Codex/file-history/medical_audit-20260813T114016+0800/legacy-workspaces-evidence-pack-receipt.json`，SHA-256 为 `bf27ed97eea6f62b6aae4af4bb481164d3d8c2a45c1e887756386b4689c0801a`。Git objects、依赖环境、可再生成缓存和匹配强凭据特征的文件没有复制到该归档；源目录未被修改。

项目内低风险 exact-path 候选：

| 绝对路径 | 近似大小 | 说明 |
| --- | ---: | --- |
| `/Users/pray/project/medical_audit/.mypy_cache` | 41 MiB | 可再生成；本轮测试已更新，不满足 72 小时阈值 |
| `/Users/pray/project/medical_audit/.pytest_cache` | 136 KiB | 可再生成；本轮测试已更新，不满足 72 小时阈值 |
| `/Users/pray/project/medical_audit/.ruff_cache` | 64 KiB | 可再生成；本轮测试已更新，不满足 72 小时阈值 |
| `/Users/pray/project/medical_audit/.codegraph` | 37 MiB | 可再生成；最后活动早于阈值 |
| `/Users/pray/project/medical_audit/web/out` | 2.5 MiB | 可再生成；最终构建后才能移动 |
| `/Users/pray/project/medical_audit/archive/.DS_Store` | 8 KiB | Finder 元数据 |
| `/Users/pray/project/medical_audit/data/.DS_Store` | 6 KiB | Finder 元数据；不移动其父目录 |

以下 `.DS_Store` 位于受保护的知识批次目录中，虽可再生成，本轮仍保留，避免清理动作深入受保护数据树。`web/.next` 在本轮构建后有新鲜活动，也不进入超过 72 小时候选。

满足 72 小时、已证明可再生成且可在本轮请求移动的 exact paths 只有：

```text
/Users/pray/project/medical_audit/.codegraph
/Users/pray/project/medical_audit/web/out
/Users/pray/project/medical_audit/archive/.DS_Store
/Users/pray/project/medical_audit/data/.DS_Store
```

合计近似 40 MiB。2026 年 8 月 13 日 14:45，经用户确认后使用系统 Trash 工具完成同卷移动；当时四个 Trash 目标保留原 inode 和内容哈希，Git 状态哈希保持不变。

清理收据位于 `/Users/pray/.Codex/file-history/medical_audit-20260813T114016+0800/local-cleanup-trash-receipt.json`，SHA-256 为 `cc03c126ed6e81fb6b6864b6760110e6c5d17551134034750a6f343d664d91d2`。恢复位置为：

```text
/Users/pray/.Trash/.codegraph
/Users/pray/.Trash/out
/Users/pray/.Trash/.DS_Store 14-43-35-198
/Users/pray/.Trash/.DS_Store 14-43-35-200
```

上述恢复位置是 14:45 收据的历史事实，不是当前事实。16:02 新鲜复核发现系统 Trash 为空，四个源路径与四个 Trash 目标均不存在；macOS unified log 显示 Finder 在 15:10:40 执行了 `Trash being emptied`，但日志不能证明触发者。当前没有本地 APFS snapshot，也没有在用户目录中找到原 inode，因此这 4 个可再生成/无跟踪对象当前不可从系统 Trash 恢复。追加收据位于 `/Users/pray/.Codex/file-history/medical_audit-20260813T114016+0800/local-trash-recovery-boundary-addendum.json`，SHA-256 为 `3105c57319755825d1f19d2791dece3dc560dcf923d03759a3ec658d497abc23`。

### 第二批受管隔离结果

执行阈值刷新为 `2026-08-10T15:56:33+08:00`。以下 5 个目录均无打开文件、最后有效活动早于阈值，所在卷与受管隔离目录相同；其 Git HEAD 或 tracked blob 参考提交均属于当前历史祖先。全量文件与符号链接摘要已写入 manifest。

```text
/Users/pray/project/medical_audit_h1_fix_20260721
/Users/pray/project/medical_audit_loop126_acceptance_contract_20260803
/Users/pray/project/medical_audit_deploy_84c2420_20260804
/Users/pray/project/medical_audit_deploy_b8e4737c_20260803
/Users/pray/project/medical_audit_loop129_deploy_2e9495d7
```

合计分配空间为 2,621,840 KiB，约 2.50 GiB。原系统 Trash manifest 位于 `/Users/pray/.Codex/file-history/medical_audit-20260813T114016+0800/legacy-workspaces-cleanup-exact-manifest.json`，SHA-256 为 `88cf3a119537184c6d13553d170e3ba61faabbd11412940d4ed421cdaf961b32`；其 Trash 操作保持 `blocked`。用户随后确认受管同卷隔离方案，授权包 SHA-256 为 `c790c7e1b4122e6adc0087f85f0fca609bf7327776cc48770edac897a0e633c5`。

2026 年 8 月 13 日 16:36，五个目录已经同卷 rename 到 `/Users/pray/.Codex/file-history/medical_audit-20260813T114016+0800/quarantine/`。五个原路径均不存在，五个隔离目标均存在；移动前后 inode、全量文件与符号链接树哈希、候选 Git 状态哈希全部一致。隔离目录根权限为 `0700`，实际永久释放空间为 `0`。

移动收据位于 `/Users/pray/.Codex/file-history/medical_audit-20260813T114016+0800/legacy-workspaces-managed-quarantine-move-receipt.json`，SHA-256 为 `b7e4f85d71146b6b1cc77d63622dc7f989b8afe538f4f585b8e57d39b6962426`。四个有效独立 Git 仓库在隔离后通过 `fsck --connectivity-only`；Loop 126 的既有损坏 gitfile 保持不变。恢复方式是把每个隔离目标同卷 rename 回收据记录的精确原路径；恢复前必须确认原路径不存在。H1 永久删除保持 `blocked`，其余四项永久删除仍需新的逐项授权。

### 第三批 Loop 128 父子目录隔离结果

隔离前，`/Users/pray/project/medical_audit_loop128_ocr_failclosed_20260804` 注册为 `/Users/pray/project/medical_audit_deploy_dda167f9_20260804_ref` 的 worktree；父仓库的 objects alternates 指向当前候选仓库 `.git/objects`。只读盘点确认：

- 两个工作区均 clean、无打开文件；`b96ba72d`、`dda167f9` 和全部 ref tip 均为当前候选历史祖先，父仓库 `fsck --connectivity-only` 通过。
- 子目录 2 个 `tmp` 文件均与当前仓库相同；父仓库 32 个 `tmp` 文件中 2 个与当前仓库相同、30 个已进入证据包，未发现未覆盖的运行证据。
- 两个目录合计 1,277,336 KiB，约 1.218 GiB；全量树哈希分别为 `ea72fce017daf8f07b1925a31ff2e98e710f93513e9e9ec81cf70d2e71257894` 和 `8b72415e75f497cd5e2111581cbb0b49d7cec41d0e4bc239f5dbb8e301fdbffb`。
- Git 2.50.1 临时探针证明：先执行 `git worktree repair --relative-paths`，再把保持同级布局的父子目录依次同卷 rename，最终 worktree 注册、分支和 `fsck` 可保持有效。
- 授权操作只改变子 worktree `.git`、父仓库 worktree `gitdir` 和 `extensions.relativeWorktrees` 三处关联元数据；其余载荷摘要必须不变。两路径 rename 不是成对原子操作，执行脚本提供了失败回滚。
- 隔离后父仓库仍依赖当前候选仓库 objects alternates，因此不是自包含 Git 副本；当前候选仓库不得因本清理任务移除。

精确授权包位于 `/Users/pray/.Codex/file-history/medical_audit-20260813T114016+0800/loop128-parent-child-managed-quarantine-authorization-request.json`，SHA-256 为 `c5391b2b3d9f0da876038ef7f2f49295f554d4109d418057a78fbda47600246a`。

2026 年 8 月 13 日 17:44，经用户确认后已完成相对关联转换和成对同卷移动。两个原路径均不存在，两个隔离目标位于 `/Users/pray/.Codex/file-history/medical_audit-20260813T114016+0800/quarantine/`；inode 保持不变，子 worktree 和父仓库的非指针载荷哈希分别保持 `230a3b302d5507d2142445863ad7364feb9d4a6e1bdb15725e73e3162f074a45` 与 `11c16a13e60baa597e6db9fd5d06e92a2834a3af4ce6aa7af44fdbd69d2c8291`。worktree 注册、clean 状态、`fsck`、ref tip 祖先关系、alternates 和候选 Git 状态全部通过；实际永久释放空间为 `0`。

移动收据位于 `/Users/pray/.Codex/file-history/medical_audit-20260813T114016+0800/loop128-parent-child-managed-quarantine-move-receipt.json`，SHA-256 为 `f10217bf562e84de1eea735d4f6f2e78d509a8f9e4f288bbe80cc8e8a9b27d4d`。三份原绝对关联元数据备份位于 `/Users/pray/.Codex/file-history/medical_audit-20260813T114016+0800/loop128-pair-prechange-metadata/`。恢复时须成对 rename 回原路径，并用该备份恢复三处绝对关联元数据；任何永久删除仍未授权。

## 生产备份清理

历史报告只列出部分 2026 年 8 月 9 日备份，且缺少新鲜 transaction 类别和隔离恢复证明。当前结论：

```text
status=blocked
reason=no_fresh_isolated_restore_evidence
production_delete=not_run
```

解除阻塞需要新鲜 L3 inventory、同 stamp 的 app/env/db/nginx/web/transaction 完整性、保留集计算、隔离恢复结果和逐条绝对路径删除授权。

## 仍待完成

| 任务 | 负责人 | 阻塞条件 | 下一门禁 | 证据等级 |
|---|---|---|---|---|
| SSO/OIDC 和可信身份代理 | 平台负责人 | 身份方案未决 | 认证架构评审 | not_run |
| 生产业务 UAT | 产品与医院审计团队 | 可信身份未启用 | 脱敏测试数据和写授权 | not_run |
| 真实 HIS、DLP、OCR/LLM | 集成负责人 | 现场与 Provider 授权 | 独立调用和费用门禁 | not_run |
| rules/archive 持久化 | 产品与后端 | 当前 Sample/Preview | PRD 和 schema 评审 | sample_only |
| 隔离恢复演练 | 运维负责人 | 新鲜备份集合未验证 | 隔离恢复授权 | blocked |
| 性能、告警和灾备 | 运维与测试 | 基线和目标未定义 | 非功能需求评审 | not_run |
| 共享 Nginx HTTP/2 警告 | 基础设施负责人 | 共享配置不在本轮范围 | 独立变更授权 | not_run |

## 2026 年 8 月 13 日候选收口复审

- 高风险 diff 复审发现两项整改附件鉴权顺序缺陷：上传在父资源可见性前处理文件；列表在附件存储未启用时提前返回空结果。
- 两条新增 RED 回归分别稳定得到 `422` 和 `200`；最小修复后整改附件定向测试 `6/6` 通过，不可见资源统一先返回 `404`。
- 全量 Python 为 `995 passed, 5 warnings`；5 条 warning 均来自第三方 SWIG 类型。Ruff 和 Mypy 117 个源文件通过。
- Web 为 41 个文件、412 项测试通过；typecheck、lint、26/26 静态页面构建通过。完整本地全栈 Playwright 为 `17/17`，机器收据为 `status=pass`、`feature_count=27`、`provider_call=false`。
- 最终候选 exact-manifest 和收口收据保存在 `/Users/pray/.Codex/file-history/medical_audit-20260813T181500+0800-candidate-closeout/`；该本地收据不构成 staging、commit、push、部署或生产业务验收授权。

## 2026 年 8 月 14 日 Draft PR 复审整改

- Draft PR 复审确认两类 P1：生产只读壳层仍残留可写控件；报告签发和整改状态迁移存在并发竞态。
- `/medical-audit`、`/chat`、`/ocr` 和 `/analytics` 在 `public-shell-readonly` 构建中不请求受保护 API，也不渲染上传、创建、发送、签发或状态变更控件。生产前端验收合同同时把这些控件列为壳层禁用项。
- 报告签发改为在任务存储锁和数据库行锁内重新检查项目可见性、关闭态、签发态和构建门禁。两个并发请求只允许一个成功，另一个返回 `409`，并且只生成一条签发操作日志。
- 整改状态更新使用旧状态条件更新。过期会话不能覆盖已经提交的状态；冲突返回 `409`。
- 知识库统计新增真实 PostgreSQL 回归，覆盖等长 chunk、多个 index version、active 和 candidate 聚合。测试数据库名必须使用 `medical_audit_test_` 前缀，测试结束删除临时表。
- 本轮使用原生临时 PostgreSQL，不使用或修改本地 Docker。完整 Python 为 `999 passed, 5 warnings`；Web 为 41 个文件、417 项测试通过；typecheck、lint 和 26/26 页面构建通过。
- 本轮 21 个授权变更文件的路径、SHA-256、质量门禁和外部副作用边界保存在 `/Users/pray/.Codex/file-history/medical_audit-20260814T101746+0800-p1-fix/p1-review-remediation-receipt.json`。
- 本轮证据等级为 L2 本地活体验证。没有访问生产业务、执行 Provider 调用、stage、commit、push、合并或部署。

## 2026 年 8 月 14 日 PR #275 交付审计与本地收口

- 首次只读交付审计在 `cc711fdb4dc2b36d2b5de705939a7726917960f1` 发现权威状态文档、PR 正文和 OpenAPI 覆盖漂移；该观察保留为历史问题来源。
- 2026-08-14 14:41 的后续只读审计确认 PR head `b9553349a31d305aefc8b1ca8b5adfaa9628adf3` 和 run `31776394739` 一致，CI 全绿；同时确认 tracked 当前状态段仍混入提交前 head 和瞬时 push 状态。
- 本报告和权威入口现改用「带时间外部观察」模型。该模型允许后续 commit 继续引用已发生的观察，但必须为新的 exact head 取得新的外部收据。
- 只读导航 API 请求门禁和整改可见性分页已通过先红后绿的定向回归。
- 后端未设置访问模式环境变量时继续回退 `header-transition-test`，本轮没有把它写成已修复。该行为被显式接受为本地兼容风险；生产 Compose、生产 env 示例和部署脚本必须设置 `public-shell-readonly`，任何缺少显式模式的新部署入口均为 NO-GO。
- 本地文档状态修复门禁没有访问生产、调用 Provider、操作本地 Docker 或数据库服务，也不包含 Git 或 GitHub 写入授权。
- 完整本地回归为 Python `1002 passed, 1 skipped, 5 warnings`、Web `417 passed` 和 Playwright `17/17`；Ruff、Mypy、typecheck、lint、26/26 build、docs lint 均通过。唯一 skip 是本机没有 `MEDICAL_AUDIT_TEST_POSTGRES_URL`；对应真实 PostgreSQL 聚合回归已在 exact-head CI 通过。
- exact-head CI run `31776394739` 进一步通过 Python `1003 passed`，包含本地环境跳过的 PostgreSQL 聚合回归。

## 2026 年 8 月 15 日本地修复门禁

- 最近可引用的远端证据仍是 `4b42b3eab6972d8ce7d870346f13d16f8ef04f79` 与 exact-head CI run `31778904386`；本节变更尚未提交、推送或取得新 CI。
- 后端缺失访问模式环境变量时改为默认 `public-shell-readonly`；只有显式 `MEDICAL_AUDIT_KB_DEV_MODE=1` 或显式模式才启用本地 Header 模拟。
- 生产 release manifest 必须精确声明 `NEXT_PUBLIC_MEDICAL_AUDIT_API_ACCESS_MODE=public-shell-readonly`。
- `/workspace` 从别名纠正为第 21 个独立页面；兼容跳转只保留 `/findings` 和 `/knowledge-query`，功能总数仍为 27。
- 生产导航只读 gate 现在要求 S1、导航后 S2 和 S1→S2 零审计增量比较；该能力只完成本地实现和合同测试，本轮没有运行生产命令。
- 疑点深链改为每个 URL 只应用一次；整改未知持久化状态稳定映射为 `409`；报告工作台按项目缓存签发 actor。
- tracked 文档中的用户特定 SSH key 绝对路径改为仓库外 `$SSH_KEY_PATH` 占位，不读取或复制 key 内容。
- 首轮完整回归为 Python `1011 passed, 1 skipped, 5 warnings`、Web `418 passed`、Playwright `17/17`；Ruff、Mypy、typecheck、lint、26/26 build 和 docs lint 通过。随后复核发现 SSH 只读确认值误用公网域名，新增 RED 回归并纠正为固定 SSH 观察目标 `101.34.52.232`；最终 Python 为 `1012 passed, 1 skipped, 5 warnings`，公开壳层静态构建通过。生产、Provider、本地 Docker、Git/GitHub 写入均未执行。

## 交付边界

- 外部交付观察确认 Draft PR #275 在 `4b42b3ea…` 完成 exact-head CI。本地修复门禁未执行 stage、commit、push、PR 修改、Ready、review、merge、部署、生产 POST、生产业务 GET、Provider 调用或生产删除。
- 本地 Docker 未扫描、清理、构建或修改。
- 首批 4 个 exact paths 已按确认移动到系统 Trash，但随后被 Finder 清空，当前不可恢复；操作触发者未知。第二批 5 个旧目录与第三批 Loop 128 父子目录均已按确认移动到受管同卷隔离目录，当前可恢复且未释放磁盘空间。所有永久删除仍未授权。

## 完成证据

本节汇总不同时间与来源的证据；本地收据、GitHub CI 和生产历史观察不得互相替代。

- 本地全栈收据：`tmp/outputs/local-fullstack-feature-acceptance-latest.json`；当前合同要求 `status=pass`、`feature_count=27`、`provider_call=false`，包含 21 个独立页面、2 个兼容跳转和 4 条活体业务工作流。最终数值以本门禁重跑后的收据为准。
- 本地全栈收据会绑定整个脏工作树，因此也记录了本轮明确保留的 `AGENTS.md`、`.claude/` 和 `CLAUDE.md`。本门禁授权范围以专项收据中的 18 个 `scoped_files_sha256` 为准，不把这些既有用户文件计入交付。
- 提交前收据身份：分支 `codex/medical-audit-reanalysis-playbook-20260813`，观察基线 SHA 为 `cc711fdb4dc2b36d2b5de705939a7726917960f1`；最近外部观察 head 为 `d1973206d4f9b01ad0b287fb252fccf760fdab5c`。两者分别绑定各自时间点，不能混写为 tracked 文档自身身份；后续状态同步提交另行由 GitHub 与仓库外收据绑定。
- Python：最新完整 `uv run pytest` 为 `1016 passed, 1 skipped, 5 warnings`；`uv run ruff check .` 和 `uv run mypy src` 通过，Mypy 覆盖 117 个源文件。唯一 skip 是本机未配置 `MEDICAL_AUDIT_TEST_POSTGRES_URL`；5 条 warning 来自第三方 SWIG 类型。
- Web：`pnpm web:test` 为 41 个文件、418 项测试通过；typecheck、lint 和 build 通过，Next.js 生成 26/26 个静态页面，仓库自有 warning 为零。
- 文档：固定上游 commit `90ff8ccc07da5afc5ae00eb3516f9efa98bd572d` 的中文样式检查与项目文档合同均通过；119 个纳入检查的 Markdown 文件没有 frontmatter、断链或标题错误，FastAPI OpenAPI 的 123 个方法/路径操作全部逐项覆盖。
- exact-head CI：run `32499803192` 为 `success`；Python `1018 passed`，Web `419 passed`，普通/公开壳层构建和文档门禁通过；该结论只覆盖观测 head `d1973206…`。
- 工程：`git diff --check` 通过。根路径公开壳层负向回归和本地 Chat Workbench 显式访问模式合同均已纳入定向验证；完整门禁结果以本节列出的最新收据为准。
- 依赖版本：Python 3.12.13、uv 0.11.11、Node.js 22.22.0、pnpm 9.15.0、Next.js 15.5.19。
- 既有生产 L3 收据：`tmp/outputs/project-reanalysis-production-state-20260812.json`，SHA-256 为 `9e08f2271ceb0334f500c2f346395fe02590343755cd47afbce22468cdb4aa21`。本轮未刷新生产状态。
