"""Data update coordinator for PoolLab Local.

Implements the active-connection Command/Response protocol described in the
official PoolLab 1.0 BLE API documentation:
  1. Connect (no pairing/bonding).
  2. Discover PoolLabSvc and its three characteristics.
  3. Enable notifications on MISO_Signal.
  4. To run a command: write it to CommandMOSI, wait for a MISO_Signal
     notification (its payload is irrelevant - it's only a "ready" ping),
     then read the response from CommandMISO.
"""
from __future__ import annotations

import asyncio
import logging
import struct
from datetime import datetime, timedelta, timezone
from typing import Any

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CHAR_MISO_CMD_UUID,
    CHAR_MISO_SIGNAL_UUID,
    CHAR_MOSI_CMD_UUID,
    CMD_GET_INFO,
    CMD_GET_MEASURES,
    DEFAULT_TIMEOUT,
    MEASUREMENT_TYPES,
    PREAMBLE,
    UPDATE_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class PoolLabCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls a PoolLab 1.0 device over BLE and caches the latest readings."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"PoolLab ({address})",
            update_interval=(
                timedelta(seconds=UPDATE_INTERVAL_SECONDS)
                if UPDATE_INTERVAL_SECONDS
                else None
            ),
        )
        self.address = address
        # The device only accepts one central connection at a time, and a
        # full poll involves several sequential command/response round
        # trips, so we serialize polls defensively even though the
        # coordinator itself shouldn't normally overlap calls.
        self._lock = asyncio.Lock()

    async def _async_update_data(self) -> dict[str, Any]:
        async with self._lock:
            return await self._poll_device()

    async def _poll_device(self) -> dict[str, Any]:
        ble_device: BLEDevice | None = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                f"PoolLab {self.address} was not seen by any Bluetooth "
                "adapter/proxy. Make sure it is powered on and in range."
            )

        client: BleakClientWithServiceCache | None = None
        try:
            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self.address,
                max_attempts=3,
            )

            response_ready = asyncio.Event()

            def _on_signal_notify(_sender: Any, _data: bytearray) -> None:
                # Payload is irrelevant; this is purely a "data is ready" ping.
                response_ready.set()

            await client.start_notify(CHAR_MISO_SIGNAL_UUID, _on_signal_notify)

            info_raw = await self._send_command(
                client, response_ready, CMD_GET_INFO, b""
            )
            info = self._parse_info(info_raw)

            result_count = info["result_count"]
            measurements: dict[int, dict[str, Any]] = {}

            cell_id = 0
            results_read = 0
            while results_read < result_count and cell_id < 16:
                for half in (0, 1):
                    if results_read >= result_count:
                        break
                    params = struct.pack("<HB", cell_id, half)
                    raw = await self._send_command(
                        client, response_ready, CMD_GET_MEASURES, params
                    )
                    for record in self._parse_measurements(raw):
                        if record is None:
                            continue
                        results_read += 1
                        existing = measurements.get(record["type_id"])
                        if existing is None or record["timestamp"] > existing["timestamp"]:
                            measurements[record["type_id"]] = record
                cell_id += 1

            return {"device_info": info, "measurements": measurements}

        except TimeoutError as err:
            raise UpdateFailed(f"Timed out talking to PoolLab: {err}") from err
        except BleakError as err:
            raise UpdateFailed(f"Bluetooth error talking to PoolLab: {err}") from err
        finally:
            if client is not None:
                try:
                    await client.disconnect()
                except BleakError:
                    pass

    @staticmethod
    async def _send_command(
        client: BleakClientWithServiceCache,
        response_ready: asyncio.Event,
        command_id: int,
        params: bytes,
    ) -> bytes:
        """Write one command, wait for the ready-notification, read the response."""
        response_ready.clear()

        payload = bytearray(max(7, 3 + len(params)))
        payload[0] = PREAMBLE
        payload[1] = command_id & 0xFF
        payload[2] = (command_id >> 8) & 0xFF
        payload[3 : 3 + len(params)] = params

        await client.write_gatt_char(
            CHAR_MOSI_CMD_UUID, bytes(payload), response=True
        )

        async with asyncio.timeout(DEFAULT_TIMEOUT):
            await response_ready.wait()

        raw = await client.read_gatt_char(CHAR_MISO_CMD_UUID)
        return bytes(raw)

    @staticmethod
    def _parse_info(raw: bytes) -> dict[str, Any]:
        """Parse the PCMD_API_GET_INFO response (dev_info_response struct)."""
        if len(raw) < 23 or raw[0] != PREAMBLE:
            raise UpdateFailed("Malformed GET_INFO response from PoolLab")

        active_id, fw_version, result_count = struct.unpack_from("<HHH", raw, 1)
        device_time_raw = int.from_bytes(raw[7:15], byteorder="little")
        mac = raw[15:21]
        battery_level = struct.unpack_from("<H", raw, 21)[0]

        return {
            "active_id": active_id,
            "fw_version": fw_version,
            "result_count": result_count,
            "device_time": (
                datetime.fromtimestamp(device_time_raw, tz=timezone.utc)
                if device_time_raw
                else None
            ),
            "mac_address": ":".join(f"{b:02X}" for b in mac),
            "battery_level": battery_level,
        }

    @staticmethod
    def _parse_measurements(raw: bytes) -> list[dict[str, Any] | None]:
        """Parse the 8 flash_measurement_result records in a GET_MEASURES reply."""
        if not raw or raw[0] != PREAMBLE:
            return [None] * 8

        body = raw[1:]
        records: list[dict[str, Any] | None] = []

        for i in range(8):
            chunk = body[i * 16 : i * 16 + 16]
            if len(chunk) < 16 or chunk == b"\x00" * 16:
                records.append(None)
                continue

            measure_id, measure_type, measure_status = struct.unpack_from(
                "<HBB", chunk, 0
            )
            timestamp = struct.unpack_from("<I", chunk, 4)[0]
            (value,) = struct.unpack_from("<f", chunk, 8)

            if measure_type == 0 and timestamp == 0:
                records.append(None)
                continue

            name, unit, decimals = MEASUREMENT_TYPES.get(
                measure_type, (f"Unknown scenario {measure_type}", "ppm", 2)
            )

            records.append(
                {
                    "measure_id": measure_id,
                    "type_id": measure_type,
                    "name": name,
                    "unit": unit,
                    "status": measure_status,
                    "timestamp": timestamp,
                    "value": round(value, decimals),
                }
            )

        return records
