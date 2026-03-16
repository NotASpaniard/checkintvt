import React, { useState, useEffect } from "react";
import { Box, Icon, Page, Text, Spinner } from "zmp-ui";
import { getUserInfo } from "zmp-sdk";

// TODO: Doi thanh URL Backend that khi deploy
const API_BASE = import.meta.env.VITE_API_BASE || "https://checkintvt-production.up.railway.app";

function HistoryPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [todayCount, setTodayCount] = useState(0);

  useEffect(() => {
    getUserInfo({
      success: (data) => {
        const zaloId = data.userInfo.id;
        fetchLogs(zaloId);
        const timer = setInterval(() => fetchLogs(zaloId), 10000);
        return () => clearInterval(timer);
      },
      fail: (err) => {
        console.error("getUserInfo error:", err);
        setLoading(false);
      }
    });
  }, []);

  const fetchLogs = async (zaloId) => {
    if (!zaloId) {
      setLogs([]);
      setLoading(false);
      return;
    }
    try {
      let url = `${API_BASE}/api/logs/today?zalo_id=${zaloId}`;

      const res = await fetch(url, {
        headers: { "ngrok-skip-browser-warning": "true" }
      });
      const data = await res.json();
      setLogs(data);
      setTodayCount(data.length);
    } catch (err) {
      console.error("Error fetching logs:", err);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (timeStr) => {
    if (!timeStr) return "--:--";
    const parts = timeStr.split(" ");
    if (parts.length >= 2) {
      return parts[1].substring(0, 5); // Lay HH:MM
    }
    return timeStr;
  };

  return (
    <Page className="page-history">
      {/* Header */}
      <Box className="history-header">
        <Text.Title className="history-title">Lich su diem danh</Text.Title>
        <Box className="today-badge">
          <Text className="today-count">{todayCount}</Text>
          <Text className="today-label">Hom nay</Text>
        </Box>
      </Box>

      {/* Danh sach Log */}
      <Box className="log-list">
        {loading ? (
          <Box className="loading-state">
            <Spinner />
            <Text className="loading-text">Dang tai du lieu...</Text>
          </Box>
        ) : logs.length === 0 ? (
          <Box className="empty-state">
            <Icon icon="zi-clock-1" size={64} className="empty-icon" />
            <Text className="empty-text">Chua co ban ghi diem danh nao hom nay</Text>
            <Text className="empty-sub">Hay ra truoc thiet bi de check-in</Text>
          </Box>
        ) : (
          logs.map((log) => (
            <Box key={log.id} className="log-item">
              <Box className="log-avatar-wrap">
                {log.has_image ? (
                  <img
                    src={`${API_BASE}/api/logs/${log.id}/image`}
                    alt={log.name}
                    className="log-avatar-img"
                    onError={(e) => { e.target.src = 'https://ui-avatars.com/api/?name=' + log.name; }}
                  />
                ) : (
                  <Box className="log-avatar-placeholder">
                    <Text className="log-avatar-letter">
                      {log.name?.charAt(0)?.toUpperCase() || "?"}
                    </Text>
                  </Box>
                )}
              </Box>

              <Box className="log-detail">
                <Text className="log-name">{log.name}</Text>
                <Box className="log-time-row">
                  <Icon icon="zi-clock-1" size={14} />
                  <Text className="log-time">{log.time}</Text>
                </Box>
              </Box>

              {log.zalo_notified && (
                <Box className="log-zalo-badge">
                  <Icon icon="zi-check-circle" size={16} />
                </Box>
              )}
            </Box>
          ))
        )}
      </Box>
    </Page>
  );
}

export default HistoryPage;
