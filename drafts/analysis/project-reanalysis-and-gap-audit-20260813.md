---
title: medical_audit 全量复盘、差异与清理审计
doc_type: analysis-report
module: repository
status: active
created: 2026-08-13
updated: 2026-08-13
owner: self
source: human+ai
observed_at: 2026-08-13T12:54:09+08:00
local_git_sha: ccc73e95820e39559430e96c01d52c8dfb77a246
production_git_sha: 25e1654e0c44ca5cbb2bb42e82debdb40fa6f224
evidence_grade: L2-local-live+prior-L3-production-read-only
production_side_effect: none
provider_call: false
---

# medical_audit 全量复盘、差异与清理审计

本报告记录候选分支 `codex/medical-audit-reanalysis-playbook-20260813` 的代码、文档、本地测试、生产历史证据和清理边界。报告不证明候选已合并、推送或部署。

## 事实

### Git 与生产基线

- 开始执行时，`main == origin/main == ccc73e95820e39559430e96c01d52c8dfb77a246`，工作树干净。
- 2026 年 8 月 12 日 L3 只读证据显示，生产部署 SHA 为 `25e1654e0c44ca5cbb2bb42e82debdb40fa6f224`。
- `25e1654e..ccc73e95` 没有 `src/` 或 `web/` 业务源码差异，仅含验收脚本和 Sprint 5 文档。
- 候选在 `ccc73e95` 之上新增未提交代码和文档；生产未变更。

### 已修复问题

1. 生产 API 增加 `public-shell-readonly`，在认证和审计业务处理前阻断受保护请求。
2. 前端生产构建不再发起受保护 API 请求，隐藏角色切换和写操作。
3. `/workspace?finding=<id>` 改为在疑点加载后定位，并统一不可见提示。
4. 整改使用真实 UUID、真实空状态、只读 Sample、父项目鉴权和后端状态机。
5. 报告签发复用项目可见性、关闭态、构建门禁和 `SIGN_REPORTS`。
6. 知识库统计按 package 和文档预聚合，修复等长文本与多 index 放大。
7. 更新旧 E2E 断言，修复 React lint 警告和 Next.js 根目录警告。

### 本地验证

- `pnpm local:fullstack:e2e`：17/17 通过。
- 临时 Store：SQLite。
- Provider：确定性 Fake，`provider_call=false`。
- 机器收据：20 个独立页面、3 个别名和 4 条真实 HTTP/SQLite 业务工作流，共 27 条功能记录。
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

候选新增权威文档入口、架构、API、用户和管理员 Playbook、验收矩阵、写作规则和 `docs:lint`。

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

## 候选收口复审

- 高风险 diff 复审发现两项整改附件鉴权顺序缺陷：上传在父资源可见性前处理文件；列表在附件存储未启用时提前返回空结果。
- 两条新增 RED 回归分别稳定得到 `422` 和 `200`；最小修复后整改附件定向测试 `6/6` 通过，不可见资源统一先返回 `404`。
- 全量 Python 为 `995 passed, 5 warnings`；5 条 warning 均来自第三方 SWIG 类型。Ruff 和 Mypy 117 个源文件通过。
- Web 为 41 个文件、412 项测试通过；typecheck、lint、26/26 静态页面构建通过。完整本地全栈 Playwright 为 `17/17`，机器收据为 `status=pass`、`feature_count=27`、`provider_call=false`。
- 最终候选 exact-manifest 和收口收据保存在 `/Users/pray/.Codex/file-history/medical_audit-20260813T181500+0800-candidate-closeout/`；该本地收据不构成 staging、commit、push、部署或生产业务验收授权。

## 交付边界

- 未执行 merge、push、PR、部署、生产 POST、生产业务 GET、Provider 调用或生产删除。
- 本地 Docker 未扫描、清理、构建或修改。
- 首批 4 个 exact paths 已按确认移动到系统 Trash，但随后被 Finder 清空，当前不可恢复；操作触发者未知。第二批 5 个旧目录与第三批 Loop 128 父子目录均已按确认移动到受管同卷隔离目录，当前可恢复且未释放磁盘空间。所有永久删除仍未授权。

## 完成证据

本节在候选代码和文档收口后更新；收据为本地证据，不代表候选已提交、合并或部署。

- 本地全栈收据：`tmp/outputs/local-fullstack-feature-acceptance-latest.json`；最新运行是 `status=pass`、`feature_count=27`、`provider_call=false`，包含 20 个独立页面、3 个别名和 4 条活体业务工作流。
- 收据候选身份：分支 `codex/medical-audit-reanalysis-playbook-20260813`，基线 SHA `ccc73e95820e39559430e96c01d52c8dfb77a246`；未提交文件清单和 manifest SHA-256 以机器收据中的 `candidate_identity` 为准。
- Python：`uv run pytest` 为 `995 passed, 5 warnings`；`uv run ruff check .` 和 `uv run mypy src` 通过，Mypy 覆盖 117 个源文件。5 条 warning 来自第三方 SWIG 类型。
- Web：`pnpm web:test` 为 41 个文件、412 项测试通过；typecheck、lint 和 build 通过，Next.js 生成 26/26 个静态页面，仓库自有 warning 为零。
- 文档：固定上游 commit `90ff8ccc07da5afc5ae00eb3516f9efa98bd572d` 的中文样式检查与项目文档合同均通过；119 个纳入检查的 Markdown 文件没有 frontmatter、断链、标题或覆盖错误。
- 工程：`git diff --check` 通过。最后新增的根路径公开壳层负向回归通过；完整 Python 套件的其余代码未再变更。
- 依赖版本：Python 3.12.13、uv 0.11.11、Node.js 22.22.0、pnpm 9.15.0、Next.js 15.5.19。
- 既有生产 L3 收据：`tmp/outputs/project-reanalysis-production-state-20260812.json`，SHA-256 为 `9e08f2271ceb0334f500c2f346395fe02590343755cd47afbce22468cdb4aa21`。本轮未刷新生产状态。
