# Spider Farmer GGS Controller — BLE Integration for Home Assistant

A custom Home Assistant integration for the **Spider Farmer GGS grow controller**, over **Bluetooth Low Energy**. Local only — no cloud, no Wi-Fi bridge, no vendor account.

---

## Please read this before using it

**This integration was built entirely by Claude** (Anthropic's AI), working from BLE traffic captured from my own controller. I own the hardware and drove the project, but I am not a programmer and I did not write this code.

**I cannot help with issues, questions, or pull requests.** I would not be able to review a code change or debug a problem, so please don't wait on me. It is published only because it may be useful to someone else with this controller — particularly after the firmware update described below, which broke every existing integration.

Use it at your own risk. It controls equipment that keeps plants alive, and a mistake could cost you a crop. If it breaks, you are on your own — though the protocol notes further down should give a capable person everything needed to fix or rebuild it.

---

## Firmware 2026: the protocol is now encrypted

Around **17 August 2026** a Spider Farmer firmware update replaced the plaintext-JSON BLE payload with an encrypted one. Any integration written against the old protocol stops working — the device simply goes quiet.

This integration implements the **new (v2) protocol**, so it works on current firmware. It does not support the old plaintext protocol.

Firmware updates are optional and are not applied automatically. Spider Farmer support will supply older firmware images on request if you ask them.

## Features

**Sensors** — temperature, humidity, VPD, CO₂, PPFD, "environment on target", soil probes 1–3 (temperature / water content / EC), soil averages, grow-plan progress (active, days elapsed/remaining/total, percent), last alarm and last operation.

**Switches** — fan, grow light, blower, and optionally grow light 2, humidifier, heater.

**Numbers** — fan speed (0–10) and light/blower/humidifier levels (0–100%), plus schedule brightness, fade time, PPFD target, dimming limits and cycle timings.

**Selects** — operating mode per module: Manual, Schedule, Cycle, PPFD, and the Environment modes (temperature, humidity, or both).

**Times** — schedule and cycle start/end times for each module.

Entities for hardware you do not have stay unavailable, which is normal.

## Planting stages

The controller stores a planting *stage*: climate targets plus a light schedule, with a date range. This integration keeps a small library of stage presets and can deploy one to the controller.

Four presets ship by default, aimed at **raising vegetable seedlings for transplanting outdoors** — germination, seedling, growing, hardening off — plus an empty `custom` slot. They are starting points, not horticultural gospel; edit them to suit what you grow.

Services:

| Service | What it does |
|---|---|
| `spider_farmer_ggs.deploy_stage` | Write a preset to the controller as the active stage, with dates |
| `spider_farmer_ggs.manage_presets` | List, save or delete presets in the local library |
| `spider_farmer_ggs.set_light_mode` / `set_fan_mode` / `set_humidifier_mode` | Change a module's operating mode |
| `spider_farmer_ggs.send_raw_command` | Diagnostic: send arbitrary JSON and return the reply |
| `spider_farmer_ggs.dump_gatt` | Diagnostic: list the controller's GATT characteristics and MTU |

Presets are stored at `/config/spider_farmer_ggs/presets.json`.

Two things to know about deploying a stage:

- **It replaces the whole stage list.** If you created several stages in the Spider Farmer app, deploying leaves you with one.
- **Include the light block.** The vendor app shows a blank grey screen on a plan whose stage has no `light1` block. This integration always writes one.

## Requirements

- Home Assistant 2024.1 or later
- A Bluetooth adapter available to Home Assistant
- A Spider Farmer GGS controller (advertises as `SF-GGS-CB`)

The controller accepts **one BLE connection at a time**. While Home Assistant is connected, the phone app cannot connect, and vice versa. Close the app if the integration stops updating.

## Installation

1. Copy the `spider_farmer_ggs` folder into `custom_components/` in your Home Assistant config directory.
2. Restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → "Spider Farmer"**, and enter your controller's Bluetooth address. Find it under **Settings → Devices & Services → Bluetooth**, listed as `SF-GGS-CB`.

If the controller never appears in Home Assistant's Bluetooth list, check whether your adapter is in passive scanning mode. Passive scanning never requests scan-response data, so the device name never arrives and name-based matching fails.

## Protocol notes (v2)

Recorded here so that anyone can repair or reimplement this without repeating the work.

Service `0xFF00`; notify `0xFF01`; write `0xFF02` (write-with-response, the only writable characteristic).

Each BLE packet:

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | magic `AA AA 00 03` |
| 4 | 2 | payload length = packet length − 8 |
| 6 | 2 | protocol version = `00 02` |
| 8 | 2 | **CRC16/MODBUS of the entire message ciphertext** |
| 10 | 4 | total assembled ciphertext length |
| 14 | 4 | this chunk's offset |
| 18 | 2 | this chunk's length |
| 20 | N | ciphertext |
| 20+N | 2 | CRC16/MODBUS of header+ciphertext |

All multi-byte fields are big-endian, including both CRCs.

**Bytes 8–9 are not a message id.** They are a second CRC, over the whole message ciphertext, identical across every chunk of one message. The controller silently discards any frame where it does not match — no error, no reply. This is the single hardest thing to discover from outside, because a receive-only implementation never has to generate it.

Payload is **AES-128-CBC with PKCS7 padding** over the whole reassembled message, chained across chunk boundaries. Key and IV are fixed literals compiled into the vendor app, identical for every controller on this firmware; see `protocol.py`.

Commands are JSON with this envelope, in this key order:

```json
{"method":"setConfigField","pid":"<device id>","params":{...},
 "msgId":"<millisecond epoch as a string>","uid":"<account id>"}
```

`msgId` is echoed in the reply so responses can be matched to requests. `pid` and `uid` are learned from the controller's own messages, so nothing needs configuring.

Further notes:

- Success is `{"code":200,"msg":"ok"}`. A silent write means the frame was rejected — check the header CRC first.
- `setConfigField` **replaces** a module's config block; always send a complete one.
- The older `setFan` / `setLight` commands are still acknowledged but the controller reverts them within about 30–40 seconds, and they can briefly disturb the module's stored mode. Write the config block instead.
- Telemetry arrives unsolicited every ~6 s as `getDevSta` / `getSysSta`; no polling is needed for sensors.
- Device state lags roughly 12 seconds behind a successful write.
- Commands larger than one packet are chunked and the controller reassembles them.

## Credits

Protocol v1 research: [cr0ssn0tice/Spider-Farmer-GGS-Controller-MQTT](https://github.com/cr0ssn0tice/Spider-Farmer-GGS-Controller-MQTT).

The v2 encryption was recovered by decompiling the vendor Android app and comparing against captured BLE traffic, for interoperability with hardware I own, after a firmware update removed functionality I was already using.

## License

Provided as-is, with no warranty and no support.
