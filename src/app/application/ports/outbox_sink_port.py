from abc import ABC, abstractmethod


class OutboxSinkPort(ABC):
    @abstractmethod
    def publish(self, event_type: str, payload: dict) -> None:
        raise NotImplementedError
