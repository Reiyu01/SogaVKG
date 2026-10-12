# Soga Visual Knowledge Graph（SogaVKG）

SogaVKG 是把分散的表格資料轉成可理解、可探索、可查詢知識圖譜的工作平台。它不綁定特定產業：實驗室資產、設備借用、研究紀錄、客戶資料或營運清單，都可用 Mapping 定義成自己的資料模型。

平台目前採用**即時投影（read-only projection）**。資料繼續留在 SQLite、PostgreSQL 或 Google Sheets；系統依 Mapping 讀取並顯示圖譜，發布時不會將來源資料複製到另一套圖資料庫。

## 想解決什麼問題？

日常資料通常散落在試算表、資料庫與不同團隊的表格中。即使欄位名稱相近，例如 `asset_code`、`設備編號`、`設備代碼`，系統也不知道它們是否代表同一個概念；使用者得自行理解外鍵、表格關係與資料位置。

SogaVKG 讓資料具有一致且可查詢的語意：

- 用 **Entity（實體）** 表示業務概念，例如設備、人員、專案、借用紀錄。
- 用 **Property（屬性）** 將來源欄位對應到可讀的概念欄位。
- 用 **Relation（關係）** 將來源欄位連成圖譜，例如「借用紀錄 → 借用人員」。
- 用 **Identity Mapping（概念對齊）** 標示不同來源的實體是相同概念，例如 `GoogleSheetAsset.asset_code` 與 `Asset.asset_code`。
- 以圖譜瀏覽、結構化條件或自然語言查詢，從「資料表與欄位」提升到「我想找什麼資訊」。

## 目前能力

| 能力 | 說明 |
| --- | --- |
| 專案工作區 | 將來源、Mapping、建置紀錄與查詢限制在同一個專案。 |
| 資料來源 | 探勘 SQLite、PostgreSQL 與 Google Sheets 的表格／工作表、欄位與樣本資料。 |
| 視覺化 Mapping | 在網頁建立實體、屬性、主鍵與關係對應，並儲存為專案內 YAML。 |
| 發布前檢查 | 驗證欄位、關係目標與重複主鍵；預覽節點數、缺少主鍵、未匹配關係等資料品質資訊。 |
| Mapping 版本 | 每次發布建立不可變版本，可檢視紀錄並還原為草稿。 |
| 圖譜探索 | 顯示概念圖、資料節點、節點屬性與關係展開。 |
| 查詢 | 使用 Mapping 驅動的唯讀查詢；設定相容模型服務後可使用自然語言查詢。 |

目前尚未提供 MySQL adapter、使用者／角色權限、持久化背景工作佇列，以及正式環境的每專案 Neo4j 隔離。詳見 [TODO.md](TODO.md)。

## 核心流程

```text
來源資料（SQLite / PostgreSQL / Google Sheets）
                    │
                    ▼
         Mapping：實體、欄位、主鍵、關係
                    │
          驗證、預覽、發布版本
                    │
                    ▼
      即時圖譜投影 ───► 圖譜瀏覽 / 結構化查詢 / AI 查詢
```

發布的是 Mapping 定義與品質摘要，不是資料副本。因此來源資料更新後，圖譜與查詢會讀取最新資料；同時，發布紀錄會保留當時使用的 Mapping 版本，讓結果可追溯。

## 快速開始

### 1. 啟動後端

需要 Python 3。於專案根目錄執行：

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

`.env` 中的 `MY_MODEL_*` 只在使用自然語言查詢時需要設定。`SQLITE_DB_PATH` 是舊有單一來源流程的可選預設值；新版專案流程請直接在介面建立資料來源。

### 2. 啟動前端

另開一個終端機：

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

預設前端網址為 `http://localhost:5173`。若 API 不在同一網域，於 `frontend/.env.local` 設定：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

後端的 `CORS_ALLOW_ORIGINS` 也必須包含實際前端網址。

## 操作方式

### 1. 建立專案

從首頁建立專案。專案是資料來源、Mapping、發布版本與圖譜查詢的隔離單位；不同資料主題應建立不同專案。

### 2. 新增資料來源

進入專案的「資料來源／建置資料」頁，選擇類型並儲存設定。

- **SQLite**：提供後端主機可讀取的資料庫檔案路徑。
- **PostgreSQL**：提供 host、port、database、username 與存放密碼的環境變數名稱（`credential_ref`）。
- **Google Sheets**：提供 Spreadsheet ID，以及存放 service account JSON 的環境變數名稱（`credential_ref`）。將 service account 的 email 加入試算表共用名單，至少給予檢視者權限。

憑證只應存在後端環境變數或秘密管理服務，絕不可放進 Mapping、Git 或前端程式。

### 3. 探勘資料並建立 Mapping

讀取 schema 後，選擇要納入的表格／工作表。對每個實體確認：

1. 實體名稱與顯示名稱。
2. 來源表與資料來源。
3. 唯一且非空的主鍵。
4. 要公開於圖譜和查詢的屬性欄位。
5. 關係的來源欄位（foreign key）、目標實體與目標鍵。

Google Sheets 通常沒有資料庫外鍵，請依欄位意義手動新增關係。

### 4. 驗證、預覽與發布

在建置頁按發布後，系統會依序儲存 Mapping、驗證欄位與關係、預覽資料品質、要求確認，最後建立 Mapping 版本與建置紀錄。

「缺少主鍵」、「重複主鍵」與「未匹配關係」都是來源資料品質訊號，應優先修正；否則部分資料無法成為節點或關係。

### 5. 探索與查詢

發布完成後，前往「知識圖譜」檢視實體、節點與關係；前往「AI 查詢」以條件或自然語言尋找資料。自然語言查詢只會依已發布的 Mapping 解讀資料，因此 Mapping 越精確，結果越可靠。

## Google Sheets 注意事項

Google Sheets API 有每分鐘讀取額度。平台會快取短時間內的 schema 與資料快照，並只讀取 Mapping 用到的工作表；仍建議避免短時間內連續按下探勘、驗證、預覽與發布。

若出現 `429 Quota exceeded`：

1. 等候至少一分鐘後再試。
2. 確認後端已重啟至最新程式碼。
3. 檢查是否有其他服務帳號或使用者共用同一 Google Cloud 專案額度。

## 驗證與檢查

後端測試不需要 Neo4j 或示範資料：

```bash
cd backend
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

前端檢查：

```bash
cd frontend
npm run lint
npm run build
```

## 專案結構

```text
backend/app/          FastAPI API、資料來源 adapter、Mapping 與圖譜服務
frontend/src/         React 操作介面
semantic/projects/    各專案的 Mapping YAML
backend/data/         示範資料與平台狀態資料庫（本機開發）
backend/tests/        後端自動化測試
TODO.md               已完成與規劃中的功能
```
