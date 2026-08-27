## Purpose

定義自然語言資產問題如何在有限資源內轉換為結構化、可驗證且不包含 raw SQL 的 semantic query plan，並於無法安全規劃時停止。

## ADDED Requirements

### Requirement: 每次問題具有可觀察的 query type
系統 SHALL 將每次 request 分類為 asset_query、conversation、unsupported 或 write，並 SHALL 在結構化結果中揭露 query_type。

#### Scenario: 資產條件查詢
- **GIVEN** 使用者詢問 C217 是否有 ESP32
- **WHEN** 系統分類該問題
- **THEN** 系統 SHALL 將其標示為 asset_query 並進入 semantic planning

#### Scenario: 使用者要求修改資產
- **GIVEN** 使用者要求變更資產狀態或數量
- **WHEN** 系統分類該問題
- **THEN** 系統 SHALL 將其標示為 write、保持 executed=false，並說明 MVP 只支援唯讀查詢

### Requirement: Semantic query plan 使用 strict contract
Asset query plan SHALL 只包含已宣告的 entity、fields、filters、order_by 與 limit，且 MUST 拒絕 unknown fields、無效型別、無效排序方向與超過上限的內容。

#### Scenario: Planner 回傳未知 plan 欄位
- **GIVEN** model-produced plan 包含 contract 未宣告的欄位
- **WHEN** 系統驗證 planner output
- **THEN** 系統 SHALL 將 output 視為無效，不得交給 query builder

### Requirement: Planner 不得輸出或執行 raw SQL
Semantic planner MUST NOT 將 SQL statement、table name、SQL fragment 或 mutation action 作為可執行 plan；所有資料操作 SHALL 由通過驗證的 semantic fields 與 filters 表示。

#### Scenario: Planner output 包含 SQL
- **GIVEN** model-produced output 含 sql 欄位或 SQL statement
- **WHEN** 系統驗證 output
- **THEN** 系統 SHALL 拒絕該 output，且不得執行其中任何內容

### Requirement: Planning 受 call budget 與 deadline 限制
系統 SHALL 對 planning 與 optional repair 使用 configured call upper bound 與 wall-clock deadline；到達任一限制時 MUST 停止新增 model calls 並回傳 refused 結果。

#### Scenario: Planning deadline 到期
- **GIVEN** planner 尚未產生有效 plan
- **WHEN** configured deadline 到期
- **THEN** 系統 SHALL 停止 planning、保持 executed=false，且不得改用未受控 fallback

### Requirement: 無效 planner output 採 fail closed
若 planner output 經 bounded validation 與 optional repair 後仍無效，系統 MUST 回傳 refused 或 invalid_plan 狀態，不得猜測使用者意圖或自行補出 query fields。

#### Scenario: Repair 後仍無法驗證
- **GIVEN** initial 與 repair output 都不符合 plan contract
- **WHEN** bounded repair 流程完成
- **THEN** 系統 SHALL 不執行資料查詢並回傳 user-safe warning

### Requirement: 不支援的查詢能力必須明確揭露
對 aggregation、跨實體 multi-hop、realtime external data、BorrowRecord、write 或其他 MVP 未提供的能力，系統 SHALL 回傳明確 warning，不得暗示已執行不存在的查詢能力。

#### Scenario: 使用者要求跨借用紀錄統計
- **GIVEN** 使用者要求依借用人統計資產
- **WHEN** 系統判斷該能力不在 MVP 範圍
- **THEN** 系統 SHALL 回傳 unsupported、保持 executed=false，並指出目前只支援 Asset 查詢
