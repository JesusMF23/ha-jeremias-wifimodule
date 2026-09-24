"""Observed WifiModule cloud protocol. Never log credentials or responses."""

import asyncio
import json

from aiohttp import ClientError, ClientTimeout

from .const import BASE_URL


class ApiError(Exception):
    """Network, response or command failure."""


class AuthError(ApiError):
    """Authentication rejected."""


class DeviceError(ApiError):
    """Selected device is missing or unsafe to control."""


class WifiModuleApi:
    """One private cookie session and serialized, bounded authentication."""

    def __init__(self, session, email, password):
        self.session = session
        self.email = email
        self.password = password
        self.authenticated = False
        self.lock = asyncio.Lock()

    async def _request(self, endpoint, body=None):
        try:
            async with self.session.request(
                "GET" if body is None else "POST",
                BASE_URL + endpoint,
                json=body,
                timeout=ClientTimeout(total=20),
                allow_redirects=False,
                headers={"Accept": "application/json"},
            ) as response:
                if response.status in (401, 403):
                    raise AuthError("Session rejected")
                if response.status != 200:
                    raise ApiError("Unexpected HTTP response")
                raw = bytearray()
                async for chunk in response.content.iter_chunked(16384):
                    raw.extend(chunk)
                    if len(raw) > 1_000_000:
                        raise ApiError("Response exceeds limit")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ApiError("Unexpected response format")
                if result.get("err") == "permissions":
                    raise AuthError("Session rejected")
                return result
        except ClientError, TimeoutError, ValueError, UnicodeError:
            # An ambiguous command failure is deliberately NOT retried.
            raise ApiError(
                "Connection or response failed; outcome may be unknown"
            ) from None

    async def _login(self):
        self.authenticated = False
        result = await self._request(
            "login", {"email": self.email, "password": self.password}
        )
        if result.get("msg") != "success":
            raise AuthError("Login rejected")
        self.authenticated = True

    async def request(self, endpoint, body=None):
        async with self.lock:
            if not self.authenticated:
                await self._login()
            try:
                return await self._request(endpoint, body)
            except AuthError:
                # Retry only after an explicit authentication rejection.
                await self._login()
                try:
                    return await self._request(endpoint, body)
                except AuthError:
                    self.authenticated = False
                    raise

    async def read(self, endpoint, key):
        result = await self.request(endpoint)
        if result.get("msg") != key or key not in result:
            raise ApiError("Unexpected API response")
        return result[key]

    async def write(self, endpoint, payload):
        result = await self.request(endpoint, payload)
        if result.get("msg") != "success":
            raise ApiError("Command not acknowledged")
        return result
