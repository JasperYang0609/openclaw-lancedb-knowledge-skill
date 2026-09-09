# Gemini 每日快照冪等修復｜OWASP Top 10:2025 Gate

狀態在實作與驗證前一律視為 `BLOCKED`；完成後逐項更新證據。

- A01 Broken Access Control：BLOCKED — 驗證快照名稱、絕對備份根、symlink 與受管子目錄邊界。
- A02 Security Misconfiguration：BLOCKED — 驗證 cron 所需環境、鎖、timezone 與 retention。
- A03 Software Supply Chain Failures：BLOCKED — 只使用既有 Python/Node 相依，執行 dependency audit。
- A04 Cryptographic Failures：BLOCKED — 驗證 manifest 與每個 payload SHA-256。
- A05 Injection：BLOCKED — 無 shell eval；名稱、時間、筆數與 provider/model 使用固定驗證。
- A06 Insecure Design：BLOCKED — 舊快照不可冒充最新；staging 成功後才發布 repair 快照。
- A07 Authentication Failures：NOT_APPLICABLE_WITH_EVIDENCE — 本地快照工具不處理登入；資料與金鑰不寫入參數或報告。
- A08 Data/Software Integrity Failures：BLOCKED — checksum、row-count、freshness、restore-canary 與重跑冪等測試。
- A09 Logging and Alerting Failures：BLOCKED — 非零失敗可由 cron 告警，成功輸出實際採用快照。
- A10 Mishandling of Exceptional Conditions：BLOCKED — 覆蓋同名、過舊、損壞、鎖衝突、部分 staging 與重跑情境。

ASVS v5.0.0：此項是本機 CLI／排程，沒有 Web/API 攻擊面，ASVS requirement register 為 `N/A_WITH_REASON`；以路徑、完整性、例外與還原負向測試替代。
