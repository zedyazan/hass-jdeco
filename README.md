# JDECo Home Assistant Integration

Custom component for [Jerusalem District Electricity Company (JDECo)](https://www.jdeco.net) that exposes your remaining prepaid electricity credit (kWh).

## Features
- Secure authentication (RSA + AES encryption, same as the official Android app)
- Shows remaining kWh as a sensor
- Configurable via the Home Assistant UI

## Installation

1. Copy the `custom_components/jdeco` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**, search for **JDECo**.
4. Enter your app username and password.
5. Select your electricity agreement from the dropdown.

## Manual Installation (HACS not yet available)

Clone this repository and copy the `custom_components/jdeco` folder as described above.

## Credits

Reverse-engineered by the community. Use at your own risk.
