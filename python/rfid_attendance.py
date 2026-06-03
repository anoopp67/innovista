import sqlite3
from datetime import datetime
'''sample data'''
registered_users = {
    "A1:B2:C3:D4": "Anoop",
    "11:22:33:44": "jason",
    "AA:BB:CC:DD": "ankit"
}

while True:
    uid = input("Scan Card: ") #scan
    if uid in registered_users:
        name = registered_users[uid] #matches with sample data
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor() #retrieves data
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S") #get current date and time and converts into custom txt format
        cursor.execute(
            "INSERT INTO attendance (uid, name, time) VALUES (?, ?, ?)",
            (uid, name, current_time)
        ) #stores attendance

        conn.commit()
        conn.close()
        print(f"Attendance Marked for {name}")

    else:
        print("Unknown Card")
