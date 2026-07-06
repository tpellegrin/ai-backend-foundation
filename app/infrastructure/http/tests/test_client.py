# ruff: noqa: S101, PLR2004
import httpx
import pytest
import respx

from app.infrastructure.http.client import (
    UpstreamProviderError,
    build_http_client,
    request_json,
)


class MockSettings:
    connect_timeout_s: float = 0.1
    read_timeout_s: float = 0.1
    total_timeout_s: float = 0.5
    retry_max_attempts: int = 3
    retry_backoff_factor: float = 0.01


@pytest.mark.unit
def test_build_http_client_honors_timeouts() -> None:
    settings = MockSettings()
    client = build_http_client(settings)
    assert client.timeout.connect == settings.connect_timeout_s
    assert client.timeout.read == settings.read_timeout_s
    assert client.timeout.write == settings.read_timeout_s
    assert client.timeout.pool == settings.total_timeout_s


@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_request_json_retries_on_503(respx_mock: respx.Router) -> None:
    settings = MockSettings()
    async with build_http_client(settings) as client:
        route = respx_mock.get("https://example.com/api").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(200, json={"foo": "bar"}),
            ]
        )

        result = await request_json(client, "GET", "https://example.com/api", settings=settings)
        assert result == {"foo": "bar"}
        assert route.call_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_request_json_raises_upstream_error_on_404(respx_mock: respx.Router) -> None:
    settings = MockSettings()
    async with build_http_client(settings) as client:
        respx_mock.get("https://example.com/api").mock(return_value=httpx.Response(404))

        with pytest.raises(UpstreamProviderError, match="HTTP 404"):
            await request_json(client, "GET", "https://example.com/api", settings=settings)


@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_request_json_no_retry_on_post_by_default(respx_mock: respx.Router) -> None:
    settings = MockSettings()
    async with build_http_client(settings) as client:
        route = respx_mock.post("https://example.com/api").mock(return_value=httpx.Response(503))

        with pytest.raises(UpstreamProviderError):
            await request_json(client, "POST", "https://example.com/api", settings=settings)

        assert route.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_request_json_retry_on_post_if_opted_in(respx_mock: respx.Router) -> None:
    settings = MockSettings()
    async with build_http_client(settings) as client:
        route = respx_mock.post("https://example.com/api").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json={"ok": True}),
            ]
        )

        result = await request_json(
            client, "POST", "https://example.com/api", retry_non_idempotent=True, settings=settings
        )
        assert result == {"ok": True}
        assert route.call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_request_json_retries_on_connect_error(respx_mock: respx.Router) -> None:
    settings = MockSettings()
    async with build_http_client(settings) as client:
        route = respx_mock.get("https://example.com/api").mock(
            side_effect=[
                httpx.ConnectError("error"),
                httpx.Response(200, json={"foo": "bar"}),
            ]
        )

        result = await request_json(client, "GET", "https://example.com/api", settings=settings)
        assert result == {"foo": "bar"}
        assert route.call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_request_json_raises_upstream_error_on_read_timeout(respx_mock: respx.Router) -> None:
    settings = MockSettings()
    async with build_http_client(settings) as client:
        respx_mock.get("https://example.com/api").mock(side_effect=httpx.ReadTimeout("timeout"))

        with pytest.raises(UpstreamProviderError, match="Connection error to"):
            await request_json(client, "GET", "https://example.com/api", settings=settings)


@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_request_json_raises_upstream_error_on_unexpected_exception(
    respx_mock: respx.Router,
) -> None:
    settings = MockSettings()
    async with build_http_client(settings) as client:
        respx_mock.get("https://example.com/api").mock(side_effect=ValueError("Unexpected"))

        with pytest.raises(UpstreamProviderError, match="Unexpected error calling"):
            await request_json(client, "GET", "https://example.com/api", settings=settings)


@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_request_json_should_not_retry_unexpected_exception(respx_mock: respx.Router) -> None:
    settings = MockSettings()
    async with build_http_client(settings) as client:
        route = respx_mock.get("https://example.com/api").mock(side_effect=ValueError("Unexpected"))

        with pytest.raises(UpstreamProviderError):
            await request_json(client, "GET", "https://example.com/api", settings=settings)

        assert route.call_count == 1
