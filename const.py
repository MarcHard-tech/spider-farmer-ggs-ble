"""Constants for the Spider Farmer GGS Controller integration."""

DOMAIN = "spider_farmer_ggs"

# BLE GATT UUIDs (vendor-specific FF00 service)
UUID_SERVICE = "0000ff00-0000-1000-8000-00805f9b34fb"
UUID_NOTIFY  = "0000ff01-0000-1000-8000-00805f9b34fb"  # Device → HA (telemetry)
UUID_WRITE   = "0000ff02-0000-1000-8000-00805f9b34fb"  # HA → Device (commands)

CONF_MAC_ADDRESS = "mac_address"
