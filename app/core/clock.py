from collections.abc import Callable
from datetime import datetime, timezone

Clock = Callable[[], datetime]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_clock() -> Clock:
    return utcnow
