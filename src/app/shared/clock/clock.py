from datetime import datetime, timezone


class Clock:
    def now(self) -> datetime:
        return datetime.now(tz=timezone.utc)
