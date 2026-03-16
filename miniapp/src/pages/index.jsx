import React, { useState, useEffect } from "react";
import { getUserInfo, login, requestSendNotification } from "zmp-sdk";
import { Box, Button, Icon, Page, Text, useSnackbar, Modal, Input } from "zmp-ui";

// Dung link Ngrok de call API Backend tu ben ngoai
const API_BASE = import.meta.env.VITE_API_BASE || "https://checkintvt-production.up.railway.app";

function HomePage() {
  const [user, setUser] = useState(null);
  const [clock, setClock] = useState("");
  const [date, setDate] = useState("");
  const [notiGranted, setNotiGranted] = useState(false);
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [staffName, setStaffName] = useState("");
  const [staffPin, setStaffPin] = useState("");
  const [isLinked, setIsLinked] = useState(false);

  const { openSnackbar } = useSnackbar();

  // Khoi phuc trang thai tu Storage khi moi vao
  useEffect(() => {
    const savedNoti = localStorage.getItem("notiGranted");
    const savedName = localStorage.getItem("staffName");

    if (savedNoti === "true") setNotiGranted(true);
    // Khong setIsLinked o day de tranh desync voi server, cho ket qua tu checkLinkingStatus
    if (savedName) setStaffName(savedName);
  }, []);

  // Dong ho so
  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setClock(`${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`);
      const days = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];
      const months = ["Thg 1", "Thg 2", "Thg 3", "Thg 4", "Thg 5", "Thg 6", "Thg 7", "Thg 8", "Thg 9", "Thg 10", "Thg 11", "Thg 12"];
      setDate(`${days[now.getDay()]}, ${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear()}`);
    };
    updateClock();
    const timer = setInterval(updateClock, 1000);
    return () => clearInterval(timer);
  }, []);

  // Lay thong tin user Zalo va kiem tra trang thai lien ket
  useEffect(() => {
    const fetchUserData = () => {
      login({
        success: () => {
          getUserInfo({
            success: (data) => {
              setUser(data.userInfo);
              checkLinkingStatus(data.userInfo.id);
            },
            fail: (err) => {
              console.log("getUserInfo error:", err);
              openSnackbar({ text: "Chưa được cấp quyền lấy thông tin Zalo", type: "error" });
            },
          });
        },
        fail: (err) => {
          console.log("Login fail:", err);
        }
      });
    };
    fetchUserData();
  }, []);

  const checkLinkingStatus = async (zalo_id) => {
    try {
      const res = await fetch(`${API_BASE}/api/users`, {
        headers: { "ngrok-skip-browser-warning": "true" }
      });
      if (!res.ok) throw new Error("Server response not ok");

      const users = await res.json();
      const matched = users.find(u => u.zalo_id === zalo_id);
      if (matched) {
        setIsLinked(true);
        setStaffName(matched.name);
        localStorage.setItem("isLinked", "true");
        localStorage.setItem("staffName", matched.name);
      } else {
        setIsLinked(false);
        setStaffName("");
        localStorage.removeItem("isLinked");
        localStorage.removeItem("staffName");
        setShowLinkModal(true);
      }
    } catch (err) {
      console.error("Check link error:", err);
      // Neu loi ket noi, tam thoi giu trang thai hien tai hoac bao loi
    }
  };

  const handleLinkAccount = async () => {
    if (!user?.id) {
      openSnackbar({ text: "Lỗi: Không lấy được Zalo ID. Vui lòng cho phép ứng dụng truy cập thông tin của bạn.", type: "error" });
      return;
    }
    if (!staffName || !staffPin) {
      openSnackbar({ text: "Vui lòng nhập đầy đủ Họ tên và Mã PIN", type: "warning" });
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/user/update-zalo-id`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify({
          zalo_id: user.id,
          name: staffName,
          pin: staffPin
        })
      });
      const result = await res.json();
      if (result.status === "success") {
        setIsLinked(true);
        localStorage.setItem("isLinked", "true");
        localStorage.setItem("staffName", staffName);
        setShowLinkModal(false);
        openSnackbar({ text: "Liên kết tài khoản thành công!", type: "success" });
        // Sau khi lien ket, force check lai cho chac
        checkLinkingStatus(user.id);
      } else {
        openSnackbar({ text: result.error || "Sai tên hoặc mã PIN", type: "error" });
      }
    } catch (err) {
      openSnackbar({ text: "Lỗi kết nối server", type: "error" });
    }
  };

  const handleRequestNoti = () => {
    requestSendNotification({
      success: () => {
        setNotiGranted(true);
        localStorage.setItem("notiGranted", "true");
        openSnackbar({ text: "Đã cấp quyền thông báo!", type: "success" });
      },
      fail: (err) => openSnackbar({ text: "Lỗi cấp quyền", type: "error" }),
    });
  };

  return (
    <Page className="page-home">
      <Box className="home-header">
        <Box className="user-info">
          {user?.avatar ? <img src={user.avatar} alt="Avatar" className="user-avatar" /> :
            <Box className="user-avatar-placeholder"><Icon icon="zi-user" size={32} /></Box>
          }
          <Box>
            <Text className="greeting-text">Xin chào,</Text>
            <Text.Title className="user-name">{user?.name || "Nhân viên"}</Text.Title>
            {isLinked && <Text style={{ color: '#00ff88', fontSize: '12px' }}>✓ Đã liên kết: {staffName}</Text>}
          </Box>
        </Box>
      </Box>

      <Box className="clock-section">
        <Text className="clock-time">{clock}</Text>
        <Text className="clock-date">{date}</Text>
      </Box>

      <Box className="noti-section">
        {!notiGranted ? (
          <Button className="noti-btn" variant="primary" size="large" fullWidth onClick={handleRequestNoti} prefixIcon={<Icon icon="zi-notif" />}>
            Cấp quyền nhận thông báo
          </Button>
        ) : (
          <Box className="noti-granted">
            <Icon icon="zi-check-circle" className="noti-icon-ok" />
            <Text className="noti-granted-text">Đã bật thông báo điểm danh</Text>
          </Box>
        )}
      </Box>

      <Box className="quick-info">
        <Box className="info-card" onClick={() => !isLinked && setShowLinkModal(true)}>
          <Icon icon="zi-user-circle" size={28} className="info-icon" />
          <Text className="info-label">Tài khoản</Text>
          <Text className="info-value">{isLinked ? "Đã liên kết" : "Chưa liên kết"}</Text>
        </Box>
        <Box className="info-card">
          <Icon icon="zi-notif" size={28} className="info-icon" />
          <Text className="info-label">Thông báo</Text>
          <Text className="info-value">{notiGranted ? "Đã bật" : "Chưa bật"}</Text>
        </Box>
      </Box>

      <Modal
        visible={showLinkModal}
        title="Liên kết nhân viên"
        onClose={() => setShowLinkModal(false)}
        verticalActions
      >
        <Box className="space-y-4">
          <Text>Nhập họ tên nhân viên để nhận thông báo điểm danh:</Text>
          <Input
            placeholder="Ví dụ: Nguyễn Văn A"
            value={staffName}
            onChange={(e) => setStaffName(e.target.value)}
          />
          <Input
            placeholder="Mã PIN (Hỏi Admin)"
            type="password"
            value={staffPin}
            onChange={(e) => setStaffPin(e.target.value)}
          />
          <Button fullWidth onClick={handleLinkAccount}>Liên kết ngay</Button>
        </Box>
      </Modal>
    </Page>
  );
}

export default HomePage;
