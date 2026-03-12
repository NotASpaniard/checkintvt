"""
TVT Device Poller
Periodically polls the TVT face recognition device for new check-in events.
Uses the SearchSnapFaceByTime API to fetch recent events.
"""

import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET
import base64
import os
import time
import threading
from datetime import datetime, timedelta
from services.zalo_service import zalo_service

# Configuration from .env
DEVICE_IP   = os.getenv("DEVICE_IP")
DEVICE_PORT = int(os.getenv("DEVICE_PORT", 80))
DEVICE_USER = os.getenv("DEVICE_USER", "admin")
DEVICE_PASS = os.getenv("DEVICE_PASS")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 5))

# Global state
last_poll_time = None
is_polling = False
poll_thread = None


def get_device_url(endpoint):
    """Build device API URL"""
    return f"http://{DEVICE_IP}:{DEVICE_PORT}/{endpoint}"


def create_session():
    """Create authenticated session with the device using Basic Auth like the web interface"""
    import base64
    
    session = requests.Session()
    
    # Create Basic Auth header like the web interface does
    auth_string = f"{DEVICE_USER}:{DEVICE_PASS}"
    auth_base64 = base64.b64encode(auth_string.encode()).decode()
    
    session.headers.update({
        "Authorization": f"Basic {auth_base64}"
    })
    
    # Set cookie like web interface
    session.cookies.set("auInfo", auth_base64)
    
    return session


def test_connection():
    """Test connection to device by calling DoLogin"""
    try:
        session = create_session()
        
        # Login like the web interface does
        login_payload = '''<?xml version="1.0" encoding="UTF-8"?>
<config version="1.0" xmlns="http://www.ipc.com/ver10">
<macInfo><address type="string"><![CDATA[00-00-00-00-00-00]]></address></macInfo>
<checkInfo><pcTime type="string"><![CDATA[2026-01-28 12:00:00]]></pcTime></checkInfo>
</config>'''
        
        r = session.post(
            get_device_url("DoLogin"),
            data=login_payload,
            headers={"Content-Type": "application/xml"},
            timeout=10
        )
        
        if r.status_code == 200 and 'status="success"' in r.text:
            print(f"[+] Connected to device at {DEVICE_IP}")
            return True
        else:
            print(f"[!] Device login failed. Status: {r.status_code}")
            print(f"    Response: {r.text[:500]}")
            return False
    except requests.exceptions.Timeout:
        print(f"[-] Connection timeout to {DEVICE_IP}")
        return False
    except Exception as e:
        print(f"[-] Connection error: {e}")
        return False


def search_snap_faces(start_time, end_time):
    """
    Search for face snap events in a time range.
    Returns list of (snapTime, faceID) tuples.
    """
    payload = f'''<?xml version="1.0" encoding="utf-8"?>
<config xmlns="http://www.ipc.com/ver10" version="1.0">
    <search>
        <starttime type="string"><![CDATA[{start_time}]]></starttime>
        <endtime type="string"><![CDATA[{end_time}]]></endtime>
    </search>
</config>'''
    
    try:
        session = create_session()
        r = session.post(
            get_device_url("SearchSnapFaceByTime"),
            data=payload,
            headers={"Content-Type": "application/xml"},
            timeout=30
        )
        
        if r.status_code != 200:
            print(f"[!] SearchSnapFaceByTime returned {r.status_code}")
            return []
        
        # Parse XML response
        root = ET.fromstring(r.text)
        ns = {"ns": "http://www.ipc.com/ver10"}
        
        results = []
        for item in root.findall(".//ns:captureFaceList/ns:item", ns):
            snap_time = item.find("ns:snapTime", ns)
            face_id = item.find("ns:faceID", ns)
            if snap_time is not None and face_id is not None:
                results.append((snap_time.text, face_id.text))
        
        return results
        
    except ET.ParseError as e:
        print(f"[-] XML Parse Error: {e}")
        return []
    except Exception as e:
        print(f"[-] Error searching faces: {e}")
        return []


def get_snap_face_details(snap_time, face_id):
    """
    Get detailed information about a specific face snap event.
    Returns dict with person info and image data.
    """
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
        r = session.post(
            get_device_url("SearchSnapFaceByKey"),
            data=payload,
            headers={"Content-Type": "application/xml"},
            timeout=30
        )
        
        if r.status_code != 200:
            print(f"[!] SearchSnapFaceByKey returned {r.status_code}")
            return None
        
        # Parse XML response
        root = ET.fromstring(r.text)
        ns = {"ns": "http://www.ipc.com/ver10"}
        
        result = {
            "snap_time": None,
            "name": "Stranger",
            "person_id": None,
            "similarity": 0,
            "temperature": None,
            "image_data": None
        }
        
        # Get snap info
        snap_info = root.find(".//ns:snapInfo", ns)
        if snap_info is not None:
            time_node = snap_info.find("ns:time", ns)
            if time_node is not None:
                result["snap_time"] = time_node.text
            
            pic_node = snap_info.find("ns:pictureData", ns)
            if pic_node is not None and pic_node.text:
                result["image_data"] = pic_node.text.strip()
        
        # Get match info (if person was recognized)
        match_info = root.find(".//ns:matchInfo", ns)
        if match_info is not None:
            sim_node = match_info.find("ns:similarity", ns)
            if sim_node is not None:
                result["similarity"] = int(sim_node.text)
            
            temp_node = match_info.find("ns:temperature", ns)
            if temp_node is not None:
                result["temperature"] = int(temp_node.text) / 100.0  # Convert to degrees
            
            person_info = match_info.find("ns:personInfo", ns)
            if person_info is not None:
                name_node = person_info.find("ns:name", ns)
                if name_node is not None:
                    result["name"] = name_node.text
                
                # TVT dung jobNumber lam ma dinh danh nhan vien (khong co personID trong XML)
                job_node = person_info.find("ns:jobNumber", ns)
                if job_node is not None and job_node.text and job_node.text.strip():
                    result["person_id"] = job_node.text.strip()
                else:
                    # Du phong: dung identifyNumber
                    id_node = person_info.find("ns:identifyNumber", ns)
                    if id_node is not None and id_node.text and id_node.text.strip():
                        result["person_id"] = id_node.text.strip()
        
        print(f"[DEBUG] Parsed => name={result['name']}, person_id={result['person_id']}, similarity={result['similarity']}")
        return result

    except ET.ParseError as e:
        print(f"[-] XML Parse Error: {e}")
        return None
    except Exception as e:
        print(f"[-] Error getting face details: {e}")
        return None


def save_image(base64_data, filename, save_dir="static/captures"):
    """Decode and save base64 image"""
    if not base64_data:
        return None
    
    try:
        # Remove header if present
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]
        
        image_data = base64.b64decode(base64_data)
        
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        filepath = os.path.join(save_dir, filename)
        with open(filepath, "wb") as f:
            f.write(image_data)
        
        return filepath
    except Exception as e:
        print(f"[-] Error saving image: {e}")
        return None


def poll_device(app, db, User, Log):
    """
    Poll device for new events and save to database.
    Should be called periodically.
    """
    global last_poll_time
    
    now = datetime.now()
    
    # Default: poll last 1 minute
    if last_poll_time is None:
        start_time = (now - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    else:
        start_time = last_poll_time.strftime("%Y-%m-%d %H:%M:%S")
    
    end_time = now.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"[*] Polling events from {start_time} to {end_time}")
    
    # Get list of recent events
    events = search_snap_faces(start_time, end_time)
    print(f"[*] Found {len(events)} events")
    
    for snap_time, face_id in events:
        # Get details for each event
        details = get_snap_face_details(snap_time, face_id)
        if not details:
            continue
        
        with app.app_context():
            # Check if already logged (avoid duplicates)
            existing = Log.query.filter_by(
                face_id=str(face_id),
                checkin_time_str=details["snap_time"]
            ).first()
            
            if existing:
                continue
            
            # Save image
            user = None
            user_id = None
            image_path = None
            if details["image_data"]:
                filename = f"capture_{snap_time}_{face_id}.jpg"
                image_path = save_image(details["image_data"], filename)
            
            # Find or create user
            if details["person_id"]:
                user = User.query.filter_by(face_id=str(details["person_id"])).first()
                if not user:
                    user = User(
                        face_id=str(details["person_id"]),
                        name=details["name"]
                    )
                    db.session.add(user)
                    db.session.commit()
                user_id = user.id
            
            # Create log entry
            new_log = Log(
                user_id=user_id,
                face_id=str(face_id),
                checkin_time_str=details["snap_time"],
                image_path=image_path,
                zalo_notified=False
            )
            db.session.add(new_log)
            db.session.commit()
            
            # Gửi thông báo Zalo nếu user có cấu hình Zalo_User_ID
            if user and user.zalo_user_id:
                # Cơ chế chống Spam: Chặn gửi nhiều tin nhắn liên tục trong 5 phút
                five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
                recent_log = Log.query.filter(
                    Log.user_id == user.id, 
                    Log.zalo_notified == True,
                    Log.timestamp >= five_mins_ago
                ).first()
                
                if not recent_log:
                    success = zalo_service.send_all_notifications(
                        user.zalo_user_id, 
                        user.name, 
                        details["snap_time"]
                    )
                    if success:
                        new_log.zalo_notified = True
                        db.session.commit()
                else:
                    print(f"[*] Bỏ qua gửi Zalo cho {user.name} do đã gửi thành công trong vòng 5 phút qua.")
            
            print(f"[OK] RECORDED: {details['name']} at {details['snap_time']}")
    
    last_poll_time = now


def start_polling(app, db, User, Log):
    """Start background polling thread"""
    global is_polling, poll_thread
    
    if is_polling:
        print("[!] Polling already running")
        return
    
    is_polling = True
    
    def poll_loop():
        global is_polling
        while is_polling:
            try:
                poll_device(app, db, User, Log)
            except Exception as e:
                print(f"[-] Polling error: {e}")
            time.sleep(POLL_INTERVAL)
    
    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    print(f"[+] Started polling every {POLL_INTERVAL} seconds")


def stop_polling():
    """Stop background polling"""
    global is_polling
    is_polling = False
    print("[*] Polling stopped")


if __name__ == "__main__":
    # Test connection
    print("Testing connection to device...")
    if test_connection():
        print("Connection successful!")
        
        # Test search
        now = datetime.now()
        start = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        end = now.strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"Searching events from {start} to {end}")
        events = search_snap_faces(start, end)
        print(f"Found {len(events)} events")
        
        for snap_time, face_id in events[:3]:  # Show first 3
            print(f"  - SnapTime: {snap_time}, FaceID: {face_id}")
            details = get_snap_face_details(snap_time, face_id)
            if details:
                print(f"    Name: {details['name']}, Similarity: {details['similarity']}%")
    else:
        print("Connection failed!")
