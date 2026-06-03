# database.py
import sqlite3
import os
from datetime import datetime
from students import REGISTERED_USERS

# ── Path to database file ─────────────────────────────────────
# os.path makes this work regardless of which folder you run
# the script from — no more "file not found" errors
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "../data/attendance.db")

# ── Step 1: Create tables on first run ───────────────────────


def init_database():
    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id   TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            rfid_uid     TEXT UNIQUE NOT NULL,
            enrolled     TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            record_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id   TEXT NOT NULL,
            student_name TEXT NOT NULL,
            timestamp    TEXT NOT NULL,
            date         TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    """)

    conn.commit()

    # Auto-populate students table from students.py
    for uid, info in REGISTERED_USERS.items():
        conn.execute(
            "INSERT OR IGNORE INTO students VALUES (?, ?, ?, ?)",
            (info["id"], info["name"], uid,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

    conn.commit()
    conn.close()
    print("[DB] Tables ready. Students synced.")


# ── Step 2: Log one attendance record ────────────────────────
def log_attendance(student_id, student_name):
    """
    Saves attendance for a student.
    Returns:
        'logged'    → new record saved successfully
        'duplicate' → student already marked today, skipped
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    # Check if already marked today
    cursor.execute(
        "SELECT record_id FROM attendance "
        "WHERE student_id = ? AND date = ?",
        (student_id, today)
    )

    if cursor.fetchone():
        conn.close()
        return "duplicate"

    # Save the new record
    cursor.execute(
        "INSERT INTO attendance VALUES (NULL, ?, ?, ?, ?)",
        (
            student_id,
            student_name,
            now.strftime("%Y-%m-%d %H:%M:%S"),
            today
        )
    )

    conn.commit()
    conn.close()
    return "logged"


# ── Step 3: Query helpers (used by Flask dashboard) ───────────
def get_today_records():
    """Returns all attendance records for today as a list of dicts."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM attendance "
        "WHERE date = ? ORDER BY timestamp DESC",
        (today,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    """Returns total, present, absent count and percentage for today."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)

    total = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    present = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE date = ?",
        (today,)
    ).fetchone()[0]

    conn.close()
    return {
        "total":   total,
        "present": present,
        "absent":  total - present,
        "pct":     round(present / max(total, 1) * 100, 1)
    }
