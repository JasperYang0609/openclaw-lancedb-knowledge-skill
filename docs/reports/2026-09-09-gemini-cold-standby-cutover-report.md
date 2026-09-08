# Gemini 正式切換／Qwen 冷備援報告

日期：2026-09-09  
狀態：IMMEDIATE_PASS／OPERATIONAL_PENDING

## 結論

Gemini `gemini-embedding-001` 768 維索引已成為正式搜尋與每日增量來源。Qwen 的服務與兩個 managed jobs 已停止，但模型、程式、索引與驗證快照均保留，沒有 uninstall 或刪除。立即驗收全部通過；只剩 2026-09-09 06:30、06:50 與 07:05 的自然排程觀察。

## 驗收證據

- 全量：5,695 份文件、125,509 rows；metadata 與 embedding identity 精確一致。
- 搜尋：固定題庫 19/20，Hit@5 0.95、MRR 0.7083；切換並停止 Qwen 後，Gemini 搜尋仍以預期來源排名第一。
- 增量：人工來源 canary 只增加 1 row，可被搜尋；移除後恢復 125,509 rows。沒有全量重建。
- 故障安全：所有新向量先完成才替換；真實 LanceDB partial-add 測試會恢復舊 rows，state 不前移。
- 快取：查詢快取與文件增量快取分離；舊約 1.2 GB 文件快取保留封存且不再由搜尋載入。
- 快照：Gemini repair 與 daily 快照均通過 checksum、restore canary、資料庫開啟與精確 row count；daily 快照約 2.19 GB。
- 排程：Gemini 增量 06:30、快照 06:50 已啟用；Qwen 對應工作已停用；07:05 每日健康報告維持啟用。
- Qwen：status 為 installed=true、running=false；最近有效快照可開啟並有 104,346 rows。
- 測試：Python 28/28、Node 51/51；dependency audit 0 vulnerabilities；目標 secret scan PASS。

## 尚待與風險

- 自然排程尚未發生，因此目前是 OPERATIONAL_PENDING；07:05 健康報告完成後才能標為 operational 100%。
- Qwen 冷備援是可回復的時間點版本，不是 Gemini 的即時鏡像；緊急回復後需補索引。
- 舊大型 Gemini 文件快取仍佔磁碟空間，但保留可降低未來查核風險；本次不刪除。

## 回滾

若 Gemini 自然排程或搜尋失敗：先停用兩個 Gemini managed jobs，再啟動 Qwen service 與兩個精確 Qwen managed jobs，完成 Qwen 搜尋 canary 後才恢復對外使用。禁止同時啟用兩套正式排程。
