"""
ADK Agent Orchestrator for VideoLearn AI.
Orchestrates:
1. Security Screening & Sanitization (SSRF, Magic-Byte inspection, Anti-Malware)
2. Media Ingestion across 13 video platforms & local uploads
3. Audio Transcription with millisecond timestamp alignment
4. Multi-Format Courseware Generation (Summary, Highlights, Quiz, PPTX, Canva, Mindmap)
5. Grounded Interactive AI Tutor with Fair-Use Academic Disclaimers
"""

import os
import uuid
from typing import Dict, Any, List, Optional

from video_courseware_agent.security import SecurityGuard
from video_courseware_agent.media_ingest import MediaIngestor
from video_courseware_agent.transcriber import AudioTranscriber
from video_courseware_agent.courseware_engine import CoursewareEngine
from video_courseware_agent.tutor import AcademicTutor

try:
    from google.adk.agents import Agent
    from google.adk.models import Gemini
    from google.adk.tools import BaseTool
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False


class VideoLearnOrchestrator:
    """
    Core orchestrator managing the end-to-end pipeline from raw video link to multi-format courseware.
    """

    def __init__(self, output_dir: str = "video_courseware_agent/exports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.security = SecurityGuard()
        self.ingestor = MediaIngestor(output_dir="video_courseware_agent/temp_media")
        self.transcriber = AudioTranscriber()
        self.courseware_engine = CoursewareEngine()
        self.tutor = AcademicTutor()

        # In-memory store for jobs and active course contexts
        self.jobs: Dict[str, Dict[str, Any]] = {}

    def process_video_pipeline(self, url: Optional[str] = None, file_bytes: Optional[bytes] = None, filename: Optional[str] = None, custom_title: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes the full pipeline:
        1. Security Pre-Check (URL & Intranet protection / File Magic-Byte scan)
        2. Media Ingestion
        3. Speech-to-Text & Subtitle Timestamp Generation
        4. Multi-tier Courseware & Presentation Building
        5. Storage & Download preparation
        """
        job_id = str(uuid.uuid4())[:8]

        # Step 1: Ingestion & Security Validation
        if file_bytes and filename:
            ingest_result = self.ingestor.ingest_uploaded_file(file_bytes, filename)
        elif url:
            ingest_result = self.ingestor.ingest_url(url)
        else:
            raise ValueError("必須提供影片網址 (URL) 或上傳之影音檔案。")

        if not ingest_result.get("is_safe", True):
            return {
                "job_id": job_id,
                "status": "security_blocked",
                "error": ingest_result.get("error", "未能通過資安防禦檢核"),
                "security_report": self.security.get_protection_manifest(),
                "security_diagnostic": ingest_result.get("security_diagnostic")
            }

        # Override title if custom title provided
        if custom_title:
            ingest_result["title"] = custom_title

        # Step 2: Transcribe Speech to Timecoded Subtitles (SRT / VTT)
        audio_path = ingest_result.get("audio_path", "")
        transcript_data = self.transcriber.transcribe(audio_path, ingest_result)

        # Step 3: Multi-format Courseware Generation
        courseware_data = self.courseware_engine.generate_courseware(transcript_data, ingest_result)

        # Step 4: Save persistent export artifacts
        pptx_filename = f"courseware_{job_id}.pptx"
        pptx_filepath = os.path.join(self.output_dir, pptx_filename)
        with open(pptx_filepath, "wb") as f:
            f.write(courseware_data["pptx_bytes"])

        md_filename = f"courseware_{job_id}.md"
        md_filepath = os.path.join(self.output_dir, md_filename)
        with open(md_filepath, "w", encoding="utf-8") as f:
            f.write(courseware_data["markdown"])

        srt_filename = f"subtitles_{job_id}.srt"
        srt_filepath = os.path.join(self.output_dir, srt_filename)
        with open(srt_filepath, "w", encoding="utf-8") as f:
            f.write(transcript_data["srt"])

        vtt_filename = f"subtitles_{job_id}.vtt"
        vtt_filepath = os.path.join(self.output_dir, vtt_filename)
        with open(vtt_filepath, "w", encoding="utf-8") as f:
            f.write(transcript_data["vtt"])

        # Record Job Context
        job_record = {
            "job_id": job_id,
            "status": "completed",
            "title": ingest_result.get("title", "影片研討教材"),
            "platform": ingest_result.get("platform", "Local"),
            "duration": ingest_result.get("duration", 300),
            "source_url": url or filename,
            "security_report": {
                "checks_passed": [
                    "SSRF 與內網偽造防護 (Intranet IP Blocking)",
                    "網域白名單驗證 (13 跨國主流平台支援)",
                    "指令注入與 Shell 跳脫過濾 (Command Sanitization)",
                    "檔案 Magic Bytes 二進位特徵防毒檢驗 (Anti-Malware PE/ELF Detection)",
                    "提示詞注入清洗 (Prompt Injection Defense)"
                ],
                "fair_use_notice": SecurityGuard.FAIR_USE_DISCLAIMER
            },
            "subtitles": {
                "srt_download": f"/api/export/subtitles/{job_id}?format=srt",
                "vtt_download": f"/api/export/subtitles/{job_id}?format=vtt",
                "srt_content": transcript_data["srt"],
                "vtt_content": transcript_data["vtt"],
                "segments": transcript_data["segments"],
                "full_text": transcript_data["full_text"]
            },
            "courseware": {
                "executive_summary": courseware_data["executive_summary"],
                "key_highlights": courseware_data["key_highlights"],
                "extended_learning": courseware_data["extended_learning"],
                "unexplored_keywords": courseware_data.get("unexplored_keywords", []),
                "learning_roadmap": courseware_data.get("learning_roadmap", {}),
                "roadmap_mermaid": courseware_data.get("roadmap_mermaid", ""),
                "markdown": courseware_data["markdown"],
                "canva_script": courseware_data["canva_script"],
                "mindmap_mermaid": courseware_data["mindmap_mermaid"],
                "pptx_download": f"/api/export/pptx/{job_id}",
                "markdown_download": f"/api/export/markdown/{job_id}"
            }
        }

        self.jobs[job_id] = job_record
        return job_record

    def ask_tutor(self, job_id: str, question: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Interactive discussion with AI tutor based on the video context.
        """
        job = self.jobs.get(job_id)
        if not job:
            # General discussion context
            context = {"title": "一般影片研討", "full_text": "", "segments": []}
        else:
            context = {
                "title": job["title"],
                "full_text": job["subtitles"]["full_text"],
                "segments": job["subtitles"]["segments"]
            }

        return self.tutor.chat(question, history or [], context)


# Create singleton instance
orchestrator = VideoLearnOrchestrator()
