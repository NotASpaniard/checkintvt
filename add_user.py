import sqlite3
import os

db_path = 'd:/checkintvt/instance/checkin.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

name = "Phạm Anh Dũng"
face_id = "1001"
dept = "Ban dieu hanh"

try:
    cur.execute("SELECT id FROM users WHERE name = ?", (name,))
    if cur.fetchone():
        print("EXISTS")
    else:
        cur.execute("INSERT INTO users (face_id, name, department) VALUES (?, ?, ?)", (face_id, name, dept))
        conn.commit()
        print("SUCCESS")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
