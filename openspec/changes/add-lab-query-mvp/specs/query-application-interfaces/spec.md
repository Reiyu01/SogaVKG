## Purpose

定義實驗室 MVP 對使用者與外部 client 公開的 versioned REST query、健康狀態、輸入驗證、回應欄位與錯誤契約。

## ADDED Requirements

### Requirement: REST query request 使用 versioned strict contract
系統 SHALL 提供 POST /api/v1/query，接受 1 至 8000 字元的非空 question，並 MUST 拒絕空白 question、unknown request fields 與超過限制的內容；MVP request 不接受 conversation history。

#### Scenario: 提交有效問題
- **GIVEN** request body 只含有效非空 question
- **WHEN** client 呼叫 POST /api/v1/query
- **THEN** 系統 SHALL 執行共用 query service 並回傳符合 response contract 的 JSON

#### Scenario: 提交未知欄位
- **GIVEN** request body 含未宣告欄位
- **WHEN** API 驗證 request
- **THEN** API SHALL 回傳 HTTP 422 validation error，且不得執行 query

### Requirement: Query response 揭露結果與執行狀態
成功處理的 query response SHALL 包含 answer、query_type、status、executed、insufficient、plan、row_count、truncated、warnings、elapsed_ms、trace 與 sources；公開 plan MUST 是 validated semantic plan，不得包含 raw SQL。

#### Scenario: Asset query 成功
- **GIVEN** query service 完成一個具有結果的 Asset query
- **WHEN** API 建立 response
- **THEN** API SHALL 回傳 HTTP 200、status=answered、executed=true，以及與 answer 對應的 sources

#### Scenario: 有效但不支援的問題
- **GIVEN** request contract 有效但問題要求 MVP 不支援的能力
- **WHEN** query service 完成分類
- **THEN** API SHALL 回傳 HTTP 200、status=unsupported、executed=false 與明確 warning

### Requirement: Validation 與 dependency failure 可區分
API SHALL 將 request contract violation 回報為 HTTP 422，將 required runtime dependency 無法完成 query 回報為 HTTP 503，且兩者都不得揭露內部 exception。

#### Scenario: Database dependency failure
- **GIVEN** request 已通過 interface validation
- **WHEN** database dependency 使 query execution 無法完成
- **THEN** API SHALL 回傳 HTTP 503 與 generic user-safe error detail

### Requirement: 提供 liveness endpoint
系統 SHALL 提供 GET /api/v1/health/live，僅反映 application process 是否可回應，不得執行完整 query。

#### Scenario: Process 可回應
- **GIVEN** application process 正常運作
- **WHEN** client 呼叫 GET /api/v1/health/live
- **THEN** API SHALL 回傳 HTTP 200 與 status=ok

### Requirement: 提供 readiness endpoint
系統 SHALL 提供 GET /api/v1/health/ready，驗證 query 所需 database 與 semantic mappings 可用；任一必要 dependency 不可用時 SHALL 回傳 HTTP 503。

#### Scenario: Semantic mappings 不可用
- **GIVEN** required Asset mapping 無法載入或驗證
- **WHEN** client 呼叫 GET /api/v1/health/ready
- **THEN** API SHALL 回傳 HTTP 503 與 user-safe dependency error

### Requirement: 所有 query interfaces 共用相同 service semantics
若未來增加 Web UI 或 CLI，所有 interfaces MUST 共用相同 query service、boundary、grounding、status 與 source semantics，不得以介面差異繞過 validation 或資料範圍。

#### Scenario: 新 interface 呼叫 query
- **GIVEN** deployment 新增非 REST interface
- **WHEN** 該 interface 執行使用者問題
- **THEN** 它 SHALL 使用與 REST endpoint 相同的 query service contract 與安全邊界
