## Context

本設計說明如何實作 proposal.md 定義的實驗室唯讀查詢 MVP。SogaVKG 目前有 SQLite 資料、Asset/Category/Location mappings、SemanticMapper 與只產生 SQL 的 SemanticQueryBuilder；尚未有 application service、自然語言 planner、實際 read execution、grounded answer 或 HTTP API。

gdrive-rag-cli 提供可重用的行為與邊界參考，但不是程式碼移植目標：

| gdrive-rag-cli capability | SogaVKG 對應設計 |
|---|---|
| bounded-query-orchestration | NaturalLanguagePlanner + strict SemanticQueryPlan validation |
| grounded-answering | 只根據 query rows 回答、numbered row sources、citation validation |
| product-interfaces | 共用 QueryService、strict REST models、liveness/readiness、422/503 |
| operations-and-recovery | Safe stage trace、dependency readiness、user-safe failure |
| quality-evaluation | 結構化 cases、逐案例 checks 與 aggregate metrics |
| Drive corpus、ingestion、synchronization、retrieval | 不移植；以 Soga mapping 與 read-only structured query 取代 |

目前 BorrowRecord 只有 ontology 與 database table，沒有 mapping，且 table 含 borrower_email。MVP 因此在 query policy 層明確排除 BorrowRecord，而不是依賴「目前沒有 mapping」作為唯一安全措施。

## Goals / Non-Goals

**Goals:**

- 建立 transport-independent QueryService，完成 question 到 answer 的端到端流程。
- 讓 model 只能產生 strict semantic plan，由 application 驗證後再交給既有 builder。
- 強制 Asset-only、parameterized、read-only、bounded-result 與 grounded-answer 邊界。
- 建立可替換 planner/answer model、database 與 interface 的 ports。
- 以 unit、contract 與 evaluation tests 驗證正常路徑及 fail-closed 行為。

**Non-Goals:**

- 不重做現有資料清理、Excel import 或 database schema。
- 不提供 BorrowRecord、個資、write execution、aggregation、multi-hop 或跨系統查詢。
- 不建立 production SSO、RBAC、row-level policy、audit platform 或全校 deployment。
- 不複製 gdrive 的 Drive connector、Elasticsearch、embedding、document chunk 或 sync lifecycle。
- 不在此 change 建立完整 Web UI；REST API 是第一個 interface。

## Required Architecture

```text
POST /api/v1/query
        │
        ▼
Strict QueryRequest
        │
        ▼
QueryService
        ├── classify question
        ├── NaturalLanguagePlanner ──▶ strict SemanticQueryPlan
        ├── QueryPolicyValidator
        ├── SemanticQueryBuilder
        ├── ReadOnlyDatabasePort
        ├── GroundedAnswerGenerator
        └── Citation/Provenance Validator
        │
        ▼
Strict QueryResponse + safe trace + row sources
```

Required responsibilities 是 strict input、bounded planning、scope validation、read-only parameterized execution、grounding、provenance 與 safe observability。具體 framework、provider 與 database 是 Reference Implementation，可在未改變 specs 的前提下替換。

## Reference Implementation

- REST 與 application lifecycle：FastAPI、Uvicorn、Pydantic v2。
- Planner 與 answer generation：OpenAI-compatible Chat Completions，封裝在 project-owned ports 後方；model 與 endpoint 由環境設定。
- Data source：既有 SQLite database 與 SQLiteAdapter，但 query application 只依賴新的 ReadOnlyDatabasePort。
- Semantic translation：沿用 SemanticMapper 與 SemanticQueryBuilder，補上 safe default fields、mandatory limit 與輸入 models。
- Tests：pytest、FastAPI TestClient，model 與 database failure 使用 fakes/mocks。
- 第一階段 server 預設綁 localhost；外部暴露與正式 caller authentication 留待後續 change。

## Decisions

### Decision: 建立共用 QueryService，而不是在 route 中直接串接元件

QueryService 負責分類、規劃、政策驗證、build、execute、grounding 與 trace，使 REST、未來 Web UI 或 CLI 使用相同安全語意。替代方案是在 FastAPI route 直接呼叫 builder；該方案會讓未來介面重複邏輯，也更容易繞過 boundary，因此不採用。

### Decision: Model 只輸出 SemanticQueryPlan

Planner output 採 extra-forbid 的 strict model，允許 entity、fields、filters、order_by 與 limit。任何 sql、table、operator fragment、mutation action 或 unknown field 都使 plan 無效；可進行有限一次 repair，但總 call count 與 deadline 仍受設定限制。

替代方案是 text-to-SQL。它會把 schema access、SQL dialect 與安全責任交給不可預測 output，無法符合 Asset-only 與 fail-closed requirements，因此不採用。

### Decision: Query policy 與 mapping 分層

Mapping 回答「semantic field 如何對應來源」，QueryPolicy 回答「目前產品允許查什麼」。即使未來新增 BorrowRecord mapping，MVP policy 仍會拒絕它。公開 Asset fields、relations、filterable/sortable fields 與 public defaults 由明確 policy 宣告。

替代方案是只依賴 mapping 是否存在；mapping 是資料整合資訊，不是 caller authorization，無法支撐未來全校 field/row-level policy，因此不採用。

### Decision: 建立獨立 ReadOnlyDatabasePort

Application service 只取得 query 方法，不取得 execute_write。SQLite Reference Adapter 使用 read-only connection profile，並在執行前確認 statement 為單一 read query；資料值一律使用 parameters。現有 DatabaseAdapter 可以保留供 import/admin path 使用，但不得注入 query application。

替代方案是直接使用現有同時暴露 execute_write 的 adapter；這會擴張 application capability，違反 least privilege，因此不採用。

### Decision: 修正 builder 的安全預設與 limit

現有 builder 在 fields 空白時使用 alias wildcard，且只有 caller 提供 limit 時才產生 LIMIT。Apply 階段將以最小修改改為 public default fields，並保證每個 query 都有 configured limit；原有 field/relation mapping 與 parameterized filter 行為保留。

### Decision: Row provenance 取代 Drive 文件 citation

每個實際用於回答的 Asset row 轉為 numbered source，至少包含 entity=Asset、record_key（優先 asset_code）與公開 fields。Answer 只能引用本次 sources；citation 或 record provenance 無效時 withholding。因 Soga source 沒有文件 URL、頁碼或 chunk index，不複製 gdrive 的 locator contract。

### Decision: 同一個 provider abstraction 支援 planning 與 answer

Reference Implementation 使用 OpenAI-compatible endpoint，但以不同 prompt 與 strict output contract區分 planning 和 answering。Provider secret 只從環境取得，不寫入 YAML 或 response；tests 使用 fake model，不要求網路。

替代方案是第一版只用 hard-coded keyword parser。它能處理少數 demo，但無法符合自然語言 query 目標；仍可作為未來可替換 planner，而不是目前 canonical implementation。

### Decision: REST contract 採同步 request 與完整 JSON response

MVP 的 POST /api/v1/query 回傳完成後的 answer、validated plan、sources 與 trace，不提供 streaming 或 conversation history。這降低第一版生命週期與 session 複雜度；後續 Web UI 可在不繞過 QueryService 的前提下新增 streaming presentation。

## Data Flow

```text
1. API 驗證 question 與 unknown fields
2. QueryService 建立 deadline 與 trace
3. Planner 分類 query_type
4. asset_query → 產生 strict SemanticQueryPlan
5. QueryPolicyValidator 驗證 Asset scope 與 public fields
6. SemanticQueryBuilder 建立 parameterized read query
7. ReadOnlyDatabasePort 執行並套用 hard maximum limit
8. Rows 轉為 numbered provenance sources
9. 無 rows → no_results / insufficient
10. 有 rows → GroundedAnswerGenerator 只讀取 question、warnings 與 sources
11. 驗證 citations；無效則 bounded repair 或 withholding
12. API 回傳 QueryResponse
```

對 conversation 可直接回覆且不得宣稱資料庫事實。對 unsupported、write、invalid_plan 或 planning budget exhaustion，不連線執行 database query。Dependency exception 只寫入 server log，public response 為 generic 503。

## Trust and Privacy Boundaries

- Question、planner output、database text fields 與 model output 都是不可信輸入。
- QueryPolicyValidator 是 planner 與 database 之間的 mandatory boundary。
- ReadOnlyDatabasePort 是 application 與 persistent data 之間的 least-privilege boundary。
- BorrowRecord、borrower_email、internal ids、foreign keys 與 source_sheet 不進入 plan、row sources、answer 或 trace。
- Model 只接收 validated public row fields；不傳 raw database、raw SQL、credentials 或未選資料列。
- Safe trace 只記錄 stage、status、counts、warnings 與 elapsed time。

## Failure Flow

```text
Invalid HTTP input ───────────────▶ HTTP 422 / no planning
Unsupported or write question ───▶ HTTP 200 status=unsupported / executed=false
Invalid planner output ──────────▶ bounded repair ─▶ refused / executed=false
Scope or field violation ────────▶ invalid_plan or refused / no database call
Database or model unavailable ───▶ generic HTTP 503
No matching rows ────────────────▶ HTTP 200 insufficient=true / sources=[]
Invalid answer citation ─────────▶ bounded repair or answer withholding
```

## Future Whole-school Extension Points

- QueryPolicy 可加入 authenticated principal、role、department、purpose 與 field/row-level decisions。
- ReadOnlyDatabasePort 可由 PostgreSQL、API adapter 或校務整合平台取代。
- Semantic mappings 可增加其他校務 entities，但每一 capability 仍需獨立 OpenSpec change。
- Safe trace 可接入 audit/event platform；在此之前不宣稱具有正式稽核能力。
- REST contract 可由 gateway/SSO 保護，但 CORS、localhost bind 或 reverse proxy 不能取代 application authorization。

## Risks / Trade-offs

- [Risk] Model 產生不穩定或惡意 plan → strict schema、policy validation、bounded repair、deadline 與 fail closed。
- [Risk] 現有 builder 的 wildcard/default-limit 行為洩漏欄位或回傳過多 rows → apply 時先修正 builder 並加入 regression tests。
- [Risk] Existing adapter 暴露 write method → QueryService 只依賴獨立 read-only port，tests 驗證 mutation path 不可達。
- [Risk] Grounded answer 仍可能扭曲 row 內容 → numbered provenance、citation validation、no-results refusal 與 evaluation cases。
- [Risk] 單一可信任使用者部署被誤用於全校環境 → README、readiness 與 deployment 文件明示限制；全校化前建立新的 auth/governance change。
- [Trade-off] Asset-only 降低第一版問題覆蓋率 → 以明確 unsupported response 換取可驗證安全邊界，之後逐 capability 擴張。

## Migration Plan

1. 建立 package/configuration 與 strict domain/API models，不修改既有資料。
2. 建立 policy、read-only port 與 builder safety changes，以 existing SQLite fixture 驗證。
3. 建立 planner、QueryService、grounded answer 與 citation validation。
4. 建立 REST app、health endpoints 與 contract tests。
5. 建立 evaluation dataset 與 CLI/test entrypoint，完成所有 safety cases。
6. 在 localhost 啟動 lab deployment，先以只含非個資的 Asset queries 驗收。

本 change 不需要 database schema migration。Rollback 可停用新 API process 並移除新增 application modules；既有 SQLite、import scripts、ontology、mappings 與原始資料維持不變。

## Open Questions

- 實驗室部署實際使用的 OpenAI-compatible endpoint 與 model 名稱可於 apply/deployment 時由環境設定，不影響 interface 或安全 contract。
- 第一個 Web UI 的呈現方式與品牌設計留待後續 change；本 change 只確保所有未來介面共用 QueryService。
