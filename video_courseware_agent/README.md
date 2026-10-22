# VideoLearn AI — 影片智慧教材生成與資安防護系統

> ⚖️ **學術研討與教育合理使用聲明**：  
> **「一切資源作學術研討幫助學習者學習，不提供商業用、或搬運影片用」**

---

## 🎯 系統概述 (Overview)

VideoLearn AI 是一套遵循 **Google Enterprise Agent Platform** 與 **ADK (Agent Development Kit)** 架構設計的智慧教材轉譯與研討系統。

使用者只需提供 13 大跨國影音平台的影片連結（或直接上傳影音檔案），系統將：
1. **多重資安防護過濾**：主動攔截惡意網址、SSRF 內網探測、指令注入及偽裝成影音的木馬病毒（Magic Bytes）。
2. **精確時間軸逐字稿轉譯**：生成毫秒級時間軸對齊的 `.srt` 與 `.vtt` 雙格式字幕。
3. **三層次結構化教材生成**：
   - 📖 **核心摘要 (Executive Summary)**：課程目標、先備知識與核心觀點。
   - 💡 **重點精華與時間戳記 (Key Highlights)**：章節要點對應精確時間跳轉點 `[MM:SS]`。
   - 🚀 **延伸學習與自我測驗 (Extended Learning)**：深度討論思考題、延伸文獻、自我評量測驗題庫（含詳細解析）。
4. **六大維度匯出支援**：
   - 📝 **Markdown 講義 (`.md`)**：排版精美、一鍵複製與匯出。
   - 📄 **Web 閱讀介面與列印 PDF**：針對列印排版最佳化，一鍵另存為 PDF 課程講義。
   - 📊 **PowerPoint 簡報 (`.pptx`)**：純 Python 零依賴 OpenXML 原生生成，相容微軟 PPT、Google 簡報、Keynote。
   - 🎨 **Canva 簡報腳本**：每頁投影片主題、要點、視覺設計提示詞（Visual Prompt）與講師逐字備忘錄。
   - 🧠 **互動心智圖 (Interactive Mindmap)**：Mermaid.js 即時渲染視覺化樹狀圖與語法匯出。
5. **AI 深度研討導師 (Academic Grounded Tutor)**：
   - 針對讀者提問進行蘇格拉底式引導與學術深入探討。
   - 全程基於影片時間軸依據，並內建提示詞注入（Prompt Injection）安全護欄。

---

## 🛡️ 7 重企業級資安防禦體系 (Cybersecurity Defense Layers)

針對惡意人士透過外部網址、偽裝檔案或提示詞注入等攻擊手段，系統實施 7 重縱深防禦：

| 防禦層級 | 防禦機制名稱 | 防護範疇與實踐細節 |
|---|---|---|
| **第 1 層** | **SSRF 伺服端請求偽造阻斷** | 強制解析網域名稱 DNS，阻斷存取 `127.0.0.1`、`10.x.x.x`、`172.16-31.x`、`192.168.x.x` 內部私有位址及 AWS/GCP 雲端 Metadata (`169.254.169.254`)。 |
| **第 2 層** | **Magic Bytes 二進位特徵防毒** | 嚴格檢驗檔案前 64 位元標頭（MP4 `ftyp`、WebM/MKV、MP3 `ID3`、WAV `RIFF`），主動阻斷偽裝成影音的 Windows PE (`MZ`) 木馬、Linux ELF (`\x7fELF`)、Shell 腳本與壓縮檔。 |
| **第 3 層** | **13 大跨國平台白名單** | 嚴格比對 YouTube、TikTok、Facebook、X (Twitter)、Instagram、Twitch、Bilibili、Vimeo、SoundCloud、Reddit、LinkedIn、Pinterest、Bandcamp 網域，全面杜絕釣魚網站。 |
| **第 4 層** | **指令注入 (Command Injection) 防禦** | 在調用底層轉譯進程前，徹底過濾與轉義 `;`、`|`、`&`、`` ` ``、`$`、`\n`、`\0` 等危險 Shell 跳脫字元。 |
| **第 5 層** | **提示詞注入 (Prompt Injection) 清洗** | 對學習者輸入與逐字稿進行 NLP 規則分析，過濾 `ignore previous instructions`、`system prompt leak`、`jailbreak mode` 等越獄指令。 |
| **第 6 層** | **沙盒進程與純音訊隔離** | 所有外部串流轉譯皆在受限沙箱環境中執行，且僅提取純音訊進行語音轉譯，不傳遞或執行任何容器二進位檔案。 |
| **第 7 層** | **學術倫理與合理使用合規校驗** | 所有 Web 頁面、VTT 字幕標頭與 PPTX 投影片封面皆強制內嵌學術研討免責聲明，嚴格禁止商業營利或影片搬運。 |

---

## 🚀 快速啟動 (How to Run)

在專案根目錄下直接執行：

```bash
# 1. 執行啟動腳本（預設監聽 8001 連接埠）
./run-videolearn.sh

# 2. 開啟瀏覽器訪問 Web 操作介面
http://localhost:8001
```

### 執行單元與整合測試套件
```bash
PYTHONPATH=. ./.bin/uv run python video_courseware_agent/test_suite.py
```

---

## 📁 檔案結構說明

```
video_courseware_agent/
├── agent.py                 # ADK 智慧體總協調者 (Orchestrator Pipeline)
├── security.py              # 7 重企業級資安防線 (SSRF, Magic Bytes, Whitelist, Injection)
├── media_ingest.py          # 多平台串流擷取與沙盒防毒驗證模組
├── transcriber.py           # 毫秒級時間軸 STT 與 SRT/VTT 字幕產出
├── courseware_engine.py     # 核心摘要、重點精華、延伸學習、Canva與心智圖引擎
├── pptx_generator.py        # 純 Python 零依賴 OpenXML PowerPoint (.pptx) 生成器
├── tutor.py                 # AI 深度研討導師 (Grounded Academic Tutor)
├── web_server.py            # FastAPI 非同步後端 API 伺服器
├── test_suite.py            # 完整單元與資安整合測試套件
├── static/
│   └── index.html           # 現代化響應式 Web 操作介面 (Tailwind + FontAwesome + Mermaid)
├── exports/                 # 匯出講義、投影片與字幕快取目錄
└── temp_media/              # 暫存沙盒音訊處理目錄
```
