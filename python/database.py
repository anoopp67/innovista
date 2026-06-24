import sqlite3
import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "../data/attendance.db")
STUDENTS_FILE = os.path.join(BASE_DIR, "students.py")


def _get_registered_users():
    """Dynamically load REGISTERED_USERS from students.py at call time."""
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("students", STUDENTS_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.REGISTERED_USERS


def init_database():
    """
    Connect and create student and attendance tables.
    Remove students no longer in students.py.
    Add any new students from students.py.
    """
    REGISTERED_USERS = _get_registered_users()

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

    if REGISTERED_USERS:
        placeholders = ",".join("?" * len(REGISTERED_USERS))
        conn.execute(
            f"DELETE FROM students WHERE rfid_uid NOT IN ({placeholders})",
            list(REGISTERED_USERS.keys())
        )
    else:
        conn.execute("DELETE FROM students")

    for uid, info in REGISTERED_USERS.items():
        conn.execute(
            "INSERT OR IGNORE INTO students VALUES (?, ?, ?, ?)",
            (info["id"], info["name"], uid,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

    conn.commit()
    conn.close()
    print("[DB] Tables ready. Students synced.")


def _next_student_id():
    """Generate the next STUxxx ID from students.py."""
    REGISTERED_USERS = _get_registered_users()
    existing_nums = []
    for info in REGISTERED_USERS.values():
        match = re.match(r"STU(\d+)", info["id"])
        if match:
            existing_nums.append(int(match.group(1)))
    next_num = max(existing_nums, default=0) + 1
    return f"STU{next_num:03d}"


def _append_to_students_file(uid, name, student_id):
    """Insert a new entry into REGISTERED_USERS in students.py."""
    with open(STUDENTS_FILE, "r") as f:
        content = f.read()

    new_line = f'    "{uid}": {{"name": "{name}", "id": "{student_id}"}},\n'
    closing_brace_index = content.rstrip().rfind("}")
    if closing_brace_index == -1:
        raise ValueError("Could not find closing brace in students.py")

    updated_content = (
        content[:closing_brace_index].rstrip("\n") + "\n"
        + new_line
        + content[closing_brace_index:]
    )

    with open(STUDENTS_FILE, "w") as f:
        f.write(updated_content)


def register_student_web(uid, name):
    """
    Register a new student from the web UI.
    Returns (success: bool, message: str, student_id: str|None)
    """
    uid = uid.upper().strip()

    REGISTERED_USERS = _get_registered_users()
    if uid in REGISTERED_USERS:
        existing = REGISTERED_USERS[uid]
        return False, f"Card already registered to {existing['name']} ({existing['id']})", None

    # Check DB for duplicate UID
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT student_id, name FROM students WHERE rfid_uid=?", (uid,)).fetchone()
    conn.close()
    if row:
        return False, f"Card already registered to {row[1]} ({row[0]})", None

    student_id = _next_student_id()
    _append_to_students_file(uid, name, student_id)

    # Add directly to DB too
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO students VALUES (?, ?, ?, ?)",
        (student_id, name, uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

    return True, f"Registered {name} as {student_id}", student_id


def get_registered_user(uid):
    """Look up a student by RFID UID from the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT student_id, name FROM students WHERE rfid_uid=?", (uid,)
    ).fetchone()
    conn.close()
    if row:
        return {"id": row["student_id"], "name": row["name"]}
    return None


def insert_student(uid, name, student_id):
    """Inserts a single newly registered student directly into the DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO students VALUES (?, ?, ?, ?)",
        (student_id, name, uid,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()


def get_all_students():
    """Returns all students in the roster."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM students ORDER BY student_id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_student(student_id):
    """Remove a student and all their attendance records."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
    conn.commit()
    conn.close()


def delete_record(record_id):
    """Remove a single attendance record."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM attendance WHERE record_id = ?", (record_id,))
    conn.commit()
    conn.close()


def delete_records_by_date(date):
    """Clear all attendance records for a given date."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM attendance WHERE date = ?", (date,))
    conn.commit()
    conn.close()


def log_attendance(student_id, student_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    cursor.execute(
        "SELECT record_id FROM attendance WHERE student_id = ? AND date = ?",
        (student_id, today)
    )
    if cursor.fetchone():
        conn.close()
        return "duplicate"

    cursor.execute(
        "INSERT INTO attendance VALUES (NULL, ?, ?, ?, ?)",
        (student_id, student_name,
         now.strftime("%Y-%m-%d %H:%M:%S"), today)
    )
    conn.commit()
    conn.close()
    return "logged"


def unmark_attendance(student_id):
    """Remove today's attendance record for a student."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "DELETE FROM attendance WHERE student_id = ? AND date = ?",
        (student_id, today)
    )
    conn.commit()
    conn.close()


def get_today_records():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM attendance WHERE date = ? ORDER BY timestamp DESC",
        (today,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    present = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE date = ?", (today,)
    ).fetchone()[0]
    conn.close()
    return {
        "total":   total,
        "present": present,
        "absent":  total - present,
        "pct":     round(present / max(total, 1) * 100, 1)
    }


def get_records_by_date(date):
    """Returns attendance records for any given date (YYYY-MM-DD)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM attendance WHERE date = ? ORDER BY timestamp DESC",
        (date,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_dates():
    """Returns every date with at least one record, newest first."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT DISTINCT date FROM attendance ORDER BY date DESC"
    ).fetchall()
    conn.close()
    return [row[0] for row in rows]