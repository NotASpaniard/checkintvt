"""
TVT Check-in Server
Flask application that polls the TVT device for check-in events and provides a web interface.
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
from database.database import db, User, Log
import device_poller
import os
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}}, allow_headers=["Content-Type", "Authorization", "ngrok-skip-browser-warning"])
    
    # Config Database - ưu tiên DATABASE_URL (Railway tự cấp), sau đó đến DB_USER... cuối cùng là SQLite
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    else:
        db_user = os.getenv('DB_USER')
        db_pass = os.getenv('DB_PASS')
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME')
        
        if all([db_user, db_pass, db_host, db_name]):
            database_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        else:
            # Dự phòng SQLite để ứng dụng không bị Crash khi chưa kịp cài biến môi trường
            # CHÚ Ý: Production nên dùng Postgres để chịu tải 100+ users
            print("[WARNING] Thieu cau hinh Postgres. Dang su dung SQLite du phong...")
            basedir = os.path.abspath(os.path.dirname(__file__))
            database_url = f"sqlite:///{os.path.join(basedir, 'instance', 'checkin_railway.db')}"
            # Đảm bảo thư mục instance tồn tại
            os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Connection pool cho 100+ users
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_pre_ping': True
    }
    
    # Initialize Extensions
    db.init_app(app)
    
    # Auto-migration: Thêm cột pin nếu chưa có cho Railway Postgres
    with app.app_context():
        try:
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS pin VARCHAR(10)"))
            db.session.execute(text("ALTER TABLE checkin_logs ADD COLUMN IF NOT EXISTS image_data TEXT"))
            db.session.execute(text("ALTER TABLE checkin_logs ADD COLUMN IF NOT EXISTS name VARCHAR(100)"))
            db.session.commit()
        except Exception as e:
            print(f"[DATABASE] Auto-migration error (co the vi SQLite hoac da co cot): {e}")
            db.session.rollback()

    # Register routes
    register_routes(app)
    
    return app


# Biến toàn cục để theo dõi trạng thái từ xa
last_heartbeat_time = None
last_camera_ip = "192.168.100.99" # Mặc định hoặc lấy từ env

def register_routes(app):
    """Register all application routes"""
    
    @app.route('/')
    def index():
        """Dashboard - show recent check-ins"""
        return render_template('index.html')

    @app.route('/tos')
    def tos():
        """Endpoint hiển thị Điều khoản sử dụng và Chính sách bảo mật"""
        return render_template('tos.html')

    
    @app.route('/api/logs')
    def api_logs():
        """Get recent check-in logs as JSON"""
        logs = Log.query.order_by(Log.timestamp.desc()).limit(50).all()
        result = []
        for log in logs:
            user_name = "Stranger"
            if log.user:
                user_name = log.user.name
            result.append({
                "id": log.id,
                "name": user_name,
                "face_id": log.face_id,
                "time": log.checkin_time_str or log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "image": log.image_path,
                "image_data": log.image_data,
                "zalo_notified": log.zalo_notified
            })
        return jsonify(result)
    
    @app.route('/api/logs/today')
    def api_logs_today():
        """Get today's check-in logs. Support filtering by zalo_id."""
        from datetime import datetime, timedelta
        from flask import request
        
        zalo_id_filter = request.args.get('zalo_id')
        print(f"[DEBUG] api_logs_today filter by zalo_id: '{zalo_id_filter}'")
        
        # Tinh toan thoi gian bat dau ngay hom nay theo gio Viet Nam (UTC+7)
        # Railway server thuong chay gio UTC
        now_utc = datetime.utcnow()
        vn_now = now_utc + timedelta(hours=7)
        vn_today_start = vn_now.replace(hour=0, minute=0, second=0, microsecond=0)
        # Chuyen nguoc lai UTC de query database
        utc_today_start = vn_today_start - timedelta(hours=7)
        
        # Mac dinh neu goi tu Mini App (co zalo_id) ma zalo_id rong -> Tra ve list trong de bao mat
        if zalo_id_filter == "":
            return jsonify([])

        query = Log.query.filter(Log.timestamp >= utc_today_start)
        
        if zalo_id_filter:
            # Tim tat ca cac record User lien quan den Zalo ID nay
            linked_users = User.query.filter_by(zalo_user_id=zalo_id_filter).all()
            if not linked_users:
                print(f"[DEBUG] No users linked to Zalo ID: {zalo_id_filter}")
                return jsonify([])
                
            user_ids = [u.id for u in linked_users]
            user_names = [u.name for u in linked_users] # Day la danh sach ten chinh thuc tu DB
            
            print(f"[DEBUG] api_logs_today - Linked User IDs: {user_ids}, Names: {user_names}")
            
            # Tim theo ID hoac theo ten (case-insensitive bang cach ilike tat ca names)
            from sqlalchemy import or_
            name_filters = [Log.name.ilike(f"%{name}%") for name in user_names]
            query = query.filter(or_(Log.user_id.in_(user_ids), *name_filters))
            
        logs = query.order_by(Log.timestamp.asc()).all() 
# Lay tu som den muon de tinh logic
        
        # Logic phan loai: Di muon / Vao lam / Check-out
        # Luu tru trang thai theo face_id/name de xu ly nhieu nguoi neu can (mac du o day da filter theo zalo_id roi)
        processed_status = {} # {user_name: has_first_checkin}
        
        result = []
        for log in logs:
            vn_time = log.timestamp + timedelta(hours=7)
            user_name = log.name or "Stranger"
            if log.user: user_name = log.user.name
            
            status_label = ""
            if user_name not in processed_status:
                # Day la ban ghi dau tien trong ngay cua ho
                # Quy dinh gio vao lam: 08:30
                if vn_time.hour > 8 or (vn_time.hour == 8 and vn_time.minute > 30):
                    status_label = "Đi muộn"
                else:
                    status_label = "Vào làm"
                processed_status[user_name] = True
            else:
                status_label = "Check-out"

            result.append({
                "id": log.id,
                "name": user_name,
                "face_id": log.face_id,
                "time": vn_time.strftime("%H:%M:%S"),
                "has_image": bool(log.image_data or log.image_path),
                "zalo_notified": log.zalo_notified,
                "status": status_label
            })
            
        # Dao nguoc lai de hien cai moi nhat len dau
        result.reverse()
        return jsonify(result)

    @app.route('/api/debug/recent_logs')
    def api_debug_recent_logs():
        """Debug endpoint to see last 10 logs in the entire DB"""
        from datetime import datetime, timedelta
        logs = Log.query.order_by(Log.timestamp.desc()).limit(20).all()
        result = []
        for log in logs:
            vn_time = log.timestamp + timedelta(hours=7)
            result.append({
                "id": log.id,
                "name_log": log.name,
                "user_id": log.user_id,
                "time_vn": vn_time.strftime("%H:%M:%S"),
                "raw_face_id": log.face_id
            })
        return jsonify({
            "server_time_utc": datetime.utcnow().strftime("%H:%M:%S"),
            "recent_logs": result
        })

    @app.route('/api/logs/<int:log_id>/image')
    def api_log_image(log_id):
        """Serve direct image from base64 DB data or file path"""
        from flask import send_file
        import base64
        from io import BytesIO
        import os
        
        log = Log.query.get(log_id)
        if not log:
            return "Not found", 404
            
        if log.image_data:
            try:
                # Remove data:image/jpeg;base64, if exists
                if "," in log.image_data:
                    _, encoded = log.image_data.split(",", 1)
                else:
                    encoded = log.image_data
                image_bytes = base64.b64decode(encoded)
                return send_file(BytesIO(image_bytes), mimetype='image/jpeg', max_age=86400) # Cache 1 ngay
            except Exception as e:
                print(f"[!] Loi decode anh base64 cua log_id {log_id}: {e}")
                
        if log.image_path and os.path.exists(log.image_path):
            return send_file(log.image_path, max_age=86400)
            
        return "No image", 404
    
    @app.route('/api/users')
    def api_users():
        """Get all registered users"""
        users = User.query.all()
        result = []
        for user in users:
            result.append({
                "id": user.id,
                "name": user.name,
                "face_id": user.face_id,
                "zalo_id": user.zalo_user_id,
                "pin": user.pin
            })
        return jsonify(result)

    @app.route('/api/user/unlink', methods=['POST'])
    def api_user_unlink():
        """Unlink Zalo ID from ALL users that have it"""
        from flask import request
        data = request.json
        zalo_id = data.get('zalo_id')
        if not zalo_id:
            return jsonify({"status": "error", "error": "Missing zalo_id"}), 400
            
        try:
            # Xoa zalo_id khoi TOAN BO cac record co ID nay (phong do trung lap)
            affected = User.query.filter_by(zalo_user_id=zalo_id).update({User.zalo_user_id: None})
            db.session.commit()
            print(f"[DEBUG] Unlinked Zalo ID {zalo_id}, records affected: {affected}")
            return jsonify({"status": "success", "affected": affected})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "error": str(e)}), 500

    @app.route('/api/user/stats')
    def api_user_stats():
        """Get check-in stats for all user instances linked to this Zalo ID"""
        from flask import request
        zalo_id = request.args.get('zalo_id')
        if not zalo_id:
            return jsonify({"error": "Missing zalo_id"}), 400
            
        # Lay tat ca User IDs lien ket voi Zalo ID nay
        users_linked = User.query.filter_by(zalo_user_id=zalo_id).all()
        if not users_linked:
            return jsonify({
                "totalDays": 26,
                "presentDays": 0,
                "lateDays": 0,
                "onTimeRate": 100
            })
            
        user_ids = [u.id for u in users_linked]
        from datetime import datetime, timedelta
        now = datetime.utcnow() + timedelta(hours=7)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=7)
        
        logs = Log.query.filter(Log.user_id.in_(user_ids), Log.timestamp >= start_of_month).all()
        
        # Lay cac ngay duy nhat
        days_present = set()
        late_count = 0
        for log in logs:
            # Chuyen gio log sang VN de tinh ngay
            vn_time = log.timestamp + timedelta(hours=7)
            day_str = vn_time.strftime("%Y-%m-%d")
            days_present.add(day_str)
            
            # Gia su di tre la sau 08:30
            if vn_time.hour > 8 or (vn_time.hour == 8 and vn_time.minute > 30):
                # Neu day la log dau tien trong ngay cua ho thi moi tinh la tre?
                # Don gian hoa: neu co log nao sau 8:30 thi co the la tre (hoac lam nua buoi)
                # O day minh chi mo phong logic
                pass

        total_days_in_month = 26 # Co dinh hoac tinh theo thang
        present_count = len(days_present)
        
        return jsonify({
            "totalDays": total_days_in_month,
            "presentDays": present_count,
            "lateDays": 0, # Tam thoi de 0 cho den khi co logic ca lam viec
            "onTimeRate": 100 if present_count == 0 else 95 
        })

    @app.route('/api/user/update-zalo-id', methods=['POST', 'OPTIONS'])
    def update_zalo_id():
        """API de Mini App gui Zalo ID ve link voi nhan vien"""
        from flask import request
        if request.method == 'OPTIONS':
            return jsonify({"status": "ok"}), 200
            
        data = request.get_json(silent=True) or {}
        zalo_id = data.get('zalo_id')
        name = data.get('name')
        pin = data.get('pin')
        
        if not zalo_id or not name or not pin:
            return jsonify({"error": "Thieu thong tin: Ten, ID hoac PIN"}), 400
            
        # Tim user theo ten va PIN
        user = User.query.filter(User.name.ilike(f"%{name}%"), User.pin == str(pin)).first()
        if user:
            user.zalo_user_id = zalo_id
            db.session.commit()
            return jsonify({"status": "success", "message": f"Da lien ket Zalo cho {user.name}"})
        else:
            return jsonify({"error": "Ten hoac ma PIN khong chinh xac"}), 404

    @app.route('/api/user/add', methods=['POST'])
    def api_add_user():
        """API de quan tri vien them hoac cap nhat ten nhan vien qua Face ID.
        Yeu cau Admin PIN de bao mat."""
        from flask import request
        data = request.get_json(silent=True) or {}
        face_id = data.get('face_id')
        name = data.get('name')
        pin = data.get('pin') # PIN cua nhan vien
        admin_pin = data.get('admin_pin') # PIN cua admin de xac thuc quyen
        
        # Kiem tra Admin PIN
        expected_admin = os.getenv('ADMIN_PIN', '1234') # Mac dinh 1234 neu chua setup
        if str(admin_pin) != str(expected_admin):
            return jsonify({"error": "Sai ma PIN quan tri"}), 403

        if not face_id or not name:
            return jsonify({"error": "Thieu thong tin Face ID hoac Ten"}), 400
            
        user = User.query.filter_by(face_id=str(face_id)).first()
        if user:
            user.name = name
            if pin: user.pin = str(pin)
            db.session.commit()
            return jsonify({"status": "success", "message": f"Da cap nhat thong tin cho Face ID {face_id}"})
        else:
            new_user = User(face_id=str(face_id), name=name, pin=str(pin) if pin else "0000")
            db.session.add(new_user)
            db.session.commit()
            return jsonify({"status": "success", "message": f"Da them nhan vien moi: {name}"})
    
    @app.route('/api/status')
    def api_status():
        """Get server and polling status based on last heartbeat"""
        from datetime import datetime
        global last_heartbeat_time, last_camera_ip
        
        is_active = False
        if last_heartbeat_time:
            diff = (datetime.now() - last_heartbeat_time).total_seconds()
            if diff < 120: # Coi như kết nối nếu có tín hiệu trong 2 phút
                is_active = True
                
        return jsonify({
            "server": "running",
            "polling": is_active,
            "device_ip": os.getenv('DEVICE_IP', last_camera_ip),
            "last_seen": last_heartbeat_time.strftime("%H:%M:%S") if last_heartbeat_time else "Never"
        })

    @app.route('/api/internal/heartbeat', methods=['POST'])
    def internal_heartbeat():
        """Nhan tin hieu song tu poller_agent.py"""
        from flask import request
        from datetime import datetime
        global last_heartbeat_time, last_camera_ip
        
        # Kiem tra API Key
        api_key = request.headers.get('X-Poller-Key', '').strip()
        expected = os.getenv('POLLER_API_KEY', '').strip()
        if not expected or api_key != expected:
            return jsonify({"error": "Unauthorized"}), 401
            
        data = request.get_json(silent=True) or {}
        if data.get('device_ip'):
            last_camera_ip = data.get('device_ip')

        last_heartbeat_time = datetime.now()
        return jsonify({"status": "ok", "time": last_heartbeat_time.strftime("%H:%M:%S")})

    @app.route('/api/internal/checkin', methods=['POST'])
    def internal_checkin():
        """Nhan du lieu check-in tu poller_agent.py chay o may local.
        Bao mat bang POLLER_API_KEY trong .env."""
        from flask import request
        from datetime import datetime
        import base64, re
        global last_heartbeat_time
        
        # Cập nhật heartbeat mỗi khi có data gửi lên
        last_heartbeat_time = datetime.now()

        # Kiem tra API Key
        api_key = request.headers.get('X-Poller-Key', '').strip()
        expected = os.getenv('POLLER_API_KEY', '').strip()
        if not expected or api_key != expected:
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json(silent=True) or {}
        face_id_raw = data.get('face_id')
        snap_time   = data.get('snap_time')
        name        = data.get('name', 'Stranger')
        person_id   = data.get('person_id')
        image_b64   = data.get('image_b64')

        if not face_id_raw or not snap_time:
            return jsonify({"error": "Thieu face_id hoac snap_time"}), 400

        # Chong trung lap
        existing = Log.query.filter_by(face_id=str(face_id_raw), checkin_time_str=snap_time).first()
        if existing:
            # Neu da ton tai nhung chua co image_data -> Cap nhat bo sung
            if not existing.image_data and image_b64:
                try:
                    existing.image_data = image_b64 if image_b64.startswith('data:') else f"data:image/jpeg;base64,{image_b64}"
                    db.session.commit()
                    return jsonify({"status": "ok", "message": "updated_image"})
                except:
                    db.session.rollback()
            return jsonify({"status": "ok", "message": "duplicate"})

        # Luu anh neu co
        image_path = None
        image_data_stored = None
        if image_b64:
            # Luu vao database (dam bao prefix hop le)
            if not image_b64.startswith('data:'):
                image_data_stored = f"data:image/jpeg;base64,{image_b64}"
            else:
                image_data_stored = image_b64

            # Van co gang luu vao file de du phong local
            try:
                img_data = base64.b64decode(image_b64.split(',')[-1])
                import os as _os
                save_dir = 'static/captures'
                _os.makedirs(save_dir, exist_ok=True)
                filename = f"capture_{snap_time.replace(' ','_').replace(':','')}_{face_id_raw}.jpg"
                filepath = _os.path.join(save_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(img_data)
                image_path = filepath
            except Exception as e:
                print(f"[!] Luu file anh that bai (co the do Cloud filesystem): {e}")

        # Tim hoac tao user
        user = None
        if person_id:
            # Uu tien tim bang face_id (va phai la instance da co zalo_id neu co the)
            user = User.query.filter_by(face_id=str(person_id)).order_by(User.zalo_user_id.desc()).first()
            if not user:
                user = User(face_id=str(person_id), name=name)
                db.session.add(user)
                db.session.flush()
        elif name and name != 'Stranger':
            # Uu tien tim instance co zalo_id de logs duoc gan vao dung tai khoan dang dung app
            user = User.query.filter(User.name.ilike(f"%{name}%")).order_by(User.zalo_user_id.desc()).first()
            if not user:
                user = User(face_id=str(face_id_raw), name=name)
                db.session.add(user)
                db.session.flush()

        # Tao log
        new_log = Log(
            user_id=user.id if user else None,
            face_id=str(face_id_raw),
            name=name, # Luu ten truc tiep tu Device cung cap
            checkin_time_str=snap_time,
            image_path=image_path,
            image_data=image_data_stored,
            event_type='checkin',
            zalo_notified=False
        )
        db.session.add(new_log)
        db.session.commit()
        print(f"[DEBUG] Saved Log: ID={new_log.id}, Name='{name}', UserID={new_log.user_id}")

        # Gui Zalo
        from datetime import datetime as dt, timedelta as td
        from services.zalo_service import zalo_service
        
        if user and user.zalo_user_id:
            # Logic: Toi da 2 thong bao/ngay (1 vao, 1 ra)
            # Lay gio VN hien tai de so sanh
            vn_now = dt.utcnow() + td(hours=7)
            vn_today_start = vn_now.replace(hour=0, minute=0, second=0, microsecond=0)
            utc_today_start = vn_today_start - td(hours=7)
            
            # Dem so thong bao da gui hom nay cho user nay
            notified_logs_today = Log.query.filter(
                Log.user_id == user.id,
                Log.zalo_notified == True,
                Log.timestamp >= utc_today_start
            ).count()
            
            # Cac moc thoi gian (mac dinh, sau nay co the cau hinh qua env)
            checkin_deadline = os.getenv('CHECKIN_DEADLINE', '08:30')
            checkout_start = os.getenv('CHECKOUT_START_TIME', '16:30') # Sau gio nay moi tinh la thong bao "Ve"
            checkout_deadline = os.getenv('CHECKOUT_DEADLINE', '17:30') # Truoc gio nay la ve som
            
            current_time_str = vn_now.strftime("%H:%M")
            should_notify = False
            noti_title = ""
            noti_content = ""
            
            if notified_logs_today == 0:
                # THONG BAO 1: VAO LAM
                is_late = current_time_str > checkin_deadline
                icon = "❌" if is_late else "✅"
                stt_text = "đi muộn" if is_late else "đúng giờ"
                noti_title = f"{icon} Điểm danh {stt_text}"
                noti_content = f"Chào {user.name}, bạn đã vào làm {stt_text} lúc {current_time_str}."
                should_notify = True
                
            elif notified_logs_today == 1:
                # THONG BAO 2: RA VE (Chi gui neu quet sau checkout_start)
                if current_time_str >= checkout_start:
                    is_early = current_time_str < checkout_deadline
                    icon = "⚠️" if is_early else "✅"
                    stt_text = "về sớm" if is_early else "đã về"
                    noti_title = f"{icon} Xác nhận {stt_text}"
                    noti_content = f"Chào {user.name}, bạn đã {stt_text} lúc {current_time_str}."
                    should_notify = True
            
            if should_notify:
                ok = zalo_service.send_custom_notification(user.zalo_user_id, noti_title, noti_content)
                if ok:
                    new_log.zalo_notified = True
                    db.session.commit()
        elif not user or name == 'Stranger':
            # Nguoi la ngan chan spam bang batching 3 phut (180 giay) tu DB de dong bo giua cac worker
            three_mins_ago = dt.utcnow() - td(minutes=3)
            recent_alert = Log.query.filter(
                (Log.user_id == None) | (Log.name == 'Stranger'),
                Log.zalo_notified == True,
                Log.timestamp >= three_mins_ago
            ).first()
            
            if not recent_alert: # Da qua 3 phut ke tu lan canh bao nguoi la truoc hoac chua bao gio canh bao
                # Dem so nguoi la trong 3 phut qua
                last_alert_time = dt.utcnow() - td(hours=24) # Default 24h neu chua tung alert
                last_alert_log = Log.query.filter(
                    (Log.user_id == None) | (Log.name == 'Stranger'),
                    Log.zalo_notified == True
                ).order_by(Log.timestamp.desc()).first()
                
                if last_alert_log:
                    last_alert_time = last_alert_log.timestamp
                    
                strangers_count = Log.query.filter(
                    (Log.user_id == None) | (Log.name == 'Stranger'),
                    Log.timestamp > last_alert_time
                ).count()
                
                strangers_count = max(1, strangers_count)
                time_range_str = new_log.timestamp.strftime("%H:%M")
                
                ok = zalo_service.send_stranger_alert_miniapp(strangers_count, time_range_str)
                if ok:
                    new_log.zalo_notified = True
                    db.session.commit()

        print(f"[OK] CHECKIN (via agent): {name} at {snap_time}")
        return jsonify({"status": "ok"})

    
    @app.route('/api/poll/start')
    def api_start_polling():
        """Start device polling"""
        device_poller.start_polling(app, db, User, Log)
        return jsonify({"status": "started"})
    
    @app.route('/api/poll/stop')
    def api_stop_polling():
        """Stop device polling"""
        device_poller.stop_polling()
        return jsonify({"status": "stopped"})

    @app.route('/zalo_verifierEEAVUVZg3baJs8PprkumJo_yg6h3YdmnC3Kv.html')
    def zalo_verify():
        """Endpoint phục vụ xác thực tên miền của Zalo"""
        return "zalo-platform-site-verification=EEAVUVZg3baJs8PprkumJo_yg6h3YdmnC3Kv"



# ---- Entry point cho Gunicorn (Railway) ----
# Gunicorn goi: gunicorn app:application
application = create_app()

# Khoi tao bang DB (Railway tu dong chay khi deploy)
with application.app_context():
    from database.database import db as _db
    _db.create_all()
    print("[OK] Database tables checked/created.")


def start_server():
    """Start server voi polling (chi dung de phat trien local)."""
    app = application
    print("\n" + "="*50)
    print("TVT Check-in Server (LOCAL MODE)")
    print("="*50)
    print("[*] Testing device connection...")
    if device_poller.test_connection():
        print("[OK] Device connection successful!")
        device_poller.start_polling(app, _db, None, None)
    else:
        print("[!] Device connection failed.")
    print("[*] Open http://localhost:5000 in your browser\n")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)


if __name__ == '__main__':
    start_server()
