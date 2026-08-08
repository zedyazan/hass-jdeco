# Quick Start Guide - Local Testing

## 🚀 Get Started in 5 Minutes

### Prerequisites
- Home Assistant running (any installation method)
- SSH access to your Home Assistant server OR file manager access
- Valid JDECo account (or dummy credentials for initial testing)

---

## ⚡ Option A: Quick Local Install (Docker/Linux)

### Step 1: SSH into Home Assistant
```bash
ssh homeassistant@your-ha-ip
# Password: your-ssh-password
```

### Step 2: Download & Install
```bash
# Clone the repo
git clone https://github.com/zedyazan/hass-jdeco.git /tmp/jdeco
# Copy to custom_components
cp -r /tmp/jdeco/custom_components/jdeco ~/.homeassistant/custom_components/
# Cleanup
rm -rf /tmp/jdeco
```

### Step 3: Restart Home Assistant
```bash
# Via Home Assistant UI:
# Settings → System → Restart

# Or via SSH:
sudo systemctl restart home-assistant@homeassistant
```

---

## 📁 Option B: Manual File Upload (Using File Manager)

### Step 1: Download Files
- Go to https://github.com/zedyazan/hass-jdeco
- Click **Code** → **Download ZIP**
- Extract the zip file

### Step 2: Upload to Home Assistant
1. Open Home Assistant **Settings → System → File editor**
2. Navigate to `config/custom_components/` 
3. Create folder `jdeco`
4. Upload these files from the downloaded ZIP:
   - `custom_components/jdeco/__init__.py`
   - `custom_components/jdeco/api.py`
   - `custom_components/jdeco/config_flow.py`
   - `custom_components/jdeco/const.py`
   - `custom_components/jdeco/coordinator.py`
   - `custom_components/jdeco/manifest.json`
   - `custom_components/jdeco/sensor.py`
   - `custom_components/jdeco/strings.json`

### Step 3: Restart Home Assistant
- **Settings → System → Restart**

---

## ✅ Verify Installation

### Check If Component Loaded
1. Go to **Settings → Devices & Services**
2. Look for **"JDECo"** in the integrations list
3. If not visible, check logs:
   - **Settings → System → Logs**
   - Search for `jdeco`

---

## 🧪 Test with Dummy Account

### Create a Test Account (Optional)
If you don't have real JDECo credentials:

1. Use a dummy account with format:
   - **Username:** `test@example.com` or `+1234567890`
   - **Password:** Any password

2. Expected behavior:
   - ✅ Should attempt authentication
   - ✅ Should show API error with retry
   - ✅ Error message should be clear
   - ✅ Integration stays clean for real credentials

### With Real Credentials
1. Use your actual JDECo app username/password
2. You should see your agreement in the dropdown
3. Select agreement → Click **Finish**

---

## 🔍 Monitor First Run

### 1. Enable Debug Logging

Edit `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    homeassistant.components.jdeco: debug
    homeassistant.components.jdeco.api: debug
    homeassistant.components.jdeco.coordinator: debug
    homeassistant.components.jdeco.config_flow: debug
```

Save and **Settings → System → Restart**

### 2. Watch the Logs

Go to **Settings → System → Logs** and search for:
- `jdeco` - Shows all component logs
- Look for patterns:

✅ **Success:**
```
Authentication successful, token obtained
Found 1 agreement(s), proceeding to selection
Authentication successful
```

❌ **Failure:**
```
Authentication failed: Login failed: [reason]
API error: Connection error
Request timeout
```

### 3. Check Sensor

Once setup completes:
1. Go to **Developer Tools → States**
2. Search for `sensor.jdeco_remaining_kwh`
3. Should show a kWh value

---

## 🐛 Troubleshooting

### Component Not Showing in Integration List

**Solution:**
1. Restart Home Assistant (full restart, not quick reload)
2. Wait 30 seconds
3. Go to **Settings → Devices & Services**
4. Click **Create Integration**
5. Search for "JDECo"

If still not visible:
```bash
# Check for errors
docker logs homeassistant 2>&1 | grep -i jdeco
# or
journalctl -u home-assistant -n 50 | grep jdeco
```

### Authentication Fails with Correct Credentials

1. **Check internet connectivity:**
   ```bash
   ping androidAPP.jdeco.net
   ```

2. **Verify JDECo API is up:** Visit https://www.jdeco.net in browser

3. **Check Home Assistant logs for the exact error**

4. **Try again** - API might be temporarily down

### Sensor Shows "Unknown" State

1. **Wait for first update** - Can take 30-60 seconds
2. **Check coordinator data:**
   - **Developer Tools → Template**
   - Enter: `{{ states('sensor.jdeco_remaining_kwh') }}`

3. **Force update:**
   ```yaml
   # In Developer Tools → Services
   Service: homeassistant.update_entity
   Target: sensor.jdeco_remaining_kwh
   ```

---

## 📊 Performance Check

### Measure Update Speed

1. Enable debug logging (see above)
2. Wait for an update cycle
3. Check logs for timing:

```
[coordinator] Fetching data...
[api] API response status: 200, method: getAgreementDetails
[api] API response status: 200, method: getAgreeDebt
[api] API response status: 200, method: getAgreementLastVoucher
[api] API response status: 200, method: getKWQty
[coordinator] Update complete in 0.8 seconds ✅
```

**Expected:** `0.5-1.5 seconds` (all 4 calls concurrent)

---

## 📁 File Locations

### Where Files Go
```
/config/
├── custom_components/
│   └── jdeco/
│       ├── __init__.py
│       ├── api.py
│       ├── config_flow.py
│       ├── const.py
│       ├── coordinator.py
│       ├── manifest.json
│       ├── sensor.py
│       ├── strings.json
│       └── translations/
```

### Verify Installation
```bash
ls -la ~/.homeassistant/custom_components/jdeco/
# Should list all .py and .json files above
```

---

## 🚀 Next Steps

### After Successful Local Test

1. **Run all test scenarios** (see TESTING.md):
   - Correct credentials
   - Wrong credentials  
   - Network errors
   - Data updates
   - Partial failures

2. **Check performance:**
   - Update time < 2 seconds
   - No errors after 1 hour

3. **Proceed to HACS** (if testing passes):
   - Add custom repository
   - Install from HACS
   - Re-run critical tests

---

## 💾 Backup Before Testing

```bash
# Backup your config
cp -r ~/.homeassistant/custom_components ~/.homeassistant/custom_components.bak

# If needed, restore:
rm -rf ~/.homeassistant/custom_components/jdeco
cp -r ~/.homeassistant/custom_components.bak/jdeco ~/.homeassistant/custom_components/
```

---

## 🆘 Get Help

If stuck:

1. **Check logs first:**
   ```bash
   # SSH into HA
   journalctl -u home-assistant -n 100 | grep jdeco
   ```

2. **Enable debug logging** (see above)

3. **Create an issue with:**
   - Error message from logs
   - Home Assistant version
   - Installation method (Docker/Bare metal/etc)
   - Steps to reproduce

4. **GitHub Issues:** https://github.com/zedyazan/hass-jdeco/issues

---

## ✨ That's It!

You're ready to test the JDECo integration locally. Follow the scenarios in [TESTING.md](TESTING.md) for comprehensive testing.

**Questions?** Open an issue on GitHub! 🚀
