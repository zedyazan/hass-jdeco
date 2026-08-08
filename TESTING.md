# JDECo Home Assistant Integration - Testing Guide

## 📋 Pre-Testing Checklist

### Files Modified
- ✅ `api.py` - Retry logic, error handling, authentication improvements
- ✅ `coordinator.py` - Concurrent API calls for performance
- ✅ `config_flow.py` - Eliminated duplicate auth, better error messages
- ✅ `__init__.py` - Improved logging and error handling
- ✅ `sensor.py` - Null safety, availability tracking
- ✅ `const.py` - Documentation improvements

---

## 🧪 Testing Scenarios

### Scenario 1: Happy Path (All Correct)
**Goal:** Verify successful authentication and data retrieval

**Prerequisites:**
- Valid JDECo credentials (or create test dummy account)
- Home Assistant instance running latest version

**Steps:**
1. Go to **Settings → Devices & Services → Create Integration**
2. Search for "JDECo"
3. Enter **valid username and password**
4. Should see list of agreements within 10 seconds
5. Select an agreement
6. Click **Finish**
7. Should see "JDECo (agreement_number)" device created

**Expected Results:**
- ✅ No errors in HA logs
- ✅ Sensor entity created: `sensor.jdeco_remaining_kwh`
- ✅ Shows remaining kWh value
- ✅ Updates every 30 minutes (default)
- ✅ Log shows "Authentication successful" message

**Debug Logs to Check:**
```
[homeassistant.components.jdeco.config_flow] Attempting authentication...
[homeassistant.components.jdeco.config_flow] Authentication successful, fetching agreements...
[homeassistant.components.jdeco.coordinator] _async_update_data: Successfully fetched data
```

---

### Scenario 2: Wrong Credentials
**Goal:** Verify error handling for invalid login

**Steps:**
1. Go to **Settings → Devices & Services → Create Integration**
2. Search for "JDECo"
3. Enter **wrong username or password**
4. Click next

**Expected Results:**
- ✅ Shows error: "auth_failed"
- ✅ Error message states: "Authentication failed - check your username/password"
- ✅ Can retry immediately
- ✅ HA logs show specific error (not generic failure)

**Debug Logs to Check:**
```
[homeassistant.components.jdeco.config_flow] Authentication failed: Login failed: [API message]
[homeassistant.components.jdeco.api] Token decryption failed (wrong credentials?): ...
```

---

### Scenario 3: Network Error (Timeout)
**Goal:** Verify retry logic works

**Steps:**
1. Temporarily disconnect internet or firewall API endpoint
2. Go to **Settings → Devices & Services → Create Integration**
3. Search for "JDECo"
4. Enter valid credentials
5. Should attempt 3 times with backoff
6. After ~6 seconds, should show timeout error

**Expected Results:**
- ✅ Shows error: "api_error"
- ✅ Integration attempts retry 3 times with increasing delays
- ✅ Logs show retry attempts
- ✅ Eventually fails gracefully with timeout message

**Debug Logs to Check:**
```
[homeassistant.components.jdeco.api] Request timeout on attempt 1
[homeassistant.components.jdeco.api] Request timeout on attempt 2
[homeassistant.components.jdeco.api] Request timeout on attempt 3
```

---

### Scenario 4: No Agreements Found
**Goal:** Verify handling of users with no agreements

**Steps:**
1. Use a test account with no agreements linked
2. Go to **Settings → Devices & Services → Create Integration**
3. Search for "JDECo"
4. Enter credentials for account with no agreements

**Expected Results:**
- ✅ Shows error: "no_agreements"
- ✅ Logs show "Found 0 agreement(s)"
- ✅ Can retry with different credentials

---

### Scenario 5: Data Update Cycle
**Goal:** Verify concurrent API calls and proper data updates

**Steps:**
1. Complete successful setup (Scenario 1)
2. Check Home Assistant logs for update cycle
3. Wait 30 minutes for automatic update (or manually trigger via Services)
4. Check logs for concurrent execution

**Expected Results:**
- ✅ All 4 API calls run concurrently (should see all start within milliseconds)
- ✅ Total update time < 1 second (vs sequential ~2+ seconds)
- ✅ Sensor value updates
- ✅ Extra attributes update (last_voucher_amount, debt_amount, etc.)
- ✅ No errors in logs

**Debug Logs to Check:**
```
[homeassistant.components.jdeco.coordinator] Fetch the latest data concurrently
[homeassistant.components.jdeco.api] API response status: 200, method: getAgreementDetails
[homeassistant.components.jdeco.api] API response status: 200, method: getAgreeDebt
[homeassistant.components.jdeco.api] API response status: 200, method: getAgreementLastVoucher
[homeassistant.components.jdeco.api] API response status: 200, method: getKWQty
```

---

### Scenario 6: Partial API Failure
**Goal:** Verify graceful handling when one API call fails

**Steps:**
1. Complete successful setup
2. Manually trigger update
3. (Simulate one endpoint being down)

**Expected Results:**
- ✅ Update succeeds even if one call fails
- ✅ Sensor shows kWh value (if that call succeeded)
- ✅ Failed attribute shows as None in logs
- ✅ Integration stays healthy

**Debug Logs to Check:**
```
[homeassistant.components.jdeco.coordinator] Failed to get agreement debt: ...
```

---

## 🔍 Manual Testing Checklist

### Enable Debug Logging

Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    homeassistant.components.jdeco: debug
    homeassistant.components.jdeco.api: debug
    homeassistant.components.jdeco.coordinator: debug
    homeassistant.components.jdeco.config_flow: debug
```

Then restart Home Assistant and check **Settings → System → Logs**.

---

### Key Test Cases

- [ ] **Auth Success** - Valid credentials → Integration loads
- [ ] **Auth Failure** - Wrong credentials → Shows proper error
- [ ] **Network Timeout** - API unreachable → Retries 3x then fails
- [ ] **No Agreements** - Valid account, no agreements → Proper error
- [ ] **Concurrent Updates** - All 4 API calls run parallel
- [ ] **Sensor Available** - Sensor shows state + attributes
- [ ] **Update Cycle** - Auto-refresh every 30 min works
- [ ] **Partial Failure** - One API fails, others succeed
- [ ] **Unload/Reload** - Integration unloads and reloads cleanly
- [ ] **Restart HA** - Integration loads on startup without errors

---

## 📊 Performance Expectations

### Before Fixes
- Sequential API calls: ~2-2.5 seconds per update
- Single failure = entire update fails
- No error details for debugging

### After Fixes
- Concurrent API calls: ~0.5-1 second per update
- Partial failures handled gracefully
- Detailed error messages for debugging
- Network failures retry automatically (3 attempts)

---

## 🐛 If Something Fails

### Check These Logs First

1. **Config Flow Errors:**
   ```
   Settings → Devices & Services → JDECo → (3 dots) → Logs
   ```

2. **System-Wide Logs:**
   ```
   Settings → System → Logs
   ```

3. **Live Tail:**
   ```bash
   # If using SSH/terminal
   journalctl -u home-assistant -f | grep jdeco
   ```

### Common Issues & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `auth_failed` | Wrong credentials | Verify username/password |
| `api_error` | Network issue | Check internet, try again |
| `no_agreements` | Account has no agreements | Use different account |
| `Connection error` | API unavailable | Wait and retry |
| `Token decryption failed` | Wrong credentials or API change | Verify credentials |

---

## ✅ Sign-Off Checklist

When all test scenarios pass:

- [ ] Scenario 1 (Happy Path) ✓
- [ ] Scenario 2 (Wrong Credentials) ✓
- [ ] Scenario 3 (Network Error) ✓
- [ ] Scenario 4 (No Agreements) ✓
- [ ] Scenario 5 (Data Update Cycle) ✓
- [ ] Scenario 6 (Partial Failure) ✓
- [ ] Debug logging works
- [ ] Sensor shows correct values
- [ ] Attributes display properly
- [ ] No errors in logs after 1 hour runtime
- [ ] Restart HA - integration loads clean

---

## 🚀 Deployment Options

### Option 1: Local Testing (Recommended First)
1. Clone the repo: `git clone https://github.com/zedyazan/hass-jdeco.git`
2. Copy to HA: `cp -r custom_components/jdeco /config/custom_components/`
3. Restart Home Assistant
4. Run all test scenarios above
5. Check logs thoroughly

### Option 2: HACS Installation (After Testing)
Once local testing passes:
1. Add repository to HACS: `https://github.com/zedyazan/hass-jdeco`
2. Install from HACS
3. Restart Home Assistant
4. Run critical test scenarios (1, 2, 5)

### Option 3: HACS Default List (Production)
Submit to HACS default list after testing and validation.

---

## 📝 Test Report Template

```
Test Date: [DATE]
HA Version: [VERSION]
JDECo Component: [COMMIT SHA]

Scenario Results:
- [ ] Scenario 1: ✓ PASS / ✗ FAIL / ⊗ N/A
- [ ] Scenario 2: ✓ PASS / ✗ FAIL / ⊗ N/A
- [ ] Scenario 3: ✓ PASS / ✗ FAIL / ⊗ N/A
- [ ] Scenario 4: ✓ PASS / ✗ FAIL / ⊗ N/A
- [ ] Scenario 5: ✓ PASS / ✗ FAIL / ⊗ N/A
- [ ] Scenario 6: ✓ PASS / ✗ FAIL / ⊗ N/A

Issues Found:
- [List any issues]

Performance:
- Auth time: ___ seconds
- First update: ___ seconds
- Subsequent updates: ___ seconds

Sign-Off: [YOUR NAME] on [DATE]
```
