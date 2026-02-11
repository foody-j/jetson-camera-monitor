#!/usr/bin/env python3
import argparse
import os
import sys
import time

try:
    import serial
    from serial import SerialException
except Exception as exc:
    print(f"[ERROR] pySerial import failed: {exc}")
    print("Install: sudo apt-get install -y python3-serial")
    sys.exit(1)


DEFAULT_PORT = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
PORT = os.getenv("RELAY_PORT", DEFAULT_PORT)
BAUDRATE = 9600
TIMEOUT_S = 1.0
DEFAULT_WIRING = "nc"

# Relay protocol (channel 1)
CMD_ON = bytes([0xA0, 0x01, 0x01, 0xA2])
CMD_OFF = bytes([0xA0, 0x01, 0x00, 0xA1])
CMD_STATUS = bytes([0xFF])


def open_serial(port: str) -> serial.Serial:
    return serial.Serial(
        port=port,
        baudrate=BAUDRATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=TIMEOUT_S,
    )


def relay_on(ser: serial.Serial, wiring: str) -> None:
    ser.write(CMD_ON)
    ser.flush()
    if wiring == "nc":
        print("[ACTION] Relay 1 ON command sent (NC wiring: DRIVER POWER OFF)")
    else:
        print("[ACTION] Relay 1 ON command sent (NO wiring: DRIVER POWER ON)")


def relay_off(ser: serial.Serial, wiring: str) -> None:
    ser.write(CMD_OFF)
    ser.flush()
    if wiring == "nc":
        print("[ACTION] Relay 1 OFF command sent (NC wiring: DRIVER POWER ON)")
    else:
        print("[ACTION] Relay 1 OFF command sent (NO wiring: DRIVER POWER OFF)")


def read_status(ser: serial.Serial) -> str:
    ser.reset_input_buffer()
    ser.write(CMD_STATUS)
    ser.flush()
    print("[ACTION] Relay status query sent")
    time.sleep(0.2)

    raw = ser.read(ser.in_waiting or 1)
    if not raw:
        msg = "(no response)"
        print(f"[INFO] Status response: {msg}")
        return msg

    text = raw.decode("ascii", errors="replace").strip()
    if not text:
        text = raw.hex(" ")
        print(f"[INFO] Status response (hex): {text}")
    else:
        print(f"[INFO] Status response (ascii): {text}")
    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="USB relay serial test (Jetson Ubuntu 22.04)"
    )
    parser.add_argument(
        "--port",
        default=PORT,
        help=f"Serial port path (default: {PORT})",
    )
    parser.add_argument(
        "--mode",
        choices=["test", "on", "off", "status"],
        default="test",
        help="Operation mode (default: test)",
    )
    parser.add_argument(
        "--wiring",
        choices=["nc", "no"],
        default=DEFAULT_WIRING,
        help=f"Relay contact wiring type (default: {DEFAULT_WIRING})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ser = None
    try:
        print(
            f"[INIT] Opening serial: {args.port} "
            f"({BAUDRATE} 8N1, timeout={TIMEOUT_S}s)"
        )
        print(f"[INIT] Wiring mode: {args.wiring.upper()}")
        ser = open_serial(args.port)
        print("[OK] Serial port opened")

        if args.mode == "on":
            relay_on(ser, args.wiring)
        elif args.mode == "off":
            relay_off(ser, args.wiring)
        elif args.mode == "status":
            read_status(ser)
        else:
            print("[TEST] Note: ON/OFF power meaning follows selected wiring mode")
            relay_on(ser, args.wiring)
            print("[INFO] Waiting 2 seconds")
            time.sleep(2.0)
            relay_off(ser, args.wiring)
            time.sleep(0.2)
            read_status(ser)
            print("[TEST] Sequence completed")
        return 0
    except SerialException as exc:
        print(f"[ERROR] Serial communication error: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
        return 130
    finally:
        if ser and ser.is_open:
            ser.close()
            print("[CLEANUP] Serial port closed")


if __name__ == "__main__":
    raise SystemExit(main())
