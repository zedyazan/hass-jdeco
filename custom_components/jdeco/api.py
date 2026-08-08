"""JDECo API client."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import uuid
from typing import Any

import aiohttp
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

from .const import (
    API_BASE_URL,
    APP_SYSTEM_ID,
    DEFAULT_TIMEOUT,
    FRF_VALUE,
    METHOD_GET_AGREEMENT_DETAILS,
    METHOD_GET_AGREEMENTS,
    METHOD_GET_AGREE_DEBT,
    METHOD_GET_LAST_VOUCHER,
    METHOD_GET_KW_QTY,
    METHOD_REQUEST_PK,
    METHOD_VERIFY_CREDENTIALS,
)

_LOGGER = logging.getLogger(__name__)


class JDecoAPIError(Exception):
    """General API error."""


class JDecoAuthError(JDecoAPIError):
    """Authentication failed."""


class JDecoAPI:
    """Async API wrapper for JDECo."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        device_id: str | None = None,
    ):
        self._session = session
        self._username = username
        self._password = password
        self._device_id = device_id or str(uuid.uuid4())
        self._base_url = API_BASE_URL
        self._aes_key: bytes | None = None
        self._auth_token: str | None = None

    async def authenticate(self) -> bool:
        """Full login flow."""
        pub_key_pem = await self._request_pk()
        if not pub_key_pem:
            raise JDecoAuthError("Failed to obtain public key")

        aes_key = get_random_bytes(32)
        iv = get_random_bytes(16)
        self._aes_key = aes_key

        rsa_key = RSA.import_key(pub_key_pem)
        cipher_rsa = PKCS1_OAEP.new(rsa_key, hashlib.sha256)
        encrypted_aes_key = cipher_rsa.encrypt(aes_key)
        encrypted_aes_key_b64 = base64.b64encode(encrypted_aes_key).decode()

        login_params = {
            "userName": self._username,
            "password": self._password,
            "encryptedAesKey": encrypted_aes_key_b64,
        }
        login_result = await self._post(
            METHOD_VERIFY_CREDENTIALS, login_params, auth_required=False
        )
        if not login_result:
            raise JDecoAuthError("Empty login response")

        enc_session_b64 = login_result.get("encryptedSession")
        iv_b64 = login_result.get("iv")
        if not enc_session_b64:
            raise JDecoAuthError("No encrypted session token")

        ciphertext = base64.b64decode(enc_session_b64)
        if iv_b64:
            iv = base64.b64decode(iv_b64)
        else:
            iv = ciphertext[:16]
            ciphertext = ciphertext[16:]

        cipher_aes = AES.new(aes_key, AES.MODE_CBC, iv)
        try:
            plain_token = unpad(cipher_aes.decrypt(ciphertext), AES.block_size)
        except ValueError as err:
            raise JDecoAuthError(f"Token decryption failed: {err}")

        self._auth_token = plain_token.decode("utf-8")
        _LOGGER.debug("Authentication successful")
        return True

    async def _request_pk(self) -> str | None:
        result = await self._post(METHOD_REQUEST_PK, {}, auth_required=False)
        return result.get("publicKey") if result else None

    async def get_agreements(self) -> list[dict[str, Any]]:
        data = await self._post(METHOD_GET_AGREEMENTS, {})
        if isinstance(data, dict) and "agreements" in data:
            return data["agreements"]
        if isinstance(data, list):
            return data
        return []

    async def get_agreement_details(self, agreement_no: str) -> dict[str, Any]:
        return await self._post(METHOD_GET_AGREEMENT_DETAILS, {"agreementNo": agreement_no})

    async def get_agreement_debt(self, agreement_no: str) -> dict[str, Any]:
        return await self._post(METHOD_GET_AGREE_DEBT, {"agreementNo": agreement_no})

    async def get_last_voucher(self, agreement_no: str) -> dict[str, Any]:
        return await self._post(METHOD_GET_LAST_VOUCHER, {"agreementNo": agreement_no})

    async def get_kw_qty(self, agreement_no: str) -> dict[str, Any]:
        return await self._post(METHOD_GET_KW_QTY, {"agreementNo": agreement_no})

    async def _post(
        self, method: str, extra_params: dict, auth_required: bool = True
    ) -> dict | list | None:
        body = {
            "systemID": APP_SYSTEM_ID,
            "authKey": self._auth_token if auth_required else "",
            "GID": self._device_id,
            "FRF": FRF_VALUE,
        }
        body.update(extra_params)

        try:
            async with self._session.post(
                self._base_url,
                json=body,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as resp:
                if resp.status != 200:
                    raise JDecoAPIError(f"HTTP {resp.status}")
                text = await resp.text()
                _LOGGER.debug("Response received for method: %s (size: %d bytes)", method, len(text))
                payload = json.loads(text)
                result_key = f"{method}Result"
                return payload.get(result_key, payload)
        except aiohttp.ClientError as err:
            raise JDecoAPIError(f"Connection error: {err}") from err
        except json.JSONDecodeError as err:
            raise JDecoAPIError(f"Invalid JSON: {err}") from err
