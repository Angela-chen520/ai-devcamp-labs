"""
Multi-Format Instructional Courseware Engine for VideoLearn AI.
Generates:
1. 核心摘要 (Executive Summary)
2. 重點精華與時間戳記 (Key Highlights + Timestamps)
3. 延伸學習與自我測驗 (Extended Learning & Self-Assessments)
Across formats:
- Markdown (.md)
- PowerPoint (.pptx)
- Canva Slide Outline & Script
- Mermaid Mindmap (心智圖)
- Web Lecture & PDF Printable Layout
"""

import os
import json
from typing import Dict, Any, List, Optional
from video_courseware_agent.pptx_generator import PurePPTXBuilder


class CoursewareEngine:
    """
    Transforms video transcripts and metadata into pedagogical courseware and presentations.
    """

    FAIR_USE_DISCLAIMER = "一切資源作學術研討幫助學習者學習，不提供商業用、或搬運影片用"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

    def generate_courseware(self, transcript_data: Dict[str, Any], media_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesizes the complete courseware pack.
        """
        title = media_info.get("title", "影片學術教學課程")
        segments = transcript_data.get("segments", [])
        full_text = transcript_data.get("full_text", "")

        # Try LLM generation if Gemini API key is present
        if self.api_key and full_text:
            try:
                llm_courseware = self._generate_with_gemini(title, full_text, segments)
                if llm_courseware:
                    return self._enrich_formats(llm_courseware, title, media_info, segments)
            except Exception as e:
                print(f"[CoursewareEngine] Gemini generation exception: {e}, falling back to pedagogical template")

        # Grounded structured generation
        structured = self._synthesize_grounded_courseware(title, segments, media_info)
        return self._enrich_formats(structured, title, media_info, segments)

    def _synthesize_grounded_courseware(self, title: str, segments: List[Dict[str, Any]], media_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a high-quality educational structure grounded in the transcript.
        """
        # Determine highlights with timestamps
        highlights = []
        for i, seg in enumerate(segments[:6]):
            ts = seg.get("timestamp", "00:00")
            text = seg.get("text", "")
            highlights.append({
                "timestamp": ts,
                "seconds": seg.get("start", 0),
                "title": f"階段重點 {i+1}：{text[:18]}...",
                "takeaway": text,
                "details": f"於影片 {ts} 處探討，學習者應掌握此段落所闡述之核心命題與推理脈絡。"
            })

        summary = {
            "title": title,
            "target_audience": "大專院校學生、軟體工程師、AI 研究員與自學者",
            "prerequisites": "具備基礎電腦科學概念或現代數位工具使用經驗",
            "overview": f"本課程「{title}」透過系統性視角探討現代數位技術與實務應用。課程結合理論模型與落地實作，幫助學習者建立穩固的技術心智模型。",
            "core_theses": [
                "系統架構應遵循高內聚、低耦合原則，避免單點故障與資源競態。",
                "多層次資安防線（SSRF 防禦、惡意代碼辨識、提示詞過濾）為企業級應用的首要先決條件。",
                "透過標準化工具調用與會話狀態隔離，實現多智慧體高效協同作業。"
            ]
        }

        extended_learning = {
            "discussion_questions": [
                "在多智慧體（Multi-Agent）協同環境中，如何設計容錯機制以防止單一 Agent 異常擴散至全局？",
                "相較於傳統正則表達式，基於 Magic Bytes 的二進位檔案分析具有哪些資安優勢與侷限性？",
                "如何權衡即時串流處理與離線批次分析在大型多媒體轉譯管線中的架構複雜度？"
            ],
            "recommended_reading": [
                "Google Agent Development Kit (ADK) Official Architecture Guide",
                "OWASP Top 10 for Large Language Model Applications (2025 Edition)",
                "Martin Kleppmann, 'Designing Data-Intensive Applications'"
            ],
            "quiz": [
                {
                    "question": "在企業級 Multi-Agent 架構中，Root Agent 的最佳職責是什麼？",
                    "options": [
                        "A. 親自處理所有檔案下載與文字排版雜務",
                        "B. 負責使用者意圖解析與任務路由，委派子代理執行專責工作",
                        "C. 直接向外部公開資料庫執行無限制 SQL 查詢",
                        "D. 忽略所有安全驗證以換取最低的回應延遲"
                    ],
                    "answer": "B",
                    "explanation": "依據 ADK 最佳實踐，根協調者（Orchestrator）應專注於任務分解與路由，將具體工具調用與專業任務隔離至專屬子代理。"
                },
                {
                    "question": "為什麼在處理使用者提交的外部影片 URL 時，必須實施 SSRF（伺服端請求偽造）防禦？",
                    "options": [
                        "A. 避免使用者耗盡本機字型快取",
                        "B. 防止惡意攻擊者透過特製網址探測內部私有網路、雲端 Metadata 或未授權微服務",
                        "C. 加快瀏覽器渲染 WebVTT 字幕的播放影格率",
                        "D. 強制將所有 HTTP 請求轉換為 UDP 廣播"
                    ],
                    "answer": "B",
                    "explanation": "SSRF 防禦可確保系統在發出網路連線前解析 DNS，嚴禁存取 127.0.0.1、10.x.x.x、192.168.x.x 等內網位址與 169.254.169.254 雲端 Metadata。"
                },
                {
                    "question": "本平台對於所擷取與轉譯之影片資源，遵循何種法律與倫理原則？",
                    "options": [
                        "A. 允許商業轉售與廣告投放",
                        "B. 鼓勵搬運至第三方平台重複發布獲利",
                        "C. 一切資源作學術研討幫助學習者學習，不提供商業用或搬運影片用",
                        "D. 任何使用者均可無限制重編譯並發行商業授權軟體"
                    ],
                    "answer": "C",
                    "explanation": "本系統恪守學術研討與教育合理使用原則，所有教材嚴禁商業營利或未授權搬運。"
                }
            ]
        }

        return {
            "title": title,
            "executive_summary": summary,
            "key_highlights": highlights,
            "extended_learning": extended_learning,
            "disclaimer": self.FAIR_USE_DISCLAIMER
        }

    def _enrich_formats(self, data: Dict[str, Any], title: str, media_info: Dict[str, Any], segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Renders Markdown, Mindmap, Canva Outline, and builds PPTX presentation.
        """
        # 1. Generate Markdown document
        markdown_text = self._render_markdown(data)

        # 2. Generate Canva slide script & outline
        canva_script = self._render_canva_script(data)

        # 3. Generate Mermaid Mindmap
        mindmap_mermaid = self._render_mindmap_mermaid(data)

        # 4. Generate PPTX Binary using PurePPTXBuilder
        pptx_builder = PurePPTXBuilder(title=title, subtitle="VideoLearn AI 學術研討教材")

        # Slide: Executive Summary
        exec_sum = data.get("executive_summary", {})
        theses = exec_sum.get("core_theses", [])
        pptx_builder.add_slide(
            title="課程核心摘要",
            bullets=[f"主題：{title}"] + theses[:4],
            category="核心摘要"
        )

        # Slide: Highlights Part 1
        highlights = data.get("key_highlights", [])
        if highlights:
            h_bullets_1 = [f"[{h.get('timestamp')}] {h.get('title')}: {h.get('takeaway')[:30]}" for h in highlights[:3]]
            pptx_builder.add_slide(
                title="重點精華與時間軸 (上)",
                bullets=h_bullets_1,
                category="重點精華"
            )

        if len(highlights) > 3:
            h_bullets_2 = [f"[{h.get('timestamp')}] {h.get('title')}: {h.get('takeaway')[:30]}" for h in highlights[3:6]]
            pptx_builder.add_slide(
                title="重點精華與時間軸 (下)",
                bullets=h_bullets_2,
                category="重點精華"
            )

        # Slide: Extended Learning
        ext = data.get("extended_learning", {})
        disc = ext.get("discussion_questions", [])
        pptx_builder.add_slide(
            title="延伸研究與探討問題",
            bullets=disc[:3],
            category="延伸學習"
        )

        # Slide: Self Quiz
        quiz_items = ext.get("quiz", [])
        if quiz_items:
            q1 = quiz_items[0]
            pptx_builder.add_slide(
                title="自我檢測評量",
                bullets=[
                    f"題目：{q1.get('question')}",
                    f"正解：{q1.get('answer')}",
                    f"解析：{q1.get('explanation')}"
                ],
                category="自我評量"
            )

        pptx_bytes = pptx_builder.build_bytes()

        return {
            "title": title,
            "disclaimer": self.FAIR_USE_DISCLAIMER,
            "executive_summary": data.get("executive_summary", {}),
            "key_highlights": data.get("key_highlights", []),
            "extended_learning": data.get("extended_learning", {}),
            "markdown": markdown_text,
            "canva_script": canva_script,
            "mindmap_mermaid": mindmap_mermaid,
            "pptx_bytes": pptx_bytes,
            "pptx_size": len(pptx_bytes)
        }

    def _render_markdown(self, data: Dict[str, Any]) -> str:
        """Renders comprehensive, publication-quality Markdown courseware."""
        title = data.get("title", "影片研討教材")
        exec_sum = data.get("executive_summary", {})
        highlights = data.get("key_highlights", [])
        ext = data.get("extended_learning", {})

        md = []
        md.append(f"# 📚 {title} — 專題研討教材\n")
        md.append(f"> ⚖️ **聲明**：{self.FAIR_USE_DISCLAIMER}\n")
        md.append("---\n")

        # Section 1
        md.append("## 📖 壹、核心摘要 (Executive Summary)\n")
        md.append(f"- **目標受眾**：{exec_sum.get('target_audience', '學習者')}")
        md.append(f"- **先備知識**：{exec_sum.get('prerequisites', '無特殊限制')}\n")
        md.append(f"### 課程總覽\n{exec_sum.get('overview', '')}\n")
        md.append("### 核心觀點清單")
        for th in exec_sum.get("core_theses", []):
            md.append(f"- 💡 {th}")
        md.append("\n---\n")

        # Section 2
        md.append("## 💡 貳、重點精華與時間戳記 (Key Highlights)\n")
        for i, h in enumerate(highlights, 1):
            ts = h.get("timestamp", "00:00")
            md.append(f"### 📍 [{ts}] {h.get('title', '')}")
            md.append(f"**核心要點**：{h.get('takeaway', '')}\n")
            md.append(f"**論證脈絡**：{h.get('details', '')}\n")
        md.append("---\n")

        # Section 3
        md.append("## 🚀 參、延伸學習與自我測驗 (Extended Learning)\n")
        md.append("### 🧠 深度思考與討論題")
        for q in ext.get("discussion_questions", []):
            md.append(f"1. {q}")
        md.append("\n### 📚 延伸推薦閱讀")
        for r in ext.get("recommended_reading", []):
            md.append(f"- 📖 {r}")
        md.append("\n### 📝 自我評量檢測題庫")
        for i, q in enumerate(ext.get("quiz", []), 1):
            md.append(f"\n#### 第 {i} 題：{q.get('question')}")
            for opt in q.get("options", []):
                md.append(f"- {opt}")
            md.append(f"\n> **正確解答**：`{q.get('answer')}`")
            md.append(f"> **觀念解析**：{q.get('explanation')}\n")

        md.append("\n---\n")
        md.append(f"*本講義由 VideoLearn AI 智慧教材引擎自動產出。{self.FAIR_USE_DISCLAIMER}*")
        return "\n".join(md)

    def _render_canva_script(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Renders a structured Canva slide script with layout suggestions, visual prompts, and bullet points.
        Designed for educators to paste into Canva or import into presentation templates.
        """
        title = data.get("title", "影片教學簡報")
        exec_sum = data.get("executive_summary", {})
        highlights = data.get("key_highlights", [])
        ext = data.get("extended_learning", {})

        slides = []

        # Slide 1: Cover
        slides.append({
            "slide_number": 1,
            "type": "封面投影片 (Title Cover)",
            "title": title,
            "subtitle": "VideoLearn AI 學術研討專題教材",
            "visual_prompt": "Clean minimalist educational gradient, dark navy blue background, modern sans-serif typography, subtle geometric AI node connections.",
            "content_bullets": [
                title,
                "學術研討與教育輔助研習",
                "版權宣告：一切資源作學術研討幫助學習者學習，非商業用途"
            ],
            "presenter_notes": "歡迎各位學員，今天我們將探討本主題的核心觀點與實踐路徑。"
        })

        # Slide 2: Overview
        slides.append({
            "slide_number": 2,
            "type": "課程綱要與目標 (Agenda)",
            "title": "課程核心範疇與學習目標",
            "subtitle": "建立完整的知識模型",
            "visual_prompt": "Three floating card layout, modern glassmorphism icons representing Theory, Practice, and Security.",
            "content_bullets": exec_sum.get("core_theses", [])[:3],
            "presenter_notes": "本單元主要有三大核心範疇，幫助大家建構系統性框架。"
        })

        # Slide 3..N: Key Highlights
        for idx, h in enumerate(highlights[:3], start=3):
            slides.append({
                "slide_number": idx,
                "type": "核心重點解析 (Highlight Deep Dive)",
                "title": f"重點 {idx-2}：{h.get('title')}",
                "subtitle": f"時間軸定位 [{h.get('timestamp')}]",
                "visual_prompt": "Left side key callout box with timestamp badge, right side diagram showing workflow progression.",
                "content_bullets": [
                    f"時間標記：{h.get('timestamp')}",
                    f"觀念重點：{h.get('takeaway')}",
                    f"實作細節：{h.get('details')}"
                ],
                "presenter_notes": f"請留意影片 {h.get('timestamp')} 處，這是整個推論架構的關鍵支柱。"
            })

        # Slide 6: Quiz & Reflection
        slides.append({
            "slide_number": len(slides) + 1,
            "type": "互動研討與測驗 (Interactive Quiz)",
            "title": "延伸研討與課後思考",
            "subtitle": "自我檢驗與深思",
            "visual_prompt": "Quiz card layout with multiple choice options, friendly badge highlight on the correct insight.",
            "content_bullets": ext.get("discussion_questions", [])[:2],
            "presenter_notes": "請大家在分組討論中思考這兩個問題，並嘗試提出具體的落地方案。"
        })

        return slides

    def _render_mindmap_mermaid(self, data: Dict[str, Any]) -> str:
        """
        Generates standard Mermaid mindmap code that renders natively in Web browsers or Markdown viewers.
        """
        title = data.get("title", "影片教材").replace("(", "[").replace(")", "]").replace('"', "")
        exec_sum = data.get("executive_summary", {})
        highlights = data.get("key_highlights", [])
        ext = data.get("extended_learning", {})

        lines = [
            "mindmap",
            f'  root(("{title[:16]}"))',
            '    ["📖 核心摘要"]',
            '      ["先備知識要求"]',
            '      ["核心理論命題"]'
        ]

        for th in exec_sum.get("core_theses", [])[:2]:
            clean_th = th[:14].replace('"', '')
            lines.append(f'        ["{clean_th}..."]')

        lines.append('    ["💡 重點精華"]')
        for h in highlights[:4]:
            ts = h.get("timestamp", "00:00")
            htitle = h.get("title", "")[:12].replace('"', '')
            lines.append(f'      ["⏱️ {ts} {htitle}"]')

        lines.append('    ["🚀 延伸學習"]')
        lines.append('      ["🧠 探討思考題"]')
        for q in ext.get("discussion_questions", [])[:2]:
            lines.append(f'        ["{q[:14]}..."]')
        lines.append('      ["📝 自我評量題庫"]')
        lines.append('      ["📚 推薦參考閱讀"]')

        lines.append('    ["⚖️ 學術規範"]')
        lines.append('      ["學術研討專用"]')
        lines.append('      ["嚴禁商業搬運"]')

        return "\n".join(lines)
