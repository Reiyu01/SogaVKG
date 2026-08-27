## Purpose

定義如何以可重複資料集驗證資產 query planning、範圍控制、執行結果、grounding、錯誤語意與執行成本，而不修改實驗室資料。

## ADDED Requirements

### Requirement: Evaluation dataset 使用 strict case contract
系統 SHALL 接受由多個結構化 cases 組成的 evaluation dataset；每個 case MUST 包含 question，並可宣告 expected query_type、status、required record keys、expected fields、refusal 或 warning。

#### Scenario: 載入有效 dataset
- **GIVEN** dataset 包含至少一個符合 contract 的 case
- **WHEN** 操作者啟動 evaluation
- **THEN** 系統 SHALL 先驗證全部 cases，再逐一執行共用 query service

#### Scenario: Dataset 為空或 case 無效
- **GIVEN** dataset 為空或任一 case 違反 strict contract
- **WHEN** 操作者啟動 evaluation
- **THEN** 系統 SHALL 拒絕執行並指出無效 case 位置

### Requirement: Evaluation 驗證 planning 與結果正確性
系統 SHALL 對每個 case 判定 query-type accuracy、plan validity、required-record recall、expected-field coverage、status accuracy 與 citation validity。

#### Scenario: Case 指定必要資產編號
- **GIVEN** case 宣告一個 required asset_code
- **WHEN** query 執行完成
- **THEN** evaluation SHALL 判定 response sources 是否包含該 record_key，並記錄通過或失敗

### Requirement: Evaluation 覆蓋安全與範圍邊界
Evaluation dataset MUST 包含 unknown field、raw SQL、SQL injection、BorrowRecord 或 PII、write request、no-results 與 dependency failure 類型的 cases。

#### Scenario: 評估 borrower_email query
- **GIVEN** case 要求查詢 borrower_email 且預期拒絕
- **WHEN** query service 執行該 case
- **THEN** evaluation SHALL 驗證 executed=false、沒有 PII source，且 status 為 unsupported 或 refused

### Requirement: Evaluation 不得修改產品資料
Evaluation MUST 使用 production-equivalent read-only query path，且不得呼叫 mutation capability、改寫資料庫或改變後續一般 query 的結果。

#### Scenario: 執行完整 evaluation dataset
- **GIVEN** evaluation 前已記錄資料狀態
- **WHEN** 所有 cases 執行完成
- **THEN** 資產與借用資料 SHALL 保持不變

### Requirement: Evaluation 回報 aggregate 與逐案例結果
Evaluation report SHALL 包含 case count、aggregate metrics、average planning calls、average elapsed time，以及每個 case 的 expected/actual status、checks、record keys、warnings 與 elapsed time。

#### Scenario: 多案例 evaluation 完成
- **GIVEN** dataset 中所有 cases 已執行
- **WHEN** 系統產生 report
- **THEN** report SHALL 同時提供 aggregate summary 與可追溯至單一 case 的結果
