# Gemini Embedding 冷備援切換設計

日期：2026-09-08  
狀態：待 Jasper 書面審閱  
適用環境：目前這台 Apple Silicon Mac／OpenClaw

## 目標

將目前的 Qwen 本地 Embedding 保留為可回復的冷備援，並把正式知識搜尋與每日增量索引切回 Google `gemini-embedding-001`。新的 Gemini API Key 由 Jasper 在最後的人工作業點以隱藏輸入方式寫入 macOS Keychain；金鑰不得進入 Git、OpenClaw 設定檔、Shell 歷史、日誌或聊天內容。

## 已確認現況

- Qwen 模型、LanceDB 索引、程式、安裝收據與既有驗證快照仍在本機；目前服務與 06:30／06:50 排程仍啟用。
- Gemini 專案與本地向量快取仍存在，模型設定為 `gemini-embedding-001`、768 維。
- 既有 Gemini 表可開啟，但資料列數與目前來源不一致，不能直接視為可用正式索引；切回時必須重建並驗證。
- 既有 Gemini 06:30 增量工作仍存在但已停用；不會在金鑰或索引尚未準備好時自行呼叫 API。
- 現行 `local_knowledge_search` 外掛限定 Qwen 專案與 Qwen 回傳格式，不能直接把路徑改成 Gemini 後冒充相容。

## 選定方案

採「先準備、後原子切換」：

1. 在不改變正式搜尋來源的情況下，完成 Gemini 專案更新、Keychain 讀取、金鑰輸入工具、排程定義、備份與驗證腳本。
2. 建立 Qwen 冷備援收據，記錄模型、索引、程式版本、快照與排程身分；不複製或刪除大型模型檔。
3. 停在 API Key Human Gate，交由 Jasper 執行隱藏輸入指令。
4. 金鑰輸入後先做單筆 API canary，再使用既有相容快取加速完整 Gemini 索引重建。
5. 重建、同步稽核、搜尋基準、快照還原全部通過後，才停用 Qwen 06:30／06:50 排程並停止 Qwen 服務；Gemini 增量與快照排程最後啟用。
6. 任一驗證失敗時不切換，Qwen 保持正式搜尋來源；若切換後驗證失敗，可依收據重新啟用 Qwen。

這個順序避免 API Key 尚未輸入時造成搜尋停機，也避免啟用一個已知落後的 Gemini 索引。

## 不採用方案

- Qwen 與 Gemini 同時正式運行：會重複使用 RAM、排程與寫入資源，也增加狀態混淆。
- 先停 Qwen、再等待 Gemini 金鑰與重建：會產生不必要的搜尋空窗。
- 刪除 Qwen 模型或索引：失去回復能力，且不符合冷備援要求。
- 直接沿用 Qwen 向量到 Gemini：模型身分不同，向量不可混用。
- 把新 Key 寫入 OpenClaw Google 模型供應者設定：會把 Embedding 專用 Key 與其他 Google 模型用途混在一起。

## 元件與責任

### Gemini 專案

- 使用 canonical Gemini-only repository 的最新受測程式更新既有 `knowledge-lancedb` 執行環境。
- 保留本機 `data/`、向量快取、專案專用 `source-map.json` 與報告；程式更新前先做雜湊與快照。
- 只允許 `google-gemini`／`gemini-embedding-001`／768 維正式設定。

### 金鑰邊界

- 使用固定 Keychain service/account 儲存 Embedding 專用 Key。
- 設定工具以無回顯方式讀取 stdin，禁止接受命令列金鑰參數。
- 執行器只在子程序記憶體中注入 `GOOGLE_API_KEY`，不回印金鑰；錯誤訊息需遮蔽長 token。
- 缺少 Keychain 項目時，索引與搜尋 fail closed，排程不得標示成功。

### 排程

- Gemini 06:30：只做每日增量索引；以鎖避免重入。
- Gemini 06:50：只在索引健康時建立可驗證快照。
- 兩項工作先建立為 disabled staging，完成讀回驗證後才啟用。
- 啟用 Gemini 前，精確停用 Qwen 兩項 managed jobs；未知工作不得修改。

### 搜尋入口

- 第一階段恢復 Gemini Skill 的來源引用搜尋流程，使用受控腳本呼叫，不宣稱現有 Qwen-only plugin 可直接相容。
- 若後續要讓 `local_knowledge_search` 動態工具同時支援 Gemini，另開獨立 plugin 規格；本次不擴大範圍。

### Qwen 冷備援

- 保留模型、LanceDB、索引狀態、安裝清單、程式 commit、整合交易收據及至少一份已驗證快照。
- 正式切換後只停止服務與停用精確識別的 managed jobs，不 uninstall、不刪檔、不覆寫索引。
- 回復程序必須先停用 Gemini 工作，再啟動 Qwen 服務、啟用 Qwen managed jobs並做搜尋 canary。

## 驗證與放行條件

切換前必須全部通過：

- canonical repo tests、product-boundary、dangerous-exec、dependency audit、secret scan、diff check。
- Keychain 缺失、錯誤金鑰、429、5xx、逾時、向量維度錯誤與快取損壞負向測試。
- Gemini 完整重建後，來源 chunk 數、LanceDB row 數與 index state 精確一致。
- 固定搜尋題庫達到既定 Hit@5／MRR 門檻，且每筆結果含來源路徑。
- 新增一筆測試來源後，06:30 等價增量流程只處理變更資料，之後能搜尋到該內容。
- Gemini 快照建立與隔離還原 canary 通過。
- Qwen 冷備援資產讀回及回復步驟 dry-run 通過。
- cron inventory 最終只能有一組正式 Embedding 增量／快照工作啟用。

## 安全範圍

- 資料分類：內部專案文件、會議／Discord 摘要與已核准的原始備份片段；送往 Google 的只有經既有秘密掃描與隱私規則處理後的 embedding 文字。
- 信任邊界：本機檔案與 LanceDB、macOS Keychain、Google Gemini Embedding API、OpenClaw cron。
- 外部成本：完整重建及後續新 chunk 會使用 Gemini API 額度；快取命中不應重複計費。
- Human Gate：API Key 輸入、正式啟用 Gemini、正式停用 Qwen。
- ASVS：非 Web／API 應用，不建立 Web ASVS register；以 OWASP A01–A10、AI overlay、供應鏈、秘密與復原測試作等價控制。

## 完成定義

本次「前置作業完成」定義為：程式、測試、Keychain 工具、disabled 排程候選、Qwen 冷備援收據與回滾程序均已提交並驗證，系統停在 Jasper 的 API Key 輸入 Gate，Qwen 仍提供正式搜尋。

本次「切換完成」定義為：新 Key canary、Gemini 全量重建、搜尋品質、增量、快照與還原全部通過；Gemini 排程啟用，Qwen 服務與 managed jobs 停止，但所有 Qwen 資產仍完整保留。
