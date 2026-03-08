from app.domain.specifications.base import Specification
from app.domain.specifications.composite import AndSpecification, OrSpecification
from app.domain.specifications.predicate import PredicateSpecification
from app.shared.errors.errors import InvalidRuleDefinitionError


class RuleSpecificationFactory:
    def from_json(self, conditions: dict) -> Specification:
        if "and" in conditions:
            return AndSpecification([self.from_json(item) for item in conditions["and"]])
        if "or" in conditions:
            return OrSpecification([self.from_json(item) for item in conditions["or"]])

        field = conditions.get("field")
        op = conditions.get("op")
        if not field or not op:
            raise InvalidRuleDefinitionError("predicate requires field and op")
        return PredicateSpecification(field=field, op=op, value=conditions.get("value"))
