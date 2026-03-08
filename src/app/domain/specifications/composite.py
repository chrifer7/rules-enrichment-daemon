from dataclasses import dataclass

from app.domain.entities.external_order import ExternalOrder
from app.domain.specifications.base import Specification


@dataclass(slots=True)
class AndSpecification(Specification):
    specs: list[Specification]

    def is_satisfied_by(self, order: ExternalOrder) -> bool:
        return all(spec.is_satisfied_by(order) for spec in self.specs)


@dataclass(slots=True)
class OrSpecification(Specification):
    specs: list[Specification]

    def is_satisfied_by(self, order: ExternalOrder) -> bool:
        return any(spec.is_satisfied_by(order) for spec in self.specs)
