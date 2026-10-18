# Lab 2: Scale — Social Spark 規模化上雲、持久會話與長期記憶實作全紀錄
# Lab 2: Scale — Social Spark Production Scaling, Durable Sessions & Memory Bank Implementation Guide

---

## 目錄 / Table of Contents
1. [專案架構與核心概念 / Architecture & Core Concepts](#1-專案架構與核心概念--architecture--core-concepts)
2. [編寫哪些檔案？為什麼這樣編寫？ / Detailed File Breakdown: What & Why](#2-編寫哪些檔案為什麼這樣編寫--detailed-file-breakdown-what--why)
3. [說明網站未提及的問題、原因解析與改善方案 / Undocumented Issues, Root Causes & Improvements](#3-說明網站未提及的問題原因解析與改善方案--undocumented-issues-root-causes--improvements)
4. [資安防護架構與機密安全措施 / Security Architecture & Secrets Governance](#4-資安防護架構與機密安全措施--security-architecture--secrets-governance)
5. [最終驗證成果與檢查點 / Final Verification & Checkpoints](#5-最終驗證成果與檢查點--final-verification--checkpoints)

---

## 1. 專案架構與核心概念 / Architecture & Core Concepts

### 中文
在進行 Lab 2: Scale 的雲端規模化建置時，我們遵循 Google Gemini Enterprise Agent Platform 的四大核心柱石之一 —— **Scale（規模化）**，完成了以下架構轉型：

1. **無伺服器 Agent Runtime（Serverless Agent Runtime）**：
   - 將原本僅能在本機執行的 ADK 代理應用封裝為容器，部署至 Google Cloud 受管的 Agent Runtime（`us-central1`）。
   - 支援無伺服器彈性縮放與縮容歸零（Scale-to-zero），沒有請求時不佔用運算資源、不產生額外伺服器成本。
2. **原生代理身分（Agent Identity & Workload Identity Federation）**：
   - 捨棄傳統在環境中分發長效 Service Account Key 的危險做法，為 Agent 賦予專屬的雲端身分主體（`principal://agents.global.proj-PROJECT_NUMBER...`）。
   - Agent 能以原生身分安全讀取 Google Secret Manager（`social-spark-env`）中的金鑰，杜絕機密外洩。
3. **跨容器持久對話會話（VertexAiSessionService）**：
   - 無伺服器容器會隨生命週期隨時重啟或縮容為 0，原本儲存在單機記憶體或 SQLite 的對話狀態會丟失。
   - 透過 `VertexAiSessionService` 將會話抽離至雲端受管儲存層，保證對話脈絡在跨容器實例間無縫存續。
4. **跨對話長期記憶庫（VertexAiMemoryBankService）**：
   - 建立託管的 Memory Bank，配置使用者偏好（`USER_PREFERENCES`）、明確指令（`EXPLICIT_INSTRUCTIONS`）與自訂貼文風格（`posting_style`），並設定 90 天過期淘汰機制（TTL）。
   - 在 Agent 掛載 `load_memory` 進行前置檢索，並在貼文成功發布後觸發非同步的 `add_session_to_memory()` 自動學習風格。
5. **前後端同源中繼代理（BFF Pattern with Application Default Credentials）**：
   - 瀏覽器客戶端嚴禁直接持有 GCP IAM 憑證；直接存取會導致未授權。
   - 在 Next.js 建立 3 個同源伺服器代理路由（`/api/adk`、`/api/posts`、`/outputs/[...path]`），在伺服器端自動附加 Token 並完整透傳 SSE 串流。
6. **全雲端私有化託管（Private Cloud Run Deployment）**：
   - 前端發布至 Cloud Run，綁定專屬服務帳戶 `social-spark-frontend`（落實最小權限原則），並配置 `--no-allow-unauthenticated` 禁止未授權公網存取。

### English
During the implementation and cloud scaling of Lab 2: Scale, we aligned with the four pillars of Google's Gemini Enterprise Agent Platform, specifically focusing on **Scale**:

1. **Serverless Agent Runtime**:
   - Containerized the ADK application into a fully managed Google Cloud Agent Runtime instance in `us-central1`.
   - Enabled scale-to-zero economics, ensuring zero compute costs when idle.
2. **Native Agent Identity**:
   - Replaced risky long-lived service account keys with a dedicated cryptographic agent identity principal (`principal://agents.global.proj-PROJECT_NUMBER...`).
   - The agent securely accesses Secret Manager (`social-spark-env`) under its own identity.
3. **Resilient Session Management (`VertexAiSessionService`)**:
   - Decoupled conversational state from container processes into managed session storage, ensuring session survival across container restarts and scale-to-zero cycles.
4. **Long-Term Memory Bank (`VertexAiMemoryBankService`)**:
   - Configured memory topics (`USER_PREFERENCES`, `EXPLICIT_INSTRUCTIONS`, and custom `posting_style`) with a 90-day retention TTL.
   - Equipped the orchestrator with `load_memory` and integrated an asynchronous post-execution hook `add_session_to_memory()` to distill user preferences.
5. **Backend-for-Frontend (BFF) Proxy with ADC**:
   - Avoided exposing GCP bearer tokens to browser clients by implementing same-origin Next.js route handlers (`/api/adk`, `/api/posts`, `/outputs/[...path]`).
   - Server-side token injection via Application Default Credentials (ADC) while seamlessly proxying SSE event streams.
6. **Private Full-Stack Cloud Deployment**:
   - Deployed the Next.js frontend to Cloud Run with `--no-allow-unauthenticated` using a dedicated service account `social-spark-frontend` holding minimal permissions (`roles/aiplatform.user`).

---

## 2. 編寫哪些檔案？為什麼這樣編寫？ / Detailed File Breakdown: What & Why

在本次 Lab 2 中，我們編寫與修改了以下 12 個核心檔案與設定檔：

| 檔案路徑 | 類型 | 核心功能與修改內容 | 為什麼這樣編寫？（架構與設計決策） |
|---|---|---|---|
| **`backend/main.py`** | 修改 | 引入 `VertexAiSessionService` 與 `VertexAiMemoryBankService`，動態解析 `APP_URL`。 | **環境自適應設計**：透過偵測 `APP_URL` 自動在「本機開發（記憶體會話）」與「雲端運作（Vertex AI 受管會話與記憶庫）」間無縫切換，避免維護兩份程式碼導致行為脫鉤。 |
| **`backend/social_poster/agent.py`** | 修改 | 掛載 `load_memory` 工具、新增 `consulting_memory` 狀態燈號、新增發文後 `add_session_to_memory()` 回呼。 | **主動學習與前置查詢決策**：在起草前先查詢歷史偏好，可大幅降低文案修改往返成本；在發布後非同步萃取對話，形成自我演進的記憶閉環。 |
| **`backend/memory_bank_config.py`** | 新建 | 提供 `show` 與 `apply` CLI 工具，透過 REST API 設定 Memory Bank 主題與 90 天 TTL。 | **精準配置自訂主題**：Agent Runtime 的主題 schema 無法在 GCP 主控台點選設定，透過腳本能精確定義 `posting_style` 並設定 7776000 秒過期淘汰策略。 |
| **`frontend/.env.local`** | 新建 | 設定 `ADK_BACKEND_ORIGIN` 指向雲端 Agent Runtime 端點。 | **切換雲端入口**：單一環境變數即可決定前端將請求發往本地後端還是雲端無伺服器 Agent。 |
| **`frontend/lib/proxy.ts`** | 新建 | 建立統一中繼代理核心，整合 GoogleAuth 自動注入 ADC Token。 | **BFF 資安隔離**：將 Token 注入完全收斂在伺服器端記憶體中，並在此處清洗 Request Headers（過濾 host、authorization），防範金鑰外洩與標頭污染。 |
| **`frontend/app/api/adk/route.ts`** | 新建 | 代理 `/api/adk` 的 GET 與 POST 請求。 | **透傳 AG-UI 串流**：以 Server-Sent Events（SSE）串流方式透傳對話訊息與即時進度事件，確保前端燈號即時流暢反應。 |
| **`frontend/app/api/posts/route.ts`** | 新建 | 代理 `/api/posts` 取得歷史貼文。 | **資料庫安全轉發**：讓前端 PostGallery 能安全自雲端 Agent 讀取歷史貼文清單。 |
| **`frontend/app/outputs/[...path]/route.ts`** | 新建 | 代理 `/outputs/...` 取得生成圖片，並加入路徑字元白名單檢驗。 | **路徑遍歷防禦（Path Traversal）**：嚴格檢查路徑片段，阻擋 `..` 與非法符號，防止惡意使用者藉由下載端點窺探伺服器系統內部檔案。 |
| **`frontend/app/api/copilotkit/route.ts`** | 修改 | 將 CopilotKit 的 `HttpAgent` 指向本地代理路由 `http://127.0.0.1:${port}/api/adk`。 | **規避掉 Token 陷阱**：官方指引特別強調，CopilotKit 的客戶端自訂 fetch 在生產環境構建時會遺失 Token，將 URL 導向本地代理可徹底根除該問題。 |
| **`frontend/app/components/PostGallery.tsx`** | 修改 | 將 `BACKEND_ORIGIN` 的預設值由寫死的 `http://localhost:8000` 改為同源空字串 `""`。 | **同源相對路徑修正**：若預設為 localhost，在雲端運行時瀏覽器會向使用者個人電腦請求導致連線拒絕；改為同源路徑後能自動被 Next.js 伺服器代理攔截。 |
| **`frontend/.gcloudignore`** | 新建 | 排除 `node_modules/`、`.next/` 與 `.env.local`。 | **加速建置並避免污染**：避免將數百 MB 的本機暫存檔與可能包含本機二進制的套件上傳至 Cloud Build，保持雲端映像檔純淨。 |
| **`.gitignore`** | 修改 | 新增 `deployment_metadata.json.lock` 排除規則。 | **版本庫乾淨防護**：防止 agents-cli 部署時生成的暫態鎖定檔被推送到 GitHub 造成衝突。 |

---

## 3. 說明網站未提及的問題、原因解析與改善方案 / Undocumented Issues, Root Causes & Improvements

在遵循說明網站指引實作時，我們排查並克服了以下 **5 個官方教材中未明確說明或容易踩坑的實務問題**：

### 1. 部署鎖定殘留導致重試失敗（`Deployment Lock in deployment_metadata.json`）
- **網站未提及之處**：官方教學僅說明執行 `agents-cli deploy`，但當前一次部署在雲端剛剛完成時，本地的 `deployment_metadata.json` 仍處於 `in_progress` 狀態，下一次部署會直接中斷並噴出錯誤：
  `❌ Error: A deployment operation is already in progress`。
- **原因解析**：`agents-cli` 本地狀態檔與雲端 Operation 完成時間存在同步延遲，本地鎖未及時釋放。
- **改善方案**：
  在發起新部署前，先執行狀態同步指令：
  ```bash
  agents-cli deploy --status --project YOUR_PROJECT --no-confirm-project
  ```
  CLI 會向雲端確認操作已是 `done: true`，進而刷新本地 metadata 標記為閒置，解除本地鎖定。

---

### 2. `PostGallery.tsx` 寫死 `localhost:8000` 導致圖片與歷史貼文連線拒絕
- **網站未提及之處**：官方指引要求學員建立 `/api/posts` 與 `/outputs/[...path]` 的 Next.js 伺服器端代理，但隨附的前端模板代碼中，`frontend/app/components/PostGallery.tsx` 第 16 行卻寫死：
  ```ts
  const BACKEND_ORIGIN = process.env.NEXT_PUBLIC_BACKEND_ORIGIN || "http://localhost:8000";
  ```
- **原因解析**：在未額外設定該環境變數時，JavaScript 的邏輯運算子 `||` 會強制回退到 `http://localhost:8000`。這會導致瀏覽器繞過剛建好的 Next.js 代理，直接向使用者的個人電腦發送請求，在雲端或不同裝置存取時，歷史貼文與圖片全數回報 `Connection Refused` 破圖。
- **改善方案**：
  改用空值合併運算子（Nullish Coalescing）：
  ```ts
  const BACKEND_ORIGIN = process.env.NEXT_PUBLIC_BACKEND_ORIGIN ?? "";
  ```
  當未特別指定外部 URL 時，瀏覽器發送**同源相對路徑**（如 `/api/posts` 與 `/outputs/...`），無縫由 Next.js 伺服器端代理接手並附加 GCP Token 轉發。

---

### 3. Cloud Build 上傳未過濾龐大 `node_modules` 與本機快取
- **網站未提及之處**：官方指令使用 `gcloud run deploy --source frontend`，但未在 `frontend/` 目錄中配置 `.gcloudignore`。
- **原因解析**：若無指定忽略規則，CLI 會將本機數萬個檔案（數百 MB 的 `node_modules` 與 `.next` 快取）打包上傳至 Cloud Storage，不僅耗費數倍上傳時間，本機的 OS 專屬二進制模組（如本機架構的 SWC/Rollup）更可能與雲端 Linux 容器發生二進制衝突導致建置崩潰。
- **改善方案**：
  在 `frontend/` 手動建立 `.gcloudignore`：
  ```ini
  #!include:.gitignore
  .next/
  node_modules/
  .env.local
  ```
  確保上傳檔案縮減 95% 以上，僅上傳原始碼由雲端原生純淨建置。

---

### 4. WSL / Linux 環境下 `gcloud run services proxy` 缺少專屬元件
- **網站未提及之處**：官方教程建議使用 `gcloud run services proxy` 建立本地認證通道，但在很多 Linux/WSL 環境下執行時會報錯：
  `This command requires the cloud-run-proxy component to be installed`，且在套件管理器託管的 gcloud 中會顯示 `component manager is disabled`。
- **原因解析**：Linux 系統套件版（APT）的 Google Cloud SDK 預設關閉了內部元件安裝器，無法由 gcloud 自行下載二進制。
- **改善方案**：
  1. 系統層面安裝：`sudo apt-get install google-cloud-cli-cloud-run-proxy`。
  2. 替代驗證方案：在本地直接啟動 Next.js 開發伺服器（`npm run dev`），由本機的 Next.js 代理直連雲端 Agent Runtime，體驗完全相同且無需額外安裝系統套件。

---

### 5. Memory Bank 主題與 TTL 無法在 GCP 主控台直接設置
- **網站未提及之處**：官方文件僅提到 Memory Bank 能記憶使用者偏好，但並未提供現成的 CLI 工具來初始化自訂主題（如 `posting_style`）與過期天數。
- **原因解析**：Vertex AI Reasoning Engine 的 Memory Bank 設定隸屬於 `contextSpec.memoryBankConfig`，必須透過 REST API 進行 PATCH 更新。
- **改善方案**：
  自主編寫 `backend/memory_bank_config.py`，使用 Google Auth 自動取得權杖，調用 Reasoning Engine REST API 並指定 `updateMask=contextSpec`，達成一鍵套用主題與 90 天過期設定。

---

## 4. 資安防護架構與機密安全措施 / Security Architecture & Secrets Governance

在整套系統建置過程中，落實了以下嚴密的資安控管：

```
                ┌────────────────────────────────────────────────────────┐
                │                    安全防護邊界                        │
                └────────────────────────────────────────────────────────┘
 [瀏覽器客戶端] ────────(同源請求、無任何金鑰、路徑清洗)────────► [Next.js 前端伺服器]
                                                                     │
                                                 (伺服器端注入 Google ADC Token)
                                                                     ▼
                                                     [Google Cloud Agent Runtime]
                                                                     │
                                                       (Agent Identity 原生主體)
                                                                     ▼
                                                           [Secret Manager]
```

1. **憑證零外洩原則（Zero Client Credential Exposure）**：
   - 瀏覽器端全程只跟同源（Same-Origin）的 Next.js 前端通訊，永遠接觸不到 Google Cloud 的 IAM Bearer Token、Service Account 憑證或內部專案架構。
2. **路徑遍歷防禦（Path Traversal Prevention）**：
   - 在 `/outputs/[...path]` 代理中對路徑片段執行字元白名單檢驗，嚴格阻絕 `..` 與跳脫符號，徹底防止攻擊者讀取伺服器內部敏感情資。
3. **SSRF（伺服器端請求偽造）防範**：
   - 代理的目的地嚴格限制由伺服器環境變數 `ADK_BACKEND_ORIGIN` 決定，外部請求無法任意指定轉發網址。
4. **最小權限原則（Least Privilege）**：
   - 前端雲端服務帳號 `social-spark-frontend` 僅被授予調用 Agent 的最低權限（`roles/aiplatform.user`），無任何專案管理員或儲存庫修改權限。
5. **私有存取（Private Ingress）**：
   - Cloud Run 設定 `--no-allow-unauthenticated`，阻擋未授權公網隨意調用您的 Agent 消耗模型配額或濫發貼文。
6. **Git 版本控制機密隔離**：
   - 所有 `.env` 與 `.env.local` 檔案一律列入 [`.gitignore`](file:///home/angela/ai-devcamp-labs/.gitignore)，並經過自動化正則腳本全盤掃描確認零金鑰外洩。

---

## 5. 最終驗證成果與檢查點 / Final Verification & Checkpoints

- ✅ **Checkpoint 1: Agent Runtime 上線**：
  - 成功部署至 `us-central1`，Engine ID 為 `3134769498318438400`。
  - 受管端點 `/openapi.json` 通過測試，回傳 `200 OK`。
- ✅ **Checkpoint 2: 持久會話與記憶庫**：
  - `backend/main.py` 成功掛載 `VertexAiSessionService` 與 `VertexAiMemoryBankService`。
  - `backend/memory_bank_config.py apply` 成功套用 `USER_PREFERENCES`、`EXPLICIT_INSTRUCTIONS`、`posting_style` 與 90 天 TTL。
- ✅ **Checkpoint 3: 前端中繼代理打通**：
  - 啟動 `npm run dev`，瀏覽器成功顯示即時管線進度：
    `Idea → 🧠 Consulting memory → 🔍 Researching → ✍️ Drafting → ⏳ Approval → ✅ Posted`。
  - 人機審核按鈕正常運作，審核通過後自動寫入 Memory Bank。
- ✅ **Checkpoint 4: Cloud Run 前端私有部署**：
  - 未授權公網存取 Cloud Run 網址直接攔截返回 `HTTP 403 Forbidden`。
  - 攜帶 IAM Token 存取 `/api/posts` 代理端點返回 `HTTP 200 OK {"posts":[]}`。
- ✅ **Checkpoint 5: 分散式可觀測性（Cloud Logging）**：
  - 在 Cloud Logging 觀測到真實轉發的 `GET /api/posts 200 OK` 紀錄，前後端全雲端鏈路運作順暢！
