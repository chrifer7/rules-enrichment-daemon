from app.application.commands.publish_outbox import OutboxPublishCommand
from app.application.ports.outbox_sink_port import OutboxSinkPort
from app.application.ports.unit_of_work import UnitOfWork


class PublishOutboxMessagesUseCase:
    def __init__(self, uow: UnitOfWork, sink: OutboxSinkPort):
        self._uow = uow
        self._sink = sink

    def execute(self, command: OutboxPublishCommand) -> int:
        published = 0
        with self._uow:
            messages = self._uow.outbox.list_pending(limit=command.batch_size)
            for msg in messages:
                try:
                    self._sink.publish(msg.event_type, msg.payload_json)
                    self._uow.outbox.mark_published(msg.message_id)
                    published += 1
                except Exception:
                    self._uow.outbox.mark_failed(msg.message_id)
            self._uow.commit()
        return published
