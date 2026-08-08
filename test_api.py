#!/usr/bin/env python3
"""
Test script for JDECo API client.
Usage: python test_api.py <username> <password> [agreement_no]
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import aiohttp
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import unpad
import base64
import hashlib
import logging

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_LOGGER = logging.getLogger(__name__)

# Constants
API_BASE_URL = "https://androidAPP.jdeco.net:2083/V3GACG"
APP_SYSTEM_ID = 3
FRF_VALUE = "ANDROID"
DEFAULT_TIMEOUT = 40

# Methods
METHOD_REQUEST_PK = "requestPK"
METHOD_VERIFY_CREDENTIALS = "verifyCustomerCredentials"
METHOD_GET_AGREEMENTS = "getCustomerAgreements"
METHOD_GET_AGREEMENT_DETAILS = "getAgreementDetails"
METHOD_GET_AGREE_DEBT = "getAgreeDebt"
METHOD_GET_LAST_VOUCHER = "getAgreementLastVoucher"
METHOD_GET_KW_QTY = "getKWQty"


class TestJDecoAPI:
    """Test JDECo API client."""
    
    def __init__(self, username: str, password: str, device_id: str = "test-device"):
        self.username = username
        self.password = password
        self.device_id = device_id
        self.auth_token: str | None = None
        self.session: aiohttp.ClientSession | None = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def _post(self, method: str, extra_params: dict, auth_required: bool = True) -> dict | list | None:
        """Make POST request."""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        body = {
            "systemID": APP_SYSTEM_ID,
            "authKey": self.auth_token if auth_required else "",
            "GID": self.device_id,
            "FRF": FRF_VALUE,
        }
        body.update(extra_params)
        
        _LOGGER.info(f"POST to {API_BASE_URL}")
        _LOGGER.debug(f"  Method: {method}")
        _LOGGER.debug(f"  Params: {json.dumps({k: v for k, v in extra_params.items() if k not in ['password']}, indent=2)}")
        
        try:
            async with self.session.post(
                API_BASE_URL,
                json=body,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as resp:
                text = await resp.text()
                _LOGGER.info(f"Response Status: {resp.status} (size: {len(text)} bytes)")
                
                if resp.status != 200:
                    _LOGGER.error(f"HTTP Error: {resp.status}")
                    _LOGGER.error(f"Response: {text[:500]}")
                    return None
                
                try:
                    payload = json.loads(text)
                    result_key = f"{method}Result"
                    result = payload.get(result_key, payload)
                    _LOGGER.debug(f"Parsed response: {json.dumps(result, indent=2)[:500]}")
                    return result
                except json.JSONDecodeError as e:
                    _LOGGER.error(f"Failed to parse JSON: {e}")
                    _LOGGER.error(f"Response text: {text[:500]}")
                    return None
        except asyncio.TimeoutError:
            _LOGGER.error("Request timeout")
            return None
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Connection error: {e}")
            return None
    
    async def test_public_key_request(self) -> bool:
        """Test 1: Request public key."""
        _LOGGER.info("\n" + "="*80)
        _LOGGER.info("TEST 1: Request Public Key")
        _LOGGER.info("="*80)
        
        result = await self._post(METHOD_REQUEST_PK, {}, auth_required=False)
        if result and "publicKey" in result:
            _LOGGER.info("✓ Public key obtained successfully")
            _LOGGER.debug(f"  Key length: {len(result['publicKey'])} characters")
            return True
        else:
            _LOGGER.error("✗ Failed to get public key")
            return False
    
    async def test_authentication(self, pub_key_pem: str) -> bool:
        """Test 2: Authenticate with credentials."""
        _LOGGER.info("\n" + "="*80)
        _LOGGER.info("TEST 2: Authentication")
        _LOGGER.info("="*80)
        
        try:
            # Generate AES key and IV
            aes_key = get_random_bytes(32)
            iv = get_random_bytes(16)
            
            # Encrypt AES key with RSA
            rsa_key = RSA.import_key(pub_key_pem)
            cipher_rsa = PKCS1_OAEP.new(rsa_key, hashlib.sha256)
            encrypted_aes_key = cipher_rsa.encrypt(aes_key)
            encrypted_aes_key_b64 = base64.b64encode(encrypted_aes_key).decode()
            
            _LOGGER.debug("  RSA encryption successful")
            
            # Send login request
            login_params = {
                "userName": self.username,
                "password": "***",  # Don't log password
                "encryptedAesKey": encrypted_aes_key_b64,
            }
            _LOGGER.debug(f"  Login params: {json.dumps({k: v[:20] + '...' if len(v) > 20 else v for k, v in login_params.items()})}")
            
            login_result = await self._post(
                METHOD_VERIFY_CREDENTIALS, 
                {
                    "userName": self.username,
                    "password": self.password,
                    "encryptedAesKey": encrypted_aes_key_b64,
                },
                auth_required=False
            )
            
            if not login_result:
                _LOGGER.error("✗ No login response")
                return False
            
            # Check for encrypted session
            enc_session_b64 = login_result.get("encryptedSession")
            iv_b64 = login_result.get("iv")
            
            if not enc_session_b64:
                error_msg = login_result.get("message", login_result.get("errorMessage", "Unknown error"))
                _LOGGER.error(f"✗ Login failed: {error_msg}")
                return False
            
            _LOGGER.debug("  Encrypted session received, decrypting...")
            
            # Decrypt session token
            try:
                ciphertext = base64.b64decode(enc_session_b64)
                if iv_b64:
                    iv = base64.b64decode(iv_b64)
                else:
                    iv = ciphertext[:16]
                    ciphertext = ciphertext[16:]
                
                cipher_aes = AES.new(aes_key, AES.MODE_CBC, iv)
                plain_token = unpad(cipher_aes.decrypt(ciphertext), AES.block_size)
                self.auth_token = plain_token.decode("utf-8")
                
                _LOGGER.info("✓ Authentication successful")
                _LOGGER.debug(f"  Token length: {len(self.auth_token)} characters")
                return True
            except (ValueError, Exception) as e:
                _LOGGER.error(f"✗ Token decryption failed: {e}")
                return False
        
        except Exception as e:
            _LOGGER.error(f"✗ Authentication error: {e}")
            return False
    
    async def test_get_agreements(self) -> list[dict[str, Any]]:
        """Test 3: Get agreements."""
        _LOGGER.info("\n" + "="*80)
        _LOGGER.info("TEST 3: Get Agreements")
        _LOGGER.info("="*80)
        
        if not self.auth_token:
            _LOGGER.error("✗ Not authenticated")
            return []
        
        result = await self._post(METHOD_GET_AGREEMENTS, {})
        if result:
            if isinstance(result, dict) and "agreements" in result:
                agreements = result["agreements"]
            elif isinstance(result, list):
                agreements = result
            else:
                agreements = []
            
            if agreements:
                _LOGGER.info(f"✓ Found {len(agreements)} agreement(s)")
                for i, agreement in enumerate(agreements):
                    agreement_no = agreement.get("agreementNo") or agreement.get("agreementNumber")
                    address = agreement.get("address", "")
                    _LOGGER.info(f"  [{i+1}] {agreement_no} - {address}")
                return agreements
            else:
                _LOGGER.warning("⚠ No agreements found")
                return []
        else:
            _LOGGER.error("✗ Failed to get agreements")
            return []
    
    async def test_agreement_details(self, agreement_no: str) -> bool:
        """Test 4: Get agreement details."""
        _LOGGER.info("\n" + "="*80)
        _LOGGER.info(f"TEST 4: Get Agreement Details ({agreement_no})")
        _LOGGER.info("="*80)
        
        if not self.auth_token:
            _LOGGER.error("✗ Not authenticated")
            return False
        
        result = await self._post(METHOD_GET_AGREEMENT_DETAILS, {"agreementNo": agreement_no})
        if result:
            _LOGGER.info("✓ Agreement details retrieved")
            _LOGGER.debug(f"  Response: {json.dumps(result, indent=2)[:300]}")
            return True
        else:
            _LOGGER.error("✗ Failed to get agreement details")
            return False
    
    async def test_agreement_debt(self, agreement_no: str) -> bool:
        """Test 5: Get agreement debt."""
        _LOGGER.info("\n" + "="*80)
        _LOGGER.info(f"TEST 5: Get Agreement Debt ({agreement_no})")
        _LOGGER.info("="*80)
        
        if not self.auth_token:
            _LOGGER.error("✗ Not authenticated")
            return False
        
        result = await self._post(METHOD_GET_AGREE_DEBT, {"agreementNo": agreement_no})
        if result:
            _LOGGER.info("✓ Agreement debt retrieved")
            _LOGGER.debug(f"  Response: {json.dumps(result, indent=2)[:300]}")
            return True
        else:
            _LOGGER.error("✗ Failed to get agreement debt")
            return False
    
    async def test_last_voucher(self, agreement_no: str) -> bool:
        """Test 6: Get last voucher."""
        _LOGGER.info("\n" + "="*80)
        _LOGGER.info(f"TEST 6: Get Last Voucher ({agreement_no})")
        _LOGGER.info("="*80)
        
        if not self.auth_token:
            _LOGGER.error("✗ Not authenticated")
            return False
        
        result = await self._post(METHOD_GET_LAST_VOUCHER, {"agreementNo": agreement_no})
        if result:
            _LOGGER.info("✓ Last voucher retrieved")
            _LOGGER.debug(f"  Response: {json.dumps(result, indent=2)[:300]}")
            return True
        else:
            _LOGGER.error("✗ Failed to get last voucher")
            return False
    
    async def test_kw_qty(self, agreement_no: str) -> bool:
        """Test 7: Get kW quantity."""
        _LOGGER.info("\n" + "="*80)
        _LOGGER.info(f"TEST 7: Get kW Quantity ({agreement_no})")
        _LOGGER.info("="*80)
        
        if not self.auth_token:
            _LOGGER.error("✗ Not authenticated")
            return False
        
        result = await self._post(METHOD_GET_KW_QTY, {"agreementNo": agreement_no})
        if result:
            _LOGGER.info("✓ kW quantity retrieved")
            _LOGGER.debug(f"  Response: {json.dumps(result, indent=2)[:300]}")
            return True
        else:
            _LOGGER.error("✗ Failed to get kW quantity")
            return False
    
    async def test_concurrent_calls(self, agreement_no: str) -> bool:
        """Test 8: Concurrent API calls (performance test)."""
        _LOGGER.info("\n" + "="*80)
        _LOGGER.info("TEST 8: Concurrent API Calls (Performance)")
        _LOGGER.info("="*80)
        
        if not self.auth_token:
            _LOGGER.error("✗ Not authenticated")
            return False
        
        import time
        start = time.time()
        
        try:
            results = await asyncio.gather(
                self._post(METHOD_GET_AGREEMENT_DETAILS, {"agreementNo": agreement_no}),
                self._post(METHOD_GET_AGREE_DEBT, {"agreementNo": agreement_no}),
                self._post(METHOD_GET_LAST_VOUCHER, {"agreementNo": agreement_no}),
                self._post(METHOD_GET_KW_QTY, {"agreementNo": agreement_no}),
                return_exceptions=True,
            )
            
            elapsed = time.time() - start
            
            success_count = sum(1 for r in results if r and not isinstance(r, Exception))
            _LOGGER.info(f"✓ Concurrent calls completed in {elapsed:.2f}s")
            _LOGGER.info(f"  Success: {success_count}/4 responses")
            
            return success_count == 4
        except Exception as e:
            _LOGGER.error(f"✗ Concurrent call failed: {e}")
            return False


async def main():
    """Run all tests."""
    if len(sys.argv) < 3:
        print("Usage: python test_api.py <username> <password> [agreement_no]")
        print("\nExample with dummy credentials:")
        print("  python test_api.py testuser testpass")
        print("\nExample with real credentials:")
        print("  python test_api.py your_username your_password A123456")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    agreement_no = sys.argv[3] if len(sys.argv) > 3 else None
    
    _LOGGER.info("="*80)
    _LOGGER.info("JDECo API Test Suite")
    _LOGGER.info("="*80)
    _LOGGER.info(f"Username: {username}")
    _LOGGER.info(f"Using dummy credentials: {username == 'testuser'}")
    
    async with TestJDecoAPI(username, password) as api:
        tests_passed = 0
        tests_failed = 0
        
        # Test 1: Public key request
        if await api.test_public_key_request():
            tests_passed += 1
            # Get the actual public key
            result = await api._post(METHOD_REQUEST_PK, {}, auth_required=False)
            if result and "publicKey" in result:
                pub_key = result["publicKey"]
                
                # Test 2: Authentication
                if await api.test_authentication(pub_key):
                    tests_passed += 1
                    
                    # Test 3: Get agreements
                    agreements = await api.test_get_agreements()
                    if agreements:
                        tests_passed += 1
                        
                        # Use provided agreement or first one
                        test_agreement = agreement_no or agreements[0].get("agreementNo") or agreements[0].get("agreementNumber")
                        
                        if test_agreement:
                            # Test 4: Agreement details
                            if await api.test_agreement_details(test_agreement):
                                tests_passed += 1
                            else:
                                tests_failed += 1
                            
                            # Test 5: Agreement debt
                            if await api.test_agreement_debt(test_agreement):
                                tests_passed += 1
                            else:
                                tests_failed += 1
                            
                            # Test 6: Last voucher
                            if await api.test_last_voucher(test_agreement):
                                tests_passed += 1
                            else:
                                tests_failed += 1
                            
                            # Test 7: kW quantity
                            if await api.test_kw_qty(test_agreement):
                                tests_passed += 1
                            else:
                                tests_failed += 1
                            
                            # Test 8: Concurrent calls
                            if await api.test_concurrent_calls(test_agreement):
                                tests_passed += 1
                            else:
                                tests_failed += 1
                    else:
                        tests_failed += 1
                else:
                    tests_failed += 1
        else:
            tests_failed += 1
    
    # Summary
    _LOGGER.info("\n" + "="*80)
    _LOGGER.info("TEST SUMMARY")
    _LOGGER.info("="*80)
    _LOGGER.info(f"Passed: {tests_passed}")
    _LOGGER.info(f"Failed: {tests_failed}")
    _LOGGER.info(f"Total:  {tests_passed + tests_failed}")
    _LOGGER.info("="*80)
    
    return 0 if tests_failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
