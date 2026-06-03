#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

try:
    import websockets
except ImportError as exc:  # pragma: no cover - exercised only in misconfigured envs
    raise SystemExit("missing dependency: websockets. Run through `uv run`.") from exc


DEFAULT_QUESTION = "门诊超量开药应该核对哪些医保审核依据？"
REQUIRED_CHAT_TEXTS = (
    "可追溯回答",
    "证据卷宗",
    "人工复核清单",
    "核验原文",
    "复制引用",
    "创建复核任务",
    "导出 Markdown 底稿",
    "导出 JSON 记录",
)


@dataclass(frozen=True)
class Viewport:
    name: str
    width: int
    height: int
    mobile: bool


VIEWPORTS = (
    Viewport(name="desktop", width=1440, height=1600, mobile=False),
    Viewport(name="mobile", width=390, height=1200, mobile=True),
)


def main() -> int:
    args = _parse_args()
    base_url = str(args.base_url).rstrip("/")
    output_dir = Path(args.output_dir)
    report_path = Path(args.report)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        backend = _load_json(f"{base_url}/index/search-backend")
    except (OSError, urllib.error.URLError) as exc:
        _write_report(
            report_path,
            {
                "status": "fail",
                "reason": f"service is not reachable: {exc}",
                "base_url": base_url,
            },
        )
        return 2
    if backend.get("ready") is not True:
        _write_report(
            report_path,
            {
                "status": "fail",
                "reason": "search backend is not ready",
                "base_url": base_url,
                "search_backend": backend,
            },
        )
        return 2

    chrome_path = _find_chrome(args.chrome)
    port = _free_port()
    debug_dir = Path("tmp/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = Path(tempfile.mkdtemp(prefix="medical-audit-visual-", dir=str(debug_dir)))
    command = [
        chrome_path,
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "about:blank",
    ]
    process = subprocess.Popen(  # noqa: S603
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        browser_url = _wait_for_browser(port=port, timeout_seconds=args.timeout_seconds)
        captures = asyncio.run(
            _capture_all(
                browser_url=browser_url,
                base_url=base_url,
                question=str(args.question),
                output_dir=output_dir,
                wait_seconds=float(args.wait_seconds),
            ),
        )
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    status = "pass" if all(item["passed"] for item in captures) else "fail"
    report = {
        "status": status,
        "base_url": base_url,
        "question": str(args.question),
        "search_backend": backend,
        "captures": captures,
    }
    _write_report(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "pass" else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture AuditScope chat workbench visual baseline screenshots.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8021")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--output-dir", default="tmp/screenshots")
    parser.add_argument(
        "--report",
        default="tmp/outputs/knowledge-query-chat-visual-baseline-latest.json",
    )
    parser.add_argument("--chrome", help="Path to Chrome or Chromium executable.")
    parser.add_argument("--wait-seconds", type=float, default=4.0)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    return parser.parse_args()


def _find_chrome(chrome_arg: str | None) -> str:
    candidates = [
        chrome_arg,
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise SystemExit("Chrome executable not found. Pass --chrome explicitly.")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_browser(*, port: int, timeout_seconds: float) -> str:
    deadline = time.monotonic() + timeout_seconds
    version_url = f"http://127.0.0.1:{port}/json/version"
    while time.monotonic() < deadline:
        try:
            payload = _load_json(version_url)
        except (OSError, urllib.error.URLError):
            time.sleep(0.2)
            continue
        websocket_url = payload.get("webSocketDebuggerUrl")
        if isinstance(websocket_url, str):
            return websocket_url
        time.sleep(0.2)
    raise SystemExit("Chrome DevTools endpoint did not become ready.")


async def _capture_all(
    *,
    browser_url: str,
    base_url: str,
    question: str,
    output_dir: Path,
    wait_seconds: float,
) -> list[dict[str, Any]]:
    async with websockets.connect(browser_url, max_size=16 * 1024 * 1024) as websocket:
        sender = _CdpSender(websocket)
        target = await sender.send("Target.createTarget", {"url": "about:blank"})
        target_id = str(target["result"]["targetId"])
        attach = await sender.send(
            "Target.attachToTarget",
            {"targetId": target_id, "flatten": True},
        )
        session_id = str(attach["result"]["sessionId"])
        await sender.send("Page.enable", session_id=session_id)
        await sender.send("Runtime.enable", session_id=session_id)
        captures: list[dict[str, Any]] = []
        for viewport in VIEWPORTS:
            captures.append(
                await _capture_viewport(
                    sender=sender,
                    session_id=session_id,
                    base_url=base_url,
                    question=question,
                    output_dir=output_dir,
                    viewport=viewport,
                    wait_seconds=wait_seconds,
                ),
            )
        return captures


async def _capture_viewport(
    *,
    sender: _CdpSender,
    session_id: str,
    base_url: str,
    question: str,
    output_dir: Path,
    viewport: Viewport,
    wait_seconds: float,
) -> dict[str, Any]:
    params = {
        "width": viewport.width,
        "height": viewport.height,
        "deviceScaleFactor": 1,
        "mobile": viewport.mobile,
    }
    await sender.send("Emulation.setDeviceMetricsOverride", params, session_id=session_id)
    url = f"{base_url}/pages/chat?question={urllib.parse.quote(question)}"
    await sender.send("Page.navigate", {"url": url}, session_id=session_id)
    await asyncio.sleep(wait_seconds)

    metrics = await _evaluate(sender, session_id, _metrics_expression())
    required_texts = await _evaluate(sender, session_id, _required_texts_expression())
    screenshot = await sender.send(
        "Page.captureScreenshot",
        {"format": "png", "fromSurface": True},
        session_id=session_id,
    )
    image_data = base64.b64decode(str(screenshot["result"]["data"]))
    image_path = output_dir / f"knowledge-query-chat-visual-baseline-{viewport.name}.png"
    image_path.write_bytes(image_data)

    missing_texts = [
        text for text in REQUIRED_CHAT_TEXTS if text not in required_texts.get("visibleText", "")
    ]
    no_horizontal_overflow = metrics["scrollWidth"] <= metrics["clientWidth"]
    passed = bool(no_horizontal_overflow and not missing_texts)
    return {
        "name": viewport.name,
        "passed": passed,
        "url": url,
        "screenshot_path": str(image_path),
        "viewport": {
            "width": viewport.width,
            "height": viewport.height,
            "mobile": viewport.mobile,
        },
        "metrics": metrics,
        "missing_texts": missing_texts,
    }


async def _evaluate(sender: _CdpSender, session_id: str, expression: str) -> dict[str, Any]:
    response = await sender.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True},
        session_id=session_id,
    )
    value = response["result"]["result"]["value"]
    if not isinstance(value, dict):
        raise RuntimeError(f"unexpected evaluate result: {value!r}")
    return value


def _metrics_expression() -> str:
    return """(() => {
      const widthOf = (selector) => Math.round(
        document.querySelector(selector)?.getBoundingClientRect().width || 0
      );
      return {
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        bodyScrollWidth: document.body.scrollWidth,
        titleWidth: widthOf('.command-title-block h1'),
        navWidth: widthOf('.command-nav'),
        transcriptWidth: widthOf('.transcript-card')
      };
    })()"""


def _required_texts_expression() -> str:
    return """(() => ({ visibleText: document.body.innerText }))()"""


class _WebSocketConnection(Protocol):
    async def send(self, message: str) -> None: ...

    async def recv(self) -> str | bytes: ...


class _CdpSender:
    def __init__(self, websocket: _WebSocketConnection) -> None:
        self._websocket = websocket
        self._counter = 0

    async def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        self._counter += 1
        payload: dict[str, Any] = {
            "id": self._counter,
            "method": method,
            "params": params or {},
        }
        if session_id is not None:
            payload["sessionId"] = session_id
        await self._websocket.send(json.dumps(payload))
        while True:
            raw = await self._websocket.recv()
            message = json.loads(raw)
            if message.get("id") != self._counter:
                continue
            if "error" in message:
                raise RuntimeError(f"CDP error for {method}: {message['error']}")
            if not isinstance(message, dict):
                raise RuntimeError(f"unexpected CDP message: {message!r}")
            return message


def _load_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected JSON payload from {url}: {payload!r}")
    return payload


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
