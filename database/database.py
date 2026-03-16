from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    face_id = db.Column(db.String(50), unique=True, nullable=True) # ID from Device
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=True)
    zalo_user_id = db.Column(db.String(100), nullable=True) # ID người dùng Zalo
    phone_number = db.Column(db.String(20), nullable=True) # Số điện thoại dự phòng
    pin = db.Column(db.String(10), nullable=True) # PIN bảo mật cho liên kết và admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.name}>'

class Log(db.Model):
    __tablename__ = 'checkin_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Nullable for strangers
    face_id = db.Column(db.String(50), nullable=True) # ID received from event
    name = db.Column(db.String(100), nullable=True) # Tên tại thời điểm điểm danh
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    checkin_time_str = db.Column(db.String(50), nullable=True) # Time string from device
    image_path = db.Column(db.String(200), nullable=True)
    image_data = db.Column(db.Text, nullable=True) # Base64 image data for Cloud persistence
    zalo_notified = db.Column(db.Boolean, default=False) # Đã bắn notification Zalo chưa
    event_type = db.Column(db.String(50), default='checkin')
    
    user = db.relationship('User', backref=db.backref('logs', lazy=True))

    def __repr__(self):
        return f'<Log {self.checkin_time_str} - {self.face_id}>'
