## Purpose

定義資產查詢回答如何只根據本次實際回傳的資料列產生、揭露可驗證 provenance，並在無結果或來源驗證失敗時拒絕補完。

## ADDED Requirements

### Requirement: 回答只使用本次 query rows
系統 MUST 只以本次已執行 query 的 approved rows 支持資產事實，不得使用 model 外部知識、先前 request 資料或未回傳的 database values 補完答案。

#### Scenario: Row 的 note 包含操作指示
- **GIVEN** query row 的文字欄位包含要求改變系統行為或揭露其他資料的內容
- **WHEN** 系統產生回答
- **THEN** 系統 SHALL 將該內容視為 untrusted data，不得據此擴張查詢、執行 action 或改變安全規則

### Requirement: 成功回答附帶本次資料列來源
非 insufficient 的 factual answer MUST 至少引用一個本次 sources 中的編號；每個 source SHALL 包含 number、entity、可驗證 record_key 與實際用於回答的公開 fields。

#### Scenario: 回答使用一筆資產資料
- **GIVEN** query 回傳具有 asset_code 的 Asset row
- **WHEN** 系統產生資產回答
- **THEN** response SHALL 提供對應 numbered source，且 answer 的 citation number SHALL 指向該 source

### Requirement: 無查詢結果時不得推測
當有效 query 已成功執行但沒有 rows 時，系統 MUST 回傳 insufficient 或 no_results 狀態，清楚說明目前資料查無符合項目，且不得生成推測性資產答案。

#### Scenario: 條件沒有符合資產
- **GIVEN** query 已執行且 row_count 為零
- **WHEN** 系統準備回答
- **THEN** 系統 SHALL 回傳查無資料、insufficient=true，且 sources 為空

### Requirement: Citation 或 provenance 無效時 fail closed
系統 SHALL 驗證 answer citations 只引用本次 response sources，且 source record_key 可由本次 rows 建立；驗證後仍不合法的回答 MUST 被 withholding。

#### Scenario: Answer 引用不存在的 source
- **GIVEN** answer draft 引用本次 sources 沒有的編號
- **WHEN** citation validation 完成後仍不合法
- **THEN** 系統 SHALL 不交付該 answer，並回傳 refused 與 user-safe warning

### Requirement: 截斷結果必須顯著揭露
若 query 因 maximum limit 只回傳部分 rows，系統 SHALL 在 response warnings 與回答內容揭露結果已截斷，不得將部分結果描述為完整集合。

#### Scenario: 符合資料超過 maximum limit
- **GIVEN** query 的實際符合筆數高於可回傳上限
- **WHEN** 系統根據有限 rows 產生回答
- **THEN** response SHALL 設定 truncated=true，且 answer SHALL 說明目前只顯示部分結果

### Requirement: Operational trace 不揭露隱藏推理或 raw SQL
系統 SHALL 揭露 query stages、status、row/source counts、warnings 與 elapsed time，但 MUST NOT 回傳 raw system prompt、hidden chain-of-thought、credential、stack trace 或 raw SQL。

#### Scenario: Query 完成
- **GIVEN** query 最終為 answered、insufficient、unsupported 或 refused
- **WHEN** 系統建立 response trace
- **THEN** trace SHALL 提供可診斷的 stage summary 與耗時，且不包含受保護內容
