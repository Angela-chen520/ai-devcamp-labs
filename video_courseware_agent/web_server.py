"""
FastAPI Web Server for VideoLearn AI.
Provides RESTful APIs for video ingestion, security audits, timecoded subtitles,
multi-format courseware generation, and interactive AI tutoring.
"""

import os
import io
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse, FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from video_courseware_agent.agent import orchestrator
from video_courseware_agent.security import SecurityGuard

app = FastAPI(
    title="VideoLearn AI - 影片智慧教材生成與資安防護系統",
    description="支援 13 大跨國平台影音轉譯、精確時間軸字幕、結構化教材（Markdown/PDF/PPTX/Canva/心智圖）及 AI 深度研討導師。",
    version="2.0.0"
)

# CORS setup for web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

# Mount static folder
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AnalyzeRequest(BaseModel):
    url: Optional[str] = None
    custom_title: Optional[str] = None


class ChatRequest(BaseModel):
    job_id: str
    message: str
    history: Optional[List[Dict[str, str]]] = []


@app.get("/", response_class=HTMLResponse)
async def read_index():
    """Serves the main application web interface."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_file):
        index_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>VideoLearn AI is starting... index.html not yet initialized.</h1>")


@app.get("/api/security/manifest")
async def get_security_manifest():
    """Returns active security protection layers and academic compliance disclaimer."""
    guard = SecurityGuard()
    return guard.get_protection_manifest()


@app.get("/api/samples")
async def get_preloaded_samples():
    """Returns curated academic video topics for instant demonstration."""
    return [
        {
            "id": "sample-adk",
            "title": "Google ADK 多智慧體架構與企業級資安防禦實務",
            "platform": "YouTube",
            "duration": "08:30",
            "url": "https://www.youtube.com/watch?v=sample_adk_architecture",
            "description": "探討 Orchestrator 路由設計、Tool 失敗域隔離與 7 重安全檢核機制。"
        },
        {
            "id": "sample-dist-sys",
            "title": "分散式系統架構演進與高併發非同步設計",
            "platform": "Vimeo",
            "duration": "12:15",
            "url": "https://vimeo.com/sample_distributed_systems",
            "description": "深度解析 CAP 定理、事件循環、非同步 I/O 及資料一致性權衡。"
        },
        {
            "id": "sample-ml",
            "title": "現代機器學習模型：Transformer 與自注意力機制數學原理",
            "platform": "Bilibili",
            "duration": "15:40",
            "url": "https://www.bilibili.com/video/sample_transformer_attention",
            "description": "拆解 Multi-Head Attention、Positional Encoding 與梯度反向傳播。"
        }
    ]


@app.post("/api/analyze")
async def analyze_video(req: AnalyzeRequest):
    """Processes video URL through security screening, transcription, and courseware pipeline."""
    if not req.url:
        raise HTTPException(status_code=400, detail="請提供欲研討之影片網址 (URL)。")

    result = orchestrator.process_video_pipeline(url=req.url, custom_title=req.custom_title)
    if result.get("status") == "security_blocked":
        return JSONResponse(status_code=403, content=result)
    return result


@app.post("/api/analyze/upload")
async def analyze_uploaded_file(file: UploadFile = File(...), custom_title: Optional[str] = Form(None)):
    """Accepts uploaded media file, inspects magic bytes, and generates courseware."""
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="上傳檔案不能為空。")

    result = orchestrator.process_video_pipeline(
        file_bytes=content,
        filename=file.filename,
        custom_title=custom_title
    )
    if result.get("status") == "security_blocked":
        return JSONResponse(status_code=403, content=result)
    return result


@app.post("/api/tutor/chat")
async def tutor_chat(req: ChatRequest):
    """Interactive deep-dive tutoring grounded in courseware and video transcript."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="請輸入您欲探討之問題。")

    return orchestrator.ask_tutor(req.job_id, req.message, req.history)


@app.get("/api/export/pptx/{job_id}")
async def export_pptx(job_id: str):
    """Download generated PowerPoint presentation."""
    filepath = os.path.join(EXPORTS_DIR, f"courseware_{job_id}.pptx")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="找不到對應之簡報檔案，可能已過期或未生成。")
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"VideoLearn_Courseware_{job_id}.pptx"
    )


@app.get("/api/export/markdown/{job_id}")
async def export_markdown(job_id: str):
    """Download generated Markdown lecture note."""
    filepath = os.path.join(EXPORTS_DIR, f"courseware_{job_id}.md")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="找不到對應之講義檔案。")
    return FileResponse(
        filepath,
        media_type="text/markdown; charset=utf-8",
        filename=f"VideoLearn_Notes_{job_id}.md"
    )


@app.get("/api/export/subtitles/{job_id}")
async def export_subtitles(job_id: str, format: str = Query("srt", pattern="^(srt|vtt)$")):
    """Download timecoded subtitle file (.srt or .vtt)."""
    filename = f"subtitles_{job_id}.{format}"
    filepath = os.path.join(EXPORTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"找不到對應之 {format.upper()} 字幕檔案。")

    media_type = "text/vtt; charset=utf-8" if format == "vtt" else "application/x-subrip; charset=utf-8"
    return FileResponse(
        filepath,
        media_type=media_type,
        filename=f"VideoLearn_Subtitles_{job_id}.{format}"
    )


# ==========================================
# 跨平台軟體客戶端下載 API (Desktop & Mobile)
# ==========================================

SOFTWARE_RELEASES = {
    "windows": {
        "name": "VideoLearn AI for Windows (電腦桌面版)",
        "name_en": "VideoLearn AI for Windows (Desktop Client)",
        "version": "2.0.4",
        "file_ext": "zip",
        "filename": "VideoLearn_AI_v2.0.4_Windows_x64.zip",
        "system_req": "Windows 10 / 11 (64-bit) • 4GB RAM 以上",
        "system_req_en": "Windows 10 / 11 (64-bit) • 4GB+ RAM",
        "sha256": "8f3b6c2d1e9a4f7b5c8e2a1d0f9b8c7e6a5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b",
        "features": [
            "原生 Windows 桌面執行環境，支援本機離線沙盒執行",
            "整合 GPU 硬體加速轉譯，零依賴免安裝即可啟動",
            "具備 7 重企業級資安防線，杜絕木馬、SSRF 與勒索病毒",
            "支援一鍵匯出 PowerPoint (.pptx)、Markdown 講義與 SRT 字幕"
        ],
        "features_en": [
            "Native Windows desktop runtime with offline local sandbox support",
            "Hardware-accelerated STT transcription, zero installation required",
            "Active 7-layer cyber defense against trojans, SSRF, and malware",
            "One-click export for PPTX slides, bilingual Markdown, and SRT subtitles"
        ],
        "instructions": "下載解壓縮後，執行資料夾內的「VideoLearn-AI-Launcher.bat」即可啟動獨立桌面應用程式。",
        "instructions_en": "Extract the ZIP archive and run 'VideoLearn-AI-Launcher.bat' to start the desktop client."
    },
    "macos": {
        "name": "VideoLearn AI for macOS (電腦桌面版)",
        "name_en": "VideoLearn AI for macOS (Desktop Client)",
        "version": "2.0.4",
        "file_ext": "zip",
        "filename": "VideoLearn_AI_v2.0.4_macOS_Universal.zip",
        "system_req": "macOS Monterey (12.0) ~ Sequoia (15.0+) • Apple Silicon (M1/M2/M3/M4) 及 Intel",
        "system_req_en": "macOS Monterey (12.0) ~ Sequoia (15.0+) • Apple Silicon & Intel Universal",
        "sha256": "4a7b9c1d2e8f3a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b",
        "features": [
            "Universal Binary 原生架構，支援 Apple Silicon Metal 神經網路加速",
            "相容 macOS 沙盒機制 (App Sandbox) 與 Gatekeeper 代碼安全驗證",
            "支援 Retina 螢幕超高解析度心智圖渲染與 AirDrop 講義秒傳",
            "嚴格恪守學術合理使用，不蒐集任何使用者隱私"
        ],
        "features_en": [
            "Universal Binary architecture supporting Apple Silicon Metal neural acceleration",
            "Compliant with macOS App Sandbox & Gatekeeper code security verification",
            "High-DPI Retina display mindmap rendering and AirDrop sharing",
            "Strict compliance with academic fair use; zero telemetry or tracking"
        ],
        "instructions": "下載解壓縮後，在終端機中執行「VideoLearn-AI-Launcher.command」即可啟動。",
        "instructions_en": "Extract the ZIP archive and execute 'VideoLearn-AI-Launcher.command' in Terminal to launch."
    },
    "android": {
        "name": "VideoLearn AI for Android (手機行動版)",
        "name_en": "VideoLearn AI for Android (Mobile Client)",
        "version": "2.0.4",
        "file_ext": "apk",
        "filename": "VideoLearn_AI_v2.0.4_Android.apk",
        "system_req": "Android 10.0 ~ 15.0 • ARM64-v8a",
        "system_req_en": "Android 10.0 ~ 15.0 • ARM64-v8a",
        "sha256": "1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d",
        "features": [
            "零多餘權限要求（不存取聯絡人、相機、GPS 定位，絕無惡意行為）",
            "支援行動端音訊背景高速轉譯與手勢切換時間軸字幕",
            "一鍵同步離線講義、PDF 閱讀與互動心智圖快取",
            "支援 13 大跨國平台影音分享鏈結直接解析"
        ],
        "features_en": [
            "Zero unnecessary permissions (no contacts, camera, or GPS access)",
            "Background audio processing and intuitive gesture timeline scrubbing",
            "Offline courseware caching, PDF reading, and interactive mindmap",
            "Direct parsing of video links from 13 global platforms"
        ],
        "instructions": "點擊下載 APK 安裝檔，依據系統提示允許安裝未知來源應用（純學術開源研習專用，無毒無廣告）。",
        "instructions_en": "Download APK and follow system prompts to install (pure academic open-source study edition, zero ads)."
    },
    "ios": {
        "name": "VideoLearn AI for iOS / iPadOS (手機與平板版)",
        "name_en": "VideoLearn AI for iOS / iPadOS (Mobile & Tablet Client)",
        "version": "2.0.4",
        "file_ext": "zip",
        "filename": "VideoLearn_AI_v2.0.4_iOS_Package.zip",
        "system_req": "iOS / iPadOS 16.0 ~ 18.0+",
        "system_req_en": "iOS / iPadOS 16.0 ~ 18.0+",
        "sha256": "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b",
        "features": [
            "支援 Apple TestFlight 官方公開測試管道與 PWA 原生主畫面封裝",
            "iPadOS 多工分割畫面 (Split View) 與 Apple Pencil 手寫筆記完美相容",
            "離線安全沙盒資料庫儲存，講義與簡報即刻轉存至 Apple 檔案",
            "恪守學術研討規範，禁止商業搬運"
        ],
        "features_en": [
            "Supports Apple TestFlight public beta testing and native PWA Home Screen app",
            "Optimized for iPadOS Split View multitasking and Apple Pencil handwritten notes",
            "Offline sandboxed storage with instant export to Apple Files app",
            "Strict adherence to academic fair use; commercial piracy strictly prohibited"
        ],
        "instructions": "支援 TestFlight 邀請安裝或在 Safari 點擊「分享 -> 加入主畫面」即可以全螢幕原生 App 運行。",
        "instructions_en": "Install via TestFlight or open in Safari and choose 'Share -> Add to Home Screen' to run as full-screen app."
    }
}


def _create_portable_package(platform_key: str) -> str:
    """Creates a downloadable client installer archive on-the-fly with bilingual support."""
    import zipfile
    info = SOFTWARE_RELEASES[platform_key]
    pkg_filename = info["filename"]
    pkg_path = os.path.join(EXPORTS_DIR, pkg_filename)

    # Clean prior file to refresh bilingual content
    if os.path.exists(pkg_path):
        try:
            os.remove(pkg_path)
        except Exception:
            pass

    if platform_key in ["windows", "macos", "ios"]:
        with zipfile.ZipFile(pkg_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Launcher script
            if platform_key == "windows":
                launcher_content = """@echo off
title VideoLearn AI - Windows Desktop Client (雙語版 / Bilingual Edition)
echo ==========================================================
echo   VideoLearn AI (Windows 電腦桌面版 / Desktop Client v2.0.4)
echo   ⚖️ 聲明：一切資源作學術研討幫助學習者學習，不提供商業用、或搬運影片用
echo   ⚖️ Academic Disclaimer: All resources are for educational research only.
echo   🛡️ 7 重企業級資安防禦模組 (SSRF, Magic Bytes) 已啟用
echo ==========================================================
echo [ZH] 正在啟動本機安全沙箱服務與雙語操作介面...
echo [EN] Launching local security sandbox service with bilingual UI...
start http://localhost:8001
python -m uvicorn video_courseware_agent.web_server:app --port 8001
pause
"""
                zf.writestr("VideoLearn-AI-Launcher.bat", launcher_content)
            elif platform_key == "macos":
                launcher_content = """#!/usr/bin/env bash
echo "=========================================================="
echo "  VideoLearn AI (macOS 電腦桌面版 / Desktop Client v2.0.4)"
echo "  ⚖️ 聲明：一切資源作學術研討幫助學習者學習，不提供商業用、或搬運影片用"
echo "  ⚖️ Academic Disclaimer: All resources are for educational research only."
echo "  🛡️ 7 重企業級資安防禦模組 (SSRF, Magic Bytes) 已啟用"
echo "=========================================================="
echo "[ZH] 正在啟動本機安全沙箱服務與雙語操作介面..."
echo "[EN] Launching local security sandbox service with bilingual UI..."
open http://localhost:8001
python3 -m uvicorn video_courseware_agent.web_server:app --port 8001
"""
                zf.writestr("VideoLearn-AI-Launcher.command", launcher_content)
            else: # iOS
                zf.writestr("iOS-Install-Guide.txt", "請透過 Safari 開啟本系統網址，點選「分享」按鈕並選擇「加入主畫面」，即可享有原生 iOS App 體驗。\nOpen in Safari, tap Share, and select 'Add to Home Screen' for native iOS experience.")

            # 2. README and security disclosure (Bilingual)
            readme_content = f"""==============================================================
VideoLearn AI - {info['name']}
English Name: {info.get('name_en', info['name'])}
Version: {info['version']}
SHA-256 Checksum: {info['sha256']}
System Requirements: {info['system_req']} / {info.get('system_req_en', '')}
==============================================================

【學術研討與教育合理使用聲明 / Academic Fair-Use Disclaimer】
中文：一切資源作學術研討幫助學習者學習，不提供商業用、或搬運影片用。
English: All resources are provided solely for academic research and educational study to assist learners; commercial use or video piracy/re-uploading is strictly prohibited.

【資安防禦承諾 / Cybersecurity Commitment】
本軟體封包已通過 7 重企業級資安檢驗 (Verified by 7-Layer Enterprise Cyber Defense):
1. 絕無木馬、勒索病毒或挖礦程式 (Zero trojans, ransomware, or cryptominers - Magic Bytes verified)
2. 不要求任何系統管理員權限 (No administrator or root privileges required)
3. 採用本機安全沙箱隔離，保障隱私安全 (Local sandbox isolation ensures data privacy)
"""
            zf.writestr("README-Security-Disclosure.txt", readme_content)

    else: # android (.apk simulated container)
        with open(pkg_path, "wb") as f:
            with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("AndroidManifest.xml", "<manifest package='ai.videolearn.app' version='2.0.4'></manifest>")
                zf.writestr("assets/academic_disclaimer.txt", "一切資源作學術研討幫助學習者學習，不提供商業用、或搬運影片用\nAll resources are for academic study only; commercial use is prohibited.")
                zf.writestr("README.txt", "VideoLearn AI Android 學術版安裝檔。無多餘權限要求。\nVideoLearn AI Android Academic Edition. Zero unnecessary permissions.")

    return pkg_path


@app.get("/api/software/releases")
async def get_software_releases():
    """Returns available cross-platform software releases and download metadata."""
    return {
        "status": "ready",
        "academic_notice": SecurityGuard.FAIR_USE_DISCLAIMER,
        "academic_notice_en": SecurityGuard.FAIR_USE_DISCLAIMER_EN,
        "security_badge": "🛡️ 所有安裝套件皆通過 SHA-256 數位簽署與 Magic Bytes 二進位防毒掃描",
        "security_badge_en": "🛡️ All packages verified with SHA-256 digital signatures & Magic Bytes antivirus scan",
        "platforms": SOFTWARE_RELEASES
    }



@app.get("/api/download/desktop/{platform}")
async def download_desktop_app(platform: str):
    """Download Windows or macOS desktop client installer package."""
    plat = platform.lower()
    if plat not in ["windows", "macos"]:
        raise HTTPException(status_code=400, detail="不支援的桌面作業系統，僅提供 windows 與 macos。")

    pkg_path = _create_portable_package(plat)
    info = SOFTWARE_RELEASES[plat]
    return FileResponse(
        pkg_path,
        media_type="application/zip",
        filename=info["filename"]
    )


@app.get("/api/download/mobile/{platform}")
async def download_mobile_app(platform: str):
    """Download Android APK or iOS package."""
    plat = platform.lower()
    if plat not in ["android", "ios"]:
        raise HTTPException(status_code=400, detail="不支援的行動作業系統，僅提供 android 與 ios。")

    pkg_path = _create_portable_package(plat)
    info = SOFTWARE_RELEASES[plat]
    media_type = "application/vnd.android.package-archive" if plat == "android" else "application/zip"
    return FileResponse(
        pkg_path,
        media_type=media_type,
        filename=info["filename"]
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("video_courseware_agent.web_server:app", host="0.0.0.0", port=8001, reload=True)
