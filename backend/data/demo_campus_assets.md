# 校園設備模擬資料庫

資料庫檔案：`/home/b225nkust/SogaVKG/backend/data/demo_campus_assets.db`

在 Builder 的 SQLite Path 欄位填入上方完整路徑，選擇「探勘 Schema」後，系統會讀出下列關聯：

```text
categories ──< assets >── locations
                  │
                  ├──< borrow_records
                  └──< maintenance_records
```

| 資料表 | 筆數 | 說明 |
|---|---:|---|
| `locations` | 5 | 校內實驗室、教室與資訊中心位置 |
| `categories` | 5 | 感測器、網路、運算、多媒體、實驗儀器分類 |
| `assets` | 20 | 核心設備資料，具有 `category_id` 與 `location_id` 外鍵 |
| `borrow_records` | 8 | 設備借用紀錄，具有 `asset_id` 外鍵 |
| `maintenance_records` | 4 | 維護紀錄，具有 `asset_id` 外鍵 |

建置後可在 AI 檢索頁測試：

- `C217 有哪些資產？`
- `哪些設備正在維護中？`
- `列出感測器類的設備名稱與數量`
- `哪些資產目前被借用？`
- `3D 印表機的維護紀錄是什麼？`
- `資訊中心有哪些運算設備？`

原始建檔 SQL 位於同目錄的 `demo_campus_assets.sql`。若想把資料庫還原為預設模擬資料，可在此目錄執行：

```bash
sqlite3 demo_campus_assets.db < demo_campus_assets.sql
```
