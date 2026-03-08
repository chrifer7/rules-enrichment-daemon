import re
from dataclasses import dataclass
from typing import Any

from app.domain.entities.external_order import ExternalOrder
from app.domain.specifications.base import Specification
from app.shared.errors.errors import InvalidRuleDefinitionError


_ALLOWED_OPS = {
    "eq", "neq", "gt", "gte", "lt", "lte", "contains", "in", "not_in",
    "starts_with", "ends_with", "exists", "regex"
}


def _extract(order: ExternalOrder, field_path: str) -> Any:
    current: Any = order
    for token in field_path.split("."):
        if isinstance(current, dict):
            current = current.get(token)
        else:
            current = getattr(current, token, None)
        if current is None:
            break
    return current


@dataclass(slots=True)
class PredicateSpecification(Specification):
    field: str
    op: str
    value: Any

    def __post_init__(self) -> None:
        if self.op not in _ALLOWED_OPS:
            raise InvalidRuleDefinitionError(f"unsupported operator: {self.op}")

    def is_satisfied_by(self, order: ExternalOrder) -> bool:
        left = _extract(order, self.field)
        op = self.op
        right = self.value

        if op == "exists":
            return left is not None
        if left is None:
            return False
        if op == "eq":
            return left == right
        if op == "neq":
            return left != right
        if op == "gt":
            return left > right
        if op == "gte":
            return left >= right
        if op == "lt":
            return left < right
        if op == "lte":
            return left <= right
        if op == "contains":
            return str(right).lower() in str(left).lower()
        if op == "in":
            return left in right
        if op == "not_in":
            return left not in right
        if op == "starts_with":
            return str(left).startswith(str(right))
        if op == "ends_with":
            return str(left).endswith(str(right))
        if op == "regex":
            pattern = str(right)
            if len(pattern) > 128:
                raise InvalidRuleDefinitionError("regex too long")
            return re.search(pattern, str(left)) is not None
        return False
