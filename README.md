# SogaVKG Lab Query MVP

SogaVKG 目前提供實驗室規模的唯讀自然語言資產查詢應用。問題先轉換成 strict
SemanticQueryPlan，通過 Asset-only policy 後，由既有 SemanticMapper 與
SemanticQueryBuilder 建立 parameterized SQL，再以 SQLite read-only connection
執行。回答只可使用本次回傳 rows，並附上 numbered row sources。

## 目前範圍與限制

- 根實體只支援 Asset，可讀取公開 Category 與 Location 顯示欄位。
- 公開欄位：asset_code、name、quantity、status、specification、note、category、location。
- BorrowRecord、borrower_email、internal IDs、foreign keys、來源工作表欄位、
  aggregation、multi-hop 與所有寫入操作均不支援。
- Model 只能產生 strict semantic plan，不得產生或執行 raw SQL。
- 每次 query 都有 default/maximum limit；answer citation 只可指向本次 sources。
- 本 MVP 只適用單一可信任使用者與 localhost 實驗室部署。
- **目前沒有 application authentication、SSO、RBAC、field/row-level
  authorization 或正式 audit，不得直接暴露為全校 production service。**

全校化前須以後續 OpenSpec changes 定義 authentication、授權、資料治理、
master data、audit 與 additional source adapters。

## 安裝與設定

~~~bash
cd /home/openclawuser/SogaVKG/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export SOGAVKG_MODEL_API_KEY='your-api-key'
export SOGAVKG_MODEL_BASE_URL='https://api.openai.com/v1'
export SOGAVKG_MODEL_NAME='gpt-4.1-mini'
~~~

所有設定使用 SOGAVKG_ 環境變數，範例在 repository root 的 .env.example。
Real API key 只應由 process environment 提供，不可寫入 YAML、source code 或 response。
相對的 database/mapping path 會以 repository root 解析。

主要 bounded settings：

- SOGAVKG_DATABASE_PATH：預設 backend/data/lab.db
- SOGAVKG_MAPPING_DIR：預設 semantic/mappings
- SOGAVKG_DEFAULT_LIMIT：預設 20
- SOGAVKG_MAXIMUM_LIMIT：預設 100
- SOGAVKG_PLANNING_MAX_CALLS、SOGAVKG_ANSWER_MAX_CALLS：最多 2
- SOGAVKG_PLANNING_DEADLINE_SECONDS、SOGAVKG_ANSWER_DEADLINE_SECONDS

## 啟動 localhost API

~~~bash
cd /home/openclawuser/SogaVKG/backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
~~~

若 localhost lab 以 repository root 的 `.env` 保存非提交設定，啟動時加上
`--env-file ../.env`；`.env` 已由 Git 忽略。正式環境仍應由 process environment
或 secret manager 注入 secret。

~~~bash
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
curl -X POST http://127.0.0.1:8000/api/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"C217 5-3-1 有哪些 ESP32-CAM？"}'
~~~

live 只表示 process 可回應；ready 驗證 lab.db 可讀、Asset mapping 可載入與必要
公開欄位存在。Readiness 不進行 model call。

POST /api/v1/query 只接受 question 一個欄位，內容須為 1 至 8000 字元。Unknown
fields、空白與超長內容回 HTTP 422。Unsupported/write query 以 HTTP 200 回傳
domain status 且 executed=false；database/model dependency failure 回 generic HTTP
503，不揭露 path、raw SQL、credential 或 stack trace。

Response 包含 answer、query_type、status、executed、insufficient、validated plan、
row_count、truncated、warnings、elapsed_ms、safe trace 與 numbered sources，且不包含
raw SQL。未設定 SOGAVKG_MODEL_API_KEY 時 health endpoints 仍可使用；需要 model 的
Asset query 會安全回 HTTP 503。

## 測試與 evaluation

~~~bash
cd /home/openclawuser/SogaVKG/backend
.venv/bin/pytest
.venv/bin/python -m scripts.run_evaluation evaluation/lab_mvp.json
~~~

Evaluation fixture 涵蓋正常 Asset/Location、required asset code、no results、
unknown field、raw SQL、SQL injection value、BorrowRecord/PII、write、invalid
citation 與 dependency failure。CLI 使用相同 production QueryService；fault
injection 的 deterministic 驗證位於 tests/test_evaluation.py。

在健康 production runtime 執行 CLI 時，`invalid-citation` 與
`dependency-failure` 不會自行注入故障，因此不納入 live 上線 gate；這兩案應以
`tests/test_evaluation.py` 的 deterministic fault profiles 驗證。

Report 包含 query-type accuracy、plan validity、required-record recall、
expected-field coverage、status accuracy、citation validity、average planning
calls 與 average elapsed time。

## 建立或更新 lab.db

以下保留既有資料流程；query application 不會呼叫 mutation scripts。

1. 確認 backend/scripts/clean_data/ 下有兩份原始 Excel。
2. 執行 clean_ucl_data.py，輸出 backend/data/raw/輸出.xlsx。
3. 在 backend/ 執行：

   ~~~bash
   .venv/bin/python scripts/init_database.py
   .venv/bin/python scripts/import_excel.py
   ~~~

4. 驗證既有 builder：

   ~~~bash
   .venv/bin/python -m scripts.test_query_builder
   ~~~

Builder demo 可參考 backend/scripts/demo情境範本.md。資料匯入/admin scripts 與
query application 的 ReadOnlyDatabasePort 維持分離。
