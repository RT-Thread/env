"""Error classification and retry utilities."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar


class EnvAgentError(Exception):
    """Base eagent error."""


class PromptTooLongError(EnvAgentError):
    pass


@dataclass
class RateLimitError(EnvAgentError):
    retry_after_ms: int = 5000


class OverloadedError(EnvAgentError):
    pass


class AuthenticationError(EnvAgentError):
    pass


class NetworkError(EnvAgentError):
    pass


class AbortError(EnvAgentError):
    pass


def classify_error(error: Exception) -> EnvAgentError:
    msg = str(error).lower()
    status = getattr(error, "status_code", None) or getattr(error, "status", None)

    if isinstance(error, EnvAgentError):
        return error

    if status in (401, 403):
        return AuthenticationError(str(error))

    if status == 429:
        retry_after = 5000
        headers = getattr(error, "headers", None)
        if headers:
            value = headers.get("retry-after") if hasattr(headers, "get") else None
            if value:
                try:
                    retry_after = max(1000, int(float(value) * 1000))
                except Exception:
                    retry_after = 5000
        return RateLimitError(str(error), retry_after_ms=retry_after)

    if status == 529:
        return OverloadedError(str(error))

    if "prompt" in msg and "long" in msg:
        return PromptTooLongError(str(error))

    if any(part in msg for part in ["network", "timed out", "connection", "socket", "fetch"]):
        return NetworkError(str(error))

    return EnvAgentError(str(error))


T = TypeVar("T")


async def with_retry(
    func: Callable[[int], Awaitable[T]],
    max_retries: int = 5,
    initial_delay_ms: int = 1000,
    max_delay_ms: int = 60_000,
) -> T:
    """Run coroutine with retry strategy for retryable errors."""

    consecutive_overloaded = 0
    last_error: EnvAgentError | None = None

    for attempt in range(max_retries + 1):
        try:
            return await func(attempt)
        except Exception as exc:  # pragma: no cover - path exercised in tests
            err = classify_error(exc)
            last_error = err

            if isinstance(err, (AuthenticationError, PromptTooLongError, AbortError)):
                raise err

            if attempt >= max_retries:
                raise err

            if isinstance(err, RateLimitError):
                delay_ms = err.retry_after_ms
            else:
                delay_ms = min(max_delay_ms, int(initial_delay_ms * (2**attempt)))

            if isinstance(err, OverloadedError):
                consecutive_overloaded += 1
                if consecutive_overloaded >= 3:
                    raise err
            else:
                consecutive_overloaded = 0

            jitter = 0.8 + (random.random() * 0.4)
            await asyncio.sleep((delay_ms * jitter) / 1000.0)

    raise last_error or EnvAgentError("retry failed")
