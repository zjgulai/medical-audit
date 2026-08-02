---
title: "Unlimited-OCR 集成与启用门禁"
doc_type: "api-integration"
module: "ocr"
status: "candidate"
created: "2026-07-29"
updated: "2026-08-02"
owner: "self"
source: "official-docs+local-engineering"
---

# Unlimited-OCR 集成与启用门禁

## 目标

为聊天附件中的扫描 PDF 和图片提供 OCR 识别，同时保持普通文本 PDF、Markdown
和纯文本文件继续使用本地解析器。OCR 只作为不可读文档的受控回退，不替代现有
文档解析、知识库索引或问答模型。

## 固定上游

- 模型仓库：`baidu/Unlimited-OCR`
- 固定 commit：`d49ff64afffc1f47ab563dc1c589bc2f78808fa4`
- 运行方式：官方 `vllm/vllm-openai:unlimited-ocr` GPU 镜像
- 模型名：`baidu/Unlimited-OCR`
- 许可证：MIT

应用只通过 OpenAI-compatible `/v1/chat/completions` 调用隔离 OCR 服务。请求固定
使用 `<image>` 标记、`skip_special_tokens=false` 和 vLLM n-gram 参数；单次请求
不自动重试。

## 运行边界

- 默认 `MEDICAL_AUDIT_UNLIMITED_OCR_ENABLED=0`。
- 普通文本解析成功时不调用 OCR。
- 扫描 PDF 或图片只有在 OCR 服务显式启用后才会调用。
- OCR 不连接数据库，不写知识库索引，不访问生产 DSN。
- 聊天附件继续受既有 20 MiB 限制；独立 OCR 工作台受 40 MiB 流式读取上限，
  并额外受页数、像素、超时和输出 token 限制。
- API key 配置只允许保存环境变量名；不得在日志、响应或审计记录中保存 secret。
- OCR 调用和问答模型调用分别记录为 `ocr_call` 与 `answer_provider_call`。

## 启用前门禁

1. 只读确认目标主机存在 NVIDIA GPU、CUDA 和至少 8 GB 可用显存。
2. 确认官方 GPU 镜像和固定 commit 能在隔离环境启动并通过 `/health`。
3. 使用无生产 DSN、无宿主公网端口的测试容器完成扫描 PDF 合同测试。
4. 对 OCR 输出做空结果、超时、超页、超像素和异常响应测试。
5. 单独授权生产 env 变更和 `ocr-gpu` Compose profile 启用。
6. 启用后执行 GET-only 健康检查和一份已脱敏扫描件的受控验收；不得自动扩大到
   批量索引或历史文档重跑。

## 配置

| 变量 | 默认值 | 作用 |
| --- | --- | --- |
| `MEDICAL_AUDIT_UNLIMITED_OCR_ENABLED` | `0` | 总开关 |
| `MEDICAL_AUDIT_UNLIMITED_OCR_BASE_URL` | `http://unlimited-ocr:8000/v1` | 隔离服务地址 |
| `MEDICAL_AUDIT_UNLIMITED_OCR_MODEL` | `baidu/Unlimited-OCR` | 服务模型名 |
| `MEDICAL_AUDIT_UNLIMITED_OCR_TIMEOUT_SECONDS` | `1200` | 单次请求超时 |
| `MEDICAL_AUDIT_UNLIMITED_OCR_MAX_PAGES` | `40` | PDF 页数上限 |
| `MEDICAL_AUDIT_UNLIMITED_OCR_PDF_DPI` | `300` | PDF 渲染分辨率 |
| `MEDICAL_AUDIT_UNLIMITED_OCR_MAX_OUTPUT_TOKENS` | `32768` | OCR 输出上限 |

## 产品接口

### `GET /api/v1/ocr/capabilities`

用于页面加载时读取运行能力，不调用 OCR provider，不写数据库、审计日志、原件存储
或知识索引。响应公开以下非密能力元数据：是否启用、引擎、固定 source commit、支持
扩展名、40 MiB 上传上限、最大页数和 PDF DPI。

### `POST /api/v1/ocr/extract`

- 需要 `UPLOAD_PERSONAL_DOCUMENT` 权限；运行时未启用时在读取上传内容前返回 `409`。
- 仅接受 PDF 和受支持图片类型，使用 1 MiB 分块读取并在超过 40 MiB 时返回 `413`。
- 成功响应返回完整文本、文件哈希、逐页文本、图片哈希、文本哈希与页面映射状态。
- 不持久化源文件或识别全文，不写知识索引，不调用问答模型。
- 成功调用后仅记录一次操作审计事件，内容限定为用户标识、扩展名、文件/模型哈希、
  大小、页数和映射状态；不记录文件名、原文、识别全文或凭据。

## OCR 工作台

静态导出路由为 `/ocr`，入口同时出现在主导航和 AI 对话快捷区。页面先调用零写入
capability 接口：运行时未启用时上传控件和执行按钮保持禁用，并明确显示基础设施
门禁；运行时就绪后才能提交单文件识别。结果支持完整文本预览、浏览器端复制/下载
TXT 和逐页证据核对，不自动写入项目、文档库或知识库。

## 当前证据边界

本地代码、渲染依赖、请求合同、失败关闭逻辑和测试可以在无 GPU 环境验证。当前
腾讯云生产主机的只读证据显示没有 NVIDIA 设备、NVIDIA Docker runtime、固定 OCR
镜像或 OCR env，因此官方 GPU profile 是 `NO-GO`。模型权重、GPU 镜像启动、生产
env 与 runtime 尚未执行；它们必须通过兼容 GPU 节点或经审核外部端点方案、单独的
生产授权和 readiness 门禁。
