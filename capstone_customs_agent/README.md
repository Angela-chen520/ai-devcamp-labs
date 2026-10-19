# 全球旅客出入境行李與報關智慧諮詢系統
### Global Traveler Smart Customs & Baggage Advisor

> 本專案為 Google AI Devcamp 個人結訓 Capstone 專案，基於 Google ADK (Agent Development Kit) 與 Gemini 2.5 Flash 構建。

---

## 📖 專案概述 (Project Overview)

許多跨國旅客在打包行李時，常因各國繁複的檢疫法規、免稅額限制與藥品規範而感到困惑或焦慮，甚至因不慎攜帶違禁品（如非洲豬瘟肉製品、加熱菸）而面臨高額罰鍰。

本系統旨在打造一個**以旅客為中心、Zero-PII 隱私安全第一**的專業諮詢代理人：
- **零個資收集 (Zero-PII)**：旅客無需亦絕不留存護照號碼、身分證字號或任何個人隱私。
- **三級動態語氣分級**：依據法規嚴格度動態調整回應語氣（綠色合規溫馨、黃色超額委婉建議申報、紅色違禁嚴肅警告）。
- **四階段報關流程引導**：提供「主動申報不罰」安心準則、時序式動線指引、關稅試算與即席雙語海關溝通小卡。
- **多語系在地化**：精準支援繁體中文 (`zh-TW`)、英式英語 (`en-GB`)、美式英語 (`en-US`)、日語 (`ja-JP`)、韓語 (`ko-KR`) 等用語差異。

---

## 🏛️ 架構設計 (Architecture)

本系統採用 **Google ADK Multi-Agent 架構** 與 **AgentTool** 路由分流，嚴格遵守 Built-in Tool (`google_search`) 獨立隔離原則：

```
                      +-----------------------------+
                      |   Traveler / Terminal CLI   |
                      +--------------+--------------+
                                     |
                         [Zero-PII Guardrail]
                  (Local Regex + Cloud DLP Sanitizer)
                                     |
                                     v
                      +-----------------------------+
                      |   Root Orchestrator Agent   |
                      |     (customs_advisor)       |
                      +--------------+--------------+
                                     |
        +----------------------------+----------------------------+
        |                            |                            |
        v                            v                            v
+------------------+         +------------------+         +------------------+
| Quarantine Agent |         |  Duty & Tax Agent|         |  Medicine Agent  |
|動植物檢疫/違禁品 |         |免稅額/紅線申報/稅|         |藥品劑量/醫療器材 |
+------------------+         +------------------+         +------------------+
        |                            |
        | (Skill: quarantine-rules)  | (Skill: duty-allowance)
        |                            | (Tool: calculate_duty_tax)
        |                            | (Tool: lookup_country_limits)
        +----------------------------+----------------------------+
                                     |
                                     v
                         +------------------------+
                         | Search Research Agent  |
                         | (Isolated GoogleSearch)|
                         +------------------------+
```

---

## 📂 專案目錄結構 (Directory Structure)

```text
capstone_customs_agent/
├── agent.py                 # ADK Multi-Agent 核心定義 (Root Agent + 4 領域專屬 Agent)
├── guardrails.py            # Zero-PII 雙層防護 (在地正則即時清洗 + Cloud DLP + Model Armor)
├── tools.py                 # 確定性業務工具 (關稅試算、各國限額快查、雙語溝通小卡生成)
├── cli.py                   # 互動式終端諮詢介面
├── README.md                # 專案詳細說明與架構手冊
├── skills/                  # ADK 領域知識技能庫
│   ├── quarantine-rules/    # 各國檢疫規範、非洲豬瘟、肉品零容忍、裁罰基準
│   ├── duty-allowance/      # 免稅額、菸酒限額、現金洗錢防制門檻、紅綠線規則
│   ├── medicine-limits/     # 臺灣 12/36 條款、處方藥份量、管制藥品警示
│   ├── tone-calibrator/     # 三級語氣動態調校指引與情境句型
│   ├── customs-guide/       # 四階段報關教學與雙語海關小卡規範
│   └── multilingual-support/# 多語系在地化對照表 (en-GB vs en-US 專有名詞對齊)
├── tests/
│   └── test_customs.py      # 單元測試套件 (涵蓋 PII 遮蔽、稅額計算、小卡生成)
└── evals/
    ├── golden.json          # 5 大黃金基準評估測試案例
    └── run_evals.py         # LLM-as-a-Judge 自動化評估執行器 (嚴格 Fail-Closed)
```

---

## 🔒 隱私與安全機制 (Zero-PII Guardrails)

1. **第 1 層：在地正則表達式快速清洗 (Stage 1 Deterministic Sanitizer)**
   - 即時辨識並遮蔽全球護照號碼 (`[REDACTED_PASSPORT]`)、臺灣身分證字號 (`[REDACTED_NATIONAL_ID]`)、手機號碼、電子郵件、信用卡號與 SSN。
   - 零延遲、百分之百阻絕於傳送至 LLM 之前。
2. **第 2 層：Google Cloud DLP 企業級檢測 (Stage 2 Cloud DLP)**
   - 透過 `google.cloud.dlp_v2` 針對高階個資實體進行深度去識別化。
3. **第 3 層：安心免責聲明附加 (Privacy Banner)**
   - 當系統偵測到旅客輸入包含機敏個資時，自動於回應開頭附加安心聲明：
     > `🔒【隱私安心聲明】：本系統採 Zero-PII 架構，您輸入的證件或個資已被即時遮蔽，我們絕不記錄或儲存任何旅客個人隱私。`
4. **Model Armor 安全整合 (Google Cloud Model Armor)**
   - 內建阻絕 Prompt Injection 與非預期攻擊注入。

---

## 🚀 快速啟動 (Quick Start)

### 1. 執行單元測試
```bash
./.bin/uv run pytest capstone_customs_agent/tests/test_customs.py -v
```
*(已通過 11/11 測試項)*

### 2. 執行黃金評估基準 (LLM-as-a-Judge)
```bash
./.bin/uv run python capstone_customs_agent/evals/run_evals.py
```

### 3. 一鍵啟動互動諮詢 CLI
```bash
./run_advisor.sh
```
或直接執行：
```bash
./.bin/uv run python capstone_customs_agent/cli.py
```

---

## 🌟 測試案例亮點 (Golden Test Cases)

1. **案例 1：香港入境臺灣攜帶肉乾臘腸（非洲豬瘟違禁品）**
   - 語氣：🔴 嚴肅警告 Level 3
   - 重點：重罰新臺幣 20 萬元至 100 萬元、絕不可放隨身或託運、立即棄置於棄置箱。
2. **案例 2：日本入境臺灣攜帶 4 瓶威士忌（超額自用應稅）**
   - 語氣：🟡 委婉建議 Level 2
   - 重點：免稅 1 公升，超額 3 公升須主動申報走紅線櫃檯，上限 5 公升，自動試算關稅與菸酒稅。
3. **案例 3：攜帶維他命與處方藥入境臺灣（合規）**
   - 語氣：🟢 安心提醒 Level 1
   - 重點：非處方藥每種 12 瓶/總數 36 瓶；處方藥自用攜帶規範。
4. **案例 4：赴英旅客英式英語諮詢加熱菸（違規禁令）**
   - 語言與語氣：精準使用 `en-GB`（hold luggage, Border Force），嚴肅告知英國禁止未核准之電子菸規範。
5. **案例 5：Zero-PII 護照號碼與身分證即時過濾測試**
   - 隱私：原始護照號碼與身分證字號完全被遮蔽為 `[REDACTED_PASSPORT]` 與 `[REDACTED_NATIONAL_ID]`，系統主動附帶隱私安心聲明。
