# rfid_attendance.py
import serial
import time
from database import init_database, log_attendance
from students import REGISTERED_USERS

# ── Configuration ─────────────────────────────────────────────
# Change SERIAL_PORT to match your machine (see table below)
SERIAL_PORT = "/dev/ttyUSB0"   # Windows: "COM3"  Mac: "/dev/tty.usbmodem..."
BAUD_RATE = 9600

# ── Helper: find your serial port ────────────────────────────
# Windows → open Device Manager → Ports → look for Arduino
# Mac     → open Terminal → run: ls /dev/tty.usb*
# Linux   → open Terminal → run: ls /dev/ttyUSB*

# ── Main loop ─────────────────────────────────────────────────


def run():
    init_database()       # Create tables + sync students on startup

    print("[INFO] Opening serial port...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)     # Wait for Arduino to reset after connecting
        print("[INFO] Connected. Waiting for card scans...\n")
    except serial.SerialException as e:
        print(f"[ERROR] Cannot open port {SERIAL_PORT}: {e}")
        print("[TIP]  Check your SERIAL_PORT value at the top of this file.")
        return

    while True:
        try:
            if ser.in_waiting > 0:
                raw = ser.readline().decode("utf-8").strip()

                if not raw:
                    continue

                print(f"[SCAN] Card detected: {raw}")

                # ── Check 1: Is this card registered? ─────────
                if raw not in REGISTERED_USERS:
                    print(f"  ✗   Not in students.py — unknown card")
                    print(f"  →   Sending FAIL to Arduino\n")
                    ser.write(b"FAIL\n")
                    continue

                user = REGISTERED_USERS[raw]
                print(f"  ✓   Matched: {user['name']} ({user['id']})")

                # ── Check 2: Already marked today? ────────────
                result = log_attendance(user["id"], user["name"])

                if result == "logged":
                    print(f"  ✅  Saved to database")
                    print(f"  →   Sending OK to Arduino (green LED)\n")

                elif result == "duplicate":
                    print(f"  ⚠   Already marked today — skipping duplicate")
                    print(f"  →   Sending OK to Arduino (green LED)\n")

                ser.write(b"OK\n")

            time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n[INFO] System stopped by user.")
            ser.close()
            break

        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            time.sleep(1)


if __name__ == "__main__":
    run()
