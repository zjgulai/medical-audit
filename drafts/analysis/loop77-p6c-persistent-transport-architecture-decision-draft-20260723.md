---
title: Loop 77 P6C 单会话持久传输架构决策草案
doc_type: architecture-decision-draft
module: knowledge-restore
status: superseded
created: 2026-07-23
updated: 2026-08-13
owner: self
source: local-evidence
---

# Loop 77 P6C 单会话持久传输架构决策草案

> 从 `/Users/pray/project/medical_audit_h1_fix_20260721` 原样归并的历史独有草稿；2026-08-13 标记为 `superseded`。当前状态以 [文档索引](../../docs/README.md) 为准。

## 决策

未来若获得新的独立授权，P6C 隔离恢复流必须只建立一个 SSH 会话。压缩 dump 仍通过该会话的 stdin 传输；远端 receiver 在同一进程内按块读取、计算字节数和 SHA-256、向 gzip/psql 子进程写入，并直接在远端执行磁盘、文件系统设备和总容量检查。

进度记录使用固定前缀写入同一会话的 stderr，最终机器凭据写入 stdout。禁止恢复期间每隔固定时间新建 SSH 监控连接，也禁止监控失败后再自动新建 SSH 连接执行 stop。

## 失败语义

- stdin 中断、receiver 写入子进程失败、gzip/psql 非零退出、磁盘低于门槛、文件系统设备/总容量漂移或标记解析失败，均使唯一尝试失败关闭。
- 失败后不得自动重试或续传。plain SQL 的部分提交状态不得复用。
- 是否停止并保留临时资源、是否删除临时资源，必须由未来授权包分别明确。
- SSH 结果未知时只能执行新的只读对账；不能把未知结果当作失败前状态，也不能盲目重试。

## 本地证明边界

Loop 77 Phase A 只使用确定性合成字节流验证：

1. 单一父子会话可以同时完成 payload 传输、字节/SHA-256 统计和同通道进度标记。
2. 成功路径要求 sender、receiver 和 consumer 三方字节数与 SHA-256 完全一致。
3. 注入失败路径必须非零退出、只接收前缀字节、记录 fail-closed，且不重试。

该证明是 L2 synthetic/local evidence。它不证明 SSH 网络稳定、Docker 或 PostgreSQL 行为、真实 gzip/psql 恢复成功，也不证明 P6C dump 可恢复。

## 下一门禁

下一步只能请求生产只读预检：重新核对生产 SHA/current/boot/lock/health、文件系统设备/总容量与可用空间、镜像身份及新临时资源名冲突。不得上传或读取 dump 内容，不得创建容器/卷，不得连接生产数据库，也不得执行 DELETE。
