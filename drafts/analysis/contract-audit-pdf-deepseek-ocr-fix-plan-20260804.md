---
title: 合同审计 PDF 与 DeepSeek 辅助 OCR 生产修复方案
doc_type: execution-plan
module: contract-audit
status: active
created: 2026-08-04
updated: 2026-08-04
owner: self
source: human+ai
---

# 目标与验收口径

本次只关闭两个第一性目标：

1. 在生产 `/chat` 完成“上传 PDF -> 选择/触发合同审计智能体 -> 生成审计结论 -> 下载可搜索 PDF 报告”。
2. 扫描 PDF 在 Unlimited-OCR GPU 侧车不可用期间，使用 CPU Tesseract 完成图像转文字，并由 `deepseek-v4-pro` 通过 strict tool call 做逐页纠错和页面映射固化。

完成必须同时具备：本地回归通过、生产部署 SHA 绑定、生产 OCR capability 启用、一次脱敏扫描 PDF 全链路完成、PDF 下载可打开且含文本、生产后只读状态健康。

# 已确认事实

- 生产当前 SHA 为 `84c242072a614a05faa67b0fc094707893c7a97e`，应用、PostgreSQL、ClamAV、Nginx 均健康。
- 生产 OCR capability 为 `enabled=false`，而 `deepseek-v4-pro` 模型目录为 `available=true`。
- DeepSeek 官方 Chat Completions 用户内容协议为文本；一次脱敏图像探针返回 HTTP 400，明确拒绝 `image_url`。因此不能把图片直接伪装成 DeepSeek 原生视觉 OCR。
- 临时方案必须如实标记为 `deepseek-v4-pro+tesseract-chi_sim+eng`：Tesseract 负责像素转写，DeepSeek 只接收文本并做严格逐页纠错。
- 现有合同审计只导出 DOCX/Markdown/JSON，没有 PDF 导出，因此需补齐后端 PDF 响应和前端下载入口。

# 修复设计

## OCR

- 复用现有 OCR protocol 和页面证据结构，增加 `deepseek-tesseract` runtime。
- PDF/图片先受页数、像素和文件大小上限约束，再由本地 `chi_sim+eng` Tesseract 转写。
- DeepSeek 输入只包含未受信 OCR 文本；用 Beta strict function schema 返回完整、顺序一致的 `page_number/text`。
- 页数缺失、乱序、空文本、HTTP/JSON/tool-call 异常全部 fail closed，不生成空审计报告。
- 生产镜像安装最小 Tesseract 运行时；API capability 显示真实混合引擎，不宣称 DeepSeek 看到了图片。

## 审计报告

- 合同审计 job 增加 `downloads.pdf`。
- 后端以 PyMuPDF 内置简体中文字体生成 A4、可搜索、多页 PDF；保留报告标题、正文和引用标记。
- `/api/v1/contract-audits/{job_id}/report?format=pdf` 返回 `application/pdf`。
- `/chat` 完成态优先展示“下载 PDF 报告”，失败或证据待复核态不展示下载。

## 部署与生产配置

- 代码通过分支、PR、`main` 后，以完整 SHA 部署。
- 按本次明确授权使用 `--skip-pre-deploy-backups`，不生成完整 app/env/DB/nginx/web 备份；保留部署锁、原子静态切换、健康检查和 smoke。
- 远端 env 仅写入非秘密 OCR 选择项，并复用现有 `DEEPSEEK_API_KEY` 引用；不输出或复制 secret。

# 执行 TODO

- [x] 恢复 Loop 127/128 代码与生产断点。
- [x] 生产只读确认 OCR disabled、DeepSeek available、基础设施健康。
- [x] 用一次脱敏 provider probe 验证 DeepSeek 不接受图像输入。
- [x] 实现 `deepseek-tesseract` OCR runtime 与严格页面映射。
- [x] 实现可搜索 PDF 报告导出和前端下载。
- [x] 增加 OCR、PDF、前端、部署跳过备份的回归测试。
- [x] 运行 Ruff、mypy、后端 focused/full、前端 test/typecheck/lint/build。
- [x] commit、push、PR、合并到 `main`。
- [x] 无备份部署到生产，并启用 DeepSeek 辅助 OCR env。
- [x] 生产执行脱敏扫描 PDF -> OCR -> 审计智能体 -> PDF 下载全链路。
- [x] 生产后执行 SHA/健康/静态/数据库/审计日志只读复核并保存 receipt。

# 执行回执

- 功能 PR：`#272`；生产部署 SHA：`2e9495d7b26d896549cdeea14aa012dda202f3f6`。
- 生产 OCR capability：`enabled=true`，引擎为 `deepseek-v4-pro+tesseract-chi_sim+eng`。
- L4 脱敏全链路 run：`loop129-contract-ocr-4e749ebb010b4edc912b3b1c0854dfd6`，合同审计 job 为 `completed`，PDF 为 `application/pdf`、可搜索且保留引用标记。
- 最终 L3 只读复核：部署 marker、静态 manifest 与目标 SHA 一致，应用、PostgreSQL、ClamAV、Nginx 健康，manifest mismatch 为 0，复核过程 audit-log delta 为 0。
- 生产前端只读验收：桌面和移动端共 44 次路由检查通过，P0/P1 均为 0；`/chat` 生产静态资产包含“下载 PDF 报告”。
- 按明确授权跳过本轮 app/env/DB/nginx/web 备份；未生成 Loop 129 备份工件。
- 首轮 L4 harness 在受保护的 deployment metadata GET 上缺少审计鉴权头，provider 调用前以 401 停止；补齐同一组只读审计头后复跑通过。

# 停止条件

- DeepSeek strict page mapping 无法稳定返回；
- Tesseract 中文语言包在生产镜像中不可用；
- 生产部署锁或当前 SHA 与预期不一致；
- PDF 下载不是 `application/pdf`、不可解析或不含可搜索文本；
- 全链路未得到 `completed`，或报告缺少来源引用标记。
