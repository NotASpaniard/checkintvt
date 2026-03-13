"""
Poller Agent - Chay TREN MAY TINH VAN PHONG (24/7)
Poll Camera TVT qua mang LAN, day du lieu len Railway API.
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
RAILWAY_URL = os.getenv("RAILWAY_API_URL", "").rstrip('/')
POLLER_API_KEY = os.getenv("POLLER_API_KEY", "")

# TANG TIMEOUT DE CHIU LAG
GLOBAL_TIMEOUT = 60 

if not DEVICE_IP or not DEVICE_PASS:
    raise RuntimeError("Thieu DEVICE_IP hoac DEVICE_PASS trong .env!")

def get_device_url(endpoint):
    return f"http://{DEVICE_IP}:{DEVICE_PORT}/{endpoint}"

def create_session():
    import base64 as b64
    session = requests.Session()
    
    # Tao Basic Auth header
    auth_string = f"{DEVICE_USER}:{DEVICE_PASS}"
    auth_base64 = b64.b64encode(auth_string.encode()).decode()
    
    session.headers.update({
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/xml"
    })
    session.cookies.set("auInfo", auth_base64)
    
    # BUOC BAT BUOC: DoLogin de thiet lap session thuc su tren Camera
    login_payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<config version="1.0" xmlns="http://www.ipc.com/ver10">
<macInfo><address type="string"><![CDATA[00-00-00-00-00-00]]></address></macInfo>
<checkInfo><pcTime type="string"><![CDATA[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]]></pcTime></checkInfo>
</config>'''
    
    # Tang timeout len 30s vi mang dang loss 60%
    try:
        r = session.post(get_device_url("DoLogin"), data=login_payload, timeout=30)
        if r.status_code == 200 and 'status="success"' in r.text:
            return session
        elif r.status_code == 401:
            print(f"[!] Sai mat khau Camera (401).")
            return None
        else:
            print(f"[!] DoLogin do loi: {r.status_code}")
            return None
    except Exception as e:
        print(f"[-] Loi mang khi DoLogin (Mang dang yeu): {e}")
        return None

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
        if not session:
            return []
            
        r = session.post(get_device_url("SearchSnapFaceByTime"), data=payload,
                         headers={"Content-Type": "application/xml"}, timeout=GLOBAL_TIMEOUT)
        
        if r.status_code == 401:
            print(f"[!] Camera tu choi Basic Auth (401).")
            return []

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
        print(f"[-] Loi ket noi Camera (Search): {e}")
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
        if not session:
            return None
            
        r = session.post(get_device_url("SearchSnapFaceByKey"), data=payload,
                         headers={"Content-Type": "application/xml"}, timeout=GLOBAL_TIMEOUT)
        root = ET.fromstring(r.text)
        ns = {"ns": "http://www.ipc.com/ver10"}
        result = {"snap_time": None, "name": "Stranger", "person_id": None,
                  "similarity": 0, "image_data": None}
        snap_info = root.find(".//ns:snapInfo", ns)
        if snap_info is not None:
            t = snap_info.find("ns:time", ns)
            if t is not None: result["snap_time"] = t.text
            pic = snap_info.find("ns:pictureData", ns)
            if pic is not None and pic.text: result["image_data"] = pic.text.strip()
        
        match_info = root.find(".//ns:matchInfo", ns)
        if match_info is not None:
            sim = match_info.find("ns:similarity", ns)
            if sim is not None: result["similarity"] = int(sim.text)
            person_info = match_info.find("ns:personInfo", ns)
            if person_info is not None:
                name_node = person_info.find("ns:name", ns)
                if name_node is not None: result["name"] = name_node.text
                job_node = person_info.find("ns:jobNumber", ns)
                if job_node is not None and job_node.text: result["person_id"] = job_node.text.strip()
        return result
    except Exception as e:
        print(f"[-] Loi lay chi tiet: {e}")
        return None

def push_to_railway(details, face_id, image_data_b64):
    headers = {"Content-Type": "application/json", "X-Poller-Key": POLLER_API_KEY}
    payload = {
        "face_id": str(face_id), "snap_time": details["snap_time"],
        "name": details["name"], "person_id": details["person_id"],
        "similarity": details["similarity"], "image_b64": image_data_b64
    }
    try:
        r = requests.post(f"{RAILWAY_URL}/api/internal/checkin", json=payload, headers=headers, timeout=30)
        if r.status_code == 200:
            print(f"[OK] Railway nhan: {details['name']} ({details['snap_time']})")
            return True
        else:
            print(f"[!] Railway loi ({r.status_code}): {r.text}")
        return False
    except Exception as e:
        print(f"[-] Loi day len Cloud: {e}")
        return False

def send_heartbeat():
    headers = {"X-Poller-Key": POLLER_API_KEY}
    try:
        r = requests.post(f"{RAILWAY_URL}/api/internal/heartbeat", 
                         json={"device_ip": DEVICE_IP},
                         headers=headers, timeout=10)
        return r.status_code == 200
    except:
        return False

def main():
    print(f"[+] POLLER AGENT v1.1 (REVERTED)")
    print(f"[+] Camera: {DEVICE_IP}:{DEVICE_PORT} | Server: {RAILWAY_URL}")
    print("-" * 50)
    
    last_poll_time = None
    last_heartbeat_sent = 0
    
    while True:
        try:
            now_ts = time.time()
            if now_ts - last_heartbeat_sent > 30: # Moi 30 giay gui 1 lan
                if send_heartbeat():
                    last_heartbeat_sent = now_ts
                else:
                    print("[-] Heartbeat failed.")

            now = datetime.now()
            # Quet lùi 30 phut de chac chan khong sot
            start = (now - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
            end = now.strftime("%Y-%m-%d %H:%M:%S")
            
            events = search_snap_faces(start, end)
            if events:
                print(f"[*] Found {len(events)} events in last 30m.")
                for snap_time, face_id in events:
                    details = get_snap_face_details(snap_time, face_id)
                    if details:
                        push_to_railway(details, face_id, details.get("image_data"))
            else:
                print(f"[.] No events found ({start} -> {end})")
                
        except KeyboardInterrupt: break
        except Exception as e: print(f"[-] Error: {e}")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
