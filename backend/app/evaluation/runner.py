import time
from pathlib import Path

from app.ai.answer_generator import citations_are_valid
from app.evaluation.models import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationCheck,
    EvaluationDataset,
    EvaluationMetrics,
    EvaluationReport,
)
from app.models.query import QueryExecution, QueryStatus
from app.services.query_service import QueryDependencyError, QueryService


def load_dataset(path: str | Path) -> EvaluationDataset:
    return EvaluationDataset.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _ratio(passed: int, total: int) -> float:
    return 1.0 if total == 0 else passed / total


class EvaluationRunner:
    """Runs every case through the same production QueryService contract."""

    def __init__(self, service: QueryService):
        self.service = service

    @staticmethod
    def _check(
        checks: list[EvaluationCheck],
        name: str,
        passed: bool,
        expected: object,
        actual: object,
    ) -> None:
        checks.append(
            EvaluationCheck(
                name=name,
                passed=passed,
                expected=expected,  # type: ignore[arg-type]
                actual=actual,  # type: ignore[arg-type]
            )
        )

    def _run_case(self, case: EvaluationCase) -> EvaluationCaseResult:
        started = time.monotonic()
        response: QueryExecution | None = None
        dependency_failure = False
        try:
            response = self.service.query(case.question)
        except QueryDependencyError:
            dependency_failure = True

        if response is None:
            actual_status = QueryStatus.DEPENDENCY_ERROR
            actual_query_type = None
            executed = False
            record_keys: list[str] = []
            fields: list[str] = []
            warnings = ["query dependency unavailable"]
            elapsed_ms = (time.monotonic() - started) * 1000
            planning_calls = 0
            plan_valid = False
            citation_valid = True
        else:
            actual_status = response.status
            actual_query_type = response.query_type
            executed = response.executed
            record_keys = [source.record_key for source in response.sources]
            fields = sorted(
                {
                    field
                    for source in response.sources
                    for field in source.fields
                }
            )
            warnings = list(response.warnings)
            elapsed_ms = response.elapsed_ms
            planning_calls = response.planning_calls
            plan_valid = (
                response.plan is not None
                and response.status != QueryStatus.INVALID_PLAN
            )
            citation_valid = (
                response.status != QueryStatus.ANSWERED
                or citations_are_valid(response.answer, response.sources)
            )

        checks: list[EvaluationCheck] = []
        if case.expected_query_type is not None:
            self._check(
                checks,
                "query_type_accuracy",
                actual_query_type == case.expected_query_type,
                case.expected_query_type.value,
                actual_query_type.value if actual_query_type is not None else None,
            )
        if case.expected_status is not None:
            self._check(
                checks,
                "status_accuracy",
                actual_status == case.expected_status,
                case.expected_status.value,
                actual_status.value,
            )
        if case.expect_plan_valid is not None:
            self._check(
                checks,
                "plan_validity",
                plan_valid is case.expect_plan_valid,
                case.expect_plan_valid,
                plan_valid,
            )

        required_found = sorted(set(case.required_record_keys) & set(record_keys))
        if case.required_record_keys:
            self._check(
                checks,
                "required_record_recall",
                len(required_found) == len(case.required_record_keys),
                sorted(case.required_record_keys),
                required_found,
            )
        expected_fields_found = sorted(set(case.expected_fields) & set(fields))
        if case.expected_fields:
            self._check(
                checks,
                "expected_field_coverage",
                len(expected_fields_found) == len(case.expected_fields),
                sorted(case.expected_fields),
                expected_fields_found,
            )
        if case.expect_refusal is not None:
            refused = actual_status in {
                QueryStatus.REFUSED,
                QueryStatus.UNSUPPORTED,
                QueryStatus.INVALID_PLAN,
            }
            self._check(
                checks,
                "refusal",
                refused is case.expect_refusal,
                case.expect_refusal,
                refused,
            )
        if case.expect_warning is not None:
            self._check(
                checks,
                "warning",
                bool(warnings) is case.expect_warning,
                case.expect_warning,
                bool(warnings),
            )
        self._check(
            checks,
            "citation_validity",
            citation_valid,
            True,
            citation_valid,
        )

        return EvaluationCaseResult(
            case_id=case.id,
            expected_query_type=case.expected_query_type,
            actual_query_type=actual_query_type,
            expected_status=case.expected_status,
            actual_status=actual_status,
            executed=executed,
            dependency_failure=dependency_failure,
            record_keys=record_keys,
            fields=fields,
            warnings=warnings,
            elapsed_ms=float(elapsed_ms),
            planning_calls=planning_calls,
            checks=checks,
            passed=all(check.passed for check in checks),
        )

    def run(self, dataset: EvaluationDataset) -> EvaluationReport:
        results = [self._run_case(case) for case in dataset.cases]
        case_by_id = {case.id: case for case in dataset.cases}

        query_type_checks = [
            result.actual_query_type == result.expected_query_type
            for result in results
            if result.expected_query_type is not None
        ]
        status_checks = [
            result.actual_status == result.expected_status
            for result in results
            if result.expected_status is not None
        ]
        plan_checks = [
            next(check.passed for check in result.checks if check.name == "plan_validity")
            for result in results
            if case_by_id[result.case_id].expect_plan_valid is not None
        ]
        citation_checks = [
            next(check.passed for check in result.checks if check.name == "citation_validity")
            for result in results
        ]

        required_total = sum(
            len(case.required_record_keys) for case in dataset.cases
        )
        required_found = sum(
            len(set(case.required_record_keys) & set(result.record_keys))
            for case, result in zip(dataset.cases, results, strict=True)
        )
        fields_total = sum(len(case.expected_fields) for case in dataset.cases)
        fields_found = sum(
            len(set(case.expected_fields) & set(result.fields))
            for case, result in zip(dataset.cases, results, strict=True)
        )
        count = len(results)
        metrics = EvaluationMetrics(
            case_count=count,
            query_type_accuracy=_ratio(sum(query_type_checks), len(query_type_checks)),
            plan_validity=_ratio(sum(plan_checks), len(plan_checks)),
            required_record_recall=_ratio(required_found, required_total),
            expected_field_coverage=_ratio(fields_found, fields_total),
            status_accuracy=_ratio(sum(status_checks), len(status_checks)),
            citation_validity=_ratio(sum(citation_checks), len(citation_checks)),
            average_planning_calls=sum(result.planning_calls for result in results) / count,
            average_elapsed_ms=sum(result.elapsed_ms for result in results) / count,
        )
        return EvaluationReport(
            dataset_name=dataset.name,
            dataset_version=dataset.version,
            metrics=metrics,
            results=results,
        )
