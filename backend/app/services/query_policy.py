from dataclasses import dataclass

from app.models.query import SemanticQueryPlan


class QueryPolicyError(ValueError):
    """A semantic plan is outside the public MVP query contract."""


@dataclass(frozen=True)
class QueryPolicy:
    public_default_fields: tuple[str, ...] = (
        "asset_code",
        "name",
        "quantity",
        "status",
        "category",
        "location",
    )
    selectable_fields: frozenset[str] = frozenset(
        {
            "asset_code",
            "name",
            "quantity",
            "status",
            "specification",
            "note",
            "category",
            "location",
        }
    )
    filterable_fields: frozenset[str] = frozenset(
        {
            "asset_code",
            "name",
            "quantity",
            "status",
            "specification",
            "note",
            "category",
            "location",
        }
    )
    sortable_fields: frozenset[str] = frozenset(
        {"asset_code", "name", "quantity", "status", "category", "location"}
    )
    allowed_relations: frozenset[str] = frozenset({"category", "location"})
    default_limit: int = 20
    maximum_limit: int = 100

    def __post_init__(self) -> None:
        if not self.public_default_fields:
            raise ValueError("public_default_fields must not be empty")
        if not set(self.public_default_fields) <= self.selectable_fields:
            raise ValueError("public_default_fields must be selectable")
        if self.default_limit < 1 or self.maximum_limit < self.default_limit:
            raise ValueError("invalid query limits")

    @property
    def public_fields(self) -> frozenset[str]:
        return self.selectable_fields

    def validate(self, plan: SemanticQueryPlan) -> SemanticQueryPlan:
        if plan.entity != "Asset":
            raise QueryPolicyError("MVP only supports Asset queries")

        fields = tuple(plan.fields) if plan.fields else self.public_default_fields
        if "asset_code" not in fields:
            fields = ("asset_code", *fields)
        unsupported_fields = set(fields) - self.selectable_fields
        if unsupported_fields:
            raise QueryPolicyError("plan contains non-public fields")

        unsupported_filters = set(plan.filters) - self.filterable_fields
        if unsupported_filters:
            raise QueryPolicyError("plan contains unsupported filters")

        if plan.order_by and plan.order_by.field not in self.sortable_fields:
            raise QueryPolicyError("plan contains unsupported sorting")

        for relation in set(fields) | set(plan.filters):
            if relation in {"category", "location"} and relation not in self.allowed_relations:
                raise QueryPolicyError("plan contains unsupported relations")

        requested_limit = plan.limit if plan.limit is not None else self.default_limit
        effective_limit = min(requested_limit, self.maximum_limit)
        return plan.model_copy(
            update={
                "fields": list(fields),
                "limit": effective_limit,
            }
        )
