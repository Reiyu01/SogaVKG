## Purpose

定義已驗證 semantic query plan 如何安全轉換並執行為唯讀、參數化且結果有上限的資料查詢，以及依賴失敗時的可觀察行為。

## ADDED Requirements

### Requirement: 執行前再次驗證 semantic plan
系統 MUST 在建立資料查詢前，依目前 entity、property、relation、filter、sort 與 limit allowlist 驗證完整 plan；任一項目無法驗證時不得執行。

#### Scenario: Plan 引用未知 property
- **GIVEN** plan 的 fields 含未定義 property
- **WHEN** query execution 準備建立查詢
- **THEN** 系統 SHALL 停止並回傳 invalid_plan，且不得連線執行資料查詢

### Requirement: 所有使用者值必須參數化
系統 MUST 將 filter values 與其他使用者來源值作為 query parameters 傳入，不得將其直接串接為可執行 statement 的 identifier、operator 或語法。

#### Scenario: Filter value 含 SQL injection 字串
- **GIVEN** 使用者問題使 filter value 包含 SQL control characters
- **WHEN** 系統建立並執行查詢
- **THEN** 該內容 SHALL 只被當作資料值，且不得改變 query structure、讀取額外資料或執行 mutation

### Requirement: Application query path 僅允許唯讀執行
系統 MUST 只執行通過驗證的 read query，且 MUST NOT 從 query application path 暴露或呼叫 INSERT、UPDATE、DELETE、DDL 或等價 mutation capability。

#### Scenario: Query path 收到 mutation action
- **GIVEN** 任一 planning 或 application component 要求資料 mutation
- **WHEN** execution policy 驗證該 action
- **THEN** 系統 SHALL 拒絕 action、保持 executed=false，且資料庫內容不變

### Requirement: 未指定 fields 時使用安全公開欄位
當有效 Asset plan 沒有指定 fields 時，系統 SHALL 選取 configured public default fields，不得以 wildcard 回傳 internal columns 或未公開資料。

#### Scenario: Plan 省略 fields
- **GIVEN** plan 是有效 Asset query 且 fields 為空
- **WHEN** 系統建立查詢
- **THEN** 結果 SHALL 只包含公開預設欄位與已允許的 relation display fields

### Requirement: 所有 query 結果均有硬性上限
系統 SHALL 對每次資料查詢套用 configured default limit 與 maximum limit；即使 planner 省略 limit 或要求更大值，實際回傳 rows 也 MUST 不超過 maximum，且截斷時 SHALL 揭露 truncated=true。

#### Scenario: Planner 要求超過最大筆數
- **GIVEN** plan 的 limit 超過 configured maximum
- **WHEN** 系統執行查詢
- **THEN** 系統 SHALL 套用 maximum limit 並在結果中揭露資料已截斷

### Requirement: Dependency failure 不揭露內部細節
若 database、mapping 或其他必要 dependency 使已驗證 query 無法完成，系統 SHALL 回傳 dependency_error，且 user-visible error MUST NOT 包含 filesystem path、raw SQL、credential 或 stack trace。

#### Scenario: Database 無法開啟
- **GIVEN** request 與 plan 均有效
- **WHEN** query executor 無法開啟資料來源
- **THEN** 系統 SHALL 回傳安全的 dependency failure，且不得宣稱查詢已成功
