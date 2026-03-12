from flask import Blueprint, request, Response, current_app
import xml.etree.ElementTree as ET
import base64
import os
import time
from datetime import datetime
from database.database import db, Log, User

bp = Blueprint('device', __name__)

def save_image(base64_data, filename):
    if not base64_data:
        return None
    try:
        # Check if header exists in base64 string (e.g. data:image/jpeg;base64,) and strip it
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]
        
        image_data = base64.b64decode(base64_data)
        
        # Ensure directory exists
        save_dir = os.path.join(current_app.root_path, 'static', 'captures')
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        filepath = os.path.join(save_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(image_data)
        
        # Return relative path for DB
        return f'static/captures/{filename}'
    except Exception as e:
        print(f"Error saving image: {e}")
        return None

@bp.route('/', methods=['GET', 'POST', 'PUT'])
@bp.route('/<path:path>', methods=['GET', 'POST', 'PUT'])
def handle_device_push(path=''):
    """
    Handle XML Push from TVT Device.
    The device might push to root '/' or any configured path.
    """
    try:
        print(f"🔔 REQUEST RECEIVED: {request.method} /{path}")
        print("Heades:", request.headers)
        
        xml_data = request.data
        if not xml_data:
            print("❌ Empty body received")
            return Response("OK", status=200)

        # Log raw data for debug
        with open('logs/device_last_push.xml', 'wb') as f:
            f.write(xml_data)

        # Parse XML
        root = ET.fromstring(xml_data)
        
        # Check if it's a Face Check-in Event (snapFace)
        # Structure based on Docs: <snapFace> -> <snapInfo> (image), <matchInfo> (person)
        
        # Note: Depending on device version, root tag might vary.
        # We look for specific identifying tags.
        
        # 1. Check for Snap Info (Image & Time)
        snap_info = root.find('.//snapInfo')
        match_info = root.find('.//matchInfo')
        
        if snap_info is None and match_info is None:
             print("Received XML but no snapInfo or matchInfo found. Probably Heartbeat or other event.")
             return Response("OK", status=200)

        # Extract Data
        checkin_time_str = ""
        image_path = None
        face_id = "Unknown"
        name = "Stranger"
        score = 0.0
        user_id = None

        if snap_info is not None:
             # Time format usually: 2026-01-27 18:00:00
             time_node = snap_info.find('snapTime') # Or 'time' based on doc variation
             if time_node is not None:
                 checkin_time_str = time_node.text
             
             # Image
             pic_node = snap_info.find('pictureData') # or sourceBase64Data
             if pic_node is not None and pic_node.text:
                 # Generate filename
                 filename = f"capture_{int(time.time())}.jpg"
                 image_path = save_image(pic_node.text, filename)

        if match_info is not None:
            # Match Info exists -> Registered User
            name_node = match_info.find('name') # or personName
            id_node = match_info.find('personID') # or personId
            score_node = match_info.find('similarity')

            if name_node is not None: name = name_node.text
            if id_node is not None: face_id = id_node.text
            if score_node is not None: 
                try: score = float(score_node.text)
                except: pass

        # Logic: Find or Create User
        # Only create user if we have a valid Face ID (not stranger)
        if face_id != "Unknown":
            user = User.query.filter_by(face_id=face_id).first()
            if not user:
                # Auto-create user if not exists (Optional feature)
                user = User(face_id=face_id, name=name)
                db.session.add(user)
                db.session.commit()
            else:
                # Update name if changed
                if user.name != name:
                    user.name = name
                    db.session.commit()
            user_id = user.id

        # Save Log
        new_log = Log(
            user_id=user_id,
            face_id=face_id,
            checkin_time_str=checkin_time_str,
            image_path=image_path,
            score=score
        )
        db.session.add(new_log)
        db.session.commit()
        
        print(f"✅ RECORDED: {name} ({face_id}) at {checkin_time_str}")

        return Response("OK", status=200)

    except ET.ParseError:
        print("Error Parsing XML")
        return Response("Invalid XML", status=400)
    except Exception as e:
        print(f"Server Error: {e}")
        return Response("Internal Error", status=500)
