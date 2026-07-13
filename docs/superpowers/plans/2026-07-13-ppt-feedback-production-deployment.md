---
title: PPT 反馈产品优化生产部署与验收计划
created_at: 2026-07-13
updated_at: 2026-07-13
project: medical_audit
scope: ppt-feedback-production-promotion
status: local-fix-validated-awaiting-pr-rereview
evidence_grade: L2-local-fullstack-plus-prior-L3-production-read-only
production_side_effect: none
provider_call: false
database_write: none
production_reverified: false
---

# PPT 反馈产品优化生产部署与验收计划

## 1. 当前结论

PR #232 代码审查发现的项目隔离、前端身份失效和部署门禁问题已完成本地修复与全量回归，但尚未完成独立 PR 复审、commit、merge 或 clean-main 发布，因此仍不满足“立即执行生产部署”的证据门槛：

- `origin/main` 与当前生产 `.deploy-sha` 均为 `51dfcb816a0c71928c206683f0fa7fef796e895a`。
- PPT 产品优化分支以该 SHA 为 merge-base；原产品实现线性领先 `50` 个提交，Loop 51 已追加后端质量闭环 commit `ffed561c` 和部署 preflight 加固 commit `d10d2fff`。
- 生产服务当前健康，但 `/documents` 仍是旧产品页面文案；这证明新产品形态尚未部署。
- 当前修复仍是未提交工作树；实际部署不得使用 `--allow-dirty`，必须在修复 commit 经复审并合入后，从 fresh fetch 的干净 `main` 执行。

因此当前状态是 `local-fix-validated-awaiting-pr-rereview`，不是 `ready_for_owner_authorization` 或 `deployed`。本轮只产生本地 L2 代码/测试证据，保持 `production unchanged`、`provider_call=false`、`database_write=false`。

## 2. 已完成的部署前证据

### 2.1 本地候选

- Ruff：全仓通过。
- Mypy：`106` 个 `src` 源文件及两个部署/smoke 脚本通过。
- Pytest：全部 `589` 个测试通过；仅有既有 Starlette 弃用警告。
- Web：`32` 个测试文件、`279` 个测试通过；typecheck、lint 通过；Next build `24/24` 页面通过。
- 本地 full-stack E2E：`13 passed`。
- 本批改变了前端身份失效和项目深链状态逻辑；旧的 45 张截图 checksum 仅作历史基线，PR 复审前仍需按既有视口执行视觉抽查，不能沿用“前端代码未变化”的结论。

### 2.2 生产只读基线

- SSH：`ubuntu@101.34.52.232`，使用 `/Users/pray/Downloads/DDDD.pem`，`BatchMode=yes`、`StrictHostKeyChecking=yes`、`IdentitiesOnly=yes`。
- 生产 SHA：`51dfcb816a0c71928c206683f0fa7fef796e895a`。
- `medical_audit_app`、`medical_audit_pg`、`medical_audit_clamav`、`ai_video_nginx`：均为 `running/healthy`。
- Nginx 配置检查通过；本机 health、search backend、公开首页和公开 health 均返回 HTTP `200`。
- 根盘使用率 `66%`，可用约 `87.3 GiB`。
- DB 备份目录约 `45.6 GiB`，Docker local volumes 约 `45.67 GB`；这是部署前容量观察项，不等于需要立即清理。
- 生产前端只读验收：`18` 路由、`36` 检查、`P0=0`、`P1=0`。
- 生产权限只读 smoke：`35` 个 GET probe、`issue_count=0`、`production_side_effect=none`、`provider_call_status=not_called`。
- 文档只读 probe：部署 SHA、权限、治理状态、后端健康和 `49,051` embedding 下限检查通过；页面文本检查未通过，因为当前生产尚未包含新文档检索页面。

## 3. 部署前必须完成的 TODO

- [x] 将 Loop 51 代码和测试按两个原子 commit 提交；未包含 3 个受保护脏文档。
- [ ] PR #232 修复后完成独立复审并合入 `main`。
- [ ] 在 fresh fetch 后的干净 `main` checkout 上确认 `git status --porcelain` 为空，且 `HEAD == origin/main == 已批准完整 SHA`。
- [ ] 在干净 checkout 重跑 Ruff、Mypy、Pytest、Web 四门禁和 local full-stack E2E。
- [ ] 对生产 review task 做只读 scope 审计：统计已关联 finding 但 dossier 顶层/模板草稿均缺少 `project_key` 的历史记录；如非零，先制定单独 backfill、冲突处理和回滚方案，不在部署脚本内隐式批量修复。
- [ ] 由所有者在腾讯云控制台复核当前实例与 known-host 指纹；不得回退到 `StrictHostKeyChecking=no`。
- [ ] 复核根盘可用空间足以容纳本次 DB/app/web 备份、镜像构建临时空间和回滚保留；未经单独授权不得删除历史备份或 Docker volume。
- [ ] 确定唯一 deploy stamp，并记录目标 SHA、旧 SHA、备份路径和回滚责任人。
- [ ] 获得生产 `--execute --confirm-production` 的单独明确授权。

## 4. 推荐执行命令

先在干净 release checkout 执行零写入 preflight；正式发布不得带 `--allow-dirty`：

```bash
uv run python scripts/deploy-tencent-cloud-production.py \
  --ssh-key /Users/pray/Downloads/DDDD.pem \
  --stamp <deploy-stamp> \
  --report tmp/outputs/production-e2e-smoke-after-deploy-<deploy-stamp>.json
```

只有获得生产授权后，执行：

```bash
uv run python scripts/deploy-tencent-cloud-production.py \
  --execute \
  --confirm-production audit.lute-tlz-dddd.top \
  --approved-sha <merged-main-full-sha> \
  --ssh-key /Users/pray/Downloads/DDDD.pem \
  --stamp <deploy-stamp> \
  --report tmp/outputs/production-e2e-smoke-after-deploy-<deploy-stamp>.json
```

本批不使用：

- `--allow-dirty`
- `--skip-web-build`
- `--skip-app-rebuild`
- `--apply-schema`
- `--include-review-write`

## 5. 部署动作边界

正式 execute 的预期动作只有：

1. 严格 known-host SSH preflight。
2. 备份 app、env、DB、Nginx 和 web 静态文件，并验证备份非空。
3. 构建 Next 静态产物。
4. 同步应用与静态文件。
5. 仅重建并重启 `medical_audit_app`，不得重建 PostgreSQL 或 ClamAV 依赖。
6. 写入新 `.deploy-sha`。
7. 运行 GET-only 生产 smoke；报告必须保持 `http_methods=["GET"]`、`database_write=false`、`provider_call=not_called`。

本批不执行 schema migration、生产 SQL 写入、对象存储写入、真实 provider 调用或写入型业务验收。

查询、回答 provider、query history、audit log 和 review task 验收不属于默认部署。只有单独取得 L4 生产写入/provider 授权后，才可另行执行：

```bash
uv run python scripts/run-production-e2e-smoke.py \
  --base-url https://audit.lute-tlz-dddd.top \
  --include-query-provider-smoke \
  --confirm-production-write audit.lute-tlz-dddd.top \
  --report tmp/outputs/production-live-query-smoke-<stamp>.json
```

## 6. 回滚方案

回滚触发条件：

- app 无法达到 healthy；
- `.deploy-sha` 与目标 SHA 不一致；
- Nginx、公开 health 或 search backend 非 200/ready；
- 生产前端验收出现 P0/P1；
- 权限只读 smoke 出现 issue；
- 文档只读 probe 在新 SHA 下仍失败；
- 9+1 导航、项目权限、table-first 分析、双视图图谱、六类报告目录或 3 个默认医疗智能体任一关键产品契约不成立。

回滚执行前先确认当前故障 SHA、目标恢复 SHA和同一部署 stamp 的 app/web 备份。执行命令：

- 若失败发生在 `_write_remote_deploy_sha` 之前（例如 app unhealthy、Nginx 或 catalog post-check 失败），远端 marker 仍是旧 SHA；`--expected-current-sha` 与 `--restore-sha` 都传该旧 SHA。
- 若失败发生在 marker 写入之后（例如默认 GET-only smoke 失败），`--expected-current-sha` 传失败部署 SHA，`--restore-sha` 传备份内旧 SHA。
- 两种情况都必须先以只读方式观测当前 marker，不得用“尝试部署的代码 SHA”代替实际 marker。

```bash
uv run python scripts/deploy-tencent-cloud-production.py \
  --rollback \
  --confirm-production audit.lute-tlz-dddd.top \
  --stamp <failed-deploy-backup-stamp> \
  --expected-current-sha <observed-current-deploy-marker-sha> \
  --restore-sha <previous-full-sha> \
  --ssh-key /Users/pray/Downloads/DDDD.pem
```

回滚顺序：

1. 冻结后续动作，保存失败日志和目标/旧 SHA。
2. 脚本先校验当前 `.deploy-sha`、stamp 对应 app/web 备份和备份内旧 `.deploy-sha`；任一不一致立即停止。
3. 恢复 app 与 web但暂不改 marker，保留当前生产 env，仅重建 `medical_audit_app`；PostgreSQL 和 ClamAV 容器 ID 必须不变。
4. 旧 app health、依赖容器和 `nginx -t` 全部通过后才原子写回旧 `.deploy-sha`；随后再运行默认 GET-only smoke。
5. Nginx 仅在配置被意外改变时恢复对应备份；本批正常路径不修改 Nginx 配置。
6. 本批不应用 schema，且默认部署后验收不执行业务写入，因此默认不得恢复 DB。只有确认存在数据库损坏或取得数据回滚授权时，才使用同 stamp 的 DB 备份执行单独恢复方案。

## 7. 部署后验收顺序

- [ ] 部署脚本最终退出 `0`，且备份 marker、app/env/db/nginx/web 五类备份非空。
- [ ] `.deploy-sha` 精确等于目标 commit SHA。
- [ ] 4 个核心容器 `running/healthy`，Nginx 配置通过。
- [ ] local/public health 与 search backend 通过。
- [ ] `pnpm production:frontend-acceptance`：`P0=0`、`P1=0`。
- [ ] `pnpm production:permission-readonly`：`35` GET probe、`issue_count=0`。
- [ ] `run-production-documents-readonly-probe.py --expected-deploy-sha <target-sha>`：所有步骤通过，新文档页文本检查由红转绿。
- [ ] 对 9 个核心页面按既有 5 组视口/缩放复核，确认 9+1 导航、品牌、横向溢出、项目操作列和历史按钮均符合基线。
- [ ] 核对默认智能体精确为 3 个医疗模板，扩展 flag 默认关闭，安装链无 provider call。
- [ ] 保存部署、只读验收、截图和 checksum 清单；更新产品开发状态，但不把只读通过写成业务写入验收。

## 8. 完成定义

只有部署脚本、目标 SHA、容器/前门、前端、权限、文档和产品视觉契约全部通过，才可声明“生产部署验收完成”。任何单项失败都保持 `production deployment incomplete`，并按回滚门处理。
