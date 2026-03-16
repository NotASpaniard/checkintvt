import React, { useState, useEffect } from "react";
import { Box, Page, Text, Icon } from "zmp-ui";

function StatsPage() {
    const [stats, setStats] = useState({
        totalDays: 24,
        presentDays: 22,
        lateDays: 2,
        onTimeRate: 92
    });

    return (
        <Page className="page-stats">
            <Box className="stats-header" style={{ padding: "20px", background: "linear-gradient(135deg, #18222d, #0d1218)", borderBottom: "1px solid rgba(212, 175, 55, 0.3)" }}>
                <Text.Title style={{ color: "#D4AF37", fontSize: "24px", marginBottom: "5px" }}>Bao cao thang nay</Text.Title>
                <Text style={{ color: "#a0aec0" }}>Tong hop chuyen can cua ban</Text>
            </Box>

            <Box p={4} m={4} style={{ background: "rgba(10, 11, 16, 0.8)", borderRadius: "12px", border: "1px solid rgba(255, 255, 255, 0.1)" }}>
                <Box flex flexDirection="row" justifyContent="space-between" alignItems="center" mb={4}>
                    <Box flex flexDirection="row" alignItems="center">
                        <Icon icon="zi-calendar" style={{ color: "#D4AF37", marginRight: "10px" }} />
                        <Text style={{ color: "white", fontSize: "16px" }}>So ngay di lam</Text>
                    </Box>
                    <Text style={{ color: "#D4AF37", fontSize: "20px", fontWeight: "bold" }}>{stats.presentDays} / {stats.totalDays}</Text>
                </Box>

                <Box flex flexDirection="row" justifyContent="space-between" alignItems="center" mb={4}>
                    <Box flex flexDirection="row" alignItems="center">
                        <Icon icon="zi-clock-1" style={{ color: "#ef4444", marginRight: "10px" }} />
                        <Text style={{ color: "white", fontSize: "16px" }}>Di tre</Text>
                    </Box>
                    <Text style={{ color: "white", fontSize: "20px", fontWeight: "bold" }}>{stats.lateDays} ngay</Text>
                </Box>

                <Box style={{ marginTop: "20px", paddingTop: "20px", borderTop: "1px dashed rgba(255,255,255,0.2)" }}>
                    <Text style={{ color: "#a0aec0", textAlign: "center", marginBottom: "10px" }}>Ty le dung gio</Text>
                    <Box flex justifyContent="center" alignItems="center">
                        <Text style={{ color: "#10b981", fontSize: "36px", fontWeight: "bold" }}>{stats.onTimeRate}%</Text>
                    </Box>
                </Box>
            </Box>

            <Box p={4} m={4} style={{ background: "rgba(10, 11, 16, 0.8)", borderRadius: "12px", border: "1px solid rgba(255, 255, 255, 0.1)" }}>
                <Text style={{ color: "#D4AF37", fontSize: "16px", marginBottom: "10px", fontWeight: "bold" }}>Huong dan tang chuyen can</Text>
                <Text style={{ color: "#a0aec0", fontSize: "14px", lineHeight: "1.5" }}>
                    He thong ghi nhan thoi gian diem danh dau tien trong ngay lam gio den. Vui long dung truoc camera truoc 08:00 AM de khong bi tinh la di tre.
                </Text>
            </Box>
        </Page>
    );
}

export default StatsPage;
