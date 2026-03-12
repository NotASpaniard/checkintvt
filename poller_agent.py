"""
Poller Agent - Chay TREN MAY TINH VAN PHONG (24/7)
Poll Camera TVT qua mang LAN, day du lieu len Railway API.

Cach chay:
    python poller_agent.py

Yeu cau trong .env:
    DEVICE_IP, DEVICE_PORT, DEVICE_USER, DEVICE_PASS
    RAILWAY_API_URL=https://your-app.railway.app
    POLLER_API_KEY=<secret-key>
"""

import requests
import xml.etree.ElementTree as ET
import base64
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ---- Cau hinh Thiet bi TVT ----
DEVICE_IP   = os.getenv("DEVICE_IP")
DEVICE_PORT = os.getenv("DEVICE_PORT", "80")
DEVICE_USER = os.getenv("DEVICE_USER", "admin")
DEVICE_PASS = os.getenv("DEVICE_PASS")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))

# ---- Cau hinh Railway ----
RAILWAY_URL = os.getenv("RAILWAY_API_URL", "http://localhost:5000")
POLLER_API_KEY = os.getenv("POLLER_API_KEY", "")

if not DEVICE_IP or not DEVICE_PASS:
    raise RuntimeError("Thieu DEVICE_IP hoac DEVICE_PASS trong .env!")

last_poll_time = None


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


def search_snap_faces(start_time, end_time):
    payload = f'''<?xml version="1.0" encoding="utf-8"?>
<config xmlns="http://www.ipc.com/ver10" version="1.0">
    <search>
        <starttime type="string"><![CDATA[{start_time}]]></starttime>
        <endtime type="string"><![CDATA[{end_time}]]></endtime>
    </search>
</config>'''
    try:
        session = create_session()
        r = session.post(get_device_url("SearchSnapFaceByTime"), data=payload,
                         headers={"Content-Type": "application/xml"}, timeout=30)
        root = ET.fromstring(r.text)
        ns = {"ns": "http://www.ipc.com/ver10"}
        results = []
        for item in root.findall(".//ns:captureFaceList/ns:item", ns):
            snap_time = item.find("ns:snapTime", ns)
            face_id = item.find("ns:faceID", ns)
            if snap_time is not None and face_id is not None:
                results.append((snap_time.text, face_id.text))
        return results
    except Exception as e:
        print(f"[-] Loi search faces: {e}")
        return []


def get_snap_face_details(snap_time, face_id):
    payload = f'''<?xml version="1.0" encoding="utf-8"?>
<config xmlns="http://www.ipc.com/ver10" version="1.0">
    <search>
        <snapTime type="uint64">{snap_time}</snapTime>
        <faceID type="uint32">{face_id}</faceID>
        <requestPanoramicPic type="boolean">false</requestPanoramicPic>
        <requestPersonPic type="boolean">true</requestPersonPic>
    </search>
</config>'''
    try:
        session = create_session()
        r = session.post(get_device_url("SearchSnapFaceByKey"), data=payload,
                         headers={"Content-Type": "application/xml"}, timeout=30)
        root = ET.fromstring(r.text)
        ns = {"ns": "http://www.ipc.com/ver10"}
        result = {"snap_time": None, "name": "Stranger", "person_id": None,
                  "similarity": 0, "image_data": None}
        snap_info = root.find(".//ns:snapInfo", ns)
        if snap_info is not None:
            t = snap_info.find("ns:time", ns)
            if t is not None:
                result["snap_time"] = t.text
            pic = snap_info.find("ns:pictureData", ns)
            if pic is not None and pic.text:
                result["image_data"] = pic.text.strip()
        match_info = root.find(".//ns:matchInfo", ns)
        if match_info is not None:
            sim = match_info.find("ns:similarity", ns)
            if sim is not None:
                result["similarity"] = int(sim.text)
            person_info = match_info.find("ns:personInfo", ns)
            if person_info is not None:
                name_node = person_info.find("ns:name", ns)
                if name_node is not None:
                    result["name"] = name_node.text
                job_node = person_info.find("ns:jobNumber", ns)
                if job_node is not None and job_node.text and job_node.text.strip():
                    result["person_id"] = job_node.text.strip()
                else:
                    id_node = person_info.find("ns:identifyNumber", ns)
                    if id_node is not None and id_node.text and id_node.text.strip():
                        result["person_id"] = id_node.text.strip()
        return result
    except Exception as e:
        print(f"[-] Loi get face details: {e}")
        return None


def push_to_railway(details, face_id, image_data_b64):
    """Day du lieu check-in len Railway API."""
    headers = {
        "Content-Type": "application/json",
        "X-Poller-Key": POLLER_API_KEY
    }
    payload = {
        "face_id": str(face_id),
        "snap_time": details["snap_time"],
        "name": details["name"],
        "person_id": details["person_id"],
        "similarity": details["similarity"],
        "image_b64": image_data_b64
    }
    try:
        r = requests.post(f"{RAILWAY_URL}/api/internal/checkin",
                          json=payload, headers=headers, timeout=15)
        result = r.json()
        if result.get("status") == "ok":
            print(f"[OK] Pushed: {details['name']} at {details['snap_time']}")
            return True
        else:
            print(f"[!] Railway tu choi: {result}")
            return False
    except Exception as e:
        print(f"[-] Loi ket noi Railway: {e}")
        return False


def poll_once():
    global last_poll_time
    now = datetime.now()
    if last_poll_time is None:
        start = (now - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    else:
        start = last_poll_time.strftime("%Y-%m-%d %H:%M:%S")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[*] Polling {start} -> {end}")

    events = search_snap_faces(start, end)
    print(f"[*] Found {len(events)} events")
    for snap_time, face_id in events:
        details = get_snap_face_details(snap_time, face_id)
        if details:
            push_to_railway(details, face_id, details.get("image_data"))
    last_poll_time = now


def main():
    print(f"[+] Poller Agent khoi dong | Device: {DEVICE_IP} | Server: {RAILWAY_URL}")
    while True:
        try:
            poll_once()
        except Exception as e:
            print(f"[-] Polling error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
