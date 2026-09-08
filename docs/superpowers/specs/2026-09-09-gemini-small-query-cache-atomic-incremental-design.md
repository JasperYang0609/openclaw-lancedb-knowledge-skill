# Gemini 小型查詢快取與安全增量替換設計

日期：2026-09-09  
狀態：已切換／自然排程觀察中
母規格：`2026-09-08-gemini-cold-standby-reactivation-design.md`

## 問題與決策

Gemini 已完成 125,509 筆索引且完整性稽核通過，但舊版把文件向量與查詢向量放在同一個大型 JSONL 快取。每次搜尋都同步載入整份約 1.2 GB 快取，會造成不必要的記憶體尖峰。現行增量流程也會先刪除舊資料，再呼叫 Gemini 產生新向量；若 API 或程序中途失敗，已可搜尋的舊資料會暫時消失。

選定 A 方案：

- 搜尋改用獨立、只保存查詢向量的小型快取，不讀取大型文件快取。
- 每日增量改用新的小型文件增量快取；舊大型文件快取只封存，不再由日常搜尋或增量載入。
- 所有新增／變更 chunk 的 Gemini 向量必須先完整產生並驗證，才能替換 LanceDB 舊資料。
- 替換期間若寫入失敗，恢復受影響路徑的舊資料；索引狀態只在資料替換成功後更新。
- Qwen 在 Gemini 搜尋、增量、快照與還原全部通過前保持正式服務；通過後只停止服務與排程，資產不刪除。

## 檔案與相容策略

- `embedding.cachePath`：新的日常文件增量快取。
- `embedding.queryCachePath`：新的查詢專用快取。
- 舊 1.2 GB 快取保留為只讀封存檔，透過收據記錄路徑、大小與 SHA-256；不複製、不刪除、不載入。
- 未設定 `queryCachePath` 的舊設定會導出獨立的 `.queries.jsonl`，不得回退共用 `cachePath`。
- 未來若要全量重建，預設重新呼叫 Gemini；封存快取只有在另案完成磁碟式讀取器後才可重用。

## 增量替換狀態機

1. 掃描來源並計算 changed／removed paths。
2. 先為所有 changed chunks 產生且驗證向量；任何失敗均不得刪除 LanceDB 資料或更新 state。
3. 讀取並暫存受影響路徑的舊 rows。
4. 刪除 changed／removed paths，寫入所有新 rows。
5. 若步驟 4 失敗，刪除受影響路徑的部分寫入並恢復舊 rows；state 保持原值。
6. 只有替換成功才原子寫入 index state 與 manifest。

## 安全範圍與威脅模型

- 資產：Gemini API 額度、Keychain 金鑰、LanceDB、索引狀態、來源文件、Qwen 冷備援。
- 資料分類：內部文件與 Discord 備份片段；仍沿用既有秘密掃描與隱私核准 Gate。
- 信任邊界：本機程式／檔案、macOS Keychain、Google Gemini API、OpenClaw 排程。
- 主要濫用／失敗情境：惡意或超大查詢灌爆快取、API 部分成功、程序中斷、磁碟寫入失敗、錯誤快取路徑讀取封存檔、重複排程、舊資料刪除後新資料未寫成。
- 最大損害：搜尋停機、索引資料缺口、API 額度異常消耗、秘密外洩。
- 控制：快取分離、輸入與向量驗證、單工作鎖、先算後換、失敗補償、state 最後提交、Qwen 回滾與金鑰不落盤。
- ASVS v5.0.0：非 Web／API 應用，`NOT_APPLICABLE_WITH_EVIDENCE`；以本文件 OWASP、故障注入、供應鏈與復原測試作等價控制。

## OWASP Top 10:2025 驗證計畫

- A01：本機檔案與 Keychain 權限、排程精確身分；待實機讀回。
- A02：舊快取不得被搜尋／增量載入，缺少必要設定 fail closed。
- A03：lockfile、依賴 audit、Skill 封裝與來源 diff。
- A04：金鑰只由 Keychain 注入；secret scan 與 log redaction。
- A05：SQL path predicate escaping、查詢／路徑負向測試。
- A06：成本上限、單一工作、Qwen fallback、不可混用不同模型向量。
- A07：非認證系統，`NOT_APPLICABLE_WITH_EVIDENCE`；Keychain 是秘密存取邊界。
- A08：封存快取 SHA-256、索引 row/state readback、快照與隔離還原。
- A09：增量 manifest、錯誤非成功、排程健康報告不得含秘密。
- A10：API／寫入故障時不先刪資料；部分寫入補償與重跑冪等。
- AI Security Overlay：不信任來源文字；不把內容當指令；Embedding 專用 Key 最小權限；API 成本與批次受控。

## 驗收條件

- 搜尋程序不開啟舊大型文件快取，記憶體不再隨該檔大小線性增加。
- 查詢重複執行命中小型查詢快取，不重複呼叫 Gemini。
- 增量向量失敗前，LanceDB delete／add／state write 次數均為 0。
- LanceDB add 失敗後，受影響舊 rows 恢復且 state 不變；重跑不產生重複 rows。
- Gemini 125,509-row 基準、搜尋題庫、人工新增來源增量、快照／隔離還原全部通過。
- Gemini 排程啟用且 Qwen managed jobs／服務停止；Qwen 模型、索引、快照與回滾收據完整。

## 回滾

任一驗收失敗時不切換；若已切換，先停用 Gemini 工作，再依冷備援收據啟動 Qwen 服務與兩個精確 managed jobs，執行搜尋 canary。Gemini 索引與快取保留供診斷，不自動刪除。
