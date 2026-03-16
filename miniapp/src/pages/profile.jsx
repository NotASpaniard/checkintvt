import React, { useState, useEffect } from "react";
import { Box, Page, Text, Icon, Button, useSnackbar } from "zmp-ui";
import { getUserInfo } from "zmp-sdk";
import { useNavigate } from "react-router-dom";

function ProfilePage() {
    const [user, setUser] = useState(null);
    const [staffName, setStaffName] = useState("");
    const { openSnackbar } = useSnackbar();
    const navigate = useNavigate();

    useEffect(() => {
        // Lay thong tin ngan gian tu Storage
        const savedName = localStorage.getItem("staffName");
        if (savedName) setStaffName(savedName);

        // Lay thong tin Zalo
        getUserInfo({
            success: (data) => {
                setUser(data.userInfo);
            },
            fail: (err) => {
                console.error("Loi lay thong tin Zalo trong Profile:", err);
            }
        });
    }, []);

    const handleUnlink = () => {
        // Xoa sach du lieu lien ket trong may dien thoai
        localStorage.removeItem("isLinked");
        localStorage.removeItem("staffName");

        openSnackbar({ text: "Da huy lien ket tai khoan thanh cong!", type: "success" });

        // Day nguoi dung ve trang chu de ho yeu cau dien thong tin lai
        setTimeout(() => {
            navigate("/");
            // Force reload app on Home Page to trigger re-check
            window.location.reload();
        }, 1500);
    };

    return (
        <Page className="page-profile">
            <Box className="profile-header" style={{ padding: "40px 20px 20px 20px", background: "linear-gradient(135deg, #0d1218, #18222d)", borderBottom: "1px solid rgba(212, 175, 55, 0.3)", display: "flex", flexDirection: "column", alignItems: "center" }}>
                {user?.avatar ? (
                    <img src={user.avatar} alt="Avatar" style={{ width: "80px", height: "80px", borderRadius: "50%", border: "2px solid #D4AF37", marginBottom: "15px" }} />
                ) : (
                    <Box style={{ width: "80px", height: "80px", borderRadius: "50%", background: "#333", display: "flex", justifyContent: "center", alignItems: "center", marginBottom: "15px" }}>
                        <Icon icon="zi-user" style={{ color: "white", fontSize: "40px" }} />
                    </Box>
                )}
                <Text.Title style={{ color: "white", fontSize: "20px" }}>{user?.name || "Tai khoan Zalo"}</Text.Title>
                <Text style={{ color: "#a0aec0", marginTop: "5px" }}>ID: {user?.id || "Chua cap quyen"}</Text>
            </Box>

            <Box p={4} m={4} style={{ background: "rgba(10, 11, 16, 0.8)", borderRadius: "12px", border: "1px solid rgba(255, 255, 255, 0.1)" }}>
                <Text style={{ color: "#D4AF37", fontSize: "16px", marginBottom: "15px", fontWeight: "bold" }}>Thong tin he thong</Text>

                <Box flex flexDirection="row" justifyContent="space-between" alignItems="center" mb={4}>
                    <Text style={{ color: "#a0aec0" }}>Trang thai</Text>
                    <Text style={{ color: "#10b981", fontWeight: "bold" }}>{staffName ? "Da lien ket" : "Chua lien ket"}</Text>
                </Box>

                <Box flex flexDirection="row" justifyContent="space-between" alignItems="center" mb={4}>
                    <Text style={{ color: "#a0aec0" }}>Nhan vien</Text>
                    <Text style={{ color: "white", fontWeight: "bold" }}>{staffName || "---"}</Text>
                </Box>
            </Box>

            {staffName && (
                <Box p={4} style={{ marginTop: "20px" }}>
                    <Button
                        fullWidth
                        variant="tertiary"
                        onClick={handleUnlink}
                        style={{ backgroundColor: "rgba(239, 68, 68, 0.1)", color: "#ef4444", border: "1px solid #ef4444" }}
                    >
                        Huy lien ket tai khoan
                    </Button>
                    <Text style={{ color: "#64748b", fontSize: "12px", textAlign: "center", marginTop: "15px" }}>
                        Hanh dong nay se yeu cau ban phai nhap lai Ma PIN trong lan kiem tra tiep theo.
                    </Text>
                </Box>
            )}

            <Box p={4} style={{ marginTop: "10px", textAlign: "center" }}>
                <Text style={{ color: "#475569", fontSize: "12px" }}>FaceMe Checkin Cop v1.2</Text>
            </Box>
        </Page>
    );
}

export default ProfilePage;
