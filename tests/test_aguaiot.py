"""Test the aguaiot class."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.helpers import (
    AguaIOTConnectionError,
    AguaIOTUnauthorized,
    AguaIOTUpdateError,
    aguaiot,
)


class FakeDevice:
    """Device stub which fails or succeeds on every update."""

    def __init__(self, name, fail=False):
        self.name = name
        self.fail = fail
        self.updated = False

    async def update(self):
        if self.fail:
            raise AguaIOTUpdateError(f"Failed to update {self.name}")
        self.updated = True


class TestHeaders:
    def test_default_headers(self, aguaiot_mock):
        headers = aguaiot_mock._headers()
        assert headers["id_brand"] == "1"
        assert headers["customer_code"] == "000000"
        assert headers["Accept"] == "application/json, text/javascript, */*; q=0.01"
        assert headers["Content-Type"] == "application/json"
        assert "brand" not in headers

    def test_brand_in_headers(self):
        inst = aguaiot(
            api_url="https://example.com",
            customer_code="000000",
            email="test@example.com",
            password="test",
            unique_id="test-uuid",
            brand_id="2",
            brand="superior",
        )
        headers = inst._headers()
        assert headers["id_brand"] == "2"
        assert headers["brand"] == "superior"

    def test_brand_id_defaults_to_one(self):
        inst = aguaiot(
            api_url="https://example.com",
            customer_code="000000",
            email="test@example.com",
            password="test",
            unique_id="test-uuid",
            brand="superior",
        )
        headers = inst._headers()
        assert headers["id_brand"] == "1"
        assert headers["brand"] == "superior"


class TestInit:
    def test_default_values(self):
        inst = aguaiot(
            api_url="https://example.com",
            customer_code="123456",
            email="user@example.com",
            password="secret",
            unique_id="abc-123",
        )
        assert inst.api_url == "https://example.com"
        assert inst.customer_code == "123456"
        assert inst.email == "user@example.com"
        assert inst.unique_id == "abc-123"
        assert inst.token is None
        assert inst.devices == []
        assert inst.air_temp_fix is False
        assert inst.reading_error_fix is False
        assert inst.language == "ENG"
        assert inst.http_timeout == 30
        assert inst.buffer_read_timeout == 30

    def test_custom_values(self):
        inst = aguaiot(
            api_url="https://custom.com/",
            customer_code="999999",
            email="a@b.com",
            password="pass",
            unique_id="id",
            air_temp_fix=True,
            reading_error_fix=True,
            language="ITA",
            http_timeout=60,
            buffer_read_timeout=45,
        )
        assert inst.api_url == "https://custom.com"
        assert inst.air_temp_fix is True
        assert inst.reading_error_fix is True
        assert inst.language == "ITA"
        assert inst.http_timeout == 60
        assert inst.buffer_read_timeout == 45

    def test_url_strips_trailing_slash(self):
        inst = aguaiot("https://test.com/", "000", "a@b.com", "p", "id")
        assert inst.api_url == "https://test.com"


class TestConnectFlow:
    @pytest.mark.asyncio
    async def test_register_app_id_http_error(self):
        inst = aguaiot(
            api_url="https://example.com",
            customer_code="000000",
            email="test@example.com",
            password="test",
            unique_id="test-uuid",
        )

        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        inst.async_client = mock_client

        with pytest.raises(AguaIOTUnauthorized):
            await inst.register_app_id()

    @pytest.mark.asyncio
    async def test_register_app_id_unauthorized(self):
        inst = aguaiot(
            api_url="https://example.com",
            customer_code="000000",
            email="test@example.com",
            password="test",
            unique_id="test-uuid",
        )

        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        inst.async_client = mock_client

        with pytest.raises(AguaIOTUnauthorized):
            await inst.register_app_id()

    @pytest.mark.asyncio
    async def test_register_app_id_success(self):
        inst = aguaiot(
            api_url="https://example.com",
            customer_code="000000",
            email="test@example.com",
            password="test",
            unique_id="test-uuid",
        )

        mock_response = AsyncMock()
        mock_response.status_code = 201
        mock_response.text = "Created"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        inst.async_client = mock_client

        result = await inst.register_app_id()
        assert result is True

    @pytest.mark.asyncio
    async def test_login_success(self):
        import time

        import jwt

        inst = aguaiot(
            api_url="https://example.com",
            customer_code="000000",
            email="test@example.com",
            password="test",
            unique_id="test-uuid",
        )

        future_exp = int(time.time()) + 3600
        token = jwt.encode(
            {"exp": future_exp},
            "secret",
            algorithm="HS256",
        )

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "token": token,
                "refresh_token": "refresh-123",
            }
        )
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        inst.async_client = mock_client

        result = await inst.login()
        assert result is True
        assert inst.token == token
        assert inst.refresh_token == "refresh-123"
        assert inst.token_expires == future_exp

    @pytest.mark.asyncio
    async def test_login_unauthorized(self):
        inst = aguaiot(
            api_url="https://example.com",
            customer_code="000000",
            email="test@example.com",
            password="test",
            unique_id="test-uuid",
        )

        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        inst.async_client = mock_client

        with pytest.raises(AguaIOTUnauthorized):
            await inst.login()


class TestUpdate:
    @pytest.mark.asyncio
    async def test_failing_device_raises_error(self, aguaiot_mock):
        aguaiot_mock.devices = [FakeDevice("failing", fail=True)]

        with pytest.raises(AguaIOTUpdateError):
            await aguaiot_mock.update()

    @pytest.mark.asyncio
    async def test_failing_device_does_not_stop_other_devices(self, aguaiot_mock):
        working = FakeDevice("working")
        aguaiot_mock.devices = [FakeDevice("failing", fail=True), working]

        await aguaiot_mock.update()

        assert working.updated is True

    @pytest.mark.asyncio
    async def test_all_devices_failing_raises_error(self, aguaiot_mock):
        aguaiot_mock.devices = [
            FakeDevice("failing-1", fail=True),
            FakeDevice("failing-2", fail=True),
        ]

        with pytest.raises(AguaIOTUpdateError):
            await aguaiot_mock.update()

    @pytest.mark.asyncio
    async def test_no_devices_does_not_raise_error(self, aguaiot_mock):
        aguaiot_mock.devices = []

        await aguaiot_mock.update()


class TestHttpClient:
    """Exercise the component with a real HTTP client transport.

    The component imports ``httpx`` at module level.  Home Assistant aliases that
    name to ``httpx2`` on newer releases, while older releases use ``httpx``.
    These tests import ``httpx`` lazily, after ``tests.helpers`` has installed
    the alias, so both setups exercise the same code path.
    """

    @pytest.mark.asyncio
    async def test_login_over_http_client(self):
        import time

        import httpx
        import jwt

        token = jwt.encode(
            {"exp": int(time.time()) + 3600},
            "test-secret-key-that-is-at-least-32-bytes-long",
            algorithm="HS256",
        )
        captured = {}

        async def handler(request):
            captured["method"] = request.method
            captured["url"] = str(request.url)
            captured["authorization"] = request.headers.get("Authorization")
            captured["local"] = request.headers.get("local")
            captured["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={"token": token, "refresh_token": "refresh-123"},
            )

        inst = aguaiot(
            api_url="https://example.com",
            customer_code="000000",
            email="test@example.com",
            password="test",
            unique_id="test-uuid",
            async_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

        try:
            assert await inst.login() is True
        finally:
            await inst.async_client.aclose()

        assert captured["method"] == "POST"
        assert captured["url"] == "https://example.com/userLogin"
        assert captured["authorization"] == "test-uuid"
        assert captured["local"] == "true"
        assert captured["payload"] == {
            "email": "test@example.com",
            "password": "test",
        }
        assert inst.token == token
        assert inst.refresh_token == "refresh-123"
        assert inst.token_expires > time.time()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "expected_url", "expected_payload"),
        [
            ("GET", "https://example.com/deviceList?id=1", {}),
            ("POST", "https://example.com/deviceList", {"id": "1"}),
        ],
    )
    async def test_handle_webcall_over_http_client(
        self, method, expected_url, expected_payload
    ):
        import time

        import httpx

        captured = {}

        async def handler(request):
            captured["method"] = request.method
            captured["url"] = str(request.url)
            captured["authorization"] = request.headers.get("Authorization")
            captured["local"] = request.headers.get("local")
            captured["payload"] = json.loads(request.content) if request.content else {}
            return httpx.Response(200, json={"result": "ok"})

        inst = aguaiot(
            api_url="https://example.com",
            customer_code="000000",
            email="test@example.com",
            password="test",
            unique_id="test-uuid",
            async_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        inst.token = "token-123"
        inst.refresh_token = "refresh-123"
        inst.token_expires = time.time() + 3600

        try:
            result = await inst.handle_webcall(
                method, "https://example.com/deviceList", {"id": "1"}
            )
        finally:
            await inst.async_client.aclose()

        assert result == {"result": "ok"}
        assert captured["method"] == method
        assert captured["url"] == expected_url
        assert captured["authorization"] == "token-123"
        assert captured["local"] == "false"
        assert captured["payload"] == expected_payload

    @pytest.mark.asyncio
    async def test_handle_webcall_transport_error(self):
        import time

        import httpx

        async def handler(request):
            raise httpx.ConnectError("connection refused")

        inst = aguaiot(
            api_url="https://example.com",
            customer_code="000000",
            email="test@example.com",
            password="test",
            unique_id="test-uuid",
            async_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        inst.token = "token-123"
        inst.refresh_token = "refresh-123"
        inst.token_expires = time.time() + 3600

        try:
            with pytest.raises(AguaIOTConnectionError):
                await inst.handle_webcall("GET", "https://example.com/deviceList", {})
        finally:
            await inst.async_client.aclose()
