import os
import requests
from dotenv import set_key, load_dotenv

class ZaloService:
    def __init__(self):
        load_dotenv()
        self.access_token = os.getenv('ZALO_ACCESS_TOKEN', '')
        self.refresh_token = os.getenv('ZALO_REFRESH_TOKEN', '')
        self.miniapp_token = os.getenv('ZALO_MINIAPP_TOKEN', '')
        self.oa_id = os.getenv('ZALO_OA_ID', '')
        self.app_id = os.getenv('ZALO_APP_ID', '')
        self.app_secret = os.getenv('ZALO_APP_SECRET', '')
        self.miniapp_id = os.getenv('ZALO_MINIAPP_ID', '')
        self.miniapp_api_key = os.getenv('ZALO_MINIAPP_API_KEY', '')
        self.admin_zalo_id = os.getenv('ADMIN_ZALO_ID', '')
        self.env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        
    def refresh_zalo_token(self):
        """Làm mới Access Token thông qua Refresh Token (Zalo API V4)"""
        if not self.app_id or not self.app_secret or not self.refresh_token:
            print("[ZALO] Thiếu cấu hình APP ID, SECRET hoặc REFRESH TOKEN để làm mới token.")
            return False
            
        print("[ZALO] Đang tiến hành làm mới Access Token...")
        url = "https://oauth.zaloapp.com/v4/oa/access_token"
        headers = {
            "secret_key": self.app_secret,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "app_id": self.app_id,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            result = response.json()
            
            if "access_token" in result and "refresh_token" in result:
                self.access_token = result["access_token"]
                self.refresh_token = result["refresh_token"]
                
                # Cập nhật ngược lại vào file .env
                set_key(self.env_path, 'ZALO_ACCESS_TOKEN', self.access_token)
                set_key(self.env_path, 'ZALO_REFRESH_TOKEN', self.refresh_token)
                print("[ZALO] Làm mới Token thành công. Đã lưu lại cấu hình .env mới.")
                return True
            else:
                print(f"[ZALO] Lỗi làm mới Token: {result}")
                return False
        except Exception as e:
            print(f"[ZALO] Lỗi kết nối khi làm mới Token: {e}")
            return False

    def send_checkin_notification(self, zalo_user_id, user_name, checkin_time_str, _retry=False):
        if not zalo_user_id or not self.access_token:
            print("[ZALO] Bỏ qua gửi Zalo do thiếu ID người dùng hoặc Access Token chưa được cấu hình.")
            return False
            
        url = "https://openapi.zalo.me/v3.0/oa/message/cs"
        headers = {
            "access_token": self.access_token,
            "X-MiniApp-Token": self.miniapp_token,
            "Content-Type": "application/json"
        }
        
        # Zalo ZBS Consultation Message Payload
        payload = {
            "recipient": {
                "user_id": zalo_user_id
            },
            "message": {
                "text": f"Xin chào {user_name}, bạn vừa điểm danh thành công trên hệ thống lúc {checkin_time_str}."
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            result = response.json()
            error_code = result.get("error")
            
            if error_code == 0:
                print(f"[ZALO] Đã gửi thông báo thành công cho nhân viên {user_name} (ZaloID: {zalo_user_id})")
                return True
            elif error_code in [-124, -216] and not _retry: # -124: Token expired/invalid, -216: OA expired/invalid
                print(f"[ZALO] Access Token có dấu hiệu hết hạn (Code: {error_code}). Bắt đầu quá trình Refresh Token...")
                if self.refresh_zalo_token():
                    # Thử lại 1 lần duy nhất với token mới
                    return self.send_checkin_notification(zalo_user_id, user_name, checkin_time_str, _retry=True)
                return False
            else:
                print(f"[ZALO] Gọi API Zalo thất bại: {result.get('message', '')} (Code: {error_code})")
                return False
        except Exception as e:
            print(f"[ZALO] Lỗi khi kết nối đến API Zalo: {e}")
            return False
    def send_miniapp_notification(self, zalo_user_id, user_name, checkin_time_str):
        """Gui Push Notification qua Zalo Mini App OpenAPI (nay len man hinh khoa)"""
        if not self.miniapp_api_key:
            print("[MINIAPP] Bo qua Push Noti: Chua cau hinh ZALO_MINIAPP_API_KEY trong .env")
            return False
        
        if not zalo_user_id:
            print("[MINIAPP] Bo qua Push Noti: Thieu Zalo User ID")
            return False
        
        url = "https://openapi.mini.zalo.me/notification/template"
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.miniapp_api_key,
            "X-User-Id": str(zalo_user_id),
            "X-MiniApp-Id": self.miniapp_id
        }
        
        payload = {
            "templateId": "0",
            "templateData": {
                "title": f"Diem danh thanh cong",
                "content": f"{user_name} da check-in luc {checkin_time_str}",
                "actionTitle": "Xem lich su",
                "actionUrl": "/history"
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            result = response.json()
            
            if result.get("error") == 0 or response.status_code == 200:
                print(f"[MINIAPP] Push Noti thanh cong cho {user_name}")
                return True
            else:
                print(f"[MINIAPP] Push Noti that bai: {result}")
                return False
        except Exception as e:
            print(f"[MINIAPP] Loi ket noi khi gui Push Noti: {e}")
            return False

    def send_stranger_alert_miniapp(self, stranger_count, time_range_str):
        """Gui Push Notification canh bao Nguoi La danh rieng cho Admin qua Mini App"""
        if not self.admin_zalo_id:
            print("[MINIAPP] Bo qua Stranger Alert: Chua cau hinh ADMIN_ZALO_ID trong .env")
            return False
            
        if not self.miniapp_api_key:
            print("[MINIAPP] Bo qua Stranger Alert: Chua cau hinh ZALO_MINIAPP_API_KEY")
            return False

        url = "https://openapi.mini.zalo.me/notification/template"
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.miniapp_api_key,
            "X-User-Id": str(self.admin_zalo_id),
            "X-MiniApp-Id": self.miniapp_id
        }
        
        payload = {
            "templateId": "0",
            "templateData": {
                "title": f"⚠️ CANH BAO BAO MAT",
                "content": f"Phat hien {stranger_count} nguoi la xuat hien luc {time_range_str}",
                "actionTitle": "Mo Camera & Lich su",
                "actionUrl": "/history"
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            result = response.json()
            
            if result.get("error") == 0 or response.status_code == 200:
                print(f"[MINIAPP] Đã gui Stranger Alert ({stranger_count} nguoi) den Admin")
                return True
            else:
                print(f"[MINIAPP] Stranger Alert thất bại: {result}")
                return False
        except Exception as e:
            print(f"[MINIAPP] Loi ket noi khi gui Stranger Alert: {e}")
            return False

    def send_all_notifications(self, zalo_user_id, user_name, checkin_time_str):
        """Phuong an 3: Gui ca OA Message + Mini App Push Notification song song"""
        oa_ok = False
        miniapp_ok = False
        
        # Kenh 1: OA Message (tin nhan vao hop Zalo)
        try:
            oa_ok = self.send_checkin_notification(zalo_user_id, user_name, checkin_time_str)
        except Exception as e:
            print(f"[ZALO] Loi OA Message: {e}")
        
        # Kenh 2: Mini App Push Notification (nay len man hinh khoa)
        try:
            miniapp_ok = self.send_miniapp_notification(zalo_user_id, user_name, checkin_time_str)
        except Exception as e:
            print(f"[MINIAPP] Loi Push Noti: {e}")
        
        if oa_ok or miniapp_ok:
            channels = []
            if oa_ok:
                channels.append("OA")
            if miniapp_ok:
                channels.append("MiniApp")
            print(f"[THONG BAO] Da gui thanh cong qua: {' + '.join(channels)} cho {user_name}")
            return True
        else:
            print(f"[THONG BAO] Ca 2 kenh deu that bai cho {user_name}")
            return False

zalo_service = ZaloService()
