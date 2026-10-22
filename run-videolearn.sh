#!/usr/bin/env bash
# VideoLearn AI (影片智慧教材生成與資安防護系統)
# Port: 8001 (or set PORT env var)
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8001}"
HOST="${HOST:-0.0.0.0}"

echo "=========================================================="
echo "  VideoLearn AI — 影片智慧教材生成與資安防護系統啟動中"
echo "  ⚖️ 聲明：一切資源作學術研討幫助學習者學習，不提供商業用、或搬運影片用"
echo "  🛡️ 7 重企業級資安防線 (SSRF、Magic Bytes、指令過濾) 已載入"
echo "=========================================================="

if [ -f "./.bin/uv" ]; then
    UV_BIN="./.bin/uv"
elif command -v uv >/dev/null 2>&1; then
    UV_BIN="uv"
else
    UV_BIN="python3 -m"
fi

echo "正在啟動伺服器，請至瀏覽器開啟：http://localhost:${PORT}"
exec ${UV_BIN} run uvicorn video_courseware_agent.web_server:app --host "${HOST}" --port "${PORT}" --reload
