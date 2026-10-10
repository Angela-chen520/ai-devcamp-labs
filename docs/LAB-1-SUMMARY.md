# Lab 1: Build — Social Spark AI Agent 實作與排錯全紀錄
# Lab 1: Build — Social Spark AI Agent Implementation & Troubleshooting Guide

---

## 目錄 / Table of Contents
1. [專案架構與代碼編寫發現 / Architecture & Implementation Discoveries](#1-專案架構與代碼編寫發現--architecture--implementation-discoveries)
2. [測試過程中發現缺少了什麼？ / What Was Missing During Testing?](#2-測試過程中發現缺少了什麼--what-was-missing-during-testing)
3. [遇到的報錯代碼、原因解析與解決方案 / Error Codes, Root Causes & Solutions](#3-遇到的報錯代碼原因解析與解決方案--error-codes-root-causes--solutions)
4. [核心架構設計決策：為什麼這樣寫？ / Design Decisions: Why Built This Way?](#4-核心架構設計決策為什麼這樣寫--design-decisions-why-built-this-way)
5. [Golden Path 最終驗證成果 / Golden Path Final Verification](#5-golden-path-最終驗證成果--golden-path-final-verification)

---

## 1. 專案架構與代碼編寫發現 / Architecture & Implementation Discoveries

### 中文
在依照 Lab 1 說明步驟進行環境建置與代理人（Agent）程式碼編寫時，發現了以下關鍵機制與設計要求：
1. **最小代理人架構（Minimal Agent）**：
   - 核心編排者（`root_agent`）使用 `gemini-2.5-flash`，專注於任務調度、意圖解析與統籌，**不直接承擔調研與發文等副作用工作**。
2. **漸進式技能揭露（Progressive Disclosure via Agent Skills）**：
   - 技能（Skills）以獨立資料夾形式封裝（如 `skills/post-formatter`、`platform-style`、`brand-voice`、`poster-style`），透過 `SkillToolset` 動態加載。
   - 代理人啟動時，系統提示詞中僅注入技能名稱與簡述（第一層：輕量上下文），只有當實際撰寫貼文需要時，才透過 `load_skill` 加載完整 `SKILL.md`（第二層），並透過 `load_skill_resource` 讀取特定平台參考規範（第三層，如 `references/linkedin.md`）。
3. **原生搜尋工具的隔離約束（Google Search Constraint）**：
   - 官方 Agent Platform 與 ADK 存在嚴格限制：**內建工具（如 `google_search`）不得與自定義函式工具（Function Tools）混合在同一個模型調用中**。
   - 必須建立獨立子代理人 `search_agent`（`name="web_researcher"`），再透過 `AgentTool(agent=search_agent)` 掛載至 `root_agent`。
4. **雙發布通道架構（Dual MCP Publishers）**：
   - **Buffer MCP**：透過遠端 HTTP MCP（`https://mcp.buffer.com/mcp`）連線，適合純文字與多平台排程發布。
   - **LinkedIn MCP**：透過本機 FastMCP（stdio 傳輸），支援以本地檔案路徑上傳高解析度視覺插圖。

### English
During the implementation of Lab 1 following the attendee guide, several critical patterns and platform constraints were discovered:
1. **Minimal Orchestrator Pattern**:
   - The primary agent (`root_agent`) uses `gemini-2.5-flash` to act as an orchestrator for routing, intent classification, and pipeline governance. It **never executes drafts or research directly**.
2. **Progressive Disclosure via Agent Skills**:
   - Skills reside in modular directories (`skills/post-formatter`, `platform-style`, `brand-voice`, `poster-style`) loaded via ADK's `SkillToolset`.
   - Context is minimized: only skill names and one-line descriptions enter the initial system prompt (Level 1). Full instructions are retrieved on-demand via `load_skill` (Level 2), and platform-specific resources via `load_skill_resource` (Level 3, e.g., `references/linkedin.md`).
3. **Built-in Tool Isolation Constraint (`google_search`)**:
   - Google GenAI / Agent Platform strictly prohibits mixing built-in grounding tools (`google_search`) with custom function tools in the same model turn.
   - The search capability must be isolated in a dedicated sub-agent `search_agent` (`name="web_researcher"`), wrapped into the orchestrator via `AgentTool(agent=search_agent)`.
4. **Dual MCP Publisher Topology**:
   - **Buffer MCP**: Remote HTTP MCP server (`https://mcp.buffer.com/mcp`) suited for multi-platform scheduling and text distribution.
   - **LinkedIn MCP**: Local stdio FastMCP server (`mcp/linkedin_server.py`) capable of ingesting and publishing local illustration image files.

---

## 2. 測試過程中發現缺少了什麼？ / What Was Missing During Testing?

### 中文
在初始編寫完成後進行端到端測試時，發現缺少了以下三個關鍵環節：
1. **缺少工具清單過濾（`tool_filter`）**：
   - Buffer 的遠端 MCP 伺服器預設曝露了 21 個工具（包括 `introspect_schema`, `execute_query`, `execute_mutation` 等資料庫底層工具）。
   - `SkillToolset` 預設曝露了 `run_skill_script` 工具。
   - 總計 28 個複雜工具一口氣灌入模型，嚴重干擾了模型對工具的理解。
2. **缺少帳號探索工具（`get_account`）**：
   - 初次優化時將 Buffer 工具嚴格限制為 `["create_post", "list_channels"]`，但 `list_channels` 強制要求提供 `organizationId`。
   - 由於缺少無參數的 `get_account` 工具，模型無法自動查詢使用者的組織 ID，導致模型停下腳步在聊天室向使用者索取 `organization ID`。
3. **缺少防範代碼直譯器幻覺的提示詞約束**：
   - 提示詞寫著「Load skills」，模型誤以為需要調用內建直譯器來執行 Python 腳本。缺少了明確的「禁止直譯器、強制直接調用 Function Tool」的負向約束。

### English
During initial end-to-end testing, three critical gaps were identified:
1. **Missing Tool Filtering (`tool_filter`)**:
   - Buffer's MCP server exposed 21 tools by default (including database/schema operations like `introspect_schema`, `execute_query`, `execute_mutation`).
   - ADK's `SkillToolset` exposed `run_skill_script`.
   - Ingesting 28 disparate tools saturated the function calling schema, degrading Gemini's structured decision-making.
2. **Missing Discovery Tool (`get_account`)**:
   - Initial filtering restricted Buffer to `["create_post", "list_channels"]`. However, Buffer's `list_channels` schema strictly requires `organizationId`.
   - Without the zero-argument `get_account` tool, the agent could not discover the user's organization autonomously, prompting it to interrogate the user in chat.
3. **Missing Tool Calling Guardrails in Instructions**:
   - The phrase "load and follow skills" triggered Gemini's internal code-execution bias. Explicit negative constraints directing the model away from python interpreters and toward direct function calling were absent.

---

## 3. 遇到的報錯代碼、原因解析與解決方案 / Error Codes, Root Causes & Solutions

### 報錯 1：`Tool 'google:python_interpreter' not found` (前端畫面卡死)

#### 【錯誤訊息 / Error Log】
```text
[CopilotKit] sendMessage error: Tool 'google:python_interpreter' not found.
Available tools: web_researcher, generate_image, list_skills, load_skill, load_skill_resource, run_skill_script, get_account, list_channels, get_channel, list_posts, get_post, list_ideas, list_idea_groups, create_idea, create_post, edit_post, delete_post, get_aggregated_post_metrics, list_post_templates, get_post_template, create_post_template, update_post_template, delete_post_template, introspect_schema, execute_query, execute_mutation, linkedin_get_profile, linkedin_create_post

event: {
  code: 'BACKGROUND_EXECUTION_ERROR',
  message: "Tool 'google:python_interpreter' not found.",
  type: 'RUN_ERROR'
}
```

#### 【原因剖析 / Root Cause Analysis】
- **中文**：
  在使用者發送「撰寫貼文並載入技能」時，Gemini 2.5 Flash 受到工具清單中 `run_skill_script`、`execute_query`、`execute_mutation` 的暗示，產生了直譯幻覺。模型輸出調用 `google:python_interpreter`，並傳入代碼：
  `print(default_api.load_skill(skill_name='post-formatter'))`。
  然而前端 CopilotKit 與後端 ADK 並未註冊名為 `google:python_interpreter` 的工具，導致拋出 `BACKGROUND_EXECUTION_ERROR`，前端畫面永遠停在 `google:python_interpreter (running..)`，無法進入下一步。
- **English**:
  Prompted with instructions to "load skills" while seeing scripting and query tools (`run_skill_script`, `execute_query`), Gemini 2.5 Flash hallucinated a built-in code interpreter call `google:python_interpreter` with payload `print(default_api.load_skill(...))`. Because neither CopilotKit nor ADK exposes this interpreter tool, the runtime crashed with an unhandled `BACKGROUND_EXECUTION_ERROR`, freezing the UI on an unresolved running spinner.

#### 【解決方案 / Solution】
1. **精簡 `SkillToolset`**：過濾掉未使用的 `run_skill_script`。
   ```python
   skill_toolset = SkillToolset(
       skills=[...],
       tool_filter=["load_skill", "load_skill_resource", "list_skills"],
   )
   ```
2. **精簡 `buffer_toolset`**：去除所有資料庫查詢工具，僅保留貼文與帳號相關操作。
   ```python
   buffer_toolset = McpToolset(
       connection_params=StreamableHTTPConnectionParams(...),
       tool_filter=["get_account", "list_channels", "create_post"],
       require_confirmation=True,
   )
   ```
3. **加入嚴格工具調用指令**：
   ```python
   Tool Calling Rules (Strict):
   - You must ONLY call available tools directly using structured function calls.
   - NEVER attempt to call 'python_interpreter' or 'google:python_interpreter'.
   - Never use Python code to invoke tools. To load a skill, directly invoke the load_skill function tool with skill_name.
   ```

---

### 報錯 2：`Duplicate function declaration found: create_post`

#### 【錯誤訊息 / Error Log】
```text
ValueError: Duplicate function declaration found: create_post
```

#### 【原因剖析 / Root Cause Analysis】
- **中文**：
  Buffer 遠端伺服器提供名為 `create_post` 的工具；本機 LinkedIn MCP 伺服器（`mcp/linkedin_server.py`）同樣定義了名為 `create_post` 的函式。Gemini API 嚴格禁止同一個請求中出現重名工具宣告。
- **English**:
  Both Buffer's remote MCP server and the local LinkedIn MCP server expose a tool named `create_post`. The Gemini API schema compiler rejects duplicate function declarations across toolsets.

#### 【解決方案 / Solution】
在 LinkedIn MCP 掛載時加上 `tool_name_prefix="linkedin"`，自動將其工具重命名為 `linkedin_create_post` 與 `linkedin_get_profile`：
```python
linkedin_toolset = McpToolset(
    connection_params=StdioConnectionParams(...),
    tool_filter=["get_profile", "create_post"],
    tool_name_prefix="linkedin",
    require_confirmation=True,
)
```

---

### 報錯 3：Agent 詢問 `Buffer organization ID` 導致流程中斷

#### 【錯誤現象 / Symptom】
```text
Agent: "I can post this for you. Could you please tell me your Buffer organization ID, or the name of the organization so I can find the ID and the LinkedIn channel?"
```

#### 【原因剖析 / Root Cause Analysis】
- **中文**：
  Buffer 的 `list_channels` 工具在 Schema 中定義了 `required: ['organizationId']`。若代理人缺少無參數的 `get_account` 工具，就無法自動讀取已登入帳號的組織清單，因而不得不向使用者提問。
- **English**:
  Buffer's `list_channels` declaration requires an `organizationId` parameter. Without `get_account`, the model has no programmatic pathway to retrieve the organization ID associated with the API key, forcing it to stall and query the human user.

#### 【解決方案 / Solution】
將 `get_account` 加入 Buffer MCP 工具白名單：
```python
tool_filter=["get_account", "list_channels", "create_post"]
```
代理人即可自動執行：`get_account` ➔ 取得組織 ID（如 `<ORGANIZATION_ID>`）➔ 調用 `list_channels` ➔ 鎖定頻道（如 `<CHANNEL_ID>`）。

---

### 報錯 4：Buffer 無法附帶本機圖片 (`Invalid post: Image could not be read from its URL`)

#### 【原因剖析 / Root Cause Analysis】
- **中文**：
  由 `generate_image` 生成的插圖儲存在本機檔案系統（如 `/home/angela/.../gallery/*.png`）。Buffer 的雲端伺服器無法存取使用者的本地檔案路徑，硬傳 `image_path` 會導致 Buffer API 報錯。
- **English**:
  Images generated by Imagen/Gemini are saved locally on the agent's filesystem. Buffer's cloud infrastructure cannot resolve local disk paths. Sending `image_path` to Buffer causes remote validation failure.

#### 【解決方案 / Solution】
在代理人 Instructions 中明確訂定發布路由規則（Publishing Routing）：
- **純文字貼文或排程發布** ➔ 路由至 Buffer `create_post`。
- **即時發布且帶有插圖** ➔ 路由至本地 LinkedIn FastMCP `linkedin_create_post`（透過 LinkedIn Posts API 直接上傳圖片二進位串流）。

---

## 4. 核心架構設計決策：為什麼這樣寫？ / Design Decisions: Why Built This Way?

### 1. 為什麼要使用 `SkillToolset` 而不是將所有規則寫進單一 Prompt？
- **效能與成本**：四個技能完整加載超過 200 行 Markdown。漸進式揭露讓預設 System Prompt 保持在 10 行以內，每次推理節省數千 Tokens。
- **治理與協同**：品牌語氣（`brand-voice`）、排版風格（`post-formatter`）是標準 Markdown 檔案，行銷人員可直接透過 Pull Request 調整規則，完全不需改動 Python 代碼。

### 2. 為什麼 `google_search` 必須獨立成子代理人？
- **平台硬性約束**：Google GenAI / Agent Platform 底層會拒絕將 Google Search Grounding 與自定義函式簽名混合發送。透過 `AgentTool`，主代理人視 `web_researcher` 為一般工具，但子代理人內部獨立完成搜尋調研並回傳結構化文字摘要。

### 3. 為什麼發布工具必須設定 `require_confirmation=True`？
- **Human-in-the-Loop（人機協同治理）**：AI 代理人具有自主調用工具的能力，若僅靠 Prompt 要求「請先詢問我」，模型仍可能因幻覺直接執行發文。
- **框架級阻斷**：`require_confirmation=True` 是 ADK 框架層級的硬性阻斷機制。未經前端點擊 `Approve` 傳回確認信號前，後端發布函式物理上無法被調用執行。

---

## 5. Golden Path 最終驗證成果 / Golden Path Final Verification

### 測試指令 / Test Prompt:
> *"Draft a LinkedIn post about why agent evals matter more than demos, with an illustration, and post it via Buffer."*

### 執行全生命週期驗證 / End-to-End Lifecycle Verification:
1. **Idea ➔ Researching**：
   - 觸發 `AgentTool: web_researcher`，獨立調研「Agent evals vs Demos」的最新論點。
2. **Researching ➔ Drafting**：
   - 依序調用 `load_skill(post-formatter)`、`load_skill(platform-style)`、`load_skill(brand-voice)`、`load_skill(poster-style)`。
   - 二級調用 `load_skill_resource(references/linkedin.md)` 載入 LinkedIn 專用排版規則。
   - 觸發 `generate_image` 成功產出高解析度概念插圖，存入 `gallery/`。
3. **Drafting ➔ Approval**：
   - 代理人輸出排版完整、語氣契合的貼文草稿，Pipeline 狀態自動轉為 `Approval`。
   - 詢問使用者發布確認；使用者核准後，觸發審核阻斷卡片（`ConfirmAction`）。
4. **Approval ➔ Posted 🚀**：
   - 使用者點擊 `Approve`，系統調用 `linkedin_create_post` 以 `DRY_RUN=true` 模式安全模擬發布。
   - 成功回傳假 URN 連結（`urn:li:share:dryrun-...`），Pipeline 全部打勾，最右側 **`Posted 🚀`** 正式亮起！
   - 左側 **`APPROVED POSTS & IMAGES`** 成功渲染審核通過的插圖與完整貼文內容。

---
*文件編寫日期 / Document Date: 2026-10-10*  
*專案驗證狀態 / Verification Status: ALL PASSED (Lab 1 Complete)*
