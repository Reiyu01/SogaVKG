## Purpose

定義實驗室 MVP 可被查詢的資產資料範圍與欄位邊界，確保任何規劃或執行路徑都不能存取借用紀錄、個人資料或未宣告資料來源。

## ADDED Requirements

### Requirement: MVP 查詢以 Asset 為唯一根實體
系統 SHALL 只允許以 Asset 作為 MVP query plan 的根實體，並 SHALL 允許透過已宣告關係讀取 Category 與 Location 的公開顯示欄位。

#### Scenario: 查詢特定地點的資產
- **GIVEN** Asset mapping 宣告 Location 為可查詢關係
- **WHEN** 使用者詢問特定地點有哪些資產
- **THEN** 系統 SHALL 只查詢 Asset 與該 Location 關係，且不得擴張至其他資料實體

### Requirement: 查詢欄位必須來自公開 allowlist
系統 MUST 只接受 query contract 明確宣告的 Asset properties 與 relations；internal identifier、foreign key、來源工作表欄位或其他未宣告欄位不得出現在 plan、結果或回答來源中。

#### Scenario: Planner 要求未公開欄位
- **GIVEN** model-produced plan 包含未列入公開 allowlist 的欄位
- **WHEN** 系統驗證該 plan
- **THEN** 系統 SHALL 拒絕執行並回傳安全的 invalid-plan 結果

### Requirement: BorrowRecord 與個人資料在 MVP 中 fail closed
系統 MUST 將 BorrowRecord、borrower_email 及其他借用人資料視為 MVP 範圍外資料；任何直接或間接要求存取這些資料的 query 都不得執行。

#### Scenario: 使用者詢問借用人的電子郵件
- **GIVEN** 使用者問題要求取得 borrower_email
- **WHEN** 系統分類並驗證查詢範圍
- **THEN** 系統 SHALL 回傳 unsupported 或 refused 狀態、保持 executed=false，且不得回傳任何借用紀錄或個人資料

### Requirement: 無法證明資料範圍時不得查詢
若 entity、field、relation 或 mapping 無法被目前公開 contract 驗證，系統 MUST 拒絕該 query，不得以名稱猜測、直接 table access 或其他 fallback 擴張資料範圍。

#### Scenario: Query plan 引用未知 relation
- **GIVEN** plan 引用目前 mapping 不存在的 relation
- **WHEN** 系統執行範圍驗證
- **THEN** 系統 SHALL 拒絕執行並指出查詢包含不支援的資料範圍
