"""Constants for the PoolLab Local integration.

All protocol details (UUIDs, command IDs, byte layouts, measurement types)
are taken from the official "PoolLab 1.0 Bluetooth API - Interface
Documentation" (Water-i.d. GmbH, version 2, 2022-03-02),
https://poollab.org/static/api/BLE.pdf
"""
from __future__ import annotations

DOMAIN = "poollab_local"

MANUFACTURER = "Water-i.d."
MODEL = "PoolLab 1.0"

# --- GATT profile ("PoolLabSvc") ---
SERVICE_UUID = "a7ee04a9-507b-4910-a528-b619d5501924"
CHAR_MISO_CMD_UUID = "2ff18b59-195d-4ee1-b78c-0cbde3eff9c2"     # read response data
CHAR_MOSI_CMD_UUID = "91bfa536-3036-4901-8813-3635fced7b90"     # write commands
CHAR_MISO_SIGNAL_UUID = "c2296c06-c7e0-4657-b42e-c8330826454c"  # notify: response ready

# --- Command framing ---
PREAMBLE = 0xAB

CMD_GET_INFO = 0x01
CMD_SET_TIME = 0x02
CMD_RESET_DEVICE = 0x03
CMD_SLEEP_DEVICE = 0x04
CMD_GET_MEASURES = 0x05
CMD_RESET_MEASURES = 0x06
CMD_SET_CONTRAST_PLUS = 0x08
CMD_SET_CONTRAST_MINUS = 0x09
CMD_GET_PPM_MGL = 0x0A
CMD_SET_PPM_MGL = 0x0B

RESULT_OK = 0x01
RESULT_ERR = 0x02

# --- Timing ---
DEFAULT_TIMEOUT = 20  # seconds; BLE connect + command round trip can be slow

# No automatic background polling. The device only accepts one BLE
# connection at a time and is typically used a few times a week at most,
# so polling on a fixed schedule would just be needless Bluetooth traffic
# and a source of connection conflicts with the LabCom app. Use the
# "Jetzt abrufen" button entity right after taking a measurement instead.
UPDATE_INTERVAL_SECONDS: int | None = None

# --- Measurement status codes (per flash_measurement_result.measure_status) ---
MEASURE_STATUS_OK = 0
MEASURE_STATUS_UNDERRANGE = 1
MEASURE_STATUS_OVERRANGE = 2

MEASURE_STATUS_NAMES = {
    MEASURE_STATUS_OK: "ok",
    MEASURE_STATUS_UNDERRANGE: "underrange",
    MEASURE_STATUS_OVERRANGE: "overrange",
}

# --- Ideal ranges (target range for "healthy" pool water) ---
# These are NOT part of the official BLE protocol - the device itself only
# knows its technical measurement range (see MEASUREMENT_TYPES below).
# These values were taken from the currently configured LabCom Cloud
# targets (as of 2026) and are specific to one pool/setup; adjust freely
# to match your own targets.
IDEAL_RANGES: dict[int, tuple[float, float]] = {
    1: (1.0, 3.0),      # Total Chlorine (ppm)
    8: (0.5, 3.0),       # Free Chlorine (ppm)
    9: (7.2, 7.4),        # pH
    10: (80.0, 120.0),    # Total Alkalinity (ppm)
    11: (20.0, 50.0),     # Cyanuric Acid (ppm)
}

# --- Measurement scenario types: type_id -> (name, unit, decimals) ---
# "ppm" is used as native_unit_of_measurement for all non-pH scenarios, matching
# the device's own unit naming in the API doc (mg/L mode is a device-side display
# toggle, not exposed separately here).
MEASUREMENT_TYPES: dict[int, tuple[str, str, int]] = {
    1: ("Total Chlorine", "ppm", 2),
    2: ("Ozone", "ppm", 2),
    3: ("Chlorine Dioxide", "ppm", 1),
    5: ("Active Oxygen", "ppm", 1),
    6: ("Bromine", "ppm", 1),
    7: ("Hydrogen Peroxide", "ppm", 2),
    8: ("Free Chlorine", "ppm", 2),
    9: ("pH", "pH", 2),
    10: ("Total Alkalinity", "ppm", 0),
    11: ("Cyanuric Acid", "ppm", 0),
    12: ("Hydrogen Peroxide HR", "ppm", 0),
    13: ("Total Hardness HR", "ppm", 1),
    14: ("Isothiazolinone", "ppm", 1),
    15: ("Nitrite LR", "ppm", 2),
    16: ("Nitrate", "ppm", 1),
    17: ("Phosphate", "ppm", 2),
    18: ("Iron LR", "ppm", 2),
    19: ("Dissolved Oxygen", "ppm", 2),
    20: ("Ammonia", "ppm", 2),
    21: ("Silica", "ppm", 2),
    22: ("Copper", "ppm", 2),
    23: ("Calcium", "ppm", 0),
    24: ("Ozone i.p.o. Chlorine", "ppm", 2),
    25: ("Magnesium", "ppm", 0),
    26: ("Potassium", "ppm", 1),
    27: ("pH HR", "pH", 2),
    28: ("pH LR", "pH", 2),
    29: ("pH HR (Saltwater)", "pH", 2),
    30: ("pH HR (Seawater)", "pH", 2),
    31: ("pH LR (Saltwater)", "pH", 2),
    32: ("pH LR (Seawater)", "pH", 2),
    33: ("pH MR (Saltwater)", "pH", 2),
    34: ("pH MR (Seawater)", "pH", 2),
    35: ("Total Hardness", "ppm", 0),
    36: ("pH MR", "pH", 2),
    37: ("Iodine", "ppm", 2),
    38: ("Urea", "ppm", 2),
    39: ("PHMB", "ppm", 0),
    40: ("Total Alkalinity (Seawater)", "ppm", 0),
    41: ("Total Chlorine (liquid)", "ppm", 2),
    42: ("Ozone (liquid)", "ppm", 2),
    43: ("Chlorine Dioxide (liquid)", "ppm", 2),
    44: ("Active Oxygen (liquid)", "ppm", 1),
    45: ("Bromine (liquid)", "ppm", 1),
    46: ("Hydrogen Peroxide (liquid)", "ppm", 2),
    47: ("Free Chlorine (liquid)", "ppm", 2),
    48: ("pH (liquid)", "pH", 2),
    49: ("Ozone i.p.o. Chlorine (liquid)", "ppm", 2),
}
