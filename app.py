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
    
    # Register routes
    register_routes(app)
    
    return app


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
                "zalo_notified": log.zalo_notified
            })
        return jsonify(result)
    
    @app.route('/api/logs/today')
    def api_logs_today():
        """Get today's check-in logs"""
        from datetime import datetime, timedelta
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        logs = Log.query.filter(Log.timestamp >= today).order_by(Log.timestamp.desc()).all()
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
                "zalo_id": user.zalo_user_id
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
        name = data.get('name') # Hoac face_id
        
        if not zalo_id or not name:
            return jsonify({"error": "Missing data"}), 400
            
        # Tim user theo ten (chu thich: sau nay nen dung Staff ID/Face ID cho doc nhat)
        user = User.query.filter(User.name.ilike(f"%{name}%")).first()
        if user:
            user.zalo_user_id = zalo_id
            db.session.commit()
            return jsonify({"status": "success", "message": f"Da lien ket Zalo cho {user.name}"})
        else:
            return jsonify({"error": "User not found"}), 404

    @app.route('/api/user/add', methods=['POST'])
    def api_add_user():
        """API de quan tri vien them hoac cap nhat ten nhan vien qua Face ID"""
        from flask import request
        data = request.get_json(silent=True) or {}
        face_id = data.get('face_id')
        name = data.get('name')
        
        if not face_id or not name:
            return jsonify({"error": "Thieu thong tin Face ID hoac Ten"}), 400
            
        user = User.query.filter_by(face_id=str(face_id)).first()
        if user:
            user.name = name
            db.session.commit()
            return jsonify({"status": "success", "message": f"Da cap nhat ten cho Face ID {face_id}"})
        else:
            new_user = User(face_id=str(face_id), name=name)
            db.session.add(new_user)
            db.session.commit()
            return jsonify({"status": "success", "message": f"Da them nhan vien moi: {name}"})
    
    @app.route('/api/status')
    def api_status():
        """Get server and polling status"""
        import device_poller as dp
        return jsonify({
            "server": "running",
            "polling": dp.is_polling,
            "device_ip": dp.DEVICE_IP,
            "poll_interval": dp.POLL_INTERVAL
        })

    @app.route('/api/internal/checkin', methods=['POST'])
    def internal_checkin():
        """Nhan du lieu check-in tu poller_agent.py chay o may local.
        Bao mat bang POLLER_API_KEY trong .env."""
        from flask import request
        import base64, re

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
            return jsonify({"status": "ok", "message": "duplicate"})

        # Luu anh neu co
        image_path = None
        if image_b64:
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
                print(f"[!] Luu anh that bai: {e}")

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
