from __future__ import annotations

import time
from typing import Any, Callable, TypeVar


T = TypeVar("T")


def retry_call(
    func: Callable[[], T],
    *,
    attempts: int = 3,
    delay_seconds: float = 0.1,
    retryable: Callable[[Exception], bool] | None = None,
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as exc:
            last_error = exc
            should_retry = retryable(exc) if retryable is not None else True
            if attempt == attempts or not should_retry:
                raise
            time.sleep(delay_seconds * attempt)
    assert last_error is not None
    raise last_error
