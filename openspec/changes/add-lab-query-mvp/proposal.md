## Why

SogaVKG 已具備實驗室資產資料、semantic mappings 與 parameterized SQL builder，但尚未能接收使用者問題、實際執行安全查詢或產生可驗證回答。現在需要以 gdrive-rag-cli 的查詢應用行為作為參考，建立 Project B 的第一個端到端唯讀查詢 MVP，並保留未來擴展至全校治理與授權的清楚邊界。

## What Changes

- 新增實驗室 Asset-only 的自然語言查詢流程，將問題轉為 strict semantic query plan，再交由既有 mapping 與 query builder 處理。
- 新增 fail-closed plan validation，限制可查詢 entity、field、relation、filter、sort 與 result limit；model 不得直接產生或執行 raw SQL。
- 新增 read-only query execution，實際執行 parameterized SQL，限制回傳筆數，且不提供任何資料 mutation 行為。
- 新增只根據本次 query rows 產生回答的 grounding 規則，並回傳可驗證的資料來源與安全 trace。
- 新增 strict versioned REST query contract、liveness、readiness，以及可區分 validation 與 dependency failure 的錯誤語意。
- 新增可重複執行的 MVP evaluation cases，涵蓋正常查詢、無資料、unsupported query、invalid plan、SQL injection 與範圍外資料。
- 明確排除 BorrowRecord、borrower_email、寫入操作、多使用者授權、跨系統整合、dashboard、persistent conversation 與全校 rollout；這些需由後續 changes 處理。

## Capabilities

### New Capabilities

- asset-query-boundary: 定義 MVP 可查詢的 Asset、Category、Location 資料範圍，以及 BorrowRecord 與個資的 fail-closed 排除行為。
- semantic-query-planning: 定義自然語言問題如何轉換為 strict、bounded、可驗證且不含 raw SQL 的 semantic query plan。
- read-only-query-execution: 定義 semantic plan 如何被安全轉換並執行為 parameterized read-only query，以及結果與失敗語意。
- grounded-result-answering: 定義回答只能使用本次 query rows、無資料時不得補完，並保留資料列 provenance 與 safe trace。
- query-application-interfaces: 定義 versioned REST query、liveness、readiness、request/response 與 error contracts。
- query-quality-evaluation: 定義可重複的 query、grounding、安全邊界與執行成本 evaluation。

### Modified Capabilities

無；SogaVKG 尚未建立 OpenSpec main specs，本 change 全部引入新的 Project B capabilities。

## Impact

- 主要影響 SogaVKG backend application layer、semantic query flow、database adapter wiring、API models、configuration 與 tests。
- 現有 SemanticMapper、SemanticQueryBuilder、Asset/Category/Location mappings 與 SQLite 資料庫將作為 Reference Implementation evidence。
- gdrive-rag-cli 保持唯讀，只提供 QueryService、strict API、bounded orchestration、grounding、health、trace 與 evaluation 的設計參考。
- 第一階段 deployment 仍採單一可信任使用者；未來全校化前必須另行規格化 authentication、RBAC、field/row-level authorization、audit、master data 與 additional source adapters。
