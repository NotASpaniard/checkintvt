"""Script chan doan toan bo he thong"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

RAILWAY_URL = os.getenv("RAILWAY_API_URL", "").rstrip('/')
POLLER_KEY = os.getenv("POLLER_API_KEY", "")
DEVICE_IP = os.getenv("DEVICE_IP", "")
DEVICE_PORT = os.getenv("DEVICE_PORT", "80")
DEVICE_PASS = os.getenv("DEVICE_PASS", "")

print("=" * 50)
print("CHAN DOAN TOAN BO HE THONG")
print("=" * 50)

# 1. In tat ca bien moi truong
print(f"\n[1] .env:\n    RAILWAY_URL  = {RAILWAY_URL}")
print(f"    POLLER_KEY   = {POLLER_KEY}")
print(f"    DEVICE_IP    = {DEVICE_IP}")
print(f"    DEVICE_PORT  = {DEVICE_PORT}")
print(f"    DEVICE_PASS  = {'***' + DEVICE_PASS[-3:] if DEVICE_PASS else '(TRONG)'}")

# 2. Test Railway status
print(f"\n[2] Kiem tra Railway /api/status ...")
try:
    r = requests.get(f"{RAILWAY_URL}/api/status", timeout=15)
    print(f"    Code: {r.status_code}")
    print(f"    Body: {r.text[:300]}")
except Exception as e:
    print(f"    LOI: {e}")

# 3. Test Railway push (voi header chi tiet)
print(f"\n[3] Kiem tra Railway /api/internal/checkin ...")
try:
    headers = {"Content-Type": "application/json", "X-Poller-Key": POLLER_KEY}
    payload = {
        "face_id": "DIAG_001", "snap_time": "2026-03-13 11:00:00",
        "name": "Test Diagnostic", "person_id": "D001",
        "similarity": 95, "image_b64": ""
    }
    print(f"    Header gui di: X-Poller-Key = '{POLLER_KEY}'")
    r = requests.post(f"{RAILWAY_URL}/api/internal/checkin", json=payload, headers=headers, timeout=15)
    print(f"    Code: {r.status_code}")
    print(f"    Body: {r.text[:300]}")
except Exception as e:
    print(f"    LOI: {e}")

# 4. Test Camera
print(f"\n[4] Kiem tra ket noi Camera {DEVICE_IP}:{DEVICE_PORT} ...")
import base64
try:
    session = requests.Session()
    auth_string = f"admin:{DEVICE_PASS}"
    auth_b64 = base64.b64encode(auth_string.encode()).decode()
    session.headers.update({"Authorization": f"Basic {auth_b64}"})
    session.cookies.set("auInfo", auth_b64)
    
    from datetime import datetime, timedelta
    now = datetime.now()
    start = (now - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    
    payload = f'''<?xml version="1.0" encoding="utf-8"?>
<config xmlns="http://www.ipc.com/ver10" version="1.0">
    <search>
        <starttime type="string"><![CDATA[{start}]]></starttime>
        <endtime type="string"><![CDATA[{end}]]></endtime>
    </search>
</config>'''
    
    r = session.post(f"http://{DEVICE_IP}:{DEVICE_PORT}/SearchSnapFaceByTime", 
                     data=payload, headers={"Content-Type": "application/xml"}, timeout=15)
    print(f"    HTTP Code: {r.status_code}")
    if r.status_code == 401:
        print(f"    --> Camera TU CHOI MAT KHAU (401 Unauthorized)")
        print(f"    --> Kiem tra lai DEVICE_PASS trong .env hoac mat khau camera da bi doi?")
    
    # In 500 ky tu dau cua phan hoi
    print(f"    Response: {r.text[:500]}")
except requests.exceptions.ConnectTimeout:
    print(f"    --> Camera TIMEOUT (mang cham hoac IP sai)")
except requests.exceptions.ConnectionError as e:
    if "10061" in str(e):
        print(f"    --> Camera TU CHOI KET NOI (Port {DEVICE_PORT} sai)")
    else:
        print(f"    --> LOI ket noi: {e}")
except Exception as e:
    print(f"    LOI: {e}")

print(f"\n{'=' * 50}")
print("KET THUC CHAN DOAN")
print("=" * 50)
