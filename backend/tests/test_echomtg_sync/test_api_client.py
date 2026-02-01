"""Tests for EchoMTG API client."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from echomtg_sync.api_client import EchoMTGClient, EchoMTGConfig


@pytest.fixture
def config():
    """Create test config."""
    return EchoMTGConfig(api_key="test_api_key")


@pytest.fixture
def client(config):
    """Create test client."""
    return EchoMTGClient(config=config)


class TestUpdateInventory:
    """Tests for update_inventory method."""

    @pytest.mark.asyncio
    async def test_sends_id_param(self, client):
        """Should send inventory id as param."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "success"}

            await client.update_inventory(inventory_id="123")

            mock.assert_called_once()
            call_args = mock.call_args
            assert call_args[0] == ("POST", "/inventory/update")
            assert call_args[1]["params"]["id"] == "123"

    @pytest.mark.asyncio
    async def test_sends_quantity_when_provided(self, client):
        """Should include quantity param when provided."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "success"}

            await client.update_inventory(inventory_id="123", quantity=5)

            params = mock.call_args[1]["params"]
            assert params["quantity"] == 5

    @pytest.mark.asyncio
    async def test_sends_condition_when_provided(self, client):
        """Should include condition param when provided."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "success"}

            await client.update_inventory(inventory_id="123", condition="LP")

            params = mock.call_args[1]["params"]
            assert params["condition"] == "LP"

    @pytest.mark.asyncio
    async def test_omits_optional_params_when_not_provided(self, client):
        """Should not include optional params when not provided."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "success"}

            await client.update_inventory(inventory_id="123")

            params = mock.call_args[1]["params"]
            assert params == {"id": "123"}


class TestRemoveInventory:
    """Tests for remove_inventory method."""

    @pytest.mark.asyncio
    async def test_sends_id_param(self, client):
        """Should send inventory id as param."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "success"}

            await client.remove_inventory(inventory_id="123")

            mock.assert_called_once_with(
                "POST", "/inventory/remove", params={"id": "123"}
            )


class TestCreateNote:
    """Tests for create_note method."""

    @pytest.mark.asyncio
    async def test_sends_note_params(self, client):
        """Should send all note params."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "success"}

            await client.create_note(
                target_id="123",
                target_app="inventory",
                note_text="Location: b3r4p100",
            )

            mock.assert_called_once_with(
                "POST",
                "/note/create",
                params={
                    "target_id": "123",
                    "target_app": "inventory",
                    "note": "Location: b3r4p100",
                },
            )


class TestRateLimiting:
    """Tests for rate limiting behavior."""

    @pytest.mark.asyncio
    async def test_enforces_rate_limit(self):
        """Multiple rapid requests should be rate limited."""
        config = EchoMTGConfig(api_key="test", rate_limit_per_second=10.0)
        client = EchoMTGClient(config=config)

        # Mock the actual HTTP request
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            start = time.monotonic()

            # Make 3 requests at 10/sec rate limit (0.1s between each)
            await client._request("GET", "/test1")
            await client._request("GET", "/test2")
            await client._request("GET", "/test3")

            elapsed = time.monotonic() - start

            # Should take at least 0.2s for 3 requests at 10/sec
            assert elapsed >= 0.18  # Allow small tolerance


class TestRetryLogic:
    """Tests for retry behavior on errors."""

    @pytest.mark.asyncio
    async def test_retries_on_500_error(self, client):
        """Should retry on 500 server errors."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                response = MagicMock()
                response.status_code = 500
                raise httpx.HTTPStatusError(
                    "Server Error",
                    request=MagicMock(),
                    response=response,
                )
            # Success on third attempt
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": "success"}
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = mock_request
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await client._request("GET", "/test")

            assert call_count == 3
            assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_retries_on_429_rate_limit(self, client):
        """Should retry with backoff on 429 rate limit error."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                response = MagicMock()
                response.status_code = 429
                raise httpx.HTTPStatusError(
                    "Rate Limited",
                    request=MagicMock(),
                    response=response,
                )
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": "success"}
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = mock_request
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await client._request("GET", "/test")

            assert call_count == 2
            assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self, config):
        """Should raise after exhausting retries."""
        config.max_retries = 2
        client = EchoMTGClient(config=config)

        async def mock_request(*args, **kwargs):
            response = MagicMock()
            response.status_code = 500
            raise httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=response,
            )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = mock_request
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(Exception, match="Failed after 2 retries"):
                await client._request("GET", "/test")

    @pytest.mark.asyncio
    async def test_does_not_retry_on_400_error(self, client):
        """Should not retry on 400 client errors."""
        async def mock_request(*args, **kwargs):
            response = MagicMock()
            response.status_code = 400
            raise httpx.HTTPStatusError(
                "Bad Request",
                request=MagicMock(),
                response=response,
            )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = mock_request
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(httpx.HTTPStatusError):
                await client._request("GET", "/test")

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self, client):
        """Should retry on timeout errors."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("Timeout")
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": "success"}
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = mock_request
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await client._request("GET", "/test")

            assert call_count == 2
            assert result == {"status": "success"}


class TestRequestHeaders:
    """Tests for request header handling."""

    @pytest.mark.asyncio
    async def test_includes_authorization_header(self, config):
        """Should include Bearer token in Authorization header."""
        client = EchoMTGClient(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await client._request("GET", "/test")

            call_args = mock_instance.request.call_args
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer test_api_key"

    @pytest.mark.asyncio
    async def test_constructs_full_url(self, config):
        """Should construct full URL from base_url and endpoint."""
        client = EchoMTGClient(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await client._request("POST", "/inventory/update")

            call_args = mock_instance.request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "https://api.echomtg.com/api/inventory/update"
