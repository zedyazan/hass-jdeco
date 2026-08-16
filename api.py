"""
JDECo API client — rewritten from test_api.py and APK analysis.

This implementation fixes PKCS1_OAEP usage (use Crypto.Hash modules) and
adds robustness for servers that accept either POST to the base URL or
POST to base_url/<method>.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from typing import Any

import aiohttp
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import unpad
from Crypto.Hash import SHA1, SHA256

from .const import (
    APP_SYSTEM_ID,
    BACKOFF_MULTIPLIER,
    CANDIDATE_BASE_URLS,
    DEFAULT_TIMEOUT,
    FRF_VALUE,
    HTTP_HEADERS,
    INITIAL_BACKOFF,
    MAX_BACKOFF,
    MAX_RETRIES,
    METHOD_GET_AGREE_DEBT,
    METHOD_GET_AGREEMENT_DETAILS,
    METHOD_GET_AGREEMENTS,
    METHOD_GET_KW_QTY,
    METHOD_GET_LAST_VOUCHER,
    METHOD_REQUEST_PK,
    METHOD_VERIFY_CREDENTIALS,
    METHOD_GET_MONTHLY_CONSUMPTION,
    METHOD_GET_ALL_VOUCHERS,
)

_LOGGER = logging.getLogger(__name__)


class JDecoAPIError(Exception):
    """General API / network error."""


class JDecoAuthError(JDecoAPIError):
    """Authentication failed (wrong credentials or token expired)."""


class JDecoAPI:
    """Async API wrapper for JDECo.

    The JDECo/WCF deployments vary: some accept POSTs to the base URL and dispatch
    based on the JSON envelope, others expect the method name as a path segment.
    To be robust we try the base URL first and fall back to base_url/<method>.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        device_id: str | None = None,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._device_id = (
            device_id or str(uuid.uuid4()).replace("-", "").upper()[:32]
        )
        self._auth_token: str | None = None
        self._working_base_url: str | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    async def authenticate(self) -> bool:
        """Discover working endpoint and authenticate.

        Tries each candidate base URL. For each URL we attempt login and token decryption.
        """
        errors: list[str] = []

        for base_url in CANDIDATE_BASE_URLS:
            _LOGGER.debug("Trying JDECo endpoint: %s", base_url)
            try:
                if await self._try_auth(base_url):
                    return True
            except JDecoAuthError:
                raise
            except Exception as exc:
                errors.append(f"{base_url}: {exc}")
                _LOGGER.debug("Endpoint %s failed: %s", base_url, exc)
                continue

        raise JDecoAuthError(
            "All JDECo endpoints failed.\n" + "\n".join(errors[:4])
        )

    async def _try_auth(self, base_url: str) -> bool:
        """Full auth attempt against one base URL."""
        url = base_url.rstrip("/")

        # ── Step 1: Get server RSA public key ─────────────────────────────
        # Post and accept whatever wrapper the server returns
        pk_resp = await self._call(url, METHOD_REQUEST_PK, {}, auth_required=False)

        if not pk_resp:
            raise JDecoAPIError(f"No response from {url} for requestPK")

        # Server returns {publicKey: "<base64>"} (different names seen)
        server_pub_b64 = (
            pk_resp.get("publicKey")
            or pk_resp.get("serverPublicKey")
            or pk_resp.get("PK")
        )
        if not server_pub_b64:
            raise JDecoAPIError(
                f"No publicKey in requestPK response: {str(pk_resp)[:200]}"
            )
        _LOGGER.debug("Server RSA public key received (%d chars)", len(server_pub_b64))

        # ── Step 2: Login ─────────────────────────────────────────────────
        # Generate AES-256 session key, encrypt with server's RSA public key
        aes_key = get_random_bytes(32)
        server_rsa = RSA.import_key(base64.b64decode(server_pub_b64))

        # Try SHA-256 first (preferred), then SHA-1 fallback.
        for hash_module, label in [(SHA256, "SHA-256"), (SHA1, "SHA-1")]:
            try:
                cipher_rsa = PKCS1_OAEP.new(server_rsa, hashAlgo=hash_module)
                enc_aes = base64.b64encode(cipher_rsa.encrypt(aes_key)).decode()

                login_resp = await self._call(
                    url,
                    METHOD_VERIFY_CREDENTIALS,
                    {
                        "userName": self._username,
                        "password": self._password,
                        "encryptedAesKey": enc_aes,
                    },
                    auth_required=False,
                )

                if not login_resp or not isinstance(login_resp, dict):
                    _LOGGER.debug("Login: no dict response with %s", label)
                    continue

                # Check for auth failure
                err_code = login_resp.get("errorCode") or login_resp.get("code")
                err_msg = login_resp.get("message") or login_resp.get("errorMessage", "")
                if err_code is not None and str(err_code) not in ("0", "200", ""):
                    raise JDecoAuthError(
                        f"Authentication failed: {err_msg or err_code}"
                    )

                # Decrypt encrypted session → auth token
                enc_session = login_resp.get("encryptedSession")
                if enc_session:
                    iv_b64 = login_resp.get("iv")
                    token = self._decrypt_session(enc_session, iv_b64, aes_key)
                    self._auth_token = token
                    self._working_base_url = url
                    _LOGGER.info("JDECo authenticated via %s [RSA-%s]", url, label)
                    return True

                # Some versions return a plain token
                plain = (
                    login_resp.get("authKey")
                    or login_resp.get("token")
                    or login_resp.get("sessionToken")
                )
                if plain and isinstance(plain, str) and len(plain) > 4:
                    self._auth_token = plain
                    self._working_base_url = url
                    _LOGGER.info(
                        "JDECo authenticated via %s (plain token) [RSA-%s]",
                        url, label,
                    )
                    return True

                _LOGGER.debug("Login response had no token [%s]: %s", label, login_resp)

            except JDecoAuthError:
                raise
            except Exception as exc:
                _LOGGER.debug("RSA-%s auth attempt failed: %s", label, exc)
                continue

        raise JDecoAPIError(f"Login succeeded but no session token from {url}")

    @staticmethod
    def _decrypt_session(enc_b64: str, iv_b64: str | None, aes_key: bytes) -> str:
        """AES-CBC decrypt the session token."""
        ct = base64.b64decode(enc_b64)
        if iv_b64:
            iv = base64.b64decode(iv_b64)
        else:
            iv, ct = ct[:16], ct[16:]
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(ct), AES.block_size).decode("utf-8")

    # ── Data methods ──────────────────────────────────────────────────────────

    async def get_agreements(self) -> list[dict[str, Any]]:
        data = await self._authenticated_call(METHOD_GET_AGREEMENTS, {})
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in ("agreements", "customerAgreements", "data"):
                if isinstance(data.get(k), list):
                    return data[k]
        return []

    async def get_agreement_details(self, agree_no: str) -> dict[str, Any]:
        res = await self._authenticated_call(
            METHOD_GET_AGREEMENT_DETAILS, {"agreementNo": agree_no}
        )
        return res if isinstance(res, dict) else {}

    async def get_agreement_debt(self, agree_no: str) -> dict[str, Any]:
        res = await self._authenticated_call(
            METHOD_GET_AGREE_DEBT, {"agreementNo": agree_no}
        )
        return res if isinstance(res, dict) else {}

    async def get_last_voucher(self, agree_no: str) -> dict[str, Any]:
        res = await self._authenticated_call(
            METHOD_GET_LAST_VOUCHER, {"agreementNo": agree_no}
        )
        return res if isinstance(res, dict) else {}

    async def get_kw_qty(self, agree_no: str) -> dict[str, Any]:
        res = await self._authenticated_call(
            METHOD_GET_KW_QTY, {"agreementNo": agree_no}
        )
        return res if isinstance(res, dict) else {}

    async def get_monthly_consumption(self, agree_no: str) -> list[dict[str, Any]]:
        res = await self._authenticated_call(
            METHOD_GET_MONTHLY_CONSUMPTION, {"agreementNo": agree_no}
        )
        if isinstance(res, list):
            return res
        if isinstance(res, dict):
            for k in ("monthlyConsumption", "data", "consumption"):
                if isinstance(res.get(k), list):
                    return res[k]
        return []

    async def get_all_vouchers(self, agree_no: str) -> list[dict[str, Any]]:
        res = await self._authenticated_call(
            METHOD_GET_ALL_VOUCHERS, {"agreementNo": agree_no}
        )
        if isinstance(res, list):
            return res
        if isinstance(res, dict):
            for k in ("vouchers", "data"):
                if isinstance(res.get(k), list):
                    return res[k]
        return []

    async def get_all_data(self, agree_no: str) -> dict[str, Any]:
        """Fetch all sensor data concurrently."""
        results = await asyncio.gather(
            self.get_agreement_details(agree_no),
            self.get_agreement_debt(agree_no),
            self.get_last_voucher(agree_no),
            self.get_kw_qty(agree_no),
            return_exceptions=True,
        )

        def _safe(v, default):
            return default if isinstance(v, Exception) else v

        for val, name in zip(results, [
            "get_agreement_details", "get_agreement_debt",
            "get_last_voucher", "get_kw_qty"
        ]):
            if isinstance(val, Exception):
                _LOGGER.debug("%s failed: %s", name, val)

        return {
            "details": _safe(results[0], {}),
            "debt": _safe(results[1], {}),
            "last_voucher": _safe(results[2], {}),
            "kw_qty": _safe(results[3], {}),
            "agreement_no": agree_no,
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _authenticated_call(self, method: str, params: dict) -> Any:
        if not self._working_base_url:
            raise JDecoAuthError("Not authenticated — call authenticate() first")
        return await self._call(self._working_base_url, method, params, auth_required=True)

    async def _call(
        self,
        base_url: str,
        method: str,
        params: dict,
        auth_required: bool = True,
    ) -> Any:
        """
        POST to the service. To handle different deployments we try URL variants:
          1) base_url (no path method)
          2) base_url/<method>

        Each variant gets the same retry/backoff logic.
        """
        base = base_url.rstrip("/")
        url_variants = [base, f"{base}/{method}"]

        envelope: dict[str, Any] = {
            "systemID": APP_SYSTEM_ID,
            "authKey": self._auth_token if auth_required else "",
            "GID": self._device_id,
            "FRF": FRF_VALUE,
        }
        envelope.update(params)

        # Try each URL variant until one returns a valid payload
        last_exc: Exception | None = None
        for url in url_variants:
            backoff = INITIAL_BACKOFF
            for attempt in range(MAX_RETRIES):
                try:
                    _LOGGER.debug("POST %s (attempt %d)", url, attempt + 1)
                    async with self._session.post(
                        url,
                        json=envelope,
                        headers=HTTP_HEADERS,
                        timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
                        ssl=False,
                    ) as resp:
                        raw = await resp.read()
                        text = raw.decode("utf-8-sig", errors="replace").strip()

                        _LOGGER.debug(
                            "HTTP %d from %s (%d bytes): %.300s",
                            resp.status, url, len(text), text,
                        )

                        if resp.status == 401:
                            raise JDecoAuthError("HTTP 401 Unauthorized")
                        if resp.status == 404:
                            raise JDecoAPIError(f"HTTP 404: {url}")
                        if resp.status not in (200, 201):
                            raise JDecoAPIError(f"HTTP {resp.status} from {url}: {text[:200]}")
                        if not text:
                            raise JDecoAPIError(f"Empty response from {url}")

                        return self._parse(text, method)

                except (JDecoAuthError, JDecoAPIError) as exc:
                    # Don't retry definitive failures unless we want to try the other URL variant
                    last_exc = exc
                    msg = str(exc)
                    if any(s in msg for s in ("401", "404", "Empty", "Invalid credentials")):
                        _LOGGER.debug("Definitive failure for %s: %s", url, exc)
                        break
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF)
                        continue
                    break

                except asyncio.TimeoutError:
                    last_exc = JDecoAPIError(f"Timeout: {url}")
                    if attempt < MAX_RETRIES - 1:
                        _LOGGER.warning("Timeout attempt %d for %s, retrying...", attempt + 1, url)
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF)
                        continue
                    break

                except aiohttp.ClientError as exc:
                    last_exc = JDecoAPIError(f"Network error: {exc}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF)
                        continue
                    break

            # If we got a definitive error that is a "try next URL" case (Empty/404), continue to next variant.
            if isinstance(last_exc, JDecoAPIError):
                msg = str(last_exc)
                if any(s in msg for s in ("404", "Empty response")):
                    _LOGGER.debug("Trying next URL variant after %s failure: %s", url, last_exc)
                    last_exc = None
                    continue

            # If auth error bubbled up, raise immediately
            if isinstance(last_exc, JDecoAuthError):
                raise last_exc

        raise last_exc or JDecoAPIError(f"Failed after {MAX_RETRIES} attempts across URL variants: {base}/{method}")

    @staticmethod
    def _parse(text: str, method: str) -> Any:
        """Parse WCF JSON response. Handles double-encoding and Result wrapper."""
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            if text.startswith('"') and text.endswith('"'):
                try:
                    payload = json.loads(json.loads(text))
                except Exception as exc:
                    raise JDecoAPIError(f"Double-encoded JSON parse error: {exc}") from exc
            else:
                raise JDecoAPIError(f"Invalid JSON: {text[:200]}")

        if isinstance(payload, dict):
            # Check API-level errors
            err_code = payload.get("errorCode") or payload.get("code")
            if err_code is not None and str(err_code) not in ("0", "200", ""):
                err_msg = (
                    payload.get("message")
                    or payload.get("errorMessage")
                    or f"Error {err_code}"
                )
                raise JDecoAPIError(f"API error: {err_msg}")

            # Unwrap WCF result envelope: {requestPKResult: {...}}
            result_key = f"{method}Result"
            if result_key in payload:
                return payload[result_key]

        return payload
