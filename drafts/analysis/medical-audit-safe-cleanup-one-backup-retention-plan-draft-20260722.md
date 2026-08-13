---
title: medical_audit 安全清理与单恢复集保留计划
doc_type: cleanup-plan
module: repository+production-operations
status: superseded
created: 2026-07-22
updated: 2026-08-13
owner: self
source: local-readonly+historical-production-evidence
---

# medical_audit 安全清理与单恢复集保留计划

> 从 `/Users/pray/project/medical_audit_h1_fix_20260721` 原样归并的历史独有草稿；2026-08-13 标记为 `superseded`。当前状态以 [文档索引](../../docs/README.md) 为准。

## 1. 决策摘要

- 将“历史备份只保留一份”解释为：保留一个最新、完整、经过恢复验证的生产恢复集，而不是只保留一个文件。
- 一个完整生产恢复集必须同时包含同一 stamp 的 `app`、`env`、`db`、`nginx`、`web` 五个成员。
- 预期保留 stamp：`h1-strict-abstention-905f9f4-20260722T090844Z`。
- 该恢复集的预期 rollback source SHA：`18d3ff86170558b0ea20eafc1dbd6e4a32c33a28`；当前生产预期 SHA 为 `905f9f485dbe1a390fbd1fefea5a89f09722cdf9`。两者必须在删除前重新只读核验。
- 本计划不删除 active release、`current` symlink、deploy transaction receipts、query/audit history、provider evidence、Git stash、唯一参考材料或昂贵的 active embedding indexes。

## 2. 证据边界

### 本轮新鲜本地事实

- 活跃规划/发布 clone：`/Users/pray/project/medical_audit_h1_fix_20260721`，约 `951M`，`origin/main=905f9f4...`。
- 根 clone：`/Users/pray/project/medical_audit`，约 `69G`，其中 `tmp/` 约 `66G`；有 `48` 个 tracked dirty entries 与 `335` 个 untracked entries，禁止整目录删除。
- 两个 Phase 7 clones 共约 `585M`，工作树 clean、无进程占用、所有 6 个 local branch tips 均已进入 `origin/main@905f9f4...`。
- `_medical_audit_refs_backup` 约 `91M`，仍有约 `20-22` 个路径在 root/H1 中缺失或内容不同，必须保留。
- 三个 Superpowers worktrees 共约 `3.1G`；两个 dirty worktree 的 diff 完全相同，diff SHA-256 为 `d353d60968fad49948fd3d3aaca6ecfffc6a49efc66adc0df610f9ba036715a2`。
- 根 `tmp/outputs` 有 7 个本地 pre-write DB dumps，总计 `20,588,602,337` bytes；去除最新 P6C dump后的旧 dump 候选为 `14,752,417,057` bytes。
- 中断文件 `tmp/knowledge-query-indexes/p6b-kimi-policy-industry-business-environment-1024-20260704/.!84219!embeddings.jsonl` 为 `800,034,816` bytes，无引用、无打开句柄。
- 根 Git object store 报告约 `344 MiB` garbage，但当前不满足立即 aggressive prune 的安全条件。

### 历史生产证据，不是本轮当前状态

- Loop 72 Phase A 在部署前只列出每类最新 5 项；当时至少有 4 个完整旧 deploy sets，且 DB 类混有一个独立 H2 agent-cleanup backup。
- Loop 72 Phase B 随后成功创建预期保留 stamp 的五类备份并完成部署，脚本 exit `0`。
- 当前服务器全量备份数、准确大小、symlink/transaction 状态与可回收空间尚未在 Loop 73 重新通过 SSH 观察。

## 3. 保留、条件删除与禁止删除

| 对象 | 分类 | 决策 | 原因/门禁 |
|---|---|---|---|
| `medical_audit_h1_fix_20260721` | active clone | 保留 | 最新 main、部署证据与计划状态 |
| `medical_audit` root | dirty root | 保留 | 大量唯一 dirty/untracked state；仅清理其已分类 artifacts |
| `_medical_audit_refs_backup` | unique references | 保留 | 合同、媒体、PPT、UI、表格、draft 仍有唯一/差异内容 |
| retained stash `f23155b...` | Git recovery | 保留 | 当前 planning/draft 恢复点，不属于历史文件备份 |
| active/referenced Kimi index roots | costly generated artifacts | 保留 | provider embeddings 重建昂贵，且部分 package keys 已 active |
| Phase 7 main/q1 clones | redundant clones | 条件删除 | clean、无占用、branch tips merged；q1 alternates 已损坏，不能作备份 |
| 3 Superpowers worktrees | redundant worktrees | 条件删除 | 先保存一份 dirty patch；保留 local branches；再正规 remove |
| 31 stale worktree admin entries | Git metadata | 条件清理 | 真实 worktrees 处理后执行 `git worktree prune` |
| 7 local pre-write DB dumps | historical local backups | 条件删除 | 生产 survivor 完整恢复验证后全部删除；删除前保留 SHA/snapshot receipts |
| interrupted `.!84219!...jsonl` | incomplete artifact | 条件删除 | 无引用/占用；执行前再查一次进程 |
| cache/debug/screenshots older than 7 days | low-value artifacts | 暂缓/可选 | 仅约 `413M`，证据价值可能高于空间收益 |
| production latest five-file set | sole production recovery set | 保留 | 需完整性、restore SHA 与隔离恢复演练通过 |
| all older deploy backup payloads | production history | 条件删除 | 生成 exact manifest，完成 quarantine 与 postcheck 后 purge |
| H2 pre-agent-cleanup DB payload | operation backup | 条件删除 | local before/rollback/receipt 已保留；仍需 survivor restore proof |
| `backups/transactions`, active release, `current` | runtime/receipts | 禁止删除 | 不属于历史 backup payload；可能被 rollback/reconciliation 引用 |
| query/audit history | audit evidence | 禁止删除 | 用户要求保留审计历史，且不属于文件备份清理 |

## 4. 预期唯一生产恢复集

只保留以下五个 exact paths；任何一个缺失、symlink、空文件、权限异常或 stamp 不一致都 `NO-GO`：

1. `/opt/medical-audit/backups/app/pre-deploy-h1-strict-abstention-905f9f4-20260722T090844Z.tar.gz`
2. `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-h1-strict-abstention-905f9f4-20260722T090844Z`
3. `/opt/medical-audit/backups/db/pre-deploy-h1-strict-abstention-905f9f4-20260722T090844Z.sql.gz`
4. `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-h1-strict-abstention-905f9f4-20260722T090844Z`
5. `/opt/medical-audit/backups/web/audit-web-pre-deploy-h1-strict-abstention-905f9f4-20260722T090844Z.tar.gz`

保留集验证要求：

- 全部为 regular files，非 symlink，mode/owner 符合部署脚本合同。
- app archive 内 `.deploy-sha` 必须为 `18d3ff8...`；Web archive 与 app archive可完整列出/解包，不能有 path traversal 或异常 special files。
- DB gzip 必须完整读取，并在隔离 PostgreSQL 16、无 host port、无生产 DSN 的临时环境完成 restore rehearsal；核对 schema、关键表与行数合同。
- env 文件只验证 metadata/hash，不读取或打印内容。
- 五文件 SHA-256、size、mtime、owner、mode 写入 private manifest；报告不得包含 secret。

## 5. 分阶段执行计划

### Phase A — 本地只读冻结

1. 重新记录所有 candidate paths 的 `lstat`、size、mtime、Git status、branch refs、alternates 与 `lsof`。
2. 对两个 dirty Superpowers worktrees 再算 diff hash，必须仍为 `d353d6...`。
3. 对 7 个 local DB dumps 验证现有 `SHA256SUMS` 路径与 metadata；不删除小型 snapshots/receipts。
4. 输出 local-delete manifest 和 SHA-256；没有 exact manifest 不执行删除。

### Phase B — 生产只读全量库存（需单独授权）

1. 运行 deployment-state audit，固定 `expected SHA=905f9f4...`、`required stamp=h1-strict-abstention-...`、`--backup-limit 1000`。
2. 对 `/opt/medical-audit/backups` 全树执行 `lstat/stat` inventory，只记录 path/category/size/mtime/mode/type，不读取 env 内容。
3. 检查 deploy lock、worker PID、transaction statuses、current release、deploy marker、disk、容器 health 与 Nginx test。
4. 将 payloads 分为 complete deploy sets、operation-specific backups、transaction receipts、unknown/orphan。unknown/orphan 一律不进入删除 manifest。

### Phase C — 唯一 survivor 恢复演练（需单独授权）

1. app/Web archive 在隔离目录只读展开并验证 restore SHA/manifest/static。
2. DB backup 在临时、无 host port PostgreSQL 16 中恢复；禁止连接生产 DB。
3. 演练失败立即停止；保留全部历史备份，不清锁、不重试删除。
4. 演练成功后删除临时容器/volume/目录，并保存 secret-free receipt。

### Phase D — Manifest 冻结与双授权

1. 生成 `keep_manifest`：只含上述五文件。
2. 生成 `delete_manifest`：列出每个候选的 exact path、category、size、mtime、SHA（适用时）和总回收 bytes。
3. 生成 `excluded_manifest`：transactions、current/release、query/audit history、unknown payloads。
4. owner 授权必须绑定三个 manifest SHA-256、候选数量和总 bytes；漂移则授权失效。

### Phase E — 本地可恢复清理（需单独授权）

1. 将两份相同 dirty worktree diff 保存为一份 patch，记录 hash；保留 local branch refs。
2. 使用 `git worktree remove` 清理 clean worktree；dirty worktree仅在 patch/hash核验后使用 explicit `--force`。
3. 独立 Phase 7 clones 使用 `/usr/bin/trash`，不永久删除；验证 branches 仍 reachable。
4. 使用 exact local manifest 删除 7 个旧 local DB dump payloads与中断文件；保留 checksum/snapshot/receipt。
5. 运行 `git worktree prune`；Git garbage 仅用保守 grace-period GC，不使用 `git gc --prune=now`。
6. 复查 root dirty status 完全未改变，并记录 `df` delta。

### Phase F — 生产 quarantine 与 purge（需独立 DELETE 授权）

1. 删除前重复 Phase B 的 SHA/lock/current/health/inventory comparison。
2. 仅将 manifest candidates 原子 `mv` 到同文件系统 private quarantine；不得跟随 symlink，不得 glob 删除。
3. 立即复查唯一 survivor、production SHA、current、containers、Nginx 与 GET-only smoke。
4. postcheck 通过后 purge quarantine；失败则按 manifest 原路径回移，不触碰 survivor。
5. purge 后全量 inventory 必须只剩一个五文件 deploy recovery set，以及明确排除的 transaction/audit receipts。

### Phase G — 收尾验收

- production SHA 与 current release 保持 `905f9f4...`；app/PostgreSQL/ClamAV/Nginx healthy。
- deploy lock absent，Nginx test pass，GET-only smoke pass，DB write false，provider not called。
- root dirty file set与清理前一致；active H1 clone、stash、unique refs backup均存在。
- 报告实际 deleted paths/count/bytes 与磁盘增量，不把估算写成事实。

## 6. 回收空间估算

- 本地第一批高置信候选：旧 local SQL dumps约 `14.75 GB`、Phase 7 clones约 `585 MB`、Superpowers worktrees约 `3.1 GB`、中断 index约 `800 MB`、Git garbage约 `344 MiB`，合计约 `19-20 GB`，但以执行前 manifest 为准。
- 若生产唯一 survivor 验证成功并删除最后一份本地 P6C dump，可再回收约 `5.84 GB`，本地总潜力约 `25 GB`。
- 生产端当前准确可回收量未知。历史报告显示每个完整 deploy set约 `5.0 GB`；不能用历史条目数量冒充当前空间结论。

## 7. Fail-closed 条件

- production SHA、required stamp、current release、deploy marker、lock/worker、candidate metadata或manifest hash任一漂移。
- survivor 五文件不完整、不可恢复、权限/类型异常，或 restore SHA 不是 `18d3ff8...`。
- candidate 是 symlink、directory、special file、active process input或被 transaction/current引用。
- root/H1 dirty scope变化，dirty patch hash变化，branch ref不可达或发现 unique/unmerged commits。
- 任一命令可能触碰 env 内容、production DB、provider、query/review/document/index/agent写入。

## 8. 下一步只读授权模板

> 明确授权执行 Loop 73 Phase B 生产只读备份清理预检：预期生产 SHA `905f9f485dbe1a390fbd1fefea5a89f09722cdf9`，预期唯一保留 stamp `h1-strict-abstention-905f9f4-20260722T090844Z`，允许使用 `/Users/pray/Downloads/DDDD.pem` 执行 deployment-state audit（`--backup-limit 1000`）以及 `/opt/medical-audit/backups` 全量 lstat/stat inventory、deploy lock/worker、transaction status、current/release/marker、disk、container health 和 Nginx 只读检查；允许生成本地 secret-free keep/delete/excluded manifests，但禁止读取或打印 env 内容，禁止 backup 创建、文件移动/删除、worktree/branch/stash 变更、DB/schema/env/runtime/provider/query/review/document/index/agent/deploy 写入。任何 SHA、stamp、lock、health、文件类型或 inventory 漂移立即停止。

生产 survivor 恢复演练、local cleanup、production quarantine/purge 必须分别取得后续精确授权，不能由本只读授权推断。

## 9. Phase B 实测结果（2026-07-22，run `20260722T103231Z`）

- pre/post deployment-state audit 均为 `L3-production-read-only/pass`：production SHA/current release保持 `905f9f4...`，GET-only，DB write `false`，provider `not_called`，audit delta为零，app/PostgreSQL/ClamAV/Nginx healthy。
- `/opt/medical-audit/backups` 两次全量 metadata scan哈希一致：`631b4b822d2634e6494d91331b66e48b5b0356160b9577882f57ebf66d6de807`；共 `138` entries、`14` 个完整五类 deploy sets、`0` 个 incomplete deploy set。
- exact survivor为 `5` files、`5,021,701,698` bytes；13 个旧完整 sets为 `65` files、`65,281,701,087` bytes的条件删除候选。该 manifest 明确 `delete_authorized=false`。
- excluded为 `68` entries；保留所有 transaction/control evidence、operation-specific agent backups、observations 与历史 cleanup manifest。11 个 transactions中有一个历史 `restore-failed`，已 fail-closed 排除，不能随 payload cleanup删除。
- deploy lock absent、matching worker为空、inventory前后稳定；未打开或哈希任何 backup payload，未读取 env 内容，未移动/删除文件。
- 结论仅为 `GO_TO_REQUEST_RESTORE_REHEARSAL_ONLY`。Phase C 隔离恢复演练仍需独立授权；在其通过前不得执行 quarantine、purge或本地旧备份删除。

## 10. Phase C 首次门禁结果（2026-07-22）

- 已获得 exact-bound 隔离恢复授权，但在首个本地 prerequisite gate 失败关闭：APFS Data volume仅余 `3,955,404 KiB`（约 `3.77 GiB`），小于 survivor DB gzip本身的 `4,835,166,573` bytes，更不足以容纳展开后的 PostgreSQL restore volume。
- Docker可用且有 `postgres:16`，但不存在 pgvector-enabled PostgreSQL 16 image。plain PostgreSQL不能作为本项目恢复成功证据。
- 只读诊断显示 Docker build cache有 `17.54 GB` reclaimable、images有 `6.808 GB` reclaimable；未执行 prune/pull/build，不能把估算当作已释放空间。
- 本次在 SSH 前停止：未读取/哈希 survivor 或 env，未创建临时目录、容器、volume，未发生生产或本地 DB write，也未自动重试或改用远端环境。
- Phase C 状态为 `NO-GO_PRE_PAYLOAD`；生产 65-file delete-candidate manifest继续保持 `delete_authorized=false`。

## 11. Phase C1 本地缓存清理与远端恢复结果（2026-07-22）

- 本地仅执行 unused Docker build cache prune：Docker报告删除 `18.54 GB`，APFS可用量实际增加 `17,705,284 KiB`；即时前后 container/image/volume identity hash一致。
- fresh生产 audit与138-entry inventory再次通过，inventory SHA保持 `631b4b82...`；生产 SHA/current/health/lock均无漂移，恢复资源名无碰撞。
- app tar严格校验发现 npm symlink `app/web/node_modules/tsconfig-paths/node_modules/.bin/json5`。当前合同只允许 regular file/directory，故在 extraction loop、容器创建及DB restore之前失败关闭。
- 失败后未重试：Web/env/Nginx/DB payload未读，临时 container/volume从未创建；error trap已删除唯一临时目录。生产 SHA/current保持不变且四个容器 healthy。
- 此失败不等于备份损坏，而是 validator合同过窄。下一次尝试必须获得新授权并实现“symlink target为relative、规范化后仍在archive root内、禁止hardlink/special file/path traversal”的 fail-closed合同。
- production delete-candidate manifest继续为 `delete_authorized=false`。

## 12. Phase C2 safe-symlink 重试结果（2026-07-22）

- fresh audit/inventory门禁通过，但app archive另含hardlink `app/web/node_modules/esbuild/bin/esbuild`。
- Phase C2授权明确禁止hardlink，validator因此在 extraction loop之前失败关闭；这同样不等于archive损坏。
- 未读取Web/env/Nginx/DB，未创建restore container/volume，临时目录已由trap清理；生产SHA/current/health无变化。
- 若继续，必须单独授权“hardlink target为同archive root内、已验证regular member，禁止指向symlink/hardlink/special file且创建时不跟随filesystem links”的合同。当前65-file删除候选仍不可执行。

## 13. Phase C3 hardlink-compatible恢复结果（2026-07-22）

- app/Web archive恢复通过：app `26,013` members、`35` symlinks、`1` hardlink、`0` special files；Web `121` members；link graph均在root内，app marker为预期rollback SHA `18d3ff8...`。
- DB plain-SQL restore、同步压缩流hash和结构/计数query均exit zero；临时容器`network none`、零host ports并限制2 CPU/8 GiB/512 pids，restore process未连接生产DB。
- 临时volume峰值约`13.32 GiB`，根盘最低仍约`31.51 GiB`，未触碰15 GiB floor。
- 最终`pg_amcheck`因isolated DB未安装可选`amcheck` extension而失败；这不是relation corruption证据。授权不允许自动补装或重试，因此正确失败关闭。
- trap已删除全部Phase C3临时资源，生产SHA/current/health无变化。由于最终receipt emission前清理，row-count JSON及DB/schema hash未保存，production delete仍被阻止。

## 14. Phase C4 amcheck-enabled DB恢复结果（2026-07-22）

- 复用了已验证archive receipt，未重新读取app/Web/env/Nginx；仅对survivor DB执行一次isolated restore，无自动重试。
- 临时DB保持`network none`、零host ports、2 CPU/8 GiB/512 pids。DB gzip流SHA-256为`5b78cff9850840e18e4f18c5eb60b374869bcd10fd5a7a1289a7f7ec96b10499`，恢复后DB大小`13,206,412,311` bytes、public tables `43`。
- `amcheck`前已先持久化intermediate receipt：schema SHA-256 `b8090c6e...`、关键表计数和`amcheck_attempted=false`；该record SHA-256为`7dbd8c13...`。
- 随后仅在临时DB创建`amcheck 1.3`并运行`pg_amcheck`，结果`pass`。所有Phase C4临时资源已清理；独立reconciliation确认生产SHA/current、锁和四容器健康状态无漂移，且未连接生产DB。
- 两行最终凭据位于`tmp/outputs/loop73-phasec4-db-restore-20260722T151254Z.jsonl`，SHA-256为`632565f171b626a98fb90c271d5e2eed7a56969f9c6a56cac2bf8a62a11ed2c9`。
- 唯一survivor恢复证据现已通过，但65-file生产候选manifest仍为`delete_authorized=false`。下一门禁必须单独绑定manifest hash、候选数`65`、总bytes `65,281,701,087`并明确授权quarantine/purge；本阶段没有移动或删除任何备份。

## 15. Phase D manifest冻结结果（2026-07-23）

- fresh生产metadata inventory仍为138 entries，双scan SHA-256均为`631b4b822d2634e6494d91331b66e48b5b0356160b9577882f57ebf66d6de807`；生产SHA/current、锁、worker、四容器健康与Nginx均无漂移。
- keep/delete-candidate/excluded分别为5/65/68 entries，路径互斥且完整覆盖inventory。候选仍是13个完整历史deploy sets、`65,281,701,087` bytes；keep为唯一已恢复验证的五文件set、`5,021,701,698` bytes。
- frozen file SHA-256：keep `5b91fec2f3621ea6882da4fe2f539f3f0d1af56b1f937ec92067f031584641a4`；delete-candidate `bdcbc5debd5d15072fb5c413d1489934d231959b8884779e593f4addbc8b5f2a`；excluded `1902c94d0c8594fbb574b8cbd152b11eef5c9631371b0e245ea7f60e42296326`；freeze summary `2da914d9858841a7c77f8a9beab056ed91432470357e6a640026856f2dbcce8a`。
- authorization request文件SHA-256为`88625bece9f6a2c09ed95b8b491cfaa4776a56bd7f3a735bf1c087b31d5942b4`。所有manifest继续明确`delete/quarantine/purge_authorized=false`；本阶段未创建quarantine、未移动或删除备份。

### 下一门禁精确授权模板

> 明确授权执行 Loop 73 Phase F 生产备份 exact-manifest quarantine 与条件 purge：绑定生产 SHA `905f9f485dbe1a390fbd1fefea5a89f09722cdf9`、inventory SHA-256 `631b4b822d2634e6494d91331b66e48b5b0356160b9577882f57ebf66d6de807`、survivor stamp `h1-strict-abstention-905f9f4-20260722T090844Z`、keep manifest file SHA-256 `5b91fec2f3621ea6882da4fe2f539f3f0d1af56b1f937ec92067f031584641a4`、delete-candidate manifest file SHA-256 `bdcbc5debd5d15072fb5c413d1489934d231959b8884779e593f4addbc8b5f2a`、excluded manifest file SHA-256 `1902c94d0c8594fbb574b8cbd152b11eef5c9631371b0e245ea7f60e42296326`、freeze summary file SHA-256 `2da914d9858841a7c77f8a9beab056ed91432470357e6a640026856f2dbcce8a`及authorization request file SHA-256 `88625bece9f6a2c09ed95b8b491cfaa4776a56bd7f3a735bf1c087b31d5942b4`；候选仅限manifest内65个regular files、总计`65,281,701,087` bytes。允许执行前fresh只读SHA/current/inventory/lock/worker/health/type/metadata comparison；允许将exact candidates原子移动到同filesystem、私有且唯一的quarantine，并在survivor/excluded完整、生产SHA/current/health/Nginx与GET-only smoke通过后按manifest逐项purge；postcheck失败或结果未知时禁止purge，保留quarantine并停止，明确成功前禁止自动重试。禁止触碰五文件survivor、68个excluded entries、transaction/query/audit history，禁止glob/symlink-follow、生产DB/schema/env/runtime/container/deploy/provider/Git写入及其他DELETE；允许清理仅本次创建且已经清空的quarantine目录。

## 16. Phase F exact-manifest清理结果（2026-07-23）

- fresh preflight与原138-entry inventory SHA `631b4b82...`完全一致；65个candidate均为metadata精确匹配的regular files，quarantine路径不存在且与backup root同device。
- quarantine原子移动65文件、manifest bytes `65,281,701,087`。独立postcheck确认backup tree仅剩5个survivor及68个excluded，生产SHA/current、容器、Nginx和GET-only smoke全部通过后才允许purge。
- purge逐项删除exact 65 candidates，无glob、无symlink follow、无自动重试。最终candidate path剩余0，quarantine状态及空目录已清理。
- post inventory稳定为73 entries，SHA-256 `f3b905dae2ee2174b662e764bd4b49bd3fa77f3410f1bf4aae023f12ad05d400`。唯一五文件survivor与68个excluded/control entries均保留。
- 可用磁盘从`48,831,684,608`增加到`114,112,131,072` bytes，实测增加`65,280,446,464` bytes；与manifest payload bytes分开报告。
- 生产SHA/current保持`905f9f4...`，无deploy lock，四容器healthy，Nginx及GET-only release/static验证通过。未连接生产DB，未执行schema/env/runtime/container/deploy/provider/Git写入或其他DELETE。
- aggregate completion receipt：`tmp/outputs/loop73-phasef-completion-20260722T162411Z.json`，SHA-256 `97a073fcbb6fdea842aeb1f20165402f5cebeeb25400701862ed3c8a0f2b3f71`。

## 17. Loop 74 Phase A 生产闭环与本地清理清单（2026-07-23）

- 生产三重只读证据均通过：deployment-state audit、release-guard S1及73-entry全量inventory绑定同一生产SHA/current `905f9f4...`。inventory SHA仍为`f3b905da...`，锁/worker absent、四容器healthy、Nginx pass；未发生生产写入。
- 本地七个DB dump总计`20,588,602,337` bytes。唯一保留最新P6C dump `5,836,185,280` bytes；六个历史dump候选为`14,752,417,057` bytes。六个历史checksum receipt fresh pass，缺少历史receipt的P6A activation dump已直接计算SHA-256 `eff21dd3...`。
- 中断embedding临时文件`800,034,816` bytes、SHA-256 `d3ef0ac9...`，无repo reference和open descriptor，进入exact-path候选。
- Superpowers保留一个dirty patch survivor；另一个相同diff的dirty worktree和一个clean worktree进入条件移除清单。其branch refs均不删除。31个stale worktree metadata仅进入未来`git worktree prune`清单。
- Phase7 Q1 clone存在broken iCloud alternate；Phase7 main可能是其object donor。因此两者都从删除候选移入excluded，需先完成独立对象依赖修复/导出。
- 本地delete-candidate manifest为10个逻辑项：`15,552,451,873` exact regular-file bytes，加`2,157,572 KiB` worktree/metadata allocation。67个branch entries与4个stash全部保留。
- manifest file SHA-256：inventory `bd823744...`、keep `c01d24fb...`、delete-candidate `fa8bd93c...`、excluded `8cd408ca...`、summary `a42e8792...`。所有文件均声明`delete/trash/worktree remove/prune/Git mutation authorized=false`。
- 下一门禁只允许绑定上述exact manifest的本地清理；不得复用Phase A只读授权。生产端已完成唯一五文件survivor保留，不再进入本地清理授权范围。

## 18. Loop 74 Phase B1 本地regular-file清理结果（2026-07-23）

- owner同意上一轮提出的下一门禁后，本阶段仅执行第一批：6个旧DB dump payload和1个中断embedding payload；未触碰worktree、branch、stash、Phase7 clone或生产。
- Phase A五个receipt hash全部精确一致；7个candidate和唯一P6C survivor都完成fresh full SHA-256、regular/nlink、size/mtime/inode/device及lsof检查。
- exact candidates先原子进入private same-filesystem quarantine；survivor和root/H1 Git status不变后，才逐项unlink。最终purged `7` files、`15,552,451,873` logical bytes，rollback为空，quarantine保留为空目录。
- 唯一P6C dump仍在，SHA-256 `b4908eee...`；deleted payload的checksum/snapshot/receipt metadata全部保留。
- root项目`du`下降`15,187,952 KiB`，但APFS即时available仅增加`51,535,872` bytes。无Data volume snapshot，也未发现cleanup期间`/Users/pray`下新增的>100 MB文件；真实physical reclaim原因仍不确定，禁止把logical deleted bytes写成physical reclaimed bytes。
- execution receipt SHA-256 `4946dbed...`；reconciliation receipt SHA-256 `e595dbc1...`。Phase B2 worktree/remove/prune仍需独立门禁。

## 19. Loop 74 Phase B2 worktree consolidation结果（2026-07-23）

- retained continuation worktree及本地patch archive均保留相同dirty diff SHA-256 `d353d609...`，覆盖三个文档路径。
- 仅移除重复dirty worktree和clean release-candidate worktree；对应branch refs/tips全部保留，未执行branch delete。
- 随后prune正好31条stale worktree metadata。registry从35 entries收敛为canonical root与retained continuation两条，最终dry-run为空。
- root/H1 status、54个root branches、3个root stashes、Phase7 main/Q1、Q1 alternate、refs backup与P6C DB survivor均未漂移。
- removed worktree allocation为`2,155,028 KiB`，stale metadata为`2,544 KiB`；执行窗口available bytes增加`834,224,128`。由于执行前另有约5.36 GB异步空间变化，禁止将physical reclaim全部归因于本阶段。
- execution receipt SHA-256 `c85cf7da...`；reconciliation receipt SHA-256 `ff26a1ff...`。未访问生产，未执行Git gc、stage/commit/push/merge、stash/Phase7 mutation或其他清理。

## 20. Loop 74 Phase C 剩余空间与依赖只读盘点（2026-07-23）

- root项目当前`du=57,350,440 KiB`。其中`tmp/knowledge-query-indexes=47,415,600 KiB`是绝对主体；唯一checksum-verified本地P6C DB survivor目录为`5,699,408 KiB`，继续保留。该本地dump尚未单独做isolated restore；既有restore proof属于生产survivor，不能混为一层证据。
- 共盘点63个index目录。31个目录、`46,262,456,320` allocated bytes存在历史DB activation/status证据，全部保护。由于本地medical-audit PostgreSQL未运行且本门禁禁止生产访问，历史active不能冒充当前runtime active。
- 条件候选为：7个deterministic fake fixture共`2,253,393,920` allocated bytes；22个probe/provider-gate目录共`405,504` bytes；1个bad-source-root目录`741,376` bytes。它们仍不是可执行delete manifest。
- 对所有same-size group做SHA-256后，只发现4个`1,257`-byte pending文件完全相同，冗余logical bytes仅`3,771`。大型embeddings/chunks没有被证明为exact duplicate。
- APFS Data snapshot为0；VM volume现有13个OS-managed 1 GiB swap files，共`13,958,643,712` allocated bytes。该状态解释free-space异步波动，但swap不进入清理候选。
- root Git connectivity通过，但仍有29个Git garbage files（`344.33 MiB`）、3个zero-byte stale locks及约`690.61 MiB` loose objects。当前有GitNexus进程且root有383条dirty status，故禁止wide `git gc`；后续只能exact-path housekeeping。
- Phase7 Q1 broken alternate仍未恢复。67个ref/reflog OID中，`d639a117...`在root、H1、Phase7 main三处均缺失，因此Phase7 main并非完整donor；两clone继续excluded。
- root内ignored `DDDD.pem`与Downloads copy同size但不同inode。未读取或hash credential内容，不能宣称byte-identical；该文件必须走独立sensitive cleanup gate。
- secret-free receipts：storage `336b67ad...`、index classification `ec506d43...`、Phase7 dependency `b481f1ae...`、summary `76d2d1dc...`。本阶段无DELETE/Trash、Git mutation/gc/prune、DB/env/runtime/provider/deploy写入或生产访问。

## 21. Loop 74 Phase D1 本地housekeeping exact-manifest freeze（2026-07-23）

- Phase C四个receipt重新hash通过；root status/refs/stashes/worktrees在freeze前后保持相同byte hash，root/H1/Phase7-main connectivity全部pass。
- exact candidate roots共55：29个Git-reported garbage files、3个zero-byte stale locks、22个probe/provider-gate目录和1个bad-source-root目录。递归manifest覆盖164个regular files及159条index-directory member记录。
- 候选总计`362,006,200` logical bytes、`362,283,008` allocated bytes；其中Git garbage为`361,054,525` logical bytes，23个index roots合计仅`951,675` bytes，三个locks为0 bytes。
- 所有候选仅为regular/directory，regular files均`nlink=1`，lsof为空；不存在symlink、hardlink或special-file候选。31个历史DB证据index、7个deterministic fake fixtures、2个unresolved indexes、Phase7、DB survivor、credential及正常Git objects/refs全部excluded。
- receipts：candidate `72fb0a8a...`、protected `57ac7250...`、freeze summary `17167215...`、authorization request `f893ffa6...`。授权请求仍写明`authorization_present=false`，本阶段未创建quarantine、未移动或删除任何文件。

## 22. Loop 74 Phase D2 fail-closed与D2R修订门禁（2026-07-23）

- owner按上一轮完整packet授权的one-shot run `20260722T194134Z`在mutation前失败关闭：candidate与四个D1 receipt校验通过，但root aggregate refs SHA从`240496b0...`变为`3ac1c27f...`。
- quarantine从未创建，`moved=[]`、`purged=[]`；55个candidate roots全部仍在且exact，lsof为空，Git garbage仍为29 files/`352,592 KiB`。failure receipt SHA-256为`58df4254...`。
- root status/stashes/worktrees、54个head branches（SHA `5eeffa51...`）、3个stashes（SHA `a9b7f686...`）及root/H1/Phase7-main connectivity均保持基线。
- 漂移门禁把Codex自动维护且随turn变化的`refs/codex/turn-diffs/*`纳入aggregate。D1没有保存旧raw ref list，因此不能事后严格归因每一条aggregate delta；修订门禁不会跳过refs，而是新冻结其余105个semantic refs，SHA-256 `8d5f06e89c5a0b5c2ef829c09acd7b51a1b8ce09cc895259581995182c323a22`。
- reconciliation receipt SHA-256为`70facb386be82f99dd80dabd11f290425e6d595c61c4b63e00cef33b6e815516`；D2R authorization request SHA-256为`9cb8faa5092a0fefa6d084e726c4878f90ae58b1df453c9b6ff7c7f68279606e`，其中`authorization_present=false`。
- 原D2授权已消耗且禁止自动重试。D2R必须重新明确授权，并继续禁止Git gc/prune/repack、branch/ref/stash mutation、其他DELETE、生产及DB/schema/env/runtime/provider/deploy操作。

## 23. Loop 74 Phase D2R retained-quarantine失败现场（2026-07-23）

- D2R preflight与quarantine postcheck均通过：55个roots全部进入mode-0700 quarantine，postcheck receipt SHA-256为`36b641ae...`。
- purge先删除首个`probe-kimi-next2-def`目录内6个regular files，共`17,937` logical bytes；随后runner错误地用pre-delete目录size复核已清空目录，观察到`64 != 256`并failed closed。
- failure receipt SHA-256为`74c35505...`，state SHA-256为`fc25a1ac...`。未自动重试或rollback；55个original roots均absent，55个quarantine roots均present。
- retained quarantine仍有158个exact regular files、`361,988,263` logical bytes/`362,254,336` allocated bytes、27个candidate directories和29个scaffolding directories，lsof为空，semantic refs/status/stashes/worktrees与connectivity保持基线。
- D2S retained-quarantine manifest SHA-256为`23bd8a6059fa5216e268933bf0df01d827a6253a60c741bfdefa4d4133e6d4ad`；authorization request SHA-256为`c5b595b549b105ba5e83e67095a1e7d90dfe8d593918cf280a49674fad758bbb`，仍为`authorization_present=false`。
- 下一门禁只能继续处理该唯一quarantine：先fresh比对158文件及exact missing-six，再逐文件unlink；全部文件删除后仅按path/type/empty deepest-first删除目录，禁止再次比较已变化的directory size/mtime。任何失败保留现场并停止。

## 24. Loop 74 Phase D2S retained-quarantine完成结果（2026-07-23）

- D2S fresh comparison确认retained payload与manifest的214 paths完全相等，覆盖158个regular files、27个candidate directories及29个scaffolding directories；55个original roots均absent，55个quarantine roots均present。
- 158文件全部通过full SHA-256/lstat/lsof检查后逐项unlink，共`361,988,263` logical bytes、`362,254,336` allocated bytes。与D2R已删除的6文件合计，完整manifest为164 files、`362,006,200` logical bytes、`362,283,008` allocated bytes。
- 全部文件删除后，仅对56个frozen exact directories执行path/type/empty检查和deepest-first rmdir；未再比较post-delete directory size/mtime。
- finalcheck SHA-256 `05c628e3...`在quarantine removal前通过；随后仅移除空payload和唯一quarantine。execution SHA-256 `6485c90e...`、reconciliation SHA-256 `4096b3e2...`、state SHA-256 `7a4f53ef...`。
- 终态为55个candidate original roots剩余0、quarantine absent、Git garbage/size-garbage均0、semantic refs/status/stashes/worktrees未漂移、root/H1/Phase7-main connectivity pass。
- root allocation下降`353,764 KiB`，与本阶段remaining allocated bytes一致；filesystem available在执行窗口增加`1,419,116,544` bytes，因APFS波动按observed delta单独记录。
- 无retry、rollback、Git gc/prune/repack/ref/stash mutation、生产访问、DB/schema/env/runtime/provider/deploy写入或其他DELETE。
