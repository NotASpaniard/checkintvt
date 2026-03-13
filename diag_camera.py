import requests
import xml.etree.ElementTree as ET
import os
from dotenv import load_dotenv

load_dotenv()

DEVICE_IP   = os.getenv("DEVICE_IP")
DEVICE_PORT = os.getenv("DEVICE_PORT", "80")
DEVICE_USER = os.getenv("DEVICE_USER", "admin")
DEVICE_PASS = os.getenv("DEVICE_PASS")

def get_device_url(endpoint):
    return f"http://{DEVICE_IP}:{DEVICE_PORT}/{endpoint}"

def create_session():
    import base64 as b64
    session = requests.Session()
    auth_string = f"{DEVICE_USER}:{DEVICE_PASS}"
    auth_b64 = b64.b64encode(auth_string.encode()).decode()
    session.headers.update({"Authorization": f"Basic {auth_b64}"})
    session.cookies.set("auInfo", auth_b64)
    return session

def get_camera_time():
    print(f"[*] Dang kiem tra thoi gian tren Camera {DEVICE_IP}...")
    try:
        session = create_session()
        # Thu lay thoi gian he thong (GetSystemTime la mot lenh pho bien cua TVT)
        r = session.get(get_device_url("GetSystemTime"), timeout=10)
        print(f"[OK] Phan hoi tu Camera: {r.text}")
    except Exception as e:
        print(f"[-] Khong the lay thoi gian: {e}")

if __name__ == "__main__":
    get_camera_time()
