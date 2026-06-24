# register_card.py
# Enrolls a new student by scanning their RFID card once and saving
# their UID + name + ID into students.py and syncing it to the database.
#
# Run: python register_card.py

import re
import os
import serial
import serial.tools.list_ports
import time

from students import REGISTERED_USERS
from database import init_database

# ── Configuration ─────────────────────────────────────────────
# Leave as "AUTO" to auto-detect the Arduino's port.
# Set a specific value (e.g. "COM3" or "/dev/ttyUSB0") to override.
SERIAL_PORT = "AUTO"
BAUD_RATE = 9600

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDENTS_FILE = os.path.join(BASE_DIR, "students.py")

# Words commonly found in the description/manufacturer of Arduino-style
# USB-serial chips, used to auto-pick the right port when several exist.
ARDUINO_HINTS = [
    "arduino", "ch340", "usb-serial", "usb serial",
    "wchusbserial", "usbmodem", "usbserial", "silicon labs", "cp210"
]


def find_serial_port():
    """
    Returns a port device string (e.g. 'COM3' or '/dev/ttyUSB0') automatically.
    - If exactly one serial port is connected, uses it.
    - If multiple are connected, prefers one matching known Arduino hints.
    - If it can't decide, lists what it found and lets the user pick.
    - Returns None if nothing is connected.
    """
    ports = list(serial.tools.list_ports.comports())

    if not ports:
        return None

    if len(ports) == 1:
        return ports[0].device

    # Multiple ports found — try to find an Arduino-like one
    for port in ports:
        text = f"{port.description or ''} {port.manufacturer or ''}".lower()
        if any(hint in text for hint in ARDUINO_HINTS):
            return port.device

    # Couldn't confidently pick — ask the user
    print("[INFO] Multiple serial ports found:")
    for i, port in enumerate(ports):
        print(f"  [{i}] {port.device} — {port.description}")
    choice = input("Select the port number for your Arduino: ").strip()
    try:
        return ports[int(choice)].device
    except (ValueError, IndexError):
        return None


def next_student_id():
    """Generates the next STUxxx ID based on existing entries."""
    existing_nums = []
    for info in REGISTERED_USERS.values():
        match = re.match(r"STU(\d+)", info["id"])
        if match:
            existing_nums.append(int(match.group(1)))
    next_num = max(existing_nums, default=0) + 1
    return f"STU{next_num:03d}"


def append_to_students_file(uid, name, student_id):
    """
    Inserts a new entry into the REGISTERED_USERS dict inside students.py,
    right before the closing brace, preserving existing formatting.
    """
    with open(STUDENTS_FILE, "r") as f:
        content = f.read()

    new_line = f'    "{uid}": {{"name": "{name}", "id": "{student_id}"}},\n'

    # Insert just before the final closing brace of the dict
    closing_brace_index = content.rstrip().rfind("}")
    if closing_brace_index == -1:
        raise ValueError("Could not find closing brace in students.py — "
                         "file may be malformed. No changes written.")

    updated_content = (
        content[:closing_brace_index].rstrip("\n") + "\n"
        + new_line
        + content[closing_brace_index:]
    )

    with open(STUDENTS_FILE, "w") as f:
        f.write(updated_content)


def wait_for_scan(ser):
    """Blocks until a real UID line comes in over serial."""
    print("[INFO] Waiting for card scan...")
    while True:
        if ser.in_waiting > 0:
            raw = ser.readline().decode("utf-8").strip()
            if not raw:
                continue
            # Real UIDs look like "A1:B2:C3:D4" — skip anything else
            if not re.match(r"^([0-9A-F]{2}:)+[0-9A-F]{2}$", raw):
                print(f"[SKIP] Ignored non-UID line: {raw}")
                continue
            return raw
        time.sleep(0.1)


def run():
    print("=== RFID Card Registration ===\n")

    port = SERIAL_PORT
    if port == "AUTO":
        print("[INFO] Auto-detecting serial port...")
        port = find_serial_port()
        if port is None:
            print("[ERROR] No serial port found. Is the Arduino plugged in?")
            print("[TIP]  You can also set SERIAL_PORT manually at the top "
                  "of this file (e.g. 'COM3' or '/dev/ttyUSB0').")
            return
        print(f"[INFO] Using port: {port}")

    print("[INFO] Opening serial port...")
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        time.sleep(2)  # Wait for Arduino to reset after connecting
        print("[INFO] Connected.\n")
    except serial.SerialException as e:
        print(f"[ERROR] Cannot open port {port}: {e}")
        print("[TIP]  Make sure no other program (Serial Monitor, "
              "rfid_attendence.py) is using this port.")
        return

    try:
        while True:
            uid = wait_for_scan(ser)
            print(f"\n[SCAN] Card UID detected: {uid}")

            if uid in REGISTERED_USERS:
                existing = REGISTERED_USERS[uid]
                print(f"  ⚠   This card is already registered to "
                      f"{existing['name']} ({existing['id']}).")
                ser.write(b"FAIL\n")

                again = input("\nScan another card? (y/n): ").strip().lower()
                if again != "y":
                    break
                continue

            name = input("  Enter student name: ").strip()
            if not name:
                print("  [SKIP] Name cannot be empty. Scan skipped.")
                ser.write(b"FAIL\n")
                continue

            student_id = next_student_id()
            confirm = input(
                f"  Register '{name}' as {student_id} with UID {uid}? (y/n): "
            ).strip().lower()

            if confirm != "y":
                print("  [SKIP] Registration cancelled.")
                ser.write(b"FAIL\n")
                continue

            append_to_students_file(uid, name, student_id)
            print(f"  ✅  Added {name} ({student_id}) to students.py")

            # Re-sync the database so the new student appears immediately
            init_database()
            ser.write(b"OK\n")

            again = input("\nRegister another card? (y/n): ").strip().lower()
            if again != "y":
                break

    except KeyboardInterrupt:
        print("\n[INFO] Registration stopped by user.")

    finally:
        ser.close()
        print("[INFO] Serial port closed.")


if __name__ == "__main__":
    run()
