# add-lab-query-mvp Implementation Evidence

本文件逐項對照六份 capability specs 的 Requirements/Scenarios。Implementation
paths 均位於 SogaVKG；gdrive-rag-cli 只作為唯讀規格參考。

## 驗證摘要

- 完整測試：在 backend 執行 .venv/bin/pytest，結果 60 passed。
- Lab smoke：執行 .venv/bin/python -m scripts.smoke_query_mvp，結果 Asset answered、
  no_results、PII unsupported、live/ready HTTP 200、database SHA-256 unchanged。
- Evaluation：tests/test_evaluation.py 共 5 tests passed，包含 production
  QueryService + SQLiteReadOnlyAdapter 的資料不變驗證。

## asset-query-boundary

| Requirement / Scenario | Implementation evidence | Test evidence |
|---|---|---|
| MVP 查詢以 Asset 為唯一根實體／查詢特定地點的資產 | backend/app/services/query_policy.py 的 QueryPolicy.validate 限定 Asset，僅允許 category/location relations；backend/app/semantic/query_builder.py 建立 relation joins | test_query_policy_builder.py::test_builder_clamps_excess_limit_and_joins_relation_sort；test_query_service.py::test_answered_query_has_public_numbered_provenance_and_safe_trace |
| 查詢欄位必須來自公開 allowlist／Planner 要求未公開欄位 | QueryPolicy 明列 default/selectable/filterable/sortable fields，未知欄位在 builder 前拒絕 | test_query_policy_builder.py::test_policy_rejects_out_of_scope_entity_pii_and_internal_fields；test_query_service.py::test_policy_invalid_plan_never_executes_database |
| BorrowRecord 與個人資料 fail closed／詢問 borrower_email | NaturalLanguagePlanner guarded classification 與 QueryPolicy 雙重拒絕 BorrowRecord/borrower_email | test_planner.py::test_non_asset_classification_never_calls_model；test_query_service.py::test_non_asset_query_never_executes_database；scripts/smoke_query_mvp.py |
| 無法證明資料範圍時不得查詢／未知 relation | QueryPolicy 對 entity、field、filter、sort、relation 採 fail closed，沒有 table fallback | test_query_policy_builder.py::test_policy_rejects_out_of_scope_entity_pii_and_internal_fields |

## semantic-query-planning

| Requirement / Scenario | Implementation evidence | Test evidence |
|---|---|---|
| 每次問題具有 query type／Asset query 與 write request | backend/app/models/query.py 的 QueryType；backend/app/ai/planner.py 分類 asset_query、conversation、unsupported、write | test_planner.py::test_planner_returns_valid_asset_plan；test_planner.py::test_non_asset_classification_never_calls_model |
| Semantic query plan 使用 strict contract／未知 plan 欄位 | SemanticQueryPlan 與 PlannerDecision 均 extra-forbid、strict typed | test_query_models.py；test_planner.py::test_planner_repairs_invalid_unknown_raw_sql_and_malformed_output |
| Planner 不得輸出或執行 raw SQL／output 包含 SQL | planner_v1.md 只宣告 semantic JSON；sql/table/action 不是 model fields，validation 失敗 | test_query_models.py::test_semantic_plan_forbids_unknown_and_raw_sql_fields；test_planner.py::test_planner_repairs_invalid_unknown_raw_sql_and_malformed_output |
| Planning 受 call budget 與 deadline 限制／deadline 到期 | NaturalLanguagePlanner 限制 max_calls 1–2，使用 monotonic deadline 與 provider timeout | test_planner.py::test_planner_stops_after_wall_clock_deadline |
| 無效 output fail closed／repair 後仍無效 | 最多一次 repair，失敗回 valid=false，QueryService 回 invalid_plan 且不執行 | test_planner.py::test_planner_fails_closed_when_repair_fails |
| 不支援能力明確揭露／跨借用紀錄統計 | guarded classification 阻擋 aggregation、BorrowRecord、PII、write，回明確 warning | test_planner.py::test_non_asset_classification_never_calls_model；test_query_service.py::test_non_asset_query_never_executes_database |

## read-only-query-execution

| Requirement / Scenario | Implementation evidence | Test evidence |
|---|---|---|
| 執行前再次驗證 plan／未知 property | QueryService 強制先呼叫 QueryPolicy.validate，再呼叫 builder/database | test_query_service.py::test_policy_invalid_plan_never_executes_database |
| 使用者值參數化／SQL injection value | SemanticQueryBuilder 只把 filter value 放入 named params | test_query_policy_builder.py::test_builder_parameterizes_sql_injection_value；test_read_only_adapter.py::test_parameter_value_cannot_change_statement_or_data |
| Query path 僅允許唯讀／mutation action | ReadOnlyDatabasePort 不宣告 write method；SQLite mode=ro、PRAGMA query_only，statement 僅允許單一 SELECT | test_read_only_adapter.py::test_read_only_port_exposes_no_write_capability；test_adapter_rejects_mutation_and_multiple_statements |
| 未指定 fields 使用公開 defaults／plan 省略 fields | QueryPolicy 與 SemanticQueryBuilder 共同套用 public_default_fields，不使用 wildcard | test_query_policy_builder.py::test_builder_uses_safe_defaults_and_mandatory_limit |
| 所有結果有硬性上限／planner 超過 maximum | Builder 強制 default/maximum limit；QueryService 只多讀一筆判斷 truncated，再裁回 maximum | test_query_policy_builder.py::test_policy_applies_public_defaults_and_clamps_limit；test_query_service.py::test_truncated_result_is_bounded_and_disclosed |
| Dependency failure 不揭露細節／database 無法開啟 | SQLiteReadOnlyAdapter 翻譯為 generic DatabaseDependencyError；API 映射 generic 503 | test_read_only_adapter.py::test_database_unavailable_is_translated；test_api.py::test_query_dependency_failure_is_generic_503 |

## grounded-result-answering

| Requirement / Scenario | Implementation evidence | Test evidence |
|---|---|---|
| 回答只使用本次 rows／note 含操作指示 | answer_v1.md 只接受 question、warnings、sources 並將 row text 視為 untrusted；QueryService 只傳公開 fields | test_query_service.py::test_prompt_injection_row_is_only_untrusted_grounding_data |
| 成功回答附本次資料列來源／使用一筆資產 | QueryService 建立 numbered RowSource，record_key 優先 asset_code；citation validator 對本次 numbers | test_query_service.py::test_answered_query_has_public_numbered_provenance_and_safe_trace；lab smoke PCB-001 |
| 無結果不得推測／條件無符合資產 | QueryService 直接回 no_results、insufficient=true、sources=[]，不呼叫 answer model | test_query_service.py::test_no_results_is_insufficient_and_does_not_call_answer_model；lab smoke |
| Citation/provenance 無效 fail closed／引用不存在 source | GroundedAnswerGenerator 最多一次 repair；仍無效時 answer withholding、status=refused | test_query_service.py::test_invalid_citation_is_repaired_once_then_withheld |
| 截斷結果顯著揭露／超過 maximum | QueryService 設 truncated、warning，GroundedAnswerGenerator 在 answer 加入部分結果聲明 | test_query_service.py::test_truncated_result_is_bounded_and_disclosed |
| Operational trace 不揭露 raw SQL／query 完成 | QueryTraceEvent 只記 stage/status/counts/elapsed/calls；public response 不含 builder result | test_query_service.py::test_answered_query_has_public_numbered_provenance_and_safe_trace；test_api.py::test_query_contract_returns_required_public_fields |

## query-application-interfaces

| Requirement / Scenario | Implementation evidence | Test evidence |
|---|---|---|
| Versioned strict REST request／有效與 unknown fields | backend/app/api/query.py 提供 POST /api/v1/query；QueryRequest 為 1–8000 chars、extra-forbid | test_api.py::test_query_contract_returns_required_public_fields；test_query_request_is_strict_and_bounded |
| Response 揭露結果與狀態／answered 與 unsupported | QueryResponse 延伸 strict QueryExecution，包含 spec 要求欄位與 validated plan | test_api.py::test_query_contract_returns_required_public_fields；test_unsupported_and_no_results_are_http_200_domain_results |
| Validation 與 dependency failure 可區分／database failure | FastAPI request validation 回 422；QueryDependencyError 回 generic 503 | test_api.py::test_query_request_is_strict_and_bounded；test_query_dependency_failure_is_generic_503 |
| Liveness／process 可回應 | GET /api/v1/health/live 不執行 query | test_api.py::test_liveness_and_readiness_endpoints；lab smoke |
| Readiness／mapping 不可用 | GET /api/v1/health/ready 呼叫 check_query_readiness 驗證 database、Asset mapping、public defaults | test_read_only_adapter.py::test_readiness_fails_when_public_mapping_is_missing；test_api.py::test_readiness_dependency_failure_is_generic_503 |
| 所有 interfaces 共用 service semantics／新增 interface | REST runtime、evaluation runner 與 smoke script 都依賴同一 QueryService，不在 route/runner 重作 policy | test_production_query_service_evaluation_keeps_database_unchanged；scripts/smoke_query_mvp.py |

## query-quality-evaluation

| Requirement / Scenario | Implementation evidence | Test evidence |
|---|---|---|
| Strict case contract／有效、空或無效 dataset | backend/app/evaluation/models.py 的 EvaluationCase/Dataset extra-forbid、至少一 case、unique IDs/expectations | test_evaluation.py::test_dataset_rejects_empty_invalid_and_duplicate_cases；test_lab_fixture_is_strict_and_covers_required_safety_cases |
| 驗證 planning 與結果／required asset_code | EvaluationRunner 建立 query type、plan、record recall、field coverage、status、citation checks | test_evaluation.py::test_runner_reports_traceable_checks_and_correct_aggregates |
| 覆蓋安全邊界／borrower_email | backend/evaluation/lab_mvp.json 包含 unknown/raw SQL/injection/PII/write/no-results/invalid citation/dependency cases | test_evaluation.py::test_lab_fixture_is_strict_and_covers_required_safety_cases |
| Evaluation 不修改資料／完整 dataset | Runner 只呼叫 production QueryService；query path 只持有 ReadOnlyDatabasePort | test_evaluation.py::test_production_query_service_evaluation_keeps_database_unchanged；lab smoke SHA-256 unchanged |
| Aggregate 與逐案例 report／多案例完成 | EvaluationReport 同時回 metrics 與含 expected/actual/checks 的 results | test_evaluation.py::test_runner_reports_traceable_checks_and_correct_aggregates；test_invalid_citation_is_visible_in_case_and_aggregate |

## Reference project integrity

- apply 階段的 write root 只有 /home/openclawuser/SogaVKG。
- 在 /home/openclawuser/gdrive-rag-cli 執行 git status --short --untracked-files=no，
  輸出為空。
- git diff --quiet 與 git diff --cached --quiet 均 exit 0。
- gdrive-rag-cli 目前的 .agents/ 與 openspec/ 是 untracked reference/planning input；
  本 change 未寫入或修改其 tracked implementation。
