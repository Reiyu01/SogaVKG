## 1. 專案基礎與 Strict Contracts

- [x] 1.1 整理 backend Python package 與 test layout，加入 MVP runtime/test dependencies，並確認既有 scripts 仍可匯入
- [x] 1.2 建立 QueryType、QueryStatus、SemanticQueryPlan、OrderBy、QueryTraceEvent、RowSource 與 QueryExecution strict domain models
- [x] 1.3 建立設定模型與 example configuration，涵蓋 database path、public fields、default/maximum limit、planning call budget、deadline 與 model endpoint，secrets 僅允許來自環境
- [x] 1.4 新增 strict model unit tests，驗證 unknown fields、無效型別、排序方向、limit 與 raw SQL 欄位會被拒絕

## 2. Asset Query Boundary 與 Builder Safety

- [x] 2.1 建立 Asset-only QueryPolicy，宣告公開 default/selectable/filterable/sortable fields 與 Category/Location relations
- [x] 2.2 實作 BorrowRecord、borrower_email、internal columns、unknown entity/field/relation 的 fail-closed policy validation
- [x] 2.3 最小修改 SemanticQueryBuilder：fields 空白時使用 public defaults，且每個 query 一律套用 default/maximum LIMIT
- [x] 2.4 補強 builder 與 policy tests，涵蓋 relation join、safe defaults、超額 limit、unknown fields、PII boundary 與 SQL injection value parameterization

## 3. Read-only Data Execution

- [x] 3.1 定義 ReadOnlyDatabasePort，讓 query application 無法取得 execute_write 或其他 mutation method
- [x] 3.2 實作 SQLite read-only adapter profile，驗證單一 read query、parameterized execution、row mapping 與 dependency error translation
- [x] 3.3 建立以暫存 SQLite fixture 執行的 adapter tests，驗證正常 rows、無結果、database unavailable、injection 不改變 statement，以及查詢前後資料保持不變
- [x] 3.4 建立 readiness dependency check，驗證 database 可讀、Asset mapping 可載入及必要 public fields 存在

## 4. Bounded Natural-language Planning

- [x] 4.1 定義 planner model port 與版本化 prompts，限制輸出為 query_type 或 strict SemanticQueryPlan，不提供 raw table/schema mutation contract
- [x] 4.2 實作 OpenAI-compatible planner adapter、JSON parsing、一次 bounded repair、call budget 與 wall-clock deadline
- [x] 4.3 實作 conversation、asset_query、unsupported 與 write 分類語意，確保非 asset query 不會進入 database execution
- [x] 4.4 使用 fake model 建立 planner tests，涵蓋有效 Asset plan、unknown plan field、raw SQL、malformed JSON、repair failure、timeout、BorrowRecord、aggregation 與 write request

## 5. QueryService、Grounding 與 Provenance

- [x] 5.1 建立 transport-independent QueryService，串接 classification、planning、policy、builder、read-only execution、grounding 與 elapsed-time trace
- [x] 5.2 將 query rows 轉換為只含公開 fields 的 numbered RowSource，record_key 優先使用 asset_code
- [x] 5.3 建立 grounded answer model port 與 prompt，確保只接收 question、warnings 與本次 RowSources，並將 row text 視為 untrusted data
- [x] 5.4 實作 citation/provenance validation、bounded repair、invalid answer withholding、no_results/insufficient 與 truncated warning
- [x] 5.5 建立 QueryService unit tests，覆蓋 answered、conversation、unsupported、write、invalid_plan、no_results、truncated、dependency failure、prompt injection row 與 invalid citation

## 6. REST API 與 Health Endpoints

- [x] 6.1 建立 FastAPI application lifecycle、dependency wiring，以及 extra-forbid 的 QueryRequest、QueryResponse 與 health response models
- [x] 6.2 實作 POST /api/v1/query，將 request validation、HTTP 422、HTTP 503 與 domain status 映射至公開 contract
- [x] 6.3 實作 GET /api/v1/health/live 與 GET /api/v1/health/ready，readiness 使用 database/mapping dependency check
- [x] 6.4 建立 API contract tests，驗證有效 query、空白/超長 question、unknown request field、unsupported query、no results、safe 503、response fields 與 raw SQL 不外洩

## 7. Quality Evaluation

- [x] 7.1 建立 strict evaluation case/dataset/report models 與 runner，所有 cases 共用 production QueryService
- [x] 7.2 建立 lab MVP evaluation fixture，涵蓋正常 Asset/Location query、required asset_code、no results、unknown field、raw SQL、SQL injection、BorrowRecord/PII、write、invalid citation 與 dependency failure
- [x] 7.3 計算 query-type accuracy、plan validity、required-record recall、expected-field coverage、status accuracy、citation validity、average planning calls 與 average elapsed time
- [x] 7.4 建立 evaluation tests，驗證空/無效 dataset 會失敗、逐案例 checks 可追溯、aggregate 正確且執行前後資料不變

## 8. 文件化與整合驗證

- [x] 8.1 更新 README 與 environment example，記錄安裝、localhost 啟動、API 範例、model 設定、Asset-only/單一可信任使用者限制及目前不具 application auth
- [x] 8.2 執行完整 unit/API/evaluation test suite，修正所有失敗並保存可重現的測試指令
- [x] 8.3 以現有 lab.db 執行唯讀 smoke test，確認資產查詢、無結果、PII 拒絕、health endpoints、source provenance 與資料未變
- [x] 8.4 比對六份 capability specs，確認每個 Requirement/Scenario 都有 implementation 或 test evidence，且 gdrive-rag-cli 未被修改
