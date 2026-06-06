"""Constants for the Spider Farmer GGS Controller integration."""

DOMAIN = "spider_farmer_ggs"

# BLE GATT UUIDs (vendor-specific FF00 service)
UUID_SERVICE = "0000ff00-0000-1000-8000-00805f9b34fb"
UUID_NOTIFY  = "0000ff01-0000-1000-8000-00805f9b34fb"  # Device → HA (telemetry)
UUID_WRITE   = "0000ff02-0000-1000-8000-00805f9b34fb"  # HA → Device (commands)

CONF_MAC_ADDRESS = "mac_address"

# ── Light mode types ─────────────────────────────────────────────────────────
LIGHT_MODE_MANUAL = 0
LIGHT_MODE_SCHEDULE = 1
LIGHT_MODE_PPFD = 12

LIGHT_MODES = {
    "Manual": LIGHT_MODE_MANUAL,
    "Schedule": LIGHT_MODE_SCHEDULE,
    "PPFD": LIGHT_MODE_PPFD,
}
LIGHT_MODES_REV = {v: k for k, v in LIGHT_MODES.items()}

# ── Fan / Blower mode types ─────────────────────────────────────────────────
FAN_MODE_MANUAL = 0
FAN_MODE_SCHEDULE = 1
FAN_MODE_CYCLE = 2
FAN_MODE_ENV_TEMP_ONLY = 3
FAN_MODE_ENV_HUMI_ONLY = 4
FAN_MODE_ENV_PRIO_TEMP = 7
FAN_MODE_ENV_PRIO_HUMI = 8
FAN_MODE_ENV_TEMP_HUMI = 13

FAN_MODES = {
    "Manual": FAN_MODE_MANUAL,
    "Schedule": FAN_MODE_SCHEDULE,
    "Cycle": FAN_MODE_CYCLE,
    "Environment: Temperature only": FAN_MODE_ENV_TEMP_ONLY,
    "Environment: Humidity only": FAN_MODE_ENV_HUMI_ONLY,
    "Environment: Prioritize temperature": FAN_MODE_ENV_PRIO_TEMP,
    "Environment: Prioritize humidity": FAN_MODE_ENV_PRIO_HUMI,
    "Environment: Temperature & humidity": FAN_MODE_ENV_TEMP_HUMI,
}
FAN_MODES_REV = {v: k for k, v in FAN_MODES.items()}

FAN_ENV_SUBMODES = {
    "Prioritize temperature": FAN_MODE_ENV_PRIO_TEMP,
    "Prioritize humidity": FAN_MODE_ENV_PRIO_HUMI,
    "Temperature only": FAN_MODE_ENV_TEMP_ONLY,
    "Humidity only": FAN_MODE_ENV_HUMI_ONLY,
    "Temperature & humidity": FAN_MODE_ENV_TEMP_HUMI,
}

# ── Humidifier mode types ────────────────────────────────────────────────────
HUMIDIFIER_MODE_MANUAL = 0
HUMIDIFIER_MODE_TIMESLOT = 1
HUMIDIFIER_MODE_CYCLE = 2
HUMIDIFIER_MODE_HUMIDITY = None  # TODO: Replace with discovered value from Task 0

HUMIDIFIER_MODES = {
    "Manual": HUMIDIFIER_MODE_MANUAL,
    "Time Slot": HUMIDIFIER_MODE_TIMESLOT,
    "Cycle": HUMIDIFIER_MODE_CYCLE,
    "Humidity": HUMIDIFIER_MODE_HUMIDITY,
}
HUMIDIFIER_MODES_REV = {v: k for k, v in HUMIDIFIER_MODES.items() if v is not None}

# ── Humidifier strength ─────────────────────────────────────────────────────
# TODO: Replace field name and values after Task 0 discovery
HUMIDIFIER_STRENGTHS = ["Automatic", "1", "2", "3", "4"]

# ── Plan storage path ────────────────────────────────────────────────────────
PLAN_STORAGE_PATH = "/config/claude_files/ggs_planting_plans.json"
