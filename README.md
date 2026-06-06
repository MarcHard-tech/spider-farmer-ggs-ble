# Spider Farmer GGS Controller — BLE Integration for Home Assistant

A custom Home Assistant integration that connects to the **Spider Farmer GGS grow controller** via **Bluetooth Low Energy (BLE)**.

This brings your grow tent environment data and device controls directly into Home Assistant — no cloud, no Wi-Fi bridge, just a direct Bluetooth connection.

## Features

### Sensors
- **Temperature** — ambient air temperature (°C)
- **Humidity** — relative humidity (%)
- **VPD** — vapour pressure deficit (kPa)
- **CO2** — carbon dioxide level (ppm)
- **PPFD** — photosynthetic light intensity (µmol/m²/s)
- **Environment On Target** — whether current conditions match your grow plan targets
- **Soil Probes (1–3)** — temperature, water content, and EC per probe
- **Soil Averages** — averaged temperature, water content, and EC across probes
- **Grow Plan** — active/stopped, days elapsed, days remaining, total days, progress %
- **Alarms & Operations** — last alarm time/type, last operation time/mode

### Switches (on/off control)
- Fan
- Grow Light
- Blower
- Humidifier *(optional — only appears if connected)*
- Grow Light 2 *(optional)*
- Heater *(optional)*

### Number Sliders (level control)
- Fan Speed (0–10)
- Grow Light Level (0–100%)
- Blower Level (0–100%)
- Grow Light 2 Level (0–100%) *(optional)*
- Humidifier Level (0–100%) *(optional)*
- Heater Level (0–100%) *(optional)*

## Requirements

- Home Assistant 2024.1 or later
- A Bluetooth adapter accessible to Home Assistant (built-in or USB)
- Spider Farmer GGS Controller (advertises as `SF-GGS-CB` over BLE)

## Installation

1. Copy the `spider_farmer_ggs` folder into your Home Assistant `custom_components` directory:
   ```
   custom_components/
   └── spider_farmer_ggs/
       ├── __init__.py
       ├── config_flow.py
       ├── const.py
       ├── coordinator.py
       ├── manifest.json
       ├── number.py
       ├── sensor.py
       ├── switch.py
       ├── strings.json
       └── translations/
           └── en.json
   ```
2. Restart Home Assistant
3. The GGS controller should be **auto-discovered** via Bluetooth. If not, go to **Settings → Devices & Services → Add Integration** and search for "Spider Farmer"

## How It Works

The integration communicates with the GGS controller over BLE using a vendor-specific GATT service (`0xFF00`). It subscribes to notifications from the device for real-time telemetry updates and sends commands to control connected equipment.

- **Local only** — all communication is direct Bluetooth, no cloud or internet required
- **Push-based** — the device pushes telemetry updates, so data stays fresh without polling
- **Auto-discovery** — Home Assistant's Bluetooth integration detects the controller automatically

## Credits

Protocol research based on work by [cr0ssn0tice](https://github.com/cr0ssn0tice/Spider-Farmer-GGS-Controller-MQTT).

## License

This project is provided as-is for personal use.
