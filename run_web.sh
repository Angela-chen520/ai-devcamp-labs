#!/usr/bin/env bash
# ==============================================================================
# Global Traveler Smart Customs & Baggage Advisor (旅客出入境行李與報關智慧諮詢系統)
# One-click startup script for Web Interface
# ==============================================================================

set -e

# Load local .env if present
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
elif [ -f "capstone_customs_agent/.env" ]; then
    set -a
    source capstone_customs_agent/.env
    set +a
fi

# Detect whether using Gemini API Key or Vertex AI
if [ -n "$GEMINI_API_KEY" ] && [ -z "$GOOGLE_GENAI_USE_VERTEXAI" ]; then
    export GOOGLE_GENAI_USE_VERTEXAI="False"
    BACKEND_DESC="Google AI Studio (GEMINI_API_KEY)"
else
    export GOOGLE_GENAI_USE_VERTEXAI="${GOOGLE_GENAI_USE_VERTEXAI:-True}"
    export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-ai-devcamp-angela-510313}"
    export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
    BACKEND_DESC="Vertex AI (${GOOGLE_CLOUD_PROJECT} @ ${GOOGLE_CLOUD_LOCATION})"
fi
export PORT="${PORT:-8000}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "✈️  啟動【全球旅客出入境行李與報關智慧諮詢系統】網頁伺服器..."
echo "🔒 Zero-PII 隱私安全守護已啟動 (不採集任何護照號碼與身分證字號)"
echo "📡 模型服務連線至：${BACKEND_DESC}"
echo "=================================================================="
echo "🌐 請在瀏覽器中開啟以下網址進行體驗："
echo "   👉 http://localhost:${PORT}"
echo "=================================================================="

# Check for local uv or system uv
if [ -x "./.bin/uv" ]; then
    UV_BIN="./.bin/uv"
elif command -v uv >/dev/null 2>&1; then
    UV_BIN="uv"
else
    echo "❌ 找不到 uv 命令，請確認 uv 已安裝。"
    exit 1
fi

exec "$UV_BIN" run python capstone_customs_agent/web_server.py
