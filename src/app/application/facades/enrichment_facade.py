import logging
from datetime import datetime, timezone

from app.application.use_cases.poll_orders import PollOrdersForEnrichmentUseCase
from app.application.use_cases.process_order import ProcessOrderForEnrichmentUseCase
from app.application.use_cases.refresh_rules_cache import RefreshRulesCacheUseCase
from app.shared.clock.clock import Clock
from app.shared.ids.ids import IdGenerator
from app.shared.observability.context import LogContext

logger = logging.getLogger(__name__)


class EnrichmentFacade:
    def __init__(
        self,
        *,
        poll_use_case: PollOrdersForEnrichmentUseCase,
        process_use_case: ProcessOrderForEnrichmentUseCase,
        refresh_rules_cache_use_case: RefreshRulesCacheUseCase,
        clock: Clock,
        id_generator: IdGenerator,
        poll_batch_size: int,
        rule_cache_ttl_seconds: int,
    ):
        self._poll = poll_use_case
        self._process = process_use_case
        self._refresh_rules = refresh_rules_cache_use_case
        self._clock = clock
        self._ids = id_generator
        self._poll_batch_size = poll_batch_size
        self._rule_cache_ttl_seconds = rule_cache_ttl_seconds

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    def run_once(self, updated_since: datetime | None = None) -> tuple[int, int, int, datetime]:
        started = self._clock.now()
        run_id = self._ids.new_id()
        context = LogContext(daemon_run_id=run_id)
        logger.info(
            "Polling cycle started",
            extra=context.to_extra(
                **{
                    "event.action": "poll_cycle_start",
                    "event.category": "process",
                    "event.outcome": "unknown",
                    "service.name": "rules-enrichment-daemon",
                    "poll.batch_size": self._poll_batch_size,
                    "poll.updated_since": updated_since.isoformat() if updated_since else None,
                }
            ),
        )

        orders = self._poll.execute(updated_since=updated_since, limit=self._poll_batch_size)
        logger.info(
            "Polling fetch result",
            extra=context.to_extra(
                **{
                    "event.action": "poll_fetch_result",
                    "event.category": "process",
                    "event.outcome": "success",
                    "orders.fetched": len(orders),
                    "poll.updated_since": updated_since.isoformat() if updated_since else None,
                }
            ),
        )
        logger.debug(
            "Polling fetch order IDs",
            extra=context.to_extra(
                **{
                    "event.action": "poll_fetch_ids",
                    "event.category": "process",
                    "event.outcome": "success",
                    "orders.ids": [o.order_id for o in orders[:50]],
                    "orders.ids_truncated": len(orders) > 50,
                }
            ),
        )

        success = 0
        failed = 0
        max_updated_at = self._as_utc(updated_since) if updated_since else started

        for order in orders:
            now = self._clock.now()
            order_started = self._clock.now()
            order_updated_at = self._as_utc(order.updated_at)
            max_updated_at = max(max_updated_at, order_updated_at)

            logger.debug(
                "Order processing started",
                extra=context.to_extra(
                    **{
                        "event.action": "order_process_start",
                        "event.category": "process",
                        "event.outcome": "unknown",
                        "order.id": order.order_id,
                        "client.code": order.client_code,
                        "facility.code": order.facility_code,
                        "order.status": order.status,
                        "order.priority": order.priority,
                        "order.updated_at": order_updated_at.isoformat(),
                        "order.lines_count": len(order.lines),
                        "order.total_weight_kg": order.total_weight_kg,
                        "order.total_volume_m3": order.total_volume_m3,
                    }
                ),
            )

            rules = self._refresh_rules.execute(
                now=now,
                ttl_seconds=self._rule_cache_ttl_seconds,
                client_code=order.client_code,
                facility_code=order.facility_code,
                zone_code=order.zone_code,
            )
            logger.debug(
                "Order rules loaded",
                extra=context.to_extra(
                    **{
                        "event.action": "order_rules_loaded",
                        "event.category": "process",
                        "event.outcome": "success",
                        "order.id": order.order_id,
                        "client.code": order.client_code,
                        "facility.code": order.facility_code,
                        "rules.count": len(rules),
                        "rules.sample_ids": [r.rule_id for r in rules[:10]],
                        "rules.sample_truncated": len(rules) > 10,
                    }
                ),
            )

            try:
                processed, correlation_id, duplicate_skip = self._process.execute(order=order, rules=rules, now=now)
                success += 1
                logger.debug(
                    "Order processing completed",
                    extra=context.to_extra(
                        **{
                            "event.action": "order_process_result",
                            "event.category": "process",
                            "event.outcome": "success",
                            "order.id": order.order_id,
                            "client.code": order.client_code,
                            "facility.code": order.facility_code,
                            "correlation.id": correlation_id,
                            "order.processed": processed,
                            "order.duplicate_skip": duplicate_skip,
                            "duration.ms": int((self._clock.now() - order_started).total_seconds() * 1000),
                        }
                    ),
                )
            except Exception as exc:
                failed += 1
                logger.exception(
                    "Order processing failed",
                    extra=context.to_extra(
                        **{
                            "event.action": "order_process",
                            "event.category": "process",
                            "event.outcome": "failure",
                            "order.id": order.order_id,
                            "client.code": order.client_code,
                            "facility.code": order.facility_code,
                            "duration.ms": int((self._clock.now() - order_started).total_seconds() * 1000),
                            "app.error_message": str(exc),
                            "app.error_class": exc.__class__.__name__,
                        }
                    ),
                )

        finished = self._clock.now()
        logger.info(
            "Polling cycle finished",
            extra=context.to_extra(
                **{
                    "event.action": "poll_cycle_end",
                    "event.category": "process",
                    "event.outcome": "success" if failed == 0 else "partial",
                    "duration.ms": int((finished - started).total_seconds() * 1000),
                    "orders.fetched": len(orders),
                    "orders.success": success,
                    "orders.failed": failed,
                    "poll.next_updated_since": max_updated_at.isoformat(),
                }
            ),
        )
        return len(orders), success, failed, max_updated_at
