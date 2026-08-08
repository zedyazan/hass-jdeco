"""JDECo API client."""
from __future__ import annotations

import asyncio
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

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 16.0  # seconds
BACKOFF_MULTIPLIER = 2.0


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
        self._public_key: str | None = None  # Cache public key

    async def authenticate(self) -> bool:
        """Full login flow with improved error handling."""
        try:
            pub_key_pem = await self._request_pk()
            if not pub_key_pem:
                raise JDecoAuthError("Failed to obtain public key from server")

            _LOGGER.debug("Public key obtained, proceeding with credential encryption")

            # Generate fresh AES key and IV for this session
            aes_key = get_random_bytes(32)
            iv = get_random_bytes(16)
            self._aes_key = aes_key

            try:
                rsa_key = RSA.import_key(pub_key_pem)
                cipher_rsa = PKCS1_OAEP.new(rsa_key, hashlib.sha256)
                encrypted_aes_key = cipher_rsa.encrypt(aes_key)
                encrypted_aes_key_b64 = base64.b64encode(encrypted_aes_key).decode()
            except (ValueError, IndexError) as err:
                raise JDecoAuthError(f"Failed to encrypt AES key: {err}") from err

            login_params = {
                "userName": self._username,
                "password": self._password,
                "encryptedAesKey": encrypted_aes_key_b64,
            }
            login_result = await self._post(
                METHOD_VERIFY_CREDENTIALS, login_params, auth_required=False
            )
            if not login_result:
                raise JDecoAuthError("Empty login response from server")

            enc_session_b64 = login_result.get("encryptedSession")
            iv_b64 = login_result.get("iv")
            
            if not enc_session_b64:
                error_msg = login_result.get("message", "Unknown error")
                raise JDecoAuthError(f"Login failed: {error_msg}")

            try:
                ciphertext = base64.b64decode(enc_session_b64)
            except Exception as err:
                raise JDecoAuthError(f"Failed to decode encrypted session: {err}") from err

            if iv_b64:
                try:
                    iv = base64.b64decode(iv_b64)
                except Exception as err:
                    raise JDecoAuthError(f"Failed to decode IV: {err}") from err
            else:
                iv = ciphertext[:16]
                ciphertext = ciphertext[16:]

            cipher_aes = AES.new(aes_key, AES.MODE_CBC, iv)
            try:
                plain_token = unpad(cipher_aes.decrypt(ciphertext), AES.block_size)
            except ValueError as err:
                raise JDecoAuthError(f"Token decryption failed (wrong credentials?): {err}") from err

            self._auth_token = plain_token.decode("utf-8")
            _LOGGER.debug("Authentication successful, token obtained")
            return True
        
        except JDecoAuthError:
            raise
        except Exception as err:
            raise JDecoAuthError(f"Unexpected error during authentication: {err}") from err

    async def _request_pk(self) -> str | None:
        """Request public key with caching."""
        if self._public_key:
            return self._public_key
        
        result = await self._post(METHOD_REQUEST_PK, {}, auth_required=False)
        if result and "publicKey" in result:
            self._public_key = result["publicKey"]
            return self._public_key
        return None

    async def get_agreements(self) -> list[dict[str, Any]]:
        """Get list of agreements."""
        data = await self._post(METHOD_GET_AGREEMENTS, {})
        if isinstance(data, dict) and "agreements" in data:
            return data["agreements"]
        if isinstance(data, list):
            return data
        return []

    async def get_agreement_details(self, agreement_no: str) -> dict[str, Any]:
        """Get agreement details."""
        return await self._post(METHOD_GET_AGREEMENT_DETAILS, {"agreementNo": agreement_no})

    async def get_agreement_debt(self, agreement_no: str) -> dict[str, Any]:
        """Get agreement debt."""
        return await self._post(METHOD_GET_AGREE_DEBT, {"agreementNo": agreement_no})

    async def get_last_voucher(self, agreement_no: str) -> dict[str, Any]:
        """Get last voucher."""
        return await self._post(METHOD_GET_LAST_VOUCHER, {"agreementNo": agreement_no})

    async def get_kw_qty(self, agreement_no: str) -> dict[str, Any]:
        """Get remaining kWh quantity."""
        return await self._post(METHOD_GET_KW_QTY, {"agreementNo": agreement_no})

    async def _post(
        self, method: str, extra_params: dict, auth_required: bool = True
    ) -> dict | list | None:
        """Make a POST request with retry logic."""
        body = {
            "systemID": APP_SYSTEM_ID,
            "authKey": self._auth_token if auth_required else "",
            "GID": self._device_id,
            "FRF": FRF_VALUE,
        }
        body.update(extra_params)

        # Retry loop with exponential backoff
        last_error = None
        backoff = INITIAL_BACKOFF
        
        for attempt in range(MAX_RETRIES):
            try:
                async with self._session.post(
                    self._base_url,
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        error_msg = f"HTTP {resp.status}: {text[:200]}"
                        _LOGGER.warning("API error on attempt %d: %s", attempt + 1, error_msg)
                        last_error = JDecoAPIError(error_msg)
                        
                        # Don't retry on auth errors
                        if resp.status == 401:
                            raise JDecoAuthError("Unauthorized - check credentials")
                        
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(backoff)
                            backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF)
                            continue
                        raise last_error
                    
                    text = await resp.text()
                    # Only log method and response size to avoid sensitive data leaks
                    _LOGGER.debug("API response status: 200, method: %s, size: %d bytes", method, len(text))
                    
                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError as err:
                        raise JDecoAPIError(f"Invalid JSON response: {err}") from err
                    
                    # Check for API-level errors in the response
                    if isinstance(payload, dict):
                        if "errorCode" in payload and payload["errorCode"] != 0:
                            error_msg = payload.get("message", f"API error code {payload['errorCode']}")
                            raise JDecoAPIError(f"API returned error: {error_msg}")
                    
                    result_key = f"{method}Result"
                    return payload.get(result_key, payload)
                    
            except asyncio.TimeoutError as err:
                error_msg = "Request timeout"
                _LOGGER.warning("%s on attempt %d", error_msg, attempt + 1)
                last_error = JDecoAPIError(error_msg)
                
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF)
                    continue
                raise last_error
                
            except aiohttp.ClientError as err:
                error_msg = f"Connection error: {err}"
                _LOGGER.warning("%s on attempt %d", error_msg, attempt + 1)
                last_error = JDecoAPIError(error_msg)
                
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF)
                    continue
                raise last_error
        
        # Should not reach here, but just in case
        raise last_error or JDecoAPIError("Unknown error after retries")
