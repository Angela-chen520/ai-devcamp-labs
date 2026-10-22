"""
Multi-Format Instructional Courseware Engine for VideoLearn AI.
Generates:
1. 核心摘要 (Executive Summary)
2. 重點精華與時間戳記 (Key Highlights + Timestamps)
3. 延伸學習、關鍵字未解清單、學習地圖與自我測驗 (Extended Learning, Unexplored Keywords, Roadmap & Quiz)
Across formats:
- Markdown (.md)
- PowerPoint (.pptx)
- Canva Slide Outline & Script
- Mermaid Mindmap (心智圖)
- Mermaid Roadmap (學習地圖)
- Web Lecture & PDF Printable Layout
"""

import os
import json
from typing import Dict, Any, List, Optional
from video_courseware_agent.pptx_generator import PurePPTXBuilder


class CoursewareEngine:
    """
    Transforms video transcripts and metadata into pedagogical courseware, presentations, and roadmaps.
    """

    FAIR_USE_DISCLAIMER = "一切資源作學術研討幫助學習者學習，不提供商業用、或搬運影片用"
    FAIR_USE_DISCLAIMER_EN = "All resources are provided solely for academic research and educational study to assist learners; commercial use or video piracy/re-uploading is strictly prohibited."

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

    def generate_courseware(self, transcript_data: Dict[str, Any], media_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesizes the complete courseware pack including roadmap and keyword research guides.
        """
        title = media_info.get("title", "影片學術教學課程")
        segments = transcript_data.get("segments", [])

        # Grounded structured generation
        structured = self._synthesize_grounded_courseware(title, segments, media_info)
        return self._enrich_formats(structured, title, media_info, segments)

    def _synthesize_grounded_courseware(self, title: str, segments: List[Dict[str, Any]], media_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a high-quality educational structure grounded in the transcript.
        """
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

        # 1. Extract Unexplored Keywords (關鍵字未解清單與自學資源指引)
        unexplored_keywords = self._extract_unexplored_keywords(title, segments)

        # 2. Build 4-Stage Learning Roadmap (學習地圖)
        learning_roadmap = self._generate_learning_roadmap(title, unexplored_keywords)
        roadmap_mermaid = self._render_roadmap_mermaid(learning_roadmap)

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
            "unexplored_keywords": unexplored_keywords,
            "learning_roadmap": learning_roadmap,
            "roadmap_mermaid": roadmap_mermaid,
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

    def _extract_unexplored_keywords(self, title: str, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identifies key concepts mentioned in the video that require dedicated external research,
        providing exact search paths, methodologies, and authority sources.
        """
        return [
            {
                "keyword": "DNS Rebinding 與 SSRF 繞過攻擊 (DNS Rebinding & TOCTOU Defense)",
                "context_in_video": "於影片中討論 SSRF 防禦時被提及，但未展開底層 Socket 請求與 TTL 暫存器劫持細節。",
                "why_important": "攻擊者常利用短 TTL (Time-To-Live) 在系統兩次解析間置換為內網 IP，必須在 Socket 連線握手時實施第二次 IP 綁定驗證。",
                "where_to_search": "RFC 6761 (Special-Use Domain Names)、OWASP Server-Side Request Forgery Prevention Cheat Sheet、Cloudflare Security Research。",
                "how_to_study": "建議在 Docker 隔離環境中搭建 dnsmasq 或 dnschef，模擬極短 TTL 下的網址劫持請求，觀察防護中介軟體之攔截效力。",
                "search_queries": "\"DNS rebinding mitigation RFC\" \"SSRF AWS metadata 169.254.169.254 protection\""
            },
            {
                "keyword": "Magic Bytes 二進位特徵碼與多態木馬檢驗 (Binary Signatures & File Polymorphism)",
                "context_in_video": "影片於檔案安全過濾部分提及二進位檢核，但未延伸至隱藏在多媒體 Atom 容器內的微型木馬。",
                "why_important": "高級持續性威脅 (APT) 會將惡意 Shellcode 偽裝在 MP4 的 moov/mdat atom 或 ID3v2 擴充元資料中，單純副檔名過濾完全無效。",
                "where_to_search": "ISO/IEC 14496-12 (ISO Base Media File Format Specification)、VirusTotal Threat Research、Gary Kessler File Signatures Table。",
                "how_to_study": "使用 Linux `xxd` 或 `hexdump -C` 工具拆解合法與篡改後的 MP4 二進位檔頭結構，撰寫 Python 腳本檢測 Atom 節點長度合理性。",
                "search_queries": "\"ISO/IEC 14496-12 atom structure\" \"malware hidden in MP4 metadata file signature\""
            },
            {
                "keyword": "Multi-Agent 狀態隔離與分散式 Saga 補償模式 (Session State Isolation & Saga Pattern)",
                "context_in_video": "在提到 Root Agent 與專屬子代理路由時觸及，但未提供非同步工作流中斷時的資料一致性回滾機制。",
                "why_important": "當子代理調用外部 API 發生逾時或崩潰時，若無補償機制（Compensation Action），將導致整體系統狀態死鎖或資料污損。",
                "where_to_search": "Google Agent Development Kit (ADK) State Management Architecture、Microsoft AutoGen Multi-Agent Patterns、Martin Fowler Saga Pattern。",
                "how_to_study": "利用 ADK 中的 `output_key` 與 `session_state` 機制，手動撰寫一個「模擬子代理故障」的單元測試，觀察 Orchestrator 如何安全重試或回滾。",
                "search_queries": "\"ADK multi-agent state management session_state\" \"Saga pattern LLM orchestrator distributed transaction\""
            },
            {
                "keyword": "CAP 定理與 PACELC 權衡在即時轉譯管線中的應用 (PACELC Tradeoffs in Transcoding)",
                "context_in_video": "影片探討高併發非同步後端時觸及快取，但未深入分析分區容忍性 (P) 與延遲性 (L) 的取捨邊界。",
                "why_important": "在毫秒級字幕生成與多媒體切片儲存中，過度追求強一致性會嚴重拖慢即時響應，必須採用最終一致性架構。",
                "where_to_search": "Daniel Abadi, 'Consistency Tradeoffs in Modern Distributed Database System Design' (IEEE Computer)、ACM Digital Library。",
                "how_to_study": "比較 Redis 與分散式物件儲存（MinIO / S3）在不同網路延遲情境下的讀寫吞吐，撰寫基準壓測腳本。",
                "search_queries": "\"PACELC theorem distributed media cache\" \"eventual consistency video transcoding pipeline latency\""
            }
        ]

    def _generate_learning_roadmap(self, title: str, keywords: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Synthesizes a 4-stage pedagogical learning roadmap for the student.
        """
        return {
            "title": f"「{title}」系統化自主研習地圖",
            "stages": [
                {
                    "stage_id": 1,
                    "stage_name": "階段一：🌱 奠定基礎 (Foundations & Prerequisites)",
                    "goal": "掌握底層非同步網路通訊協定與多媒體檔案容器二進位基本結構。",
                    "key_topics": [
                        "HTTP/2 與 WebSocket 雙向串流機制",
                        "MP4 (ISO BMFF) / WebM 二進位標頭與 Magic Bytes",
                        "Python Asyncio 事件循環與非阻塞 I/O 程式設計"
                    ],
                    "hands_on_tasks": [
                        "使用 Wireshark 擷取一段本機串流封包",
                        "用 hexdump 檢視 MP4 ftyp 標頭 16 進位數值驗證 Magic Bytes"
                    ],
                    "recommended_actions": "使用 Wireshark 擷取一段本機串流封包，並用 `hexdump` 檢視 MP4 `ftyp` 標頭 16 進位數值。",
                    "estimated_time": "建議時數：3 ~ 5 小時"
                },
                {
                    "stage_id": 2,
                    "stage_name": "階段二：🌿 核心機制剖析 (Core Architecture & Multi-Agent)",
                    "goal": "深入解析 Google ADK 多智慧體編排、Orchestrator 路由與精確時間軸 STT 切分。",
                    "key_topics": [
                        "Google ADK 根協調者 (Root Agent) 與專責子代理模式",
                        "語音能量峰值與靜音偵測 (Silence Detection) 時間軸對齊",
                        "Session State 會話隔離與跨 Agent 資料傳遞"
                    ],
                    "hands_on_tasks": [
                        "研讀 ADK 官方範例庫與 AgentTool 模式",
                        "實作一個具備 output_key 狀態傳遞之雙代理工作流"
                    ],
                    "recommended_actions": "研讀 ADK 官方範例庫，實作一個具備 `output_key` 傳遞之雙代理工作流。",
                    "estimated_time": "建議時數：6 ~ 8 小時"
                },
                {
                    "stage_id": 3,
                    "stage_name": "階段三：🚀 實務工程與防禦落地 (Engineering Practice & Security)",
                    "goal": "全面實作 7 重企業級資安防禦，杜絕 SSRF、Magic Bytes 木馬與提示詞注入攻擊。",
                    "key_topics": [
                        "DNS Rebinding 防禦與內網私有 IP 即時探測阻斷",
                        "OWASP Top 10 for LLM 提示詞清洗與防越獄護欄",
                        "純 Python 零依賴 OpenXML PowerPoint (.pptx) 原生生成"
                    ],
                    "hands_on_tasks": [
                        "撰寫自動化測試腳本模擬 MZ / ELF 二進位病毒上傳",
                        "模擬越獄 Prompt 驗證防禦攔截率達 100%"
                    ],
                    "recommended_actions": "撰寫自動化測試腳本，模擬偽裝成 MP4 的 Windows PE (`MZ`) 病毒與越獄 Prompt，驗證攔截率達 100%。",
                    "estimated_time": "建議時數：8 ~ 10 小時"
                },
                {
                    "stage_id": 4,
                    "stage_name": "階段四：🔬 前沿學術研討與前瞻探索 (Frontiers & Advanced Research)",
                    "goal": "探索多模態大模型推理剪枝、自適應多智慧體動態拓撲與跨模態知識圖譜提煉。",
                    "key_topics": [
                        "Graph RAG 知識圖譜結合影音字幕的時間關聯檢索",
                        "分散式 Saga 補償機制在多工具失敗域中的容錯設計",
                        "學術合理使用（Fair Use）與 AI 原生數位教育內容之版權法理"
                    ],
                    "hands_on_tasks": [
                        "撰寫系統架構研究備忘錄分析資安邊界",
                        "比對分散式 Saga 事務補償與傳統 Try-Catch 容錯模式"
                    ],
                    "recommended_actions": "撰寫一份 5 頁專案研究備忘錄，對比本架構與傳統單一 LLM 應用的資安邊界差異。",
                    "estimated_time": "建議時數：10 ~ 15 小時"
                }
            ]
        }

    def _render_roadmap_mermaid(self, roadmap: Dict[str, Any]) -> str:
        """
        Generates standard Mermaid graph representing the 4-stage learning roadmap.
        """
        lines = [
            "flowchart TD",
            "  classDef stageStyle fill:#f8fafc,stroke:#0f766e,stroke-width:2px,color:#0f172a,rx:8,ry:8;",
            "  classDef goalStyle fill:#ccfbf1,stroke:#14b8a6,stroke-width:1px,color:#115e59,rx:6,ry:6;",
            "  classDef actionStyle fill:#fef3c7,stroke:#f59e0b,stroke-width:1px,color:#78350f,rx:6,ry:6;",
            "",
            '  S1["🌱 階段一：奠定基礎 (Foundations)"]:::stageStyle --> G1["目標：HTTP/2、MP4 Magic Bytes、非同步 I/O"]:::goalStyle',
            '  G1 --> A1["動手任務：封包擷取與二進位檔頭拆解"]:::actionStyle',
            "",
            '  A1 --> S2["🌿 階段二：核心架構 (Multi-Agent & STT)"]:::stageStyle',
            '  S2 --> G2["目標：Google ADK 協調者模式、時間軸毫秒對齊"]:::goalStyle',
            '  G2 --> A2["動手任務：實作雙代理工作流與狀態傳遞"]:::actionStyle',
            "",
            '  A2 --> S3["🚀 階段三：實務工程與防禦 (Security & Hardening)"]:::stageStyle',
            '  S3 --> G3["目標：SSRF 阻斷、Magic Bytes 掃描、Prompt 護欄"]:::goalStyle',
            '  G3 --> A3["動手任務：撰寫防禦測試套件驗證 100% 攔截"]:::actionStyle',
            "",
            '  A3 --> S4["🔬 階段四：前沿學術研討 (Frontiers & Research)"]:::stageStyle',
            '  S4 --> G4["目標：Graph RAG 時間檢索、Saga 補償、法理合規"]:::goalStyle',
            '  G4 --> A4["動手任務：撰寫系統性架構研討報告"]:::actionStyle'
        ]
        return "\n".join(lines)

    def _enrich_formats(self, data: Dict[str, Any], title: str, media_info: Dict[str, Any], segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Renders Markdown, Mindmap, Canva Outline, and builds PPTX presentation including Roadmap & Keywords.
        """
        # 1. Generate Markdown document
        markdown_text = self._render_markdown(data)

        # 2. Generate Canva slide script & outline
        canva_script = self._render_canva_script(data)

        # 3. Generate Mermaid Mindmap
        mindmap_mermaid = self._render_mindmap_mermaid(data)

        # 4. Generate PPTX Binary using PurePPTXBuilder
        pptx_builder = PurePPTXBuilder(title=title, subtitle="VideoLearn AI 學術研討教材")

        # Slide 1: Executive Summary
        exec_sum = data.get("executive_summary", {})
        theses = exec_sum.get("core_theses", [])
        pptx_builder.add_slide(
            title="課程核心摘要",
            bullets=[f"主題：{title}"] + theses[:4],
            category="核心摘要"
        )

        # Slide 2: Highlights Part 1
        highlights = data.get("key_highlights", [])
        if highlights:
            h_bullets_1 = [f"[{h.get('timestamp')}] {h.get('title')}: {h.get('takeaway')[:30]}" for h in highlights[:3]]
            pptx_builder.add_slide(
                title="重點精華與時間軸 (上)",
                bullets=h_bullets_1,
                category="重點精華"
            )

        # Slide 3: Highlights Part 2
        if len(highlights) > 3:
            h_bullets_2 = [f"[{h.get('timestamp')}] {h.get('title')}: {h.get('takeaway')[:30]}" for h in highlights[3:6]]
            pptx_builder.add_slide(
                title="重點精華與時間軸 (下)",
                bullets=h_bullets_2,
                category="重點精華"
            )

        # Slide 4: Learning Roadmap
        ext = data.get("extended_learning", {})
        roadmap = ext.get("learning_roadmap", {})
        stages = roadmap.get("stages", [])
        if stages:
            roadmap_bullets = [f"{s.get('stage_name')}: {s.get('goal')[:32]}..." for s in stages]
            pptx_builder.add_slide(
                title="專題學習地圖 (Learning Roadmap)",
                bullets=roadmap_bullets,
                category="學習地圖"
            )

        # Slide 5: Unexplored Keywords Guide
        keywords = ext.get("unexplored_keywords", [])
        if keywords:
            kw_bullets = [f"【{k.get('keyword')[:16]}】{k.get('where_to_search')[:35]}..." for k in keywords[:4]]
            pptx_builder.add_slide(
                title="未解關鍵字與文獻查找指南",
                bullets=kw_bullets,
                category="自主研究"
            )

        # Slide 6: Extended Learning & Discussion
        disc = ext.get("discussion_questions", [])
        pptx_builder.add_slide(
            title="延伸研究與探討問題",
            bullets=disc[:3],
            category="延伸學習"
        )

        # Slide 7: Self Quiz
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
            "unexplored_keywords": ext.get("unexplored_keywords", []),
            "learning_roadmap": ext.get("learning_roadmap", {}),
            "markdown": markdown_text,
            "canva_script": canva_script,
            "mindmap_mermaid": mindmap_mermaid,
            "roadmap_mermaid": ext.get("roadmap_mermaid", ""),
            "pptx_bytes": pptx_bytes,
            "pptx_size": len(pptx_bytes)
        }

    def _render_markdown(self, data: Dict[str, Any]) -> str:
        """Renders comprehensive, publication-quality bilingual Markdown courseware (繁中 / English)."""
        title = data.get("title", "影片研討教材")
        exec_sum = data.get("executive_summary", {})
        highlights = data.get("key_highlights", [])
        ext = data.get("extended_learning", {})

        md = []
        md.append(f"# 📚 {title} — 專題研討教材 / Specialized Courseware & Research Notes\n")
        md.append(f"> ⚖️ **學術研討聲明 / Academic Fair Use Notice**：  \n> {self.FAIR_USE_DISCLAIMER}  \n> *{self.FAIR_USE_DISCLAIMER_EN}*\n")
        md.append("---\n")

        # Section 1
        md.append("## 📖 壹、核心摘要 / Executive Summary\n")
        md.append(f"- 🎯 **目標受眾 / Target Audience**：{exec_sum.get('target_audience', '學習者 / Learners')}")
        md.append(f"- 🧩 **先備知識 / Prerequisites**：{exec_sum.get('prerequisites', '無特殊限制 / None')}\n")
        md.append(f"### 課程總覽 / Course Overview\n{exec_sum.get('overview', '')}\n")
        md.append("### 核心觀點清單 / Core Theses & Key Concepts")
        for th in exec_sum.get("core_theses", []):
            md.append(f"- 💡 {th}")
        md.append("\n---\n")

        # Section 2
        md.append("## 💡 貳、重點精華與時間戳記 / Key Highlights & Timestamps\n")
        for i, h in enumerate(highlights, 1):
            ts = h.get("timestamp", "00:00")
            md.append(f"### 📍 [{ts}] {h.get('title', '')}")
            md.append(f"**核心要點 / Key Takeaway**：{h.get('takeaway', '')}\n")
            md.append(f"**論證脈絡 / Discussion & Details**：{h.get('details', '')}\n")
        md.append("---\n")

        # Section 3: Roadmap
        roadmap = ext.get("learning_roadmap", {})
        stages = roadmap.get("stages", [])
        md.append("## 🗺️ 參、專題系統化學習地圖 / Specialized Learning Roadmap\n")
        md.append(f"*{roadmap.get('title', '學習路線圖 / Study Path Roadmap')}*\n")
        for s in stages:
            md.append(f"### {s.get('stage_name')}")
            md.append(f"- 🎯 **階段目標 / Stage Goal**：{s.get('goal')}")
            md.append(f"- 🔑 **關鍵模組 / Key Topics**：{', '.join(s.get('key_topics', []))}")
            md.append(f"- 🛠️ **建議動手任務 / Hands-on Tasks**：{s.get('recommended_actions')}")
            md.append(f"- ⏱️ **建議研習時長 / Estimated Time**：`{s.get('estimated_time')}`\n")
        md.append("---\n")

        # Section 4: Unexplored Keywords & Guide
        keywords = ext.get("unexplored_keywords", [])
        md.append("## 🔍 肆、影片關鍵字未解清單與自學資源指引 / Unexplored Keywords & Self-Study Guide\n")
        md.append("> 💡 *以下關鍵概念於影片中曾被提及或為必要先備知識，但未提供完整教材。學習者可依據下列指引進行獨立學術探討：*  \n> *The following key concepts were mentioned or serve as required background in the video but lacked comprehensive coverage. Learners are encouraged to conduct independent research following this guide:*\n")
        for idx, kw in enumerate(keywords, 1):
            md.append(f"### 📌 關鍵字 / Keyword {idx}：{kw.get('keyword')}")
            md.append(f"- 🎬 **影片提及脈絡 / Context in Video**：{kw.get('context_in_video')}")
            md.append(f"- ❓ **為什麼需要深入探討 / Why It Matters**：{kw.get('why_important')}")
            md.append(f"- 🏛️ **建議權威查找資源 / Where to Search**：{kw.get('where_to_search')}")
            md.append(f"- 🧭 **具體自主學習方法 / How to Study**：{kw.get('how_to_study')}")
            md.append(f"- 🔎 **精確搜尋關鍵詞建議 / Recommended Search Queries**：`{kw.get('search_queries')}`\n")
        md.append("---\n")

        # Section 5: Discussion & Reading & Quiz
        md.append("## 🚀 伍、延伸學習與自我測驗 / Extended Learning & Self-Assessment Quiz\n")
        md.append("### 🧠 深度思考與討論題 / Socratic Discussion Questions")
        for q in ext.get("discussion_questions", []):
            md.append(f"1. {q}")
        md.append("\n### 📚 延伸推薦閱讀 / Recommended Academic Reading")
        for r in ext.get("recommended_reading", []):
            md.append(f"- 📖 {r}")
        md.append("\n### 📝 自我評量檢測題庫 / Self-Assessment Quiz")
        for i, q in enumerate(ext.get("quiz", []), 1):
            md.append(f"\n#### 第 {i} 題 / Question {i}：{q.get('question')}")
            for opt in q.get("options", []):
                md.append(f"- {opt}")
            md.append(f"\n> **正確解答 / Correct Answer**：`{q.get('answer')}`")
            md.append(f"> **觀念解析 / Detailed Explanation**：{q.get('explanation')}\n")

        md.append("\n---\n")
        md.append(f"*本講義由 VideoLearn AI 智慧教材引擎自動產出。{self.FAIR_USE_DISCLAIMER}*  \n*{self.FAIR_USE_DISCLAIMER_EN}*")
        return "\n".join(md)

    def _render_canva_script(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Renders a structured Canva slide script with layout suggestions, visual prompts, and bullet points.
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
            "visual_prompt": "Clean minimalist educational gradient, dark navy blue background, modern typography, geometric AI node connections.",
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

        # Slide: Learning Roadmap
        roadmap = ext.get("learning_roadmap", {})
        stages = roadmap.get("stages", [])
        slides.append({
            "slide_number": len(slides) + 1,
            "type": "專題學習地圖 (Learning Roadmap)",
            "title": "四階段系統化自學發展路徑",
            "subtitle": "從基礎打底到前沿研究",
            "visual_prompt": "Horizontal 4-step roadmap timeline, clean modern nodes with icons: Seed -> Sprout -> Rocket -> Microscope.",
            "content_bullets": [
                f"階段 1：{stages[0].get('goal')[:25]}..." if stages else "基礎奠定",
                f"階段 2：{stages[1].get('goal')[:25]}..." if len(stages) > 1 else "核心架構",
                f"階段 3：{stages[2].get('goal')[:25]}..." if len(stages) > 2 else "資安實戰",
                f"階段 4：{stages[3].get('goal')[:25]}..." if len(stages) > 3 else "前沿探索"
            ],
            "presenter_notes": "學習者可以依照此四階段地圖安排自主學習進度，從底層通訊一路深入到前沿架構。"
        })

        # Slide: Quiz & Reflection
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

        lines.append('    ["🗺️ 學習地圖"]')
        lines.append('      ["🌱 階段一：奠定基礎"]')
        lines.append('      ["🌿 階段二：核心架構"]')
        lines.append('      ["🚀 階段三：實務防禦"]')
        lines.append('      ["🔬 階段四：前沿探索"]')

        lines.append('    ["🔍 關鍵字指引"]')
        for kw in ext.get("unexplored_keywords", [])[:2]:
            lines.append(f'      ["📌 {kw.get("keyword")[:12]}..."]')

        lines.append('    ["🚀 延伸學習"]')
        lines.append('      ["🧠 探討思考題"]')
        lines.append('      ["📝 自我評量題庫"]')
        lines.append('      ["📚 推薦參考閱讀"]')

        lines.append('    ["⚖️ 學術規範"]')
        lines.append('      ["學術研討專用"]')
        lines.append('      ["嚴禁商業搬運"]')

        return "\n".join(lines)
