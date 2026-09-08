# Gemini 小快取與安全增量替換｜OWASP 2025 Gate

日期：2026-09-09  
狀態：IMMEDIATE_PASS／自然排程驗收待 2026-09-09 06:30～07:05

本檔是 `docs/superpowers/specs/2026-09-09-gemini-small-query-cache-atomic-incremental-design.md` 的可追溯安全結案表。完成前 A01–A10 只能標 `PASS`、`BLOCKED` 或 `NOT_APPLICABLE_WITH_EVIDENCE`。

## 最終矩陣

- A01 Broken Access Control：PASS—Embedding 專用金鑰只由固定 macOS Keychain service/account 讀取；兩個 Gemini job 以精確 UUID 與 declaration key 讀回，兩個 Qwen job 已精確停用。
- A02 Security Misconfiguration：PASS—文件增量快取與查詢快取分離；共用或缺失路徑 fail closed；搜尋以錯誤 API 金鑰仍可從查詢快取成功，證明不會載入舊 1.2 GB 文件快取或誤呼叫 API。
- A03 Software Supply Chain：PASS—Python 28/28、Node 51/51、語法／編譯檢查通過；`npm audit` 為 0 vulnerabilities，lockfile 與部署來源均已追蹤。
- A04 Cryptographic Failures：PASS—金鑰以無回顯方式輸入 Keychain，只在子程序記憶體注入；目標 secret scan 通過，命令、manifest 與日誌均未記錄金鑰。
- A05 Injection：PASS—路徑 predicate 使用 SQL literal escaping，惡意路徑負向測試與真實 LanceDB partial-add rollback 測試通過。
- A06 Insecure Design：PASS—增量流程先完整產生並驗證新向量，再替換資料；API／向量失敗前不執行 delete/add/state write；單工作鎖、模型身分與 768 維邊界均驗證。
- A07 Authentication Failures：NOT_APPLICABLE_WITH_EVIDENCE—本機 CLI 無使用者認證；秘密存取由 macOS Keychain 與本機帳號邊界負責，A01／A04 驗證。
- A08 Software or Data Integrity：PASS—完整索引 125,509 rows 與 state／manifest 精確一致；封存快取已做內容 hash；2.19 GB Gemini 快照通過 checksum、隔離 restore canary、資料庫開啟與精確 row count 驗證。
- A09 Logging and Alerting：PASS—增量／索引 manifest 可稽核；錯誤以非零退出；Gemini 兩個 job 均有首錯告警，07:05 每日健康報告已啟用且上一輪成功。
- A10 Exceptional Conditions：PASS—API、向量、delete、partial add 與 state-write 故障注入均通過；真實 LanceDB partial add 會清除部分新資料並恢復舊 rows，state 不前移。
- AI Security Overlay：PASS—來源文字只作 embedding 內容、不作工具指令；Embedding 專用 Key 與其他模型用途分離；API 呼叫僅針對新增／變更 chunk，Qwen 回滾資產保留。
- ASVS v5.0.0：NOT_APPLICABLE_WITH_EVIDENCE—非 Web／API 應用，沒有 HTTP 應用端點、session、browser client 或多租戶授權面；等價控制為 OWASP A01–A10、故障注入、供應鏈及復原測試。

## 完成證據

- 完整索引與稽核：5,695 份文件、125,509 chunks／rows，metadata 與 embedding identity 精確一致。
- 搜尋品質：固定 20 題為 19/20，Hit@5 0.95、MRR 0.7083，通過 0.8／0.6 門檻；切換後搜尋第一名命中預期來源。
- 增量 canary：只加入 1 個測試來源／1 個 chunk，可搜尋；移除後只刪除該路徑，rows 回到 125,509。
- 資源：首次 Gemini 搜尋最大 RSS 約 722 MB；查詢快取約 213 KB，舊 1.2 GB 文件快取不再由搜尋載入。
- 快照／還原：`repair-gemini-a-20260909-0105` 與 `daily-2026-09-09` 均通過；每日快照約 2.19 GB，精確恢復 125,509 rows。
- 排程：Gemini 06:30 增量與 06:50 驗證快照已啟用；Qwen 對應 jobs 已停用，Qwen service 已停止但 installed=true，模型、索引與最近有效快照保留。
- 尚待營運觀察：2026-09-09 06:30／06:50 自然排程與 07:05 健康報告。這不影響 immediate cutover PASS，但在自然執行完成前不得宣稱 operational 100%。
- 已知剩餘風險：Qwen 冷備援是 104,346-row 的時間點快照，不是 Gemini 125,509-row 的即時鏡像；它可供緊急回復，但回復後須補索引。
