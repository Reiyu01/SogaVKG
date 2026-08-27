from app.adapters.read_only import DatabaseDependencyError, ReadOnlyDatabasePort
from app.semantic.mapper import SemanticMapper
from app.services.query_policy import QueryPolicy


class ReadinessError(RuntimeError):
    """A required query dependency is unavailable."""


def check_query_readiness(
    database: ReadOnlyDatabasePort,
    mapper: SemanticMapper,
    policy: QueryPolicy,
) -> None:
    try:
        database.check_readiness()
        mapper.get_entity("Asset")
        mapped_fields = set(mapper.get_properties("Asset")) | set(
            mapper.get_relations("Asset")
        )
        if not set(policy.public_default_fields) <= mapped_fields:
            raise ReadinessError("required public mappings are unavailable")
    except ReadinessError:
        raise
    except (DatabaseDependencyError, FileNotFoundError, ValueError) as exc:
        raise ReadinessError("query dependency unavailable") from exc
