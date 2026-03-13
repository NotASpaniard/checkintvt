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
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        query = Log.query.filter(Log.timestamp >= today)
        
        if zalo_id_filter:
            # Chi lay logs cua user co zalo_id nay
            query = query.join(User).filter(User.zalo_user_id == zalo_id_filter)
            
        logs = query.order_by(Log.timestamp.desc()).all()
        result = []
        for log in logs:
            user_name = "Stranger"
            if log.user:
                user_name = log.user.name
            elif log.face_id:
                # Tim ten neu chua duoc gan user_id
                u = User.query.filter_by(face_id=str(log.face_id)).first()
                if u: user_name = u.name
            result.append({
                "id": log.id,
                "name": user_name,
                "face_id": log.face_id,
                "time": log.checkin_time_str or log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "image": log.image_path,
                "image_data": log.image_data, # New Base64 support
                "zalo_notified": log.zalo_notified
            })
        return jsonify(result)
    
    @app.route('/api/users')
    def api_users():
        """Get all registered users"""
        users = User.query.all()
        result = []
        for user in users:
            result.append({
                "id": user.id,
                "face_id": user.face_id,
                "name": user.name,
                "department": user.department,
                "zalo_id": user.zalo_user_id,
                "pin": user.pin or "Chua dat"
            })
        return jsonify(result)

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
            user = User.query.filter_by(face_id=str(person_id)).first()
            if not user:
                user = User(face_id=str(person_id), name=name)
                db.session.add(user)
                db.session.flush()
        elif name and name != 'Stranger':
            user = User.query.filter(User.name.ilike(f"%{name}%")).first()
            if not user:
                user = User(face_id=str(face_id_raw), name=name)
                db.session.add(user)
                db.session.flush()

        # Tao log
        new_log = Log(
            user_id=user.id if user else None,
            face_id=str(face_id_raw),
            checkin_time_str=snap_time,
            image_path=image_path,
            image_data=image_data_stored,
            event_type='checkin',
            zalo_notified=False
        )
        db.session.add(new_log)
        db.session.commit()

        # Gui Zalo
        if user and user.zalo_user_id:
            from datetime import datetime as dt, timedelta as td
            from services.zalo_service import zalo_service
            five_ago = dt.utcnow() - td(minutes=5)
            recent = Log.query.filter(
                Log.user_id == user.id,
                Log.zalo_notified == True,
                Log.timestamp >= five_ago
            ).first()
            if not recent:
                ok = zalo_service.send_all_notifications(user.zalo_user_id, user.name, snap_time)
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
