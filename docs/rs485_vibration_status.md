# RS485 Vibration Sensor Status (Jetson)

## Summary
- Jetson Linux + USB-RS485 (CH340) + WitMotion WT-VB02-485 sensors.
- Two environments observed:
  - Jetson A: UID 0x53/0x54/0x55 (0x55 often unstable).
  - Jetson B: UID 0x50/0x51/0x52 (0x52 had Y-axis issues intermittently).
- `test_vibration_pymodbus3.py` sometimes reads all sensors well, but failures are intermittent and appear "random."

## Key Observations
- USB serial device occasionally disappears:
  - `/dev/ttyUSB0` missing (`No such file or directory`).
  - When this happens, all UIDs fail.
- When device is present:
  - Some frames show ACC values but VEL/DISP all zero.
  - This suggests responses are truncated or corrupted in the latter registers.
- `lsusb` confirms CH340 (`1a86:7523`) when recognized.
- Stable communication improves after Windows tool reboots the sensors.

## Likely Causes (Ranked)
1) CH340 RS485 direction control instability on Linux (half-duplex timing).
2) RS485 bus quality: termination/biasing/line noise, especially with long cable.
3) Sensor state/configuration not stable after power cycles (reboot fixes temporarily).
4) USB link instability (hub/cable/power).

## Bus Topology and Termination
- Current wiring: `[sensor] - [termination] - 10m - [USB-RS485 dongle] - Jetson`
- Recommendation: add a second 120 ohm termination at the USB-RS485 end.
- Termination must be only at the two ends (do not place in the middle).
- Consider bias resistors if the dongle has none.

## Repro Logs (Highlights)
- Errors when device disappears:
  - `could not open port /dev/ttyUSB0`
- Partial data frames:
  - ACC registers present, VEL/DISP all zero in some samples.

## Suggested Next Tests
1) Use a stable port alias when available (`/dev/ttyUSB_CH340` or `/dev/serial/by-id/...`).
2) Add termination at USB-RS485 end and re-test.
3) Test single-sensor mode (one UID only).
4) Swap addresses between sensors to see if the issue follows the sensor or the address.
5) Reduce polling rate and increase timeout to see if truncation reduces.
6) Avoid USB hubs; direct connection with a known-good cable.

## Potential Improvements (Code)
- Add port auto-selection preference for `/dev/ttyUSB_CH340` or `/dev/serial/by-id`.
- Add a "single UID only" diagnostic mode.
- Add optional continuous raw-register dump for debugging.
