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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("video_courseware_agent.web_server:app", host="0.0.0.0", port=8001, reload=True)
