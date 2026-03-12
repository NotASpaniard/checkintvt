from services.zalo_service import zalo_service
import sys

def test_zalo(zalo_user_id):
    print("=" * 50)
    print("KIỂM THỬ GỬI TIN NHẮN ZALO QUA API ZBS V4")
    print("=" * 50)
    
    print(f"1. Kiểm tra cấu hình .env...")
    print(f"   - Oa ID: {zalo_service.oa_id}")
    print(f"   - App ID: {zalo_service.app_id}")
    print(f"   - Có Access_Token: {'CÓ' if zalo_service.access_token else 'KHÔNG'}")
    print(f"   - Có Refresh_Token: {'CÓ' if zalo_service.refresh_token else 'KHÔNG'}")
    
    if not zalo_service.access_token and not zalo_service.refresh_token:
        print("\n[LỖI] Anh chưa có bất kỳ Token nào trong file .env cả. Vui lòng lấy Token trên API Explorer dán vào!")
        return
        
    print(f"\n2. Bắt đầu gửi thử tin nhắn cho Zalo ID: {zalo_user_id}")
    success = zalo_service.send_checkin_notification(
        zalo_user_id=zalo_user_id,
        user_name="Nguyễn Văn A (Test)",
        checkin_time_str="14:50:00 11/03/2026"
    )
    
    if success:
        print("\n[THÀNH CÔNG] 🎉 Tin nhắn đã được gửi! Anh kiểm tra điện thoại xem có Ting Ting không nhé!")
    else:
        print("\n[THẤT BẠI] ❌ Có lỗi xảy ra. Hãy kiểm tra lại Access Token hoặc xem Zalo_User_ID có đúng không.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Sử dụng: python test_zalo.py <ZALO_USER_ID_CỦA_ANH>")
        sys.exit(1)
        
    test_zalo(sys.argv[1])
