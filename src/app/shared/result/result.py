from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class Result(Generic[T, E]):
    value: T | None = None
    error: E | None = None

    @property
    def is_ok(self) -> bool:
        return self.error is None

    @property
    def is_error(self) -> bool:
        return self.error is not None

    @staticmethod
    def ok(value: T) -> "Result[T, E]":
        return Result(value=value)

    @staticmethod
    def fail(error: E) -> "Result[T, E]":
        return Result(error=error)
