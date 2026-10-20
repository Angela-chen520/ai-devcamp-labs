# ✈️ 全球旅客出入境行李與報關智慧諮詢系統 — 雙語操作指南
# Global Traveler Smart Customs & Baggage Advisor — Bilingual User Guide

> **版本 / Version**：v2.0.0 (Aviation SPA Multi-Page Edition)  
> **核心技術 / Core Tech**：Google ADK (Agent Development Kit), Gemini 2.5 Flash, Zero-PII Guardrails, Deterministic Rule Engines, FastAPI  
> **專案定位 / Mission**：專為跨國旅客打造的智慧行李合規核驗、文化禁忌避雷針、在地天候穿搭建議與海關報關教學全方位助理。 / A comprehensive, privacy-first AI advisor designed to alleviate traveler baggage anxiety through intelligent customs compliance, cultural etiquette warnings, weather forecasting, and clear declaration guidance.

---

## 🌐 語言切換 / Quick Language Jump

* 🇹🇼 **[前往 繁體中文版本 (Traditional Chinese Version)](#-繁體中文版-traditional-chinese)**
* 🇬🇧 **[Jump to English Version](#-english-version)**

---

# 🇹🇼 繁體中文版 (Traditional Chinese)

## 📑 目錄

1. [系統核心價值與隱私承諾](#1-系統核心價值與隱私承諾)
2. [系統架構與代理人協同運作](#2-系統架構與代理人協同運作)
3. [快速啟動與環境準備](#3-快速啟動與環境準備)
4. [網頁入口介面五大功能分頁圖解指引](#4-網頁入口介面五大功能分頁圖解指引)
   - [4.1 頂部航空導航列與偏好設定](#41-頂部航空導航列與偏好設定)
   - [4.2 分頁一：首頁與新手操作指引 (Home & Guide)](#42-分頁一首頁與新手操作指引)
   - [4.3 分頁二：行李申報智慧核驗 (Smart Baggage Inspection)](#43-分頁二行李申報智慧核驗)
   - [4.4 分頁三：入境文化禮儀與法規禁忌 (Culture & Penalties)](#44-分頁三入境文化禮儀與法規禁忌)
   - [4.5 分頁四：機場海關報關流程教學 (Customs Clearance Guide)](#45-分頁四機場海關報關流程教學)
   - [4.6 分頁五：18 國免稅限額速查表 (Master Statutory Limits)](#46-分頁五18-國免稅限額速查表)
5. [三級動態語氣與合規評級標準](#5-三級動態語氣與合規評級標準)
6. [API 金鑰安全規範與隱私防護](#6-api-金鑰安全規範與隱私防護)
7. [展示與部署方案 (Demo Deployment Options)](#7-展示與部署方案)
8. [常見問題與障礙排除 (FAQ)](#8-常見問題與障礙排除)

---

### 1. 系統核心價值與隱私承諾

出國旅遊或商務出差時，許多旅客常因各國複雜多變的海關法規、免稅額上限、藥品管制與動植物檢疫禁令感到焦慮。更嚴重的是，每年都有大量旅客因不慎攜帶肉製品（如非洲豬瘟禁令）、電子菸或超額現金，而在抵達目的地機場時面臨**數十萬元罰鍰、沒收物品、拘留甚至驅逐出境**。

本系統為解決上述痛點而打造，並秉持以下最高準則：

#### 🔒 零個資收集 (Zero-PII Privacy First)
* **無需護照、身分證與真實姓名**：旅客查詢行李規範時，系統絕不要求、亦絕不留存任何個人身分證件。
* **本地正則雙層清洗 (Stage 1 Regex Sanitizer)**：即時在瀏覽器前端與後端攔截並替換各國護照號碼、臺灣身分證號、電話、信用卡號與電子郵件為 `[REDACTED_*]` 標記，完全隔絕機敏資料傳遞給大型語言模型。
* **安心隱私標籤**：若使用者不慎輸入個資，系統會主動顯示隱私聲明，保障旅客資料安全。

#### ⚖️ 三級動態語氣分級 (Dynamic 3-Tier Tone)
依據物品法規危險程度，自動調校回應風格：
* 🟢 **綠色（完全合規）**：語氣溫和親切、安心提醒。
* 🟡 **黃色（超額應稅/限制物品）**：委婉建議自用限額、提醒主動走紅線申報以避免受罰。
* 🔴 **紅色（絕對禁止攜帶之違禁品）**：嚴肅警告法律後果、列出重罰金額、指導立即棄置於海關農檢棄置箱。

#### 🗺️ 18 國全球法規、文化禁忌與在地天候整合
內建臺灣、日本、韓國、加拿大、義大利、荷蘭、新加坡、泰國、越南、菲律賓、馬來西亞、法國、澳洲、西班牙、希臘、美國、英國、香港等 18 國完整法規資料庫、旅客人身管理條例與旅遊穿搭氣象。

---

### 2. 系統架構與代理人協同運作

本系統嚴格遵循 **Google ADK (Agent Development Kit)** 架構，採用 Orchestrator-Subagent 多代理人模式，並落實 Built-in Tool 獨立隔離原則：

```text
                                  +-----------------------------+
                                  |     旅客網頁入口 (FastAPI)   |
                                  |   http://localhost:8000     |
                                  +--------------+--------------+
                                                 |
                                     [Zero-PII 守門過濾器]
                                   (在地正則即時去識別化遮蔽)
                                                 |
                                                 v
                                  +-----------------------------+
                                  |   海關核心協調代理人 (Root)   |
                                  |      (customs_advisor)      |
                                  +--------------+--------------+
                                                 |
                  +------------------------------+------------------------------+
                  |                              |                              |
                  v                              v                              v
       +--------------------+         +--------------------+         +--------------------+
       |   動植物檢疫代理人   |         |   關稅與免稅額代理人 |         |    藥品與管制代理人  |
       |  (quarantine_agent)|         |  (duty_tax_agent)  |         |   (medicine_agent) |
       +--------------------+         +--------------------+         +--------------------+
       | 肉製品/蔬果/非洲豬瘟 |         | 菸酒/現金洗錢防制/ |         | 12/36條款/成藥劑量 |
       | 生態危害/重罰基準   |         | 紅綠線走道/關稅試算 |         | 處方箋/管制品警告  |
       +--------------------+         +--------------------+         +--------------------+
                  |                              |                              |
                  +------------------------------+------------------------------+
                                                 |
                                                 v
                                  +-----------------------------+
                                  |    即時法規檢索獨立代理人    |
                                  |   (search_research_agent)   |
                                  |   [Built-in Google Search]  |
                                  +-----------------------------+
```

---

### 3. 快速啟動與環境準備

#### 3.1 系統需求
* **作業系統**：Linux / macOS / Windows (WSL2)
* **Python 版本**：Python 3.10 或更新版本
* **套件管理工具**：推薦使用高效的 `uv`（亦支援一般 `pip`）

#### 3.2 設定環境變數（金鑰安全設置）
本專案已提供環境變數範本 `capstone_customs_agent/.env.example`。請依據您的模式建立 `.env` 檔案：

```bash
# 複製設定範本為本機專屬 .env 檔（.env 已被 .gitignore 忽略，不會被上傳）
cp capstone_customs_agent/.env.example .env
```

在 `.env` 中填入金鑰（二選一）：

* **選項 A：Google AI Studio 免費 API Key（最推薦、最快）**
  ```env
  GEMINI_API_KEY=AIzaSy...您的免費APIKey...
  GOOGLE_GENAI_USE_VERTEXAI=False
  ```
  *(可於 [Google AI Studio](https://aistudio.google.com/) 免費獲取)*

* **選項 B：Google Cloud Vertex AI 企業模式**
  ```env
  GOOGLE_GENAI_USE_VERTEXAI=True
  GOOGLE_CLOUD_PROJECT=your-gcp-project-id
  GOOGLE_CLOUD_LOCATION=us-central1
  ```

#### 3.3 一鍵啟動網頁入口 (Web Portal)

執行專案根目錄的啟動腳本：

```bash
./run_web.sh
```

終端機輸出：
```text
✈️  啟動【全球旅客出入境行李與報關智慧諮詢系統】網頁伺服器...
🔒 Zero-PII 隱私安全守護已啟動 (不採集任何護照號碼與身分證字號)
📡 模型服務連線至：Google AI Studio (GEMINI_API_KEY)
==================================================================
🌐 請在瀏覽器中開啟以下網址進行體驗：
   👉 http://localhost:8000
==================================================================
```

開啟瀏覽器造訪 **`http://localhost:8000`** 即可開始操作！

#### 3.4 終端機互動 CLI 諮詢模式（可選）
若想在純文字終端機中體驗：
```bash
./run_advisor.sh
```

#### 3.5 執行全套單元驗證測試
```bash
uv run pytest capstone_customs_agent/tests/test_customs.py -v
```
*(14 項單元測試全數自動通過，覆蓋 18 國法規、氣象換算、關稅試算與 Zero-PII 隱私過濾)*

---

### 4. 網頁入口介面五大功能分頁圖解指引

系統採用現代化**海關航空專用介面 (Aviation Single Page Application)**，透過頂部寬敞的雙層索引列，可隨時在五大專屬功能頁面間切換。

#### 4.1 頂部航空導航列與偏好設定
頂部導航列採用航太午夜藍與金色點綴，劃分為上下雙層：
1. **第一層（品牌與全域控制列）**：
   * **航太標誌與動態航班代碼**：顯示當前選定的航線代碼（例如：`TPE ✈️ NRT`）。
   * **主題光暗切換器**：
     * ☀️ **日間模式 (Light)**：適合明亮戶外與室內閱覽。
     * 🌙 **夜間模式 (Dark)**：深色護眼午夜藍調。
     * 💻 **隨系統同步 (System)**：自動隨旅客設備/作業系統環境光暗智慧調配。
   * **五大多語系切換器**：繁體中文 (`zh-TW`)、英式英語 (`en-GB`)、美式英語 (`en-US`)、日本語 (`ja-JP`)、한국어 (`ko-KR`)。
2. **第二層（五大功能索引標籤）**：
   * 🛫 **首頁使用說明**
   * 🧳 **行李申報核驗**
   * 🏛️ **入境文化禮儀**
   * 📋 **海關報關教學**
   * 📊 **18 國限額速查**

#### 4.2 分頁一：首頁與新手操作指引
* **頁面定位**：初次抵達旅客的操作導引與系統安全認證。
* **新手操作四步驟圖解**：
  1. **選擇出發與目的國**：設定航線並指定旅遊日期。
  2. **勾選或輸入行李物品**：點選常見違禁或應稅物品，或以自然語言輸入欲攜帶品項。
  3. **即時獲取法規與穿搭報告**：取得三級風險標籤、天候預報、關稅試算與雙語溝通小卡。
  4. **預覽文化禁忌與報關動線**：切換至其他分頁了解目的地特殊罰則與通關走道。
* **快速跳轉傳送門按鈕**：可一鍵直達「行李智慧核驗」或「機場報關流程教學」。

#### 4.3 分頁二：行李申報智慧核驗
* **步驟 1：航線與日期選擇**：
  * 支援 18 個主要出入境國家/地區。選單變更時，頂部航線指示牌動態更新。
  * 選定旅遊日期後，系統自動發送請求查詢目的地氣象預報，顯示氣溫、降雨提醒以及具體行李穿搭建議。
* **步驟 2：物品清單輸入**：
  * 熱門物品快速勾選標籤（威士忌、處方藥、加熱菸、肉鬆蛋黃酥、日幣現鈔等）。
  * 自由文字輸入框（具備 Zero-PII 即時去識別化）。
* **步驟 3：智慧核驗等待計時器**：
  * 點擊「即刻開始智慧行李核驗」，畫面浮現動態雷達掃描與「預估剩餘時間：約 4~6 秒」計時器。
* **步驟 4：審查報告呈現**：
  * **通關風險評級戳印**：🟢 符合自用規範 / 🟡 超額需申報 / 🔴 嚴正警告違禁品。
  * **AI 多代理人法規深入分析**。
  * **關稅與稅費試算卡**：自動計算免稅額、超額數量與應納稅費。
  * **即席雙語海關溝通小卡**：生成目的國母語對照卡，手機一鍵出示給外國海關。

#### 4.4 分頁三：入境文化禮儀與法規禁忌
* ⚖️ **重大管理法規與刑責警示（避免罰款與拘禁）**：
  * **新加坡**：嚴禁口香糖（最高罰款 10,000 新幣）；地鐵飲食與亂丟垃圾重罰。
  * **日本**：嚴格管制未登記無人機；未經檢疫攜帶肉品處 3 年以下徒刑或 300 萬日圓罰金。
  * **泰國**：嚴禁毀損泰皇肖像或泰銖紙幣；電子菸全面違法；涉毒重罪。
  * **義大利 / 法國**：大眾運輸務必打票；購買仿冒名牌精品處重罰。
  * **澳洲**：未申報動植物零容忍，當場開罰 6,260 澳幣並遣返。
* 🤝 **當地文化風俗與日常禮儀**：
  * 各國小費習慣（美加 15~20%、日韓無小費）。
  * 寺廟/教堂參拜著裝規範。
  * 機場管制區禁拍照與肖像權法令。

#### 4.5 分頁四：機場海關報關流程教學
* 🌟 **海關黃金第一準則：主動申報絕不罰！**
  * 海關處罰的是「隱匿匿報」企圖走綠線者。只要在通關前主動向海關出示物品並填單申報，即便超額，最壞情況僅需補繳稅款，絕不會面臨沒收罰款或刑事裁罰！
* 🚶 **通關四階段流程**：
  1. 行前檢視與單據備妥 ➔ 2. 機上填寫申報單 ➔ 3. 走紅線（應申報）或綠線（免申報）通道 ➔ 4. 查驗與稅費繳納。

#### 4.6 分頁五：18 國免稅限額速查表
彙整全球 18 國最新法定限額：
* 酒類公升數與瓶數限制
* 菸品支數與加熱菸禁令
* 現金與外幣洗錢防制申報門檻
* 藥品與處方箋自用規範
* 個人海外購物免稅額總值

---

### 5. 三級動態語氣與合規評級標準

| 評級 | 代表燈號 | 適用情境 | 系統語氣範例 | 處置建議 |
| :--- | :---: | :--- | :--- | :--- |
| **Level 1 合規自用** | 🟢 綠燈 | 在免稅額與管制數量內之常規自用物品（如衣物、常備維他命） | 「請放心！您攜帶的物品完全符合該國免稅自用規範，祝您旅途愉快！」 | 走綠線免申報通道通關 |
| **Level 2 超額應稅** | 🟡 黃燈 | 攜帶合法但數量/金額超出免稅限額之自用物品（如 4 瓶威士忌、超額現金） | 「提醒您，此數量已超出目的地免稅限額。建議您主動填寫申報單並走紅線檯，主動申報僅需補繳稅款，安心又合法。」 | 備妥購買發票，入境走紅線申報補稅 |
| **Level 3 違禁管制** | 🔴 紅燈 | 各國嚴禁輸入之動植物生鮮、肉品（非洲豬瘟）、電子菸、毒品、仿冒品 | 「⚠️ 嚴肅警告！該物品為目的國嚴格禁止輸入之違禁品。攜帶入境將面臨高額罰款甚至刑責，請務必於出境前移出行李或於入境前丟棄至棄置箱！」 | 絕不可攜帶；若誤帶須於入境查驗前丟入檢疫棄置箱 |

---

### 6. API 金鑰安全規範與隱私防護

* **`.gitignore` 自動屏障**：已忽略所有 `*.env` 檔案，真實金鑰絕對不會進入 Git。
* **範本安全檔 (`.env.example`)**：版本庫僅提供佔位符結構。
* **Zero-PII 正則過濾**：在呼叫 LLM 前強制遮蔽護照號碼與身分證字號。

---

### 7. 展示與部署方案 (Demo Deployment Options)

* **方案 A：本機快速展示模式 (Local Interactive Demo)**：clone 專案後設定 `.env` 中的 `GEMINI_API_KEY`，執行 `./run_web.sh` 即可在 `http://localhost:8000` 完整體驗。
* **方案 B：Google Cloud Run 無伺服器雲端託管**：使用 `gcloud run deploy` 部署，金鑰保存在雲端環境變數中，對外公開 HTTPS 網址。
* **方案 C：Hugging Face Spaces / Render 免費雲端部署**：連結 GitHub 倉庫並在後台設定 Secret，提供免伺服器維護的展示連結。
* **方案 D：離線作品集展示**：在 README 中提供展示 GIF 與經典測試案例截圖。

---

### 8. 常見問題與障礙排除 (FAQ)

* **Q1：連接埠 8000 被佔用？**  
  執行 `PORT=8080 ./run_web.sh` 切換連接埠。
* **Q2：國外機場不小心攜帶超額物品怎麼辦？**  
  千萬不要走綠線！立即走向紅線櫃檯向海關主動告知「I would like to declare these items」，主動申報完全合法且不罰！
* **Q3：輸入真實姓名或證件號碼會外洩嗎？**  
  本系統建置 Zero-PII 前後端雙層防護，所有證件號碼均會在第一時間被替換為遮蔽標記，絕不儲存或傳送。

---
---

# 🇬🇧 English Version

## 📑 Table of Contents

1. [Core Mission & Zero-PII Privacy Guarantee](#1-core-mission--zero-pii-privacy-guarantee)
2. [Multi-Agent Architecture & Specialist Agents](#2-multi-agent-architecture--specialist-agents)
3. [Quick Start & Environment Setup](#3-quick-start--environment-setup)
4. [Aviation Web Portal Walkthrough (5 Core Views)](#4-aviation-web-portal-walkthrough-5-core-views)
   - [4.1 Navigation Bar & Personalization](#41-navigation-bar--personalization)
   - [4.2 Tab 1: Home & Onboarding Guide](#42-tab-1-home--onboarding-guide)
   - [4.3 Tab 2: Smart Baggage Inspection](#43-tab-2-smart-baggage-inspection)
   - [4.4 Tab 3: Destination Culture & Penalties](#44-tab-3-destination-culture--penalties)
   - [4.5 Tab 4: Customs Clearance Flow Guide](#45-tab-4-customs-clearance-flow-guide)
   - [4.6 Tab 5: Master Statutory Limits (18 Countries)](#46-tab-5-master-statutory-limits-18-countries)
5. [Dynamic 3-Tier Tone Calibration](#5-dynamic-3-tier-tone-calibration)
6. [API Key Security & Privacy Safeguards](#6-api-key-security--privacy-safeguards)
7. [Demo Deployment Options](#7-demo-deployment-options)
8. [Frequently Asked Questions (FAQ)](#8-frequently-asked-questions-faq)

---

### 1. Core Mission & Zero-PII Privacy Guarantee

International travelers frequently experience anxiety over complex and constantly shifting customs tariffs, biosecurity quarantines, medication limits, and import restrictions. Unintentional non-compliance—such as bringing cured pork snacks into African Swine Fever zones, carrying unapproved vapes, or exceeding undeclared cash limits—can result in **severe penalties, confiscation, detention, or deportation**.

This system solves these pain points through three core architectural pillars:

#### 🔒 Zero-PII Privacy-First Commitment
* **No Passport or ID Required**: Travelers never need to provide passport numbers, national IDs, or sensitive personal information to query baggage regulations.
* **Two-Stage Deterministic Regex Scrubbing**: The system intercepts and replaces passport numbers, national identity numbers, phone numbers, emails, and credit cards with `[REDACTED_*]` tags locally before any LLM API call.
* **Privacy Reassurance Banner**: Automatically attached when scrubbed tokens are detected to reassure travelers of zero data retention.

#### ⚖️ Dynamic 3-Tier Tone Calibration
The system dynamically calibrates its persona and communication tone based on legal risk:
* 🟢 **Level 1 Green (Compliant / Safe)**: Reassuring, warm, and helpful.
* 🟡 **Level 2 Yellow (Exceeding Allowance / Duty Required)**: Polite suggestions, clarifying duty-free limits and encouraging voluntary Red Channel declaration.
* 🔴 **Level 3 Red (Prohibited / Illegal Contraband)**: Stern legal warnings, highlighting exact financial penalties and directing immediate disposal in quarantine amnesty bins.

#### 🗺️ 18 Major Global Destinations Supported
Includes full statutory limit databases, traveler conduct laws, and packing weather for Taiwan, Japan, South Korea, Canada, Italy, Netherlands, Singapore, Thailand, Vietnam, Philippines, Malaysia, France, Australia, Spain, Greece, USA, UK, and Hong Kong.

---

### 2. Multi-Agent Architecture & Specialist Agents

Built strictly following the **Google ADK (Agent Development Kit)** multi-agent orchestration design, separating specialist responsibilities and isolating built-in search tools:

```text
                                  +-----------------------------+
                                  |    Traveler Web Portal UI   |
                                  |    http://localhost:8000    |
                                  +--------------+--------------+
                                                 |
                                     [Zero-PII Guardrail Filter]
                                   (Local Deterministic Sanitizer)
                                                 |
                                                 v
                                  +-----------------------------+
                                  |   Root Orchestrator Agent   |
                                  |      (customs_advisor)      |
                                  +--------------+--------------+
                                                 |
                  +------------------------------+------------------------------+
                  |                              |                              |
                  v                              v                              v
       +--------------------+         +--------------------+         +--------------------+
       |  Quarantine Agent  |         | Duty & Tax Agent   |         |   Medicine Agent   |
       | (quarantine_rules) |         |  (duty_allowance)  |         | (medicine_limits)  |
       +--------------------+         +--------------------+         +--------------------+
       | Meat, ASF, Plants, |         | Alcohol, Tobacco,  |         | OTC 12/36 rule,    |
       | Seeds, Biosecurity |         | Red/Green Channel, |         | Prescriptions,     |
       | & High Penalties   |         | Duty Calculation   |         | Controlled Drugs   |
       +--------------------+         +--------------------+         +--------------------+
                  |                              |                              |
                  +------------------------------+------------------------------+
                                                 |
                                                 v
                                  +-----------------------------+
                                  |    Search Research Agent    |
                                  |   (search_research_agent)   |
                                  |   [Built-in Google Search]  |
                                  +-----------------------------+
```

---

### 3. Quick Start & Environment Setup

#### 3.1 Prerequisites
* **Operating System**: Linux / macOS / Windows (WSL2)
* **Python**: Python 3.10+
* **Package Manager**: `uv` (recommended) or standard `pip`

#### 3.2 Environment Variables Configuration
A template configuration file is provided at `capstone_customs_agent/.env.example`:

```bash
# Copy template to root .env (this file is git-ignored and never committed)
cp capstone_customs_agent/.env.example .env
```

Configure credentials in `.env` (choose either Mode A or Mode B):

* **Mode A: Google AI Studio Free API Key (Recommended)**
  ```env
  GEMINI_API_KEY=AIzaSy...your_gemini_api_key_here...
  GOOGLE_GENAI_USE_VERTEXAI=False
  ```
  *(Obtain a free key at [Google AI Studio](https://aistudio.google.com/))*

* **Mode B: Google Cloud Vertex AI (Enterprise Mode)**
  ```env
  GOOGLE_GENAI_USE_VERTEXAI=True
  GOOGLE_CLOUD_PROJECT=your-gcp-project-id
  GOOGLE_CLOUD_LOCATION=us-central1
  ```

#### 3.3 Launch Web Portal (One-Click)

Run the root startup script:

```bash
./run_web.sh
```

Terminal Output:
```text
✈️  Starting [Global Traveler Smart Customs & Baggage Advisor] Web Server...
🔒 Zero-PII Privacy Guardrail Active (No passport or national ID collection)
📡 Model Backend Connected to: Google AI Studio (GEMINI_API_KEY)
==================================================================
🌐 Open your browser and navigate to:
   👉 http://localhost:8000
==================================================================
```

Open your browser at **`http://localhost:8000`** to start using the portal!

#### 3.4 Interactive CLI Terminal Mode (Optional)
```bash
./run_advisor.sh
```

#### 3.5 Run Unit Test Suite
```bash
uv run pytest capstone_customs_agent/tests/test_customs.py -v
```
*(All 14 tests pass, covering 18-country rules, weather conversions, duty tax calculators, and Zero-PII sanitization)*

---

### 4. Aviation Web Portal Walkthrough (5 Core Views)

The web client is engineered as a modern Single Page Application (SPA) inspired by international airport flight operations and customs inspection terminals.

#### 4.1 Navigation Bar & Personalization
* **Top Header Layer**:
  * **Brand & Dynamic Route Badge**: Displays the active corridor code (e.g. `TPE ✈️ NRT`).
  * **Theme Switcher**: ☀️ Light mode, 🌙 Dark midnight mode, and 💻 System auto-sync.
  * **Multilingual Switcher**: Traditional Chinese (`zh-TW`), British English (`en-GB`), American English (`en-US`), Japanese (`ja-JP`), and Korean (`ko-KR`).
* **Lower Tab Navigation Layer**: 5 spacious tab buttons to switch between views instantly without reloading.

#### 4.2 Tab 1: Home & Onboarding Guide
* **Purpose**: Clear orientation and security assurance for first-time visitors.
* **4-Step Onboarding Graphic**:
  1. **Select Route & Dates**: Pick origin, destination, and dates.
  2. **Declare Baggage Items**: Select common tags or type custom items.
  3. **Receive Instant Verification**: Get risk status, packing weather forecast, duty calculations, and phrase cards.
  4. **Explore Etiquette & Declaration**: Review local conduct laws and airport customs channels.
* **Direct Jump Buttons**: Quick shortcuts to Baggage Inspection or Declaration Guide.

#### 4.3 Tab 2: Smart Baggage Inspection
* **Step 1: Route & Dates Selection**:
  * 18 destination corridors with synchronized airport codes.
  * Date picker automatically queries climate forecasts, clothing tips, and weather warnings.
* **Step 2: Declare Baggage Items**:
  * Quick-select chips (4 bottles of Whisky, 2 months of prescription drugs, heated tobacco, meat pastries, cash).
  * Natural language free-text input with inline Zero-PII masking.
* **Step 3: Verification Wait Timer**:
  * Displays radar scanning animation with an estimated wait countdown (~4-6 seconds).
* **Step 4: Comprehensive Assessment Report**:
  * **Risk Clearance Stamp**: 🟢 Safe / 🟡 Declaration Advised / 🔴 Prohibited.
  * **In-Depth Multi-Agent Regulatory Assessment**.
  * **Duty & Tax Breakdown Card**: Clear calculation of exemptions, taxable excess, and estimated import tariffs.
  * **Bilingual Customs Phrase Card**: Ready to show to foreign customs officers on smartphone screens without language barriers.

#### 4.4 Tab 3: Destination Culture & Penalties
* ⚖️ **Critical Traveler Conduct Laws (Avoiding Fines & Detention)**:
  * **Singapore**: Complete ban on chewing gum importation (fines up to SGD 10,000); strict penalties for littering and eating on MRT.
  * **Japan**: Unregistered drone flight regulations; strict biosecurity penalties (up to 3 years imprisonment or JPY 3M fine for uninspected meats).
  * **Thailand**: Strict lèse-majesté laws; electronic cigarettes are strictly illegal; severe drug trafficking penalties.
  * **Italy / France**: Mandatory ticket validation on public transport; severe fines for buying counterfeit designer goods.
  * **Australia**: Zero-tolerance biosecurity; immediate AUD 6,260 on-the-spot fine and visa cancellation for undeclared organic material.
* 🤝 **Local Cultural Customs & Social Etiquette**:
  * Tipping norms (15-20% in US/Canada; no tipping in Japan/Korea; rounding up in Europe).
  * Temple and cathedral dress codes.
  * Photography restrictions at airport security, borders, and government zones.

#### 4.5 Tab 4: Customs Clearance Flow Guide
* 🌟 **Golden Rule of Customs: Voluntary Declaration is Never Penalized!**
  * Customs penalties target travelers attempting to conceal dutiable items through the Green Channel. As long as you voluntarily declare items at the Red Channel, the worst-case scenario is simply paying duty or voluntarily abandoning the item—no fines, no blacklists, and no criminal charges!
* 🚶 **4-Stage Timeline**:
  1. Pre-Trip Packing & Receipt Organization ➔ 2. In-Flight Declaration Form ➔ 3. Channel Selection (Red vs. Green) ➔ 4. Inspection & Duty Payment.

#### 4.6 Tab 5: Master Statutory Limits (18 Countries)
Provides consolidated statutory thresholds across 18 countries:
* Alcohol volume and bottle allowances.
* Cigarette and tobacco limits (and e-cigarette / heated tobacco prohibitions).
* Anti-money laundering cash reporting thresholds.
* OTC and prescription medication personal limits.
* General overseas shopping exemption values.

---

### 5. Dynamic 3-Tier Tone Calibration

| Risk Level | Visual Badge | Applicable Context | System Tone Example | Recommended Action |
| :--- | :---: | :--- | :--- | :--- |
| **Level 1 Compliant** | 🟢 Green | Standard personal belongings within statutory limits (e.g. clothing, daily vitamins) | "Rest assured! Your items fully comply with personal duty-free regulations. Have a wonderful trip!" | Proceed through Green Channel (Nothing to Declare) |
| **Level 2 Dutiable** | 🟡 Yellow | Legal goods exceeding duty-free allowances (e.g. 4 bottles of whisky, excess foreign cash) | "Please note that this quantity exceeds the duty-free limit. We recommend declaring via the Red Channel. Voluntary declaration only incurs standard duty." | Keep purchase receipts ready and declare at Red Channel |
| **Level 3 Prohibited** | 🔴 Red | Strictly prohibited goods (ASF meat, fresh fruit, seeds, illicit vapes, contraband) | "⚠️ Stern Warning! This item is strictly prohibited. Bringing it into the country incurs heavy financial fines or criminal prosecution. Dispose of it before arrival!" | Do not pack; discard in airport biosecurity amnesty bins prior to customs |

---

### 6. API Key Security & Privacy Safeguards

* **`.gitignore` Shield**: All `*.env` files are strictly excluded from git tracking.
* **Safe Template (`.env.example`)**: Only placeholder values are included in version control.
* **Deterministic Zero-PII Regex**: Passport numbers and national IDs are scrubbed locally before model ingestion.
* **Stateless Operation**: No PII or traveler session data is permanently stored.

---

### 7. Demo Deployment Options

* **Option A: Local Interactive Demo (Recommended)**: Clone the repository, add a free `GEMINI_API_KEY` into `.env`, and run `./run_web.sh` to access `http://localhost:8000`.
* **Option B: Google Cloud Run Serverless Hosting**: Deploy with `gcloud run deploy`. Secrets are injected via Cloud Run environment variables or Secret Manager, generating a public HTTPS endpoint while keeping code and keys confidential.
* **Option C: Hugging Face Spaces / Render Hosting**: Connect your GitHub repository and inject `GEMINI_API_KEY` into repository settings for a free public demo.
* **Option D: Offline Showcase**: Embed walkthrough GIFs, UI screenshots, and golden evaluation results directly in README files.

---

### 8. Frequently Asked Questions (FAQ)

* **Q1: Port 8000 is already in use?**  
  Launch on another port using `PORT=8080 ./run_web.sh`.
* **Q2: What if I realize I accidentally packed excess alcohol upon landing?**  
  Do NOT enter the Green Channel! Immediately proceed to the Red Channel and tell the officer: *"I would like to declare these items."* Voluntary declaration is 100% legal and never fined.
* **Q3: What if I paste text containing real names or passport numbers?**  
  The system's Zero-PII filter masks all passport and national ID numbers into `[REDACTED_*]` tags immediately, ensuring no personal credentials reach external models.

---

*Compiled with care by the Global Traveler Smart Customs & Baggage Advisor Team.*  
*Wishing all international travelers safe journeys and smooth border crossings! ✈️🌏*
