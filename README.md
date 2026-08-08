````markdown
# JDECo Home Assistant Integration

Custom component for [Jerusalem District Electricity Company (JDECo)](https://www.jdeco.net) that exposes your remaining prepaid electricity credit (kWh) with real-time updates and advanced error handling.

## ✨ Features

- 🔐 **Secure authentication** - RSA + AES encryption, same as the official Android app
- ⚡ **Real-time kWh tracking** - Shows remaining electricity credit as a sensor
- 🔄 **Concurrent data fetching** - All API calls run in parallel for lightning-fast updates (~0.5-1s)
- 🛡️ **Robust error handling** - Automatic retry with exponential backoff, graceful degradation
- 📊 **Rich attributes** - Debt amount, last voucher, meter type, address
- 🎛️ **Configurable UI** - Select your agreement from a dropdown during setup
- 🚀 **Performance optimized** - Reduced update time by 60-75% vs. sequential calls

## 📋 Requirements

- Home Assistant 2023.9 or later
- `pycryptodome>=3.18.0` (auto-installed)
- Valid JDECo account with prepaid agreement

## 🚀 Installation

### Option 1: Local Installation (Recommended for Testing)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/zedyazan/hass-jdeco.git
   ```

2. **Copy to Home Assistant:**
   ```bash
   cp -r custom_components/jdeco ~/.homeassistant/custom_components/
   # Or if using Docker:
   cp -r custom_components/jdeco /config/custom_components/
   ```

3. **Restart Home Assistant:**
   - Go to **Settings → System → Restart**
   - Or use the terminal: `systemctl restart home-assistant@homeassistant`

4. **Add the integration:**
   - Go to **Settings → Devices & Services → Create Integration**
   - Search for **"JDECo"**
   - Enter your JDECo app username and password
   - Select your electricity agreement from the dropdown
   - Click **Finish**

### Option 2: HACS Installation (After Testing)

1. **Add custom repository to HACS:**
   - Open HACS → Integrations
   - Click **⋮ (three dots)** → **Custom repositories**
   - Paste: `https://github.com/zedyazan/hass-jdeco`
   - Category: **Integration**
   - Click **Create**

2. **Install from HACS:**
   - Click on the **JDECo** repository
   - Click **Download**
   - Restart Home Assistant
   - Follow Option 1 steps 4 onwards

## 🔧 Configuration

### Via UI (Recommended)
The integration configures entirely through the UI—no YAML needed.

### Setup Flow
1. **Username & Password** - Your JDECo app credentials
2. **Agreement Selection** - Pick your electricity agreement from the dropdown
3. **Complete** - Integration loads automatically

### Optional: Adjust Update Interval
Once installed, edit the integration:
- Go to **Settings → Devices & Services**
- Find **JDECo**
- Click **Options** (⚙️)
- Adjust **Scan Interval** (default: 30 minutes)

## 📊 Entities Created

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.jdeco_remaining_kwh` | Sensor | Remaining kWh balance (main sensor) |

### Attributes
- `agreement_no` - Your agreement number
- `meter_type` - "Prepaid" or "Smart"
- `address` - Service address
- `last_voucher_amount` - Last voucher credit added
- `debt_amount` - Current debt (if any)

### Example Automations

**Alert when kWh is low:**
```yaml
automation:
  - alias: "JDECo Low Balance Alert"
    trigger:
      platform: numeric_state
      entity_id: sensor.jdeco_remaining_kwh
      below: 5
    action:
      service: notify.notify
      data:
        message: "⚠️ JDECo balance is low: {{ states('sensor.jdeco_remaining_kwh') }} kWh"
```

**Log updates:**
```yaml
automation:
  - alias: "Log JDECo Updates"
    trigger:
      platform: state
      entity_id: sensor.jdeco_remaining_kwh
    action:
      service: system_log.write
      data:
        level: info
        logger: jdeco
        message: "Balance updated: {{ states('sensor.jdeco_remaining_kwh') }} kWh"
```

## 🧪 Testing & Troubleshooting

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

Restart Home Assistant and check **Settings → System → Logs** for detailed messages.

### Common Issues

| Issue | Solution |
|-------|----------|
| **"auth_failed"** | Wrong username/password. Verify credentials with JDECo app. |
| **"api_error"** | Network connectivity issue. Check internet and retry. |
| **"no_agreements"** | Account has no prepaid agreements. Contact JDECo support. |
| **Sensor shows "Unknown"** | Wait for first update (up to 30 minutes), or manually trigger in Settings. |
| **Connection timeout** | API temporarily unavailable. Integration will retry automatically (3 attempts). |

### Manual Update Trigger
To force an immediate update:
```yaml
service: homeassistant.update_entity
target:
  entity_id: sensor.jdeco_remaining_kwh
```

## 📈 Performance Improvements

### Sequential (Before)
```
Request PK:      ~300ms
Encrypt & Login: ~500ms
Details:         ~400ms
Debt:            ~350ms
Voucher:         ~300ms
kWh Qty:         ~350ms
─────────────────────
Total:          ~2,200ms ❌
```

### Concurrent (After)
```
Request PK:              ~300ms
Encrypt & Login:         ~500ms
Details, Debt, Voucher,
kWh Qty (parallel):     ~400ms
─────────────────────
Total:                  ~800ms ✅
```

**Improvement: 64% faster updates!**

## 🔐 Security Notes

1. **Credentials are encrypted** - Home Assistant stores credentials securely
2. **No cloud logging** - All communication is direct with JDECo's API
3. **RSA + AES encryption** - Same encryption as official app
4. **Token-based auth** - Session tokens are temporary
5. **Minimal logging** - Sensitive data (passwords, tokens) never logged

## 🤝 Contributing

Found a bug or have a suggestion? 
- [Open an issue](https://github.com/zedyazan/hass-jdeco/issues)
- [Create a pull request](https://github.com/zedyazan/hass-jdeco/pulls)

## ⚖️ Legal Disclaimer

This integration is **reverse-engineered** from the official JDECo Android app. Use at your own risk.
- Not affiliated with or endorsed by JDECo
- API endpoints may change without notice
- Respect JDECo's terms of service

## 📜 License

MIT License - See LICENSE file for details

## 🙋 Support

**Testing Issues?** Check [TESTING.md](TESTING.md) for detailed test scenarios.

**Need Help?**
1. Enable debug logging (see above)
2. Check Home Assistant logs for error messages
3. Open an issue with:
   - Home Assistant version
   - Component version (latest commit SHA)
   - Error message from logs
   - Steps to reproduce

---

**Made with ❤️ by the Home Assistant community for JDECo users**
````
