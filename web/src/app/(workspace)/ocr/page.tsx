"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

import { extractOcrText, fetchOcrCapabilities } from "@/lib/api-client";
import type { OcrCapabilityResponse, OcrExtractionResponse } from "@/lib/api-types";
import { isPublicShellReadonly } from "@/lib/runtime-access";

type CapabilityState =
  | { readonly kind: "loading" }
  | { readonly kind: "ready"; readonly value: OcrCapabilityResponse }
  | { readonly kind: "error"; readonly message: string };

const DEFAULT_ACCEPT = ".pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff";

export default function OcrWorkbenchPage() {
  const publicShellReadonly = isPublicShellReadonly();
  const [capability, setCapability] = useState<CapabilityState>({ kind: "loading" });
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<OcrExtractionResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (publicShellReadonly) {
      setCapability({
        kind: "error",
        message: "生产只读导览不读取 OCR 能力，也不开放文件上传和识别操作。"
      });
      return;
    }
    let mounted = true;
    void fetchOcrCapabilities()
      .then((response) => {
        if (mounted) {
          setCapability({ kind: "ready", value: response });
        }
      })
      .catch(() => {
        if (mounted) {
          setCapability({
            kind: "error",
            message: "OCR 能力状态读取失败，请稍后刷新页面。"
          });
        }
      });
    return () => {
      mounted = false;
    };
  }, [publicShellReadonly]);

  const capabilityValue = capability.kind === "ready" ? capability.value : null;
  const runtimeReady = capabilityValue?.enabled === true;
  const supportedTypes = useMemo(
    () => capabilityValue?.supported_extensions.map((extension) => extension.toUpperCase()).join(" / ")
      ?? "PDF / PNG / JPG / JPEG / BMP / TIF / TIFF",
    [capabilityValue]
  );
  const maxUploadLabel = capabilityValue
    ? `${Math.floor(capabilityValue.max_upload_bytes / 1024 / 1024)} MiB`
    : "40 MiB";

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    setResult(null);
    setNotice("");
    if (selected && capabilityValue && selected.size > capabilityValue.max_upload_bytes) {
      setNotice(`文件超过 ${maxUploadLabel} 限制，请选择更小的文件。`);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (publicShellReadonly || !file || !runtimeReady || submitting) {
      return;
    }
    if (capabilityValue && file.size > capabilityValue.max_upload_bytes) {
      setNotice(`文件超过 ${maxUploadLabel} 限制，请选择更小的文件。`);
      return;
    }

    setSubmitting(true);
    setNotice("");
    setResult(null);
    try {
      const response = await extractOcrText(file);
      setResult(response);
      setNotice(
        response.mapping_status === "resolved"
          ? "识别完成，页面证据映射已校验。"
          : "识别完成，但页面映射仍需人工复核。"
      );
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "OCR 识别失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  }

  async function copyText() {
    if (!result?.text) {
      return;
    }
    try {
      await navigator.clipboard.writeText(result.text);
      setNotice("识别文本已复制。请在引用前核对原件与页码。 ");
    } catch {
      setNotice("浏览器未允许复制，请使用下载文本。 ");
    }
  }

  function downloadText() {
    if (!result) {
      return;
    }
    const blob = new Blob([result.text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const baseName = result.file_name.replace(/\.[^.]+$/, "") || "ocr-result";
    anchor.href = url;
    anchor.download = `${baseName}-OCR.txt`;
    document.body.appendChild(anchor);
    try {
      anchor.click();
    } finally {
      anchor.remove();
      URL.revokeObjectURL(url);
    }
    setNotice("识别文本已生成下载。请保留原件用于证据复核。 ");
  }

  return (
    <main className="ocr-workbench" data-runtime-ready={runtimeReady ? "true" : "false"}>
      <header className="ocr-workbench__header">
        <div>
          <p className="ocr-workbench__kicker">文本 OCR</p>
          <h1>扫描材料识别工作台</h1>
          <p>将扫描 PDF 或图片转换为可核验文本，并保留逐页哈希与页码映射。</p>
        </div>
        <span className={`ocr-runtime-badge ${runtimeReady ? "is-ready" : "is-blocked"}`}>
          {capability.kind === "loading"
            ? "正在检查运行能力"
            : runtimeReady
              ? "Unlimited-OCR 已就绪"
              : "Unlimited-OCR 未启用"}
        </span>
      </header>

      <section className="ocr-boundary-strip" aria-label="处理边界">
        <div><span>01</span><strong>选择材料</strong><small>本地选择，不预存原件</small></div>
        <div><span>02</span><strong>页面识别</strong><small>仅调用 Unlimited-OCR</small></div>
        <div><span>03</span><strong>证据校验</strong><small>页码、图片与文本哈希</small></div>
        <div><span>04</span><strong>导出复核</strong><small>复制或下载纯文本</small></div>
      </section>

      {capability.kind === "error" ? (
        <div className="ocr-alert is-error" role="alert">{capability.message}</div>
      ) : !runtimeReady && capability.kind === "ready" ? (
        <div className="ocr-alert is-warning" role="status">
          当前运行环境尚未启用 Unlimited-OCR。管理员需先完成 GPU 节点或经审核外部端点门禁；本页不会自动拉取模型或修改运行配置。
        </div>
      ) : null}

      <div className="ocr-workbench__grid">
        {publicShellReadonly ? (
          <section className="ocr-upload-card" aria-label="OCR 只读导览">
            <div className="ocr-section-heading">
              <div>
                <p>材料输入</p>
                <h2>上传待识别文件</h2>
              </div>
              <span>只读导览</span>
            </div>
            <div className="ocr-alert is-warning" role="status">
              可信身份认证启用前，OCR 文件上传、文本识别和 Provider 调用均不开放。
            </div>
            <dl className="ocr-safety-list">
              <div><dt>业务数据读取</dt><dd>已关闭</dd></div>
              <div><dt>文件上传</dt><dd>已关闭</dd></div>
              <div><dt>OCR Provider</dt><dd>不调用</dd></div>
              <div><dt>业务写入</dt><dd>已关闭</dd></div>
            </dl>
          </section>
        ) : (
        <form className="ocr-upload-card" onSubmit={submit}>
          <div className="ocr-section-heading">
            <div>
              <p>材料输入</p>
              <h2>上传待识别文件</h2>
            </div>
            <span>单文件</span>
          </div>

          <label className={`ocr-dropzone ${file ? "has-file" : ""}`}>
            <input
              type="file"
              accept={DEFAULT_ACCEPT}
              onChange={selectFile}
              disabled={!runtimeReady || submitting}
            />
            <span className="ocr-dropzone__mark" aria-hidden="true">识</span>
            <strong>{file ? file.name : "选择扫描 PDF 或图片"}</strong>
            <p>{file ? `${formatBytes(file.size)} · 等待识别` : `支持 ${supportedTypes}`}</p>
            <small>上限 {maxUploadLabel}；源文件与识别全文不写入业务资料库或知识索引。</small>
          </label>

          <button
            className="ocr-primary-action"
            type="submit"
            disabled={!runtimeReady || !file || submitting}
          >
            {submitting ? "正在识别并校验页面…" : "开始文本识别"}
          </button>

          <dl className="ocr-safety-list">
            <div><dt>业务数据库</dt><dd>不写入</dd></div>
            <div><dt>原件存储</dt><dd>不保留</dd></div>
            <div><dt>知识索引</dt><dd>不写入</dd></div>
            <div><dt>操作留痕</dt><dd>成功后仅写安全元数据与哈希</dd></div>
          </dl>
        </form>
        )}

        <section className="ocr-result-card" aria-labelledby="ocr-result-title">
          <div className="ocr-section-heading">
            <div>
              <p>识别结果</p>
              <h2 id="ocr-result-title">文本与页面证据</h2>
            </div>
            {result ? <span>{result.page_count} 页</span> : <span>待识别</span>}
          </div>

          {notice ? <div className="ocr-inline-notice" role="status" aria-live="polite">{notice}</div> : null}

          {result ? (
            <>
              <div className="ocr-result-summary">
                <div><span>文件</span><strong>{result.file_name}</strong></div>
                <div><span>页面映射</span><strong>{result.mapping_status === "resolved" ? "已校验" : "待复核"}</strong></div>
                <div><span>识别引擎</span><strong>{result.engine}</strong></div>
              </div>
              <label className="ocr-text-preview">
                <span>完整识别文本</span>
                <textarea value={result.text} readOnly aria-label="完整识别文本" />
              </label>
              <div className="ocr-result-actions">
                <button type="button" onClick={() => void copyText()}>复制文本</button>
                <button type="button" onClick={downloadText}>下载 TXT</button>
              </div>
              <div className="ocr-page-evidence">
                <h3>逐页证据</h3>
                <ol>
                  {result.pages.map((page) => (
                    <li key={page.page_number}>
                      <div>
                        <strong>第 {page.page_number} 页</strong>
                        <span>{page.mapping_status === "resolved" ? "映射已校验" : "映射待复核"}</span>
                      </div>
                      <p>{page.text || "本页未识别到文本。"}</p>
                      <code title={page.text_sha256}>文本 {shortHash(page.text_sha256)}</code>
                      <code title={page.image_sha256}>图像 {shortHash(page.image_sha256)}</code>
                    </li>
                  ))}
                </ol>
              </div>
            </>
          ) : (
            <div className="ocr-empty-state">
              <span aria-hidden="true">⌁</span>
              <strong>尚无识别结果</strong>
              <p>选择材料后，系统会在这里呈现完整文本、逐页映射和证据哈希。</p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KiB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MiB`;
}

function shortHash(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-8)}`;
}
