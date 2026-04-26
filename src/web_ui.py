"""Minimal web UI for one-click pipeline execution."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.config import get_settings
from src.pipeline import run_full_pipeline


# Strip ANSI control codes (colors, cursor ops) and OSC hyperlinks from Rich/httpx logs.
_ANSI_CSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_ANSI_OSC_RE = re.compile(r"\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)")


HTML_PAGE = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CAD評価ランナー</title>
  <style>
    :root {
      --bg: #f4f7fb;
      --card: #ffffff;
      --ink: #10243e;
      --muted: #5f7087;
      --brand: #0f5ea8;
      --brand-2: #1890d8;
      --ok: #177245;
      --err: #b3261e;
      --line: #d9e2ec;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", sans-serif;
      color: var(--ink);
      background: radial-gradient(1200px 600px at 20% -10%, #e3f0ff, transparent), var(--bg);
    }
    .wrap {
      max-width: 1100px;
      margin: 24px auto;
      padding: 0 16px;
      display: grid;
      gap: 16px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: 0 6px 20px rgba(16, 36, 62, 0.06);
      padding: 16px;
    }
    h1 { margin: 0 0 6px; font-size: 24px; }
    .sub { color: var(--muted); margin: 0; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      align-items: end;
    }
    label { display: block; font-weight: 600; margin-bottom: 6px; }
    select, button {
      width: 100%;
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 8px 10px;
      font-size: 14px;
      background: #fff;
    }
    .checks { display: flex; gap: 14px; flex-wrap: wrap; padding-top: 8px; }
    .checks label { font-weight: 500; margin: 0; display: inline-flex; align-items: center; gap: 6px; }
    .btn {
      background: linear-gradient(120deg, var(--brand), var(--brand-2));
      color: #fff;
      border: none;
      font-weight: 700;
      cursor: pointer;
    }
    .btn:disabled { opacity: 0.6; cursor: not-allowed; }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .status.idle { color: var(--muted); }
    .status.running { color: var(--brand); }
    .status.success { color: var(--ok); }
    .status.error { color: var(--err); }
    .progress-wrap { margin-top: 12px; }
    .progress-meta {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 6px;
    }
    .progress-track {
      width: 100%;
      height: 10px;
      border-radius: 999px;
      background: #e7eef6;
      overflow: hidden;
      border: 1px solid var(--line);
    }
    .progress-fill {
      height: 100%;
      width: 0%;
      transition: width 0.3s ease;
      background: linear-gradient(120deg, var(--brand), var(--brand-2));
    }
    pre {
      margin: 0;
      padding: 12px;
      border-radius: 10px;
      background: #0f1722;
      color: #cdd8e7;
      border: 1px solid #25374f;
      min-height: 320px;
      max-height: 55vh;
      overflow: auto;
      font-size: 12px;
      line-height: 1.45;
      white-space: pre-wrap;
    }
    .links a {
      color: var(--brand);
      text-decoration: none;
      font-weight: 600;
      margin-right: 12px;
    }
    .links a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <h1>CAD AI 評価ランナー</h1>
      <p class="sub">クライアント向けワンクリック実行: データセット生成、変換、Gemini生成、採点、レポート作成。</p>
    </section>

    <section class="card">
      <div class="grid">
        <div>
          <label for="pattern">プロンプトパターン</label>
          <select id="pattern">
            <option value="all" selected>すべて (1 + 2 + 3)</option>
            <option value="1">パターン 1</option>
            <option value="2">パターン 2</option>
            <option value="3">パターン 3</option>
          </select>
        </div>
        <div>
          <button id="start" class="btn">パイプライン開始</button>
        </div>
        <div>
          <span id="status" class="status idle">待機中</span>
        </div>
      </div>
      <div class="progress-wrap">
        <div class="progress-meta">
          <span id="progressLabel">未開始</span>
          <span id="progressPct">0%</span>
        </div>
        <div class="progress-track"><div id="progressBar" class="progress-fill"></div></div>
        <div id="uiMessage" style="margin-top:6px; color:#b3261e; font-size:12px;"></div>
      </div>
    </section>

    <section class="card">
      <div class="links">
        <a href="/reports/html" target="_blank">HTMLレポートを開く</a>
        <a href="/reports/json" target="_blank">JSONレポートをダウンロード</a>
        <a href="/reports/xlsx" target="_blank">Excelレポートをダウンロード</a>
      </div>
    </section>

    <section class="card">
      <h3 style="margin-top:0">ライブログ</h3>
      <pre id="logs"></pre>
    </section>
  </div>

  <script>
    const startBtn = document.getElementById('start');
    const statusEl = document.getElementById('status');
    const logsEl = document.getElementById('logs');
    const progressBar = document.getElementById('progressBar');
    const progressPct = document.getElementById('progressPct');
    const progressLabel = document.getElementById('progressLabel');
    const uiMessage = document.getElementById('uiMessage');

    const statusLabels = {
      idle: '待機中',
      running: '実行中',
      success: '成功',
      error: 'エラー',
    };

    const stageLabels = {
      idle: '待機中',
      starting: '開始中',
      dataset: 'データセット生成',
      convert: '画像変換',
      generate: '生成',
      compare: '比較・採点',
      reports: 'レポート作成',
      done: '完了',
    };

    function setStatus(status) {
      statusEl.className = `status ${status}`;
      statusEl.textContent = statusLabels[status] || status;
    }

    async function startRun() {
      const payload = {
        pattern: document.getElementById('pattern').value,
        skip_dataset: true,
        skip_convert: true,
      };
      uiMessage.textContent = '';
      // Immediate feedback so users see start action took effect.
      setStatus('running');
      startBtn.disabled = true;
      progressLabel.textContent = '開始中 - リクエストを受け付けました';

      try {
        const res = await fetch(`/api/start?ts=${Date.now()}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          cache: 'no-store',
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) {
          setStatus('idle');
          startBtn.disabled = false;
          uiMessage.textContent = data.error || '実行を開始できませんでした';
        }
      } catch (err) {
        setStatus('error');
        startBtn.disabled = false;
        uiMessage.textContent = '/api/start の呼び出しに失敗しました。UIサーバーが起動中か確認してください。';
      }

      poll();
    }

    async function poll() {
      try {
        const res = await fetch(`/api/status?ts=${Date.now()}`, { cache: 'no-store' });
        const data = await res.json();
        uiMessage.textContent = '';
      setStatus(data.status);
      logsEl.textContent = data.logs.join('\\n');
      logsEl.scrollTop = logsEl.scrollHeight;
      startBtn.disabled = data.status === 'running';

      const p = data.progress || {};
      const pct = typeof p.percent === 'number' ? p.percent : 0;
      progressBar.style.width = `${Math.max(0, Math.min(100, pct))}%`;
      progressPct.textContent = `${pct.toFixed(1)}%`;
      const detail = p.detail || '';
      const stage = p.stage || 'idle';
      const current = p.current || 0;
      const total = p.count_total || 0;
      const countText = total > 0 ? ` (${current}/${total})` : '';
      const stageText = stageLabels[stage] || stage;
      progressLabel.textContent = `${stageText}${countText}${detail ? ' - ' + detail : ''}`;
      } catch (err) {
        setStatus('error');
        uiMessage.textContent = 'バックエンドサーバーに接続できません。cad-eval ui を再起動してください。';
      }
    }

    startBtn.addEventListener('click', startRun);
    setInterval(poll, 1500);
    poll();
  </script>
</body>
</html>
"""


class _LogCollector:
    """File-like object to capture pipeline stdout/stderr lines."""

    def __init__(self, state: "_RunState") -> None:
        self._state = state

    def write(self, text: str) -> int:
        if text:
            self._state.append_log(text)
        return len(text)

    def flush(self) -> None:
        return None


@dataclass
class _RunState:
    status: str = "idle"
    logs: list[str] = field(default_factory=list)
    progress: dict[str, Any] = field(default_factory=lambda: {
        "stage": "idle",
      "detail": "未開始",
        "completed": 0,
        "total": 1,
        "current": 0,
        "count_total": 0,
        "percent": 0.0,
    })
    lock: threading.Lock = field(default_factory=threading.Lock)

    def append_log(self, text: str) -> None:
      with self.lock:
        clean_text = _ANSI_OSC_RE.sub("", text)
        clean_text = _ANSI_CSI_RE.sub("", clean_text)
        parts = clean_text.replace("\r", "").split("\n")
        for part in parts:
          if part.strip():
            self.logs.append(part)
        # Keep only recent lines to avoid unbounded memory growth
        if len(self.logs) > 2000:
          self.logs = self.logs[-2000:]

    def set_status(self, value: str) -> None:
        with self.lock:
            self.status = value

    def set_progress(self, value: dict[str, Any]) -> None:
        with self.lock:
            self.progress = dict(value)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {"status": self.status, "logs": list(self.logs), "progress": dict(self.progress)}


_STATE = _RunState()


def _has_runtime_files(root: Path, pattern: str) -> bool:
  return any(root.rglob(pattern))


def _resolve_pipeline_reuse_flags() -> tuple[bool, bool]:
  settings = get_settings()
  has_dxf = _has_runtime_files(settings.dxf_dir, "*.dxf")
  has_images = _has_runtime_files(settings.images_dir, f"*.{settings.image_format}")
  skip_dataset = has_dxf
  skip_convert = has_dxf and has_images
  return skip_dataset, skip_convert


def _run_pipeline_worker(pattern: str, skip_dataset: bool, skip_convert: bool) -> None:
    _STATE.set_status("running")
    with _STATE.lock:
        _STATE.logs = []
    _STATE.progress = {
      "stage": "starting",
      "detail": "初期化中",
      "completed": 0,
      "total": 1,
      "current": 0,
      "count_total": 0,
      "percent": 0.0,
    }

    collector = _LogCollector(_STATE)

    try:
        pattern_ids = None if pattern == "all" else [int(pattern)]

        def _progress_cb(event: dict[str, Any]) -> None:
            _STATE.set_progress(event)

        with redirect_stdout(collector), redirect_stderr(collector):
            run_full_pipeline(
                pattern_ids=pattern_ids,
                skip_dataset=skip_dataset,
                skip_convert=skip_convert,
                progress_callback=_progress_cb,
            )
        _STATE.set_status("success")
    except Exception:
        _STATE.append_log(traceback.format_exc())
        _STATE.set_status("error")


def _json_response(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int = 200) -> None:
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store, max-age=0")
    handler.send_header("Pragma", "no-cache")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _serve_file(handler: BaseHTTPRequestHandler, path: Path, content_type: str) -> None:
    if not path.exists():
        _json_response(handler, {"error": f"ファイルが見つかりません: {path.name}"}, status=404)
        return

    data = path.read_bytes()
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        settings = get_settings()

        if parsed.path == "/":
            body = HTML_PAGE.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/status":
            _json_response(self, _STATE.snapshot())
            return

        if parsed.path == "/reports/html":
            _serve_file(self, settings.reports_dir / "evaluation_report.html", "text/html; charset=utf-8")
            return

        if parsed.path == "/reports/json":
            _serve_file(self, settings.reports_dir / "evaluation_report.json", "application/json")
            return

        if parsed.path == "/reports/xlsx":
            _serve_file(
                self,
                settings.reports_dir / "evaluation_report.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            return

        _json_response(self, {"error": "見つかりません"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/start":
            _json_response(self, {"error": "見つかりません"}, status=404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"

        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            _json_response(self, {"error": "JSONボディが不正です"}, status=400)
            return

        pattern = str(payload.get("pattern", "all"))
        if pattern not in {"all", "1", "2", "3"}:
            _json_response(self, {"error": "pattern は all, 1, 2, 3 のいずれかを指定してください"}, status=400)
            return

        skip_dataset, skip_convert = _resolve_pipeline_reuse_flags()

        snapshot = _STATE.snapshot()
        if snapshot["status"] == "running":
            _json_response(self, {"error": "パイプラインはすでに実行中です"}, status=409)
            return

        # Set running state before thread starts to avoid UI race showing "idle".
        with _STATE.lock:
            _STATE.status = "running"
            _STATE.logs = []
            _STATE.progress = {
                "stage": "starting",
                "detail": "キューに追加済み",
                "completed": 0,
                "total": 1,
                "current": 0,
                "count_total": 0,
                "percent": 0.0,
            }

        t = threading.Thread(
            target=_run_pipeline_worker,
            kwargs={
                "pattern": pattern,
                "skip_dataset": skip_dataset,
                "skip_convert": skip_convert,
            },
            daemon=True,
        )
        t.start()

        _json_response(self, {"ok": True, "status": "running"}, status=202)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        # Reduce noise in terminal.
        return None


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the one-click web UI server."""
    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"CAD Eval UI running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
