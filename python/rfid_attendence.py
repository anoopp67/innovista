# rfid_attendance.py
import serial
import sqlite3
import time
import os
DB_PATH = os.path.join(os.path.dirname(__file__), "../data/attendance.db")
from database import init_database, log_attendance, get_registered_user

SERIAL_PORT = "COM3"   
BAUD_RATE = 9600


def run():
    init_database()

    print("[INFO] Opening serial port...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        print("[INFO] Connected. Waiting for card scans...\n")
    except serial.SerialException as e:
        print(f"[ERROR] Cannot open port {SERIAL_PORT}: {e}")
        return

    while True:
        try:
            if ser.in_waiting > 0:
                uid = ser.readline().decode("utf-8").strip()

                if not uid:
                    continue

                print(f"[SCAN] UID received: {uid}")

                # ── Check if UID is registered in database ────
                user = get_registered_user(uid)

                if not user:
                    print(f"  ✗   Unknown card — not registered")
                    print(f"  →   Sending FAIL to Arduino\n")
                    ser.write(b"FAIL\n")
                    continue

                print(f"  ✓   Matched: {user['name']} ({user['id']})")

                result = log_attendance(user["id"], user["name"])

                if result == "logged":
                    print(f"  ✅  Attendance saved for {user['name']}")
                elif result == "duplicate":
                    print(f"  ⚠   Already marked today: {user['name']}")

                print(f"  →   Sending OK to Arduino (green LED)\n")
                ser.write(b"OK\n")

            time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n[INFO] System stopped by user.")
            ser.close()
            break

        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(1)


if __name__ == "__main__":
    run()
