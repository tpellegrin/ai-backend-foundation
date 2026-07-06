from typing import Any, Protocol, cast, runtime_checkable

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)


@runtime_checkable
class HttpClientSettings(Protocol):
    """Protocol for HTTP client settings."""

    connect_timeout_s: float
    read_timeout_s: float
    total_timeout_s: float
    retry_max_attempts: int
    retry_backoff_factor: float


class UpstreamProviderError(Exception):
    """Raised when an external HTTP call fails."""


def build_http_client(settings: HttpClientSettings) -> httpx.AsyncClient:
    """Build a configured httpx.AsyncClient."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=settings.connect_timeout_s,
            read=settings.read_timeout_s,
            write=settings.read_timeout_s,
            pool=settings.total_timeout_s,
        )
    )


async def request_json(  # noqa: PLR0913
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json: Any = None,  # noqa: ANN401
    params: dict[str, Any] | None = None,
    retry_non_idempotent: bool = False,
    settings: HttpClientSettings,
) -> dict[str, Any]:
    """
    Make an HTTP request and return the JSON response.
    Includes retries and error wrapping.
    """
    method = method.upper()

    def should_retry(exc: BaseException) -> bool:
        if not isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError)):
            return False

        if (
            isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500  # noqa: PLR2004
        ):
            return False

        # Non-idempotent verbs (POST, PATCH) only retry if explicitly opted-in
        return not (method in ("POST", "PATCH") and not retry_non_idempotent)

    retrier = AsyncRetrying(
        stop=stop_after_attempt(settings.retry_max_attempts),
        wait=wait_exponential_jitter(initial=settings.retry_backoff_factor),
        retry=retry_if_exception(should_retry),
        reraise=True,
    )

    try:
        async for attempt in retrier:
            with attempt:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json,
                    params=params,
                )
                response.raise_for_status()
                return cast(dict[str, Any], response.json())
    except httpx.HTTPStatusError as exc:
        raise UpstreamProviderError(f"HTTP {exc.response.status_code} from {url}") from exc  # noqa: TRY003
    except (httpx.ConnectError, httpx.ReadTimeout) as exc:
        raise UpstreamProviderError(f"Connection error to {url}") from exc  # noqa: TRY003
    except UpstreamProviderError:
        raise
    except Exception as exc:
        raise UpstreamProviderError(f"Unexpected error calling {url}") from exc  # noqa: TRY003

    raise RuntimeError("Unreachable")
