# Soga Knowledge Graph Platform

將關聯式資料來源轉成可定義、可建置與可查詢的知識圖譜平台。實驗室資產資料只是目前的示範資料；實體、屬性、關係與資料表皆由 Mapping 定義，不是產品內建的產業模型。

## 目前能力

- 從 SQLite 探勘資料表、欄位、外鍵與樣本資料。
- 在網頁中建立 Entity / Property / Relation Mapping，儲存為 YAML。
- 依 Mapping 將資料匯入 Neo4j，並建立關係與全文索引。
- 以結構化語義查詢或自然語言查詢圖譜資料。
- 檢視 Mapping schema 與圖譜資料。

目前網頁的資料來源精靈已接通 SQLite；Google Sheets、MySQL 與 PostgreSQL 是規劃中的 adapter，不應在未實作前視為可用。

## 本機啟動

1. 建立後端環境並安裝依賴：

   ```bash
   cd backend
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   ```

2. 從範本建立設定檔，填入自己的 Neo4j 與模型服務設定。不要提交 `.env`，也不要將憑證寫入前端程式。

   ```bash
   cp .env.example .env
   ```

3. 啟動 API：

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

4. 啟動前端：

   ```bash
   cd ../frontend
   cp .env.example .env.local
   npm install
   npm run dev
   ```

   若前端與 API 不同網域，設定 `VITE_API_BASE_URL`；若由同一個反向代理提供服務，保留空白即可。後端的 `CORS_ALLOW_ORIGINS` 必須包含前端實際網域。

5. 在「建置資料」頁填入 SQLite 路徑、探勘 schema、確認 Mapping 後啟動建置。建置工作使用該頁送出的來源；也可用 `SQLITE_DB_PATH` 設定部署預設值。這避免將任何範例資料庫路徑寫進程式。示範資料可以由 `backend/scripts/` 的資料清理與匯入流程產生，但不是平台運作的必要前提。

## 驗證

後端語義查詢轉 Cypher 的測試不需要 Neo4j 或示範資料：

```bash
cd backend
python3 -m unittest discover -s tests -v
```

前端檢查：

```bash
cd frontend
npm run lint
npm run build
```

## 下一階段

平台接下來會優先補齊多資料來源 adapter、可部署的工作佇列／工作狀態儲存、Mapping 驗證與版本控制、以及具權限與稽核能力的查詢層。這些能力完成後，才能安全支援跨產業上線。
