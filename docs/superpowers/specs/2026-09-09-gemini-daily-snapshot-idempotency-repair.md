# Gemini 每日快照冪等修復規格

## 問題

人工驗收曾先建立正式名稱 `daily-YYYY-MM-DD`。06:30 Gemini 增量完成後，06:50 排程因同名目錄已存在而安全失敗；既有快照也早於最新索引，不能當成今日有效復原點。

## 核准範圍

- 每日排程先讀取並驗證當日 Gemini incremental manifest。
- 快照必須晚於 `indexedAt`，且資料庫筆數必須等於 `rowsAfter` 與目前索引筆數。
- 同名快照若已完整且最新，冪等成功，不重複複製。
- 同名快照若過舊或不可信，保留原目錄不覆寫，另建 deterministic `repair-YYYY-MM-DD-*` 快照並做 checksum、資料庫開啟與隔離還原驗證。
- 人工／測試快照只能使用 `repair-*` 或 `incident-*` 名稱，不再占用正式 `daily-*` 名稱。
- 不重建 Gemini 索引、不呼叫 embedding API、不異動 Qwen 冷備援。

## 失敗與恢復

- manifest 缺失、provider/model 不符、筆數不一致、鎖被占用、既有與替代快照都不可信時，一律非零退出。
- 新快照仍採 staging 後原子搬移；舊快照永不原地覆寫或刪除。
- 重跑會驗證並重用相同 deterministic 快照，不製造無限副本。

## 驗收

- 同名最新快照重跑成功且不新增副本。
- 同名過舊快照保留，建立並重用最新 repair 快照。
- 路徑穿越、錯誤 provider/model、manifest/索引筆數不一致與未帶時區時間均 fail closed。
- 完整測試、安全掃描、實機快照、隔離還原、排程 readback 皆通過。
